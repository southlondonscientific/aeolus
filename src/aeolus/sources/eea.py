# Aeolus: download and standardise air quality data
# Copyright (C) 2025 Ruaraidh Dobson, South London Scientific

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
European Environment Agency (EEA) Data Source.

This module provides data fetchers for the EEA Air Quality Download Service,
covering regulatory monitoring stations across 40+ European countries.

The EEA aggregates data reported by EU member states and cooperating countries
under the Air Quality Directive. Data is available from 2013 onwards in hourly
resolution.

Pollutants include: NO2, PM10, PM2.5, O3, SO2, CO, NO, NOx, benzene, and
many trace metals and organic compounds.

No API key is required. Data download uses the ``airbase`` SDK
(``pip install airbase``), which handles the EEA's Parquet download API
and per-country Samplingpoint format variations.

Station metadata: ESRI REST service (ArcGIS) — no SDK required
Data download: airbase SDK wrapping the EEA Parquet Download API

Implementation notes:
    The EEA publishes two dataset variants (E1a and E2a) through different
    reporting pipelines. We use "Verified" (E1a) which has the best coverage
    for recent data. The per-row ``Verification`` field (not the dataset ID)
    determines ratification status:
      - 1 = Not yet verified  -> "Provisional"
      - 2 = Verified by EEA   -> "Verified"
      - 3 = Verified by member state -> "Verified"

    The Samplingpoint identifier format varies wildly between countries
    (e.g. "IE/SPO.IE.IE0131ASample1_8" for Ireland, "DE/SPO.DE_DEBB021_NO2_dataGroup1"
    for Germany, "FR/SPO-FR01011_38" for France). Rather than maintaining fragile
    per-country regex patterns, we use the airbase SDK's metadata CSV to build
    a Samplingpoint -> EoI station code mapping.

    See docs/superpowers/plans/2026-04-07-eea-sonitus-sources.md for the
    full research notes on dataset variants and Samplingpoint formats.
"""

import math
import os
import tempfile
import warnings
from datetime import datetime, timezone
from logging import getLogger

import pandas as pd
import requests

from ..decorators import retry_on_network_error
from ..registry import register_source
from ..transforms import (
    add_column,
    compose,
    filter_rows,
    rename_columns,
    reset_index,
    select_columns,
)
from ..types import (
    DATA_COLUMNS,
    METADATA_COLUMNS,
    AeolusDataWarning,
    empty_data_frame,
    empty_metadata_frame,
)

logger = getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

ESRI_BASE = (
    "https://air.discomap.eea.europa.eu/arcgis/rest/services/"
    "AirQuality/AirQualityDownloadServiceEUMonitoringStations/MapServer/0"
)

# ESRI pagination limit
_ESRI_PAGE_SIZE = 2000

# EEA pollutant codes -> Aeolus measurand names
POLLUTANT_CODE_MAP = {
    1: "SO2",
    5: "PM10",
    7: "O3",
    8: "NO2",
    9: "NOx",
    10: "CO",
    38: "NO",
    6001: "PM2.5",
    6002: "PM1",
    20: "C6H6",
}

# EEA Verification codes -> Aeolus ratification values
VERIFICATION_MAP = {
    1: "Provisional",
    2: "Verified",
    3: "Verified",
}

# Pollutant names as they appear in PopupInfo HTML
_POPUP_POLLUTANT_PATTERNS = {
    "Nitrogen dioxide": "NO2",
    "Nitrogen oxides": "NOx",
    "Particulate matter < 10": "PM10",
    "Particulate matter < 2.5": "PM2.5",
    "Particulate matter < 1": "PM1",
    "Ozone": "O3",
    "Sulphur dioxide": "SO2",
    "Carbon monoxide": "CO",
    "Benzene": "C6H6",
    "NO2": "NO2",
    "PM10": "PM10",
    "PM2.5": "PM2.5",
    "O3": "O3",
}

# Module-level cache for the airbase client and SPO->EoI mapping
_client = None
_spo_to_eoi: dict[str, str] | None = None


# ============================================================================
# AIRBASE SDK CLIENT
# ============================================================================


def _get_client():
    """Get or create an airbase client singleton."""
    import airbase

    global _client
    if _client is None:
        _client = airbase.AirbaseClient()
    return _client


def _get_spo_mapping() -> dict[str, str]:
    """Build a Samplingpoint -> EoI code mapping from airbase metadata.

    The metadata CSV maps ``Sampling Point Id`` (e.g. ``SPO.IE.IE0131ASample1_8``)
    to ``Air Quality Station EoI Code`` (e.g. ``IE0131A``).  The Parquet data
    uses ``{CC}/{Sampling Point Id}`` as the ``Samplingpoint`` column, so we
    store mappings both with and without the country prefix.

    This mapping is cached at module level after the first call.
    """
    global _spo_to_eoi
    if _spo_to_eoi is not None:
        return _spo_to_eoi

    client = _get_client()
    tmpfile = os.path.join(tempfile.gettempdir(), "aeolus_eea_metadata.csv")
    client.download_metadata(tmpfile)

    df = pd.read_csv(tmpfile, on_bad_lines="skip", low_memory=False)

    spo_col = "Sampling Point Id"
    eoi_col = "Air Quality Station EoI Code"

    mapping = {}
    for _, row in df[[eoi_col, spo_col]].drop_duplicates().iterrows():
        spo = str(row[spo_col]).strip('"')
        eoi = str(row[eoi_col]).strip('"')
        if spo and eoi and spo != "nan" and eoi != "nan":
            mapping[spo] = eoi

    _spo_to_eoi = mapping
    logger.info("Built EEA Samplingpoint mapping: %d entries", len(mapping))
    return _spo_to_eoi


def _samplingpoint_to_eoi(samplingpoint: str) -> str:
    """Convert a Samplingpoint identifier to an EoI station code.

    Looks up the airbase metadata mapping. Falls back to returning
    the raw Samplingpoint if no mapping is found.
    """
    mapping = _get_spo_mapping()

    # Try with and without country prefix (e.g. "IE/SPO.IE..." -> "SPO.IE...")
    if "/" in samplingpoint:
        spo = samplingpoint.split("/", 1)[1]
    else:
        spo = samplingpoint

    return mapping.get(spo, samplingpoint)


# ============================================================================
# WEB MERCATOR -> WGS84 CONVERSION
# ============================================================================


def _web_mercator_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Convert Web Mercator (EPSG:3857) coordinates to WGS84 (EPSG:4326).

    Returns (latitude, longitude).
    """
    lon = x * 180.0 / 20037508.34
    lat = (
        math.atan(math.exp(y * math.pi / 20037508.34)) * 360.0 / math.pi - 90.0
    )
    return lat, lon


# ============================================================================
# ESRI REST CLIENT (station metadata)
# ============================================================================


@retry_on_network_error
def _call_esri_api(params: dict) -> dict | None:
    """Query the EEA ESRI REST service for station metadata."""
    url = f"{ESRI_BASE}/query"
    params = {**params, "f": "json", "outFields": "*"}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _parse_measurands_from_popup(popup_html: str) -> list[str] | None:
    """Extract pollutant names from the PopupInfo HTML field."""
    measurands = []
    for pattern, name in _POPUP_POLLUTANT_PATTERNS.items():
        if pattern in popup_html and name not in measurands:
            measurands.append(name)
    return sorted(measurands) if measurands else None


def _bbox_to_esri_envelope(bbox: tuple[float, float, float, float]) -> str:
    """Convert (min_lon, min_lat, max_lon, max_lat) to ESRI envelope JSON."""
    min_lon, min_lat, max_lon, max_lat = bbox
    return (
        f'{{"xmin":{min_lon},"ymin":{min_lat},'
        f'"xmax":{max_lon},"ymax":{max_lat},'
        f'"spatialReference":{{"wkid":4326}}}}'
    )


def _parse_esri_features(features: list[dict]) -> list[dict]:
    """Convert ESRI feature dicts to flat metadata records."""
    records = []
    for feature in features:
        attrs = feature["attributes"]
        geom = feature.get("geometry", {})

        lat, lon = None, None
        if geom.get("x") is not None and geom.get("y") is not None:
            lat, lon = _web_mercator_to_wgs84(geom["x"], geom["y"])

        popup = attrs.get("PopupInfo", "")
        measurands = _parse_measurands_from_popup(popup)

        records.append({
            "site_code": attrs.get("AirQualityStationEoICode", ""),
            "site_name": attrs.get("AQStationName", ""),
            "latitude": lat,
            "longitude": lon,
            "source_network": "EEA",
            "measurands": measurands,
        })
    return records


# ============================================================================
# METADATA FETCHER
# ============================================================================


def fetch_eea_metadata(
    *,
    country: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    **filters,
) -> pd.DataFrame:
    """Fetch EEA station metadata.

    If no filters are provided, fetches all ~7,000 stations across Europe
    (paginated, takes ~4 seconds).

    Parameters
    ----------
    country : str, optional
        ISO 3166-1 alpha-2 country code (e.g. "IE", "DE", "FR").
    bbox : tuple, optional
        Bounding box as (min_lon, min_lat, max_lon, max_lat).

    Returns
    -------
    pd.DataFrame
        DataFrame with standard metadata columns.
    """
    params: dict = {"resultRecordCount": _ESRI_PAGE_SIZE}

    where_clauses = []
    if country is not None:
        where_clauses.append(f"CountryCode='{country.upper()}'")

    params["where"] = " AND ".join(where_clauses) if where_clauses else "1=1"

    if bbox is not None:
        params["geometry"] = _bbox_to_esri_envelope(bbox)
        params["geometryType"] = "esriGeometryEnvelope"
        params["spatialRel"] = "esriSpatialRelIntersects"
        params["inSR"] = "4326"

    # Paginate: ESRI returns max 2000 per request
    all_records: list[dict] = []
    offset = 0
    while True:
        params["resultOffset"] = offset
        result = _call_esri_api(params)
        if result is None or "features" not in result:
            break

        features = result["features"]
        if not features:
            break

        all_records.extend(_parse_esri_features(features))
        offset += len(features)

        if not result.get("exceededTransferLimit", False):
            break

    if not all_records:
        return empty_metadata_frame()

    return pd.DataFrame(all_records, columns=METADATA_COLUMNS)


# ============================================================================
# DATA NORMALISATION
# ============================================================================


def normalise_eea_data():
    """Return a compose() pipeline that normalises raw EEA Parquet data.

    The pipeline:
    1. Filters rows where Validity >= 1
    2. Maps Samplingpoint to EoI station code via airbase metadata
    3. Maps Pollutant int codes to measurand names
    4. Renames Start -> date_time, Value -> value
    5. Converts value to numeric
    6. Normalises Unit from "ug.m-3" to "ug/m3"
    7. Adds source_network="EEA"
    8. Maps Verification to ratification
    9. Adds created_at
    10. Selects standard columns and resets index
    """

    def extract_site_codes(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["site_code"] = df["Samplingpoint"].apply(_samplingpoint_to_eoi)
        return df

    def map_pollutants(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["measurand"] = df["Pollutant"].map(POLLUTANT_CODE_MAP)
        return df

    def convert_value(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df

    def normalise_units(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["units"] = df["units"].str.replace("ug.m-3", "ug/m3", regex=False)
        return df

    def map_verification(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ratification"] = df["Verification"].map(VERIFICATION_MAP).fillna("Provisional")
        return df

    return compose(
        filter_rows(lambda df: df["Validity"] >= 1),
        extract_site_codes,
        map_pollutants,
        rename_columns({"Start": "date_time", "Value": "value", "Unit": "units"}),
        convert_value,
        normalise_units,
        add_column("source_network", "EEA"),
        map_verification,
        add_column("created_at", lambda df: datetime.now(timezone.utc)),
        select_columns(*DATA_COLUMNS),
        reset_index(),
    )


# ============================================================================
# DATA FETCHER
# ============================================================================


def _infer_country_from_sites(sites: list[str]) -> str | None:
    """Infer the 2-letter country code from EoI site codes.

    EoI codes start with a 2-letter country prefix (e.g. IE0131A -> IE).
    Returns the country code if all sites share the same prefix, else None.
    """
    countries = {s[:2] for s in sites if len(s) >= 2}
    return countries.pop() if len(countries) == 1 else None


def fetch_eea_data(
    sites: list[str],
    start_date: datetime,
    end_date: datetime,
    *,
    country: str | None = None,
    pollutants: list[str] | None = None,
) -> pd.DataFrame:
    """Fetch air quality data from the EEA via the airbase SDK.

    Parameters
    ----------
    sites : list[str]
        List of EoI station codes (e.g. ["IE0131A", "IE007CP"]).
    start_date : datetime
        Start of date range (inclusive).
    end_date : datetime
        End of date range (inclusive).
    country : str, optional
        ISO 3166-1 alpha-2 country code. If not provided, inferred from sites.
    pollutants : list[str], optional
        Aeolus measurand names to fetch (e.g. ["NO2", "PM2.5"]).
        If not provided, fetches all available pollutants.

    Returns
    -------
    pd.DataFrame
        Normalised data with standard 8-column schema.
    """
    import airbase

    if country is None:
        country = _infer_country_from_sites(sites)

    if country is None:
        warnings.warn(
            "Cannot infer country from mixed-country site codes. "
            "Pass country= explicitly.",
            AeolusDataWarning,
            stacklevel=2,
        )
        return empty_data_frame()

    # Build airbase request
    client = _get_client()

    # Map Aeolus pollutant names to EEA notation
    poll_arg = None
    if pollutants:
        poll_arg = []
        for p in pollutants:
            results = client.search_pollutant(p)
            if results:
                poll_arg.append(results[0]["poll"])

    try:
        request = client.request(
            "Verified",
            country.upper(),
            poll=poll_arg,
        )
    except Exception as e:
        warnings.warn(
            f"Failed to build EEA request: {e}",
            AeolusDataWarning,
            stacklevel=2,
        )
        return empty_data_frame()

    # Download to temp directory
    tmpdir = tempfile.mkdtemp(prefix="aeolus_eea_")
    try:
        request.download(dir=tmpdir)
    except Exception as e:
        warnings.warn(
            f"EEA download failed: {e}",
            AeolusDataWarning,
            stacklevel=2,
        )
        return empty_data_frame()

    # Read all parquet files
    dfs: list[pd.DataFrame] = []
    for root, _dirs, files in os.walk(tmpdir):
        for fname in files:
            if fname.endswith(".parquet"):
                fpath = os.path.join(root, fname)
                df = pd.read_parquet(fpath)
                if not df.empty:
                    dfs.append(df)

    if not dfs:
        return empty_data_frame()

    raw_df = pd.concat(dfs, ignore_index=True)

    # Filter to requested date range (airbase downloads full history).
    # Match timezone awareness of the Start column.
    ts_start = pd.Timestamp(start_date)
    ts_end = pd.Timestamp(end_date)
    if raw_df["Start"].dt.tz is not None and ts_start.tzinfo is None:
        ts_start = ts_start.tz_localize("UTC")
        ts_end = ts_end.tz_localize("UTC")
    elif raw_df["Start"].dt.tz is None and ts_start.tzinfo is not None:
        ts_start = ts_start.tz_localize(None)
        ts_end = ts_end.tz_localize(None)
    raw_df = raw_df[
        (raw_df["Start"] >= ts_start) & (raw_df["Start"] < ts_end)
    ]

    if raw_df.empty:
        return empty_data_frame()

    # Normalise
    normalise = normalise_eea_data()
    df = normalise(raw_df)

    # Filter to requested sites
    sites_upper = {s.upper() for s in sites}
    df = df[df["site_code"].str.upper().isin(sites_upper)]

    if df.empty:
        return empty_data_frame()

    return df.reset_index(drop=True)


# ============================================================================
# SOURCE REGISTRATION
# ============================================================================

register_source("EEA", {
    "type": "network",
    "name": "EEA",
    "fetch_metadata": fetch_eea_metadata,
    "fetch_data": fetch_eea_data,
    "normalise": normalise_eea_data(),
    "requires_api_key": False,
})
