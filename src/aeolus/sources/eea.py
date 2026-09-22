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

No API key or optional SDK is required.

Station metadata: ESRI REST service (ArcGIS)
Data download: EEA Parquet Download API (Azure)
Samplingpoint mapping: EEA metadata CSV (discomap.eea.europa.eu)

Implementation notes:
    The download API serves three datasets: 1 = up-to-date (E2a, recent data
    only), 2 = verified (E1a, reported annually), 3 = historical Airbase
    (<=2012) — see ``DATASET_UTD``/``DATASET_VERIFIED``/``DATASET_AIRBASE``. The per-row ``Verification`` field determines
    ratification status (EIONET observationverification vocabulary):
      - 1 = Verified             -> "Verified"
      - 2 = Preliminary verified -> "Provisional"
      - 3 = Not verified         -> "Provisional"

    The Samplingpoint identifier format varies wildly between countries
    (e.g. "IE/SPO.IE.IE0131ASample1_8" for Ireland, "DE/SPO.DE_DEBB021_NO2_dataGroup1"
    for Germany, "ES/SP_01022001_10_47" for Spain). Rather than maintaining fragile
    per-country regex patterns, we fetch the EEA's metadata CSV which maps
    Samplingpoint IDs to EoI station codes authoritatively.

    See docs/superpowers/plans/2026-04-07-eea-sonitus-sources.md for the
    full research notes on dataset variants and Samplingpoint formats.
"""

import math
import warnings
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
from logging import getLogger
from zipfile import ZipFile

import numpy as np
import pandas as pd
import requests

from .._dates import to_utc
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
from ..units import canonical_units
from ..schema import legacy_mirror
from ..types import (
    ADAPTER_DATA_COLUMNS_QA,
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

DOWNLOAD_API_BASE = "https://eeadmz1-downloads-api-appservice.azurewebsites.net"

# EEA metadata CSV — hosted on EEA's own discomap infrastructure
_METADATA_CSV_URL = (
    "https://discomap.eea.europa.eu/App/AQViewer/download"
    "?fqn=Airquality_Dissem.b2g.measurements&f=csv"
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

# Aeolus measurand names -> EEA pollutant notation (for API requests)
MEASURAND_TO_NOTATION = {
    "SO2": "SO2",
    "PM10": "PM10",
    "O3": "O3",
    "NO2": "NO2",
    "NOx": "NOX as NO2",
    "CO": "CO",
    "NO": "NO",
    "PM2.5": "PM2.5",
    "PM1": "PM1",
    "C6H6": "C6H6",
}

# Dataset ids of the EEA download API. NB: the API's own zip folders confirm
# these — 1 is the *up-to-date* feed, not the verified one (the constant was
# misnamed DATASET_UTD = 1 until v0.5.0, so earlier years came back empty).
DATASET_UTD = 1        # E2a: recent data, continuously transmitted
DATASET_VERIFIED = 2   # E1a: reported annually after national QA/QC
DATASET_AIRBASE = 3    # historical Airbase, 2002–2012
DATASET_PRIORITY = (DATASET_VERIFIED, DATASET_UTD, DATASET_AIRBASE)  # who wins a duplicate day
DATASET_BACKEND = {DATASET_VERIFIED: "EEA_E1A", DATASET_UTD: "EEA_E2A", DATASET_AIRBASE: "EEA_AIRBASE"}

# EEA states hourly Start/End are "converted to the UTC+1 timezone". Verified
# true for the up-to-date feed in DE/NL/IE/ES/PL and the verified archive in
# DE/NL/PL/IT. Two exceptions found by measurement:
#   - Italy's up-to-date feed is local civil time (Europe/Rome);
#   - Ireland's verified archive is plain UTC (lag 0 vs Sonitus, r=0.9999).
# Everything else is assumed UTC+1 — which is why EEA stays `experimental`.
_UTD_LOCAL_CLOCK = {"IT": "Europe/Rome"}
_E1A_CLOCK_OVERRIDES = {"IE": "UTC"}

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

# Module-level cache for the Samplingpoint -> EoI mapping
_spo_to_eoi: dict[str, str] | None = None


# ============================================================================
# SAMPLINGPOINT -> EOI CODE MAPPING
# ============================================================================


@retry_on_network_error
def _fetch_metadata_csv() -> str | None:
    """Download the EEA metadata CSV from discomap.eea.europa.eu.

    Despite the ``f=csv`` parameter, the endpoint returns a ZIP file
    containing ``DataExtract.csv`` (with ``Content-Type: text/html``).
    """
    resp = requests.get(_METADATA_CSV_URL, timeout=60)
    resp.raise_for_status()

    # The response is a ZIP containing DataExtract.csv
    with ZipFile(BytesIO(resp.content)) as zf:
        with zf.open("DataExtract.csv") as f:
            return f.read().decode("utf-8", errors="replace")


def _get_spo_mapping() -> dict[str, str]:
    """Build a Samplingpoint -> EoI code mapping from the EEA metadata CSV.

    The CSV maps ``Sampling Point Id`` (e.g. ``SPO.IE.IE0131ASample1_8``)
    to ``Air Quality Station EoI Code`` (e.g. ``IE0131A``).  The Parquet data
    uses ``{CC}/{Sampling Point Id}`` as the ``Samplingpoint`` column, so we
    store the mapping keyed by the SPO portion (after the country prefix slash).

    This mapping is cached at module level after the first call.
    """
    global _spo_to_eoi
    if _spo_to_eoi is not None:
        return _spo_to_eoi

    csv_text = _fetch_metadata_csv()
    if csv_text is None:
        # Don't latch the cache on transient errors — leave it None so the
        # next call retries. Returning a local empty dict for this call only.
        logger.warning("Failed to download EEA metadata CSV; site code mapping unavailable")
        return {}

    spo_col = "Sampling Point Id"
    eoi_col = "Air Quality Station EoI Code"

    try:
        # The EEA CSV has known formatting issues (unescaped commas in fields,
        # inconsistent quoting). Use Python engine with error_bad_lines=skip
        # and only read the two columns we need.
        df = pd.read_csv(
            StringIO(csv_text),
            usecols=[spo_col, eoi_col],
            on_bad_lines="skip",
            engine="python",
        )
    except Exception:
        # Fallback: the CSV may have severe issues. Parse line-by-line.
        logger.warning("EEA metadata CSV parsing failed; building mapping line-by-line")
        mapping = _parse_csv_fallback(csv_text, spo_col, eoi_col)
        if mapping:
            _spo_to_eoi = mapping
        else:
            logger.warning("EEA metadata CSV yielded no mappings; not caching")
        return mapping

    mapping: dict[str, str] = {}
    for _, row in df.drop_duplicates().iterrows():
        spo = str(row[spo_col]).strip('"')
        eoi = str(row[eoi_col]).strip('"')
        if spo and eoi and spo != "nan" and eoi != "nan":
            mapping[spo] = eoi

    if not mapping:
        # An empty mapping is never legitimate (the real CSV has tens of
        # thousands of rows). Don't latch it — leave the cache None so the
        # next call retries.
        logger.warning("EEA metadata CSV yielded no mappings; not caching")
        return {}

    _spo_to_eoi = mapping
    logger.info("Built EEA Samplingpoint mapping: %d entries", len(mapping))
    return _spo_to_eoi


def _parse_csv_fallback(csv_text: str, spo_col: str, eoi_col: str) -> dict[str, str]:
    """Parse the metadata CSV line-by-line as a fallback for malformed CSVs."""
    mapping: dict[str, str] = {}
    lines = csv_text.split("\n")
    if not lines:
        return mapping

    # Find column indices from header
    header = lines[0].split(",")
    try:
        spo_idx = next(i for i, h in enumerate(header) if spo_col in h)
        eoi_idx = next(i for i, h in enumerate(header) if eoi_col in h)
    except StopIteration:
        return mapping

    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) > max(spo_idx, eoi_idx):
            spo = parts[spo_idx].strip('"').strip()
            eoi = parts[eoi_idx].strip('"').strip()
            if spo and eoi:
                mapping[spo] = eoi

    return mapping


def _samplingpoint_to_eoi(
    samplingpoint: str, mapping: dict[str, str] | None = None
) -> str:
    """Convert a Samplingpoint identifier to an EoI station code.

    Looks up the EEA metadata CSV mapping. Falls back to returning
    the raw Samplingpoint if no mapping is found.
    """
    if mapping is None:
        mapping = _get_spo_mapping()

    # Strip country prefix: "IE/SPO.IE.IE0131A..." -> "SPO.IE.IE0131A..."
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
# PARQUET DOWNLOAD API
# ============================================================================


@retry_on_network_error
def _download_parquet(body: dict) -> bytes | None:
    """POST to the EEA Parquet Download API, return raw ZIP bytes."""
    url = f"{DOWNLOAD_API_BASE}/ParquetFile/dynamic"
    resp = requests.post(url, json=body, timeout=120)
    resp.raise_for_status()
    return resp.content


# ============================================================================
# DATA NORMALISATION
# ============================================================================


def normalise_eea_data():
    """Return a compose() pipeline that normalises raw EEA Parquet data.

    The pipeline:
    1. Filters rows where Validity >= 1
    2. Maps Samplingpoint to EoI station code via EEA metadata CSV
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
        # Resolve the mapping once per frame, not once per row: while the
        # cache is unpopulated every _get_spo_mapping() call re-downloads.
        mapping = _get_spo_mapping()
        df["site_code"] = df["Samplingpoint"].apply(
            _samplingpoint_to_eoi, mapping=mapping
        )
        return df

    def stamps_to_utc(df: pd.DataFrame) -> pd.DataFrame:
        """Convert EEA's hourly ``Start`` to tz-aware UTC, per dataset and country.

        The EEA states hourly Start/End are "converted to the UTC+1 timezone"
        (fixed, no daylight saving). Measured exceptions, see the module
        constants: Italy's up-to-date feed is local civil time, and Ireland's
        verified archive is plain UTC. The hour that does not exist in spring,
        and the ambiguous one in autumn, cannot be placed for a local-clock
        feed and are dropped.
        """
        df = df.copy()
        naive = pd.to_datetime(df["date_time"])
        if naive.dt.tz is not None:
            naive = naive.dt.tz_localize(None)
        country = df["Samplingpoint"].astype(str).str.split("/").str[0]  # "IE/SPO.IE…" -> "IE"
        dataset = df["dataset"] if "dataset" in df.columns else pd.Series(DATASET_UTD, index=df.index)
        utc = naive.dt.tz_localize("Etc/GMT-1").dt.tz_convert("UTC")  # POSIX sign: GMT-1 is UTC+1
        for code, zone in _UTD_LOCAL_CLOCK.items():
            rows = (country == code) & (dataset == DATASET_UTD)
            if rows.any():
                utc[rows] = naive[rows].dt.tz_localize(zone, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
        for code, zone in _E1A_CLOCK_OVERRIDES.items():
            rows = (country == code) & (dataset == DATASET_VERIFIED)
            if rows.any():
                utc[rows] = naive[rows].dt.tz_localize(zone).dt.tz_convert("UTC")
        df["date_time"] = utc
        return df[df["date_time"].notna()]

    def prefer_verified_days(df: pd.DataFrame) -> pd.DataFrame:
        """Serve each (site, measurand, day) from the highest-priority dataset that
        holds any row for it — verified beats up-to-date beats Airbase.

        Day-level, not hour-level, and before the validity filter, so that:
        co-located instruments at one station are not merged; an hour the
        archive rejected is not resurrected from the feed; and Italian
        up-to-date points whose stamps do not follow the DST model cannot
        double up beside archive rows on overlap days.
        """
        if "dataset" not in df.columns or df.empty:
            return df
        priority = df["dataset"].map({d: i for i, d in enumerate(DATASET_PRIORITY)})
        day = df["date_time"].dt.floor("D")
        best = priority.groupby([df["site_code"], df["measurand"], day], observed=True).transform("min")
        return df[priority == best]

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
        # Canonicalise ALL EEA unit notations, not just 'ug.m-3': map the micro
        # sign (both U+00B5 and the Greek mu U+03BC) to 'u', and the '.m-3'
        # suffix to '/m3'. This turns 'mg.m-3' -> 'mg/m3' (e.g. CO), 'ng.m-3' ->
        # 'ng/m3', and 'µg/m3' -> 'ug/m3', so units are consistent across all
        # species from the source rather than CO being left as 'mg.m-3'.
        df["units"] = canonical_units(df["units"])
        return df

    def map_verification(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # The EIONET code itself is the QA token. Anything that is not an
        # integer code (blank, "n/a", a float that is not whole) is a null
        # code, never an error and never a made-up status.
        codes = pd.to_numeric(df["Verification"], errors="coerce")
        integral = codes.notna() & np.isfinite(codes) & (codes % 1 == 0)
        text = codes.where(integral, 0).fillna(0).astype(int).astype(str)
        df["qa_code"] = pd.Series(np.where(integral, text, None), index=df.index, dtype=object)
        df["ratification"] = legacy_mirror("EEA", df["qa_code"])
        return df

    return compose(
        extract_site_codes,
        map_pollutants,
        rename_columns({"Start": "date_time", "Value": "value", "Unit": "units"}),
        stamps_to_utc,
        prefer_verified_days,
        # After the priority step, so an hour the archive rejected stays rejected
        filter_rows(lambda df: df["Validity"] >= 1),
        convert_value,
        # convert_value coerces unparseable values to NaN; drop them (the
        # Validity>=1 filter is a QA flag, not a value-presence check). Matches
        # every other source, which drop NaN measurements.
        filter_rows(lambda df: df["value"].notna()),
        normalise_units,
        add_column("source_network", "EEA"),
        map_verification,
        add_column("created_at", lambda df: datetime.now(timezone.utc)),
        # Which dataset served the row; the finaliser keeps it as `backend`
        add_column("backend", lambda df: df["dataset"].map(DATASET_BACKEND) if "dataset" in df.columns else "EEA"),
        select_columns(*ADAPTER_DATA_COLUMNS_QA, "backend", require_all=True),
        reset_index(),
    )


# ============================================================================
# DATA FETCHER
# ============================================================================


def _parse_parquet_zip(zip_bytes: bytes) -> pd.DataFrame | None:
    dfs: list[pd.DataFrame] = []
    with ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith(".parquet"):
                with zf.open(name) as f:
                    df = pd.read_parquet(BytesIO(f.read()))
                    if not df.empty:
                        dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else None


def _fetch_dataset(body_base: dict, dataset: int) -> pd.DataFrame | None:
    """One dataset's raw rows for the window, tagged with the dataset id."""
    zip_bytes = _download_parquet({**body_base, "dataset": dataset})
    if not zip_bytes:
        return None
    try:
        raw = _parse_parquet_zip(zip_bytes)
    except Exception as e:  # noqa: BLE001 - a bad zip from one dataset must not sink the others
        warnings.warn(
            f"Failed to parse EEA Parquet response (dataset {dataset}): {e}",
            AeolusDataWarning,
            stacklevel=3,
        )
        return None
    return None if raw is None else raw.assign(dataset=dataset)


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
    """Fetch air quality data from the EEA Parquet Download API.

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
    if country is None:
        country = _infer_country_from_sites(sites)

    if country is None:
        warnings.warn(
            "Cannot infer country from mixed-country site codes. "
            "Pass country= explicitly.",
            AeolusDataWarning,
            stacklevel=2,
        )
        return empty_data_frame(qa=True)

    # Build POST body for the EEA Parquet API
    notation_list: list[str] = []
    if pollutants:
        for p in pollutants:
            notation = MEASURAND_TO_NOTATION.get(p)
            if notation:
                notation_list.append(notation)

    # The service reads our bounds on its own UTC+1 grid (a "Z" suffix
    # notwithstanding), so a plain request drops the window's last hour and
    # adds one before its start. Ask an hour wider each side and trim after.
    start_utc, end_utc = to_utc(start_date), to_utc(end_date)
    body_base: dict = {
        "countries": [country.upper()],
        "cities": [],
        "pollutants": notation_list if notation_list else [],
        "dateTimeStart": (start_utc - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dateTimeEnd": (end_utc + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "compress": True,
    }
    # The verified archive and the up-to-date feed overlap by up to two years
    # (which years depends on the country), so both are always asked for;
    # Airbase only holds 2002–2012.
    datasets = [DATASET_VERIFIED, DATASET_UTD]
    if to_utc(start_date).year <= 2012:
        datasets.append(DATASET_AIRBASE)
    frames = [f for f in (_fetch_dataset(body_base, d) for d in datasets) if f is not None]
    if not frames:
        return empty_data_frame(qa=True)
    raw_df = pd.concat(frames, ignore_index=True)

    # Normalise
    normalise = normalise_eea_data()
    df = normalise(raw_df)

    # Filter to requested sites and to the requested window
    sites_upper = {s.upper() for s in sites}
    df = df[df["site_code"].str.upper().isin(sites_upper)]
    df = df[(df["date_time"] >= start_utc) & (df["date_time"] <= end_utc)]

    if df.empty:
        return empty_data_frame(qa=True)

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
    "bbox_aware": True,
    "status": "experimental",
    "status_note": (
        "timestamps are converted from the EEA's UTC+1 convention, which is verified only for "
        "the up-to-date feed in DE/NL/IE/ES/PL (Italy: local time) and the verified archive in "
        "DE/NL/PL/IT (Ireland: plain UTC); other countries and the Airbase archive are assumed."
    ),
})
