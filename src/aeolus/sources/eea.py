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

No API key is required.

Station metadata: ESRI REST service (ArcGIS)
Data download: Parquet Download API (Azure)
Country/pollutant lists: REST GET endpoints

Implementation notes:
    The EEA publishes two dataset variants (E1a and E2a) through different
    reporting pipelines. We use E1a (dataset=1) which has the best coverage
    for recent data. The per-row ``Verification`` field (not the dataset ID)
    determines ratification status:
      - 1 = Not yet verified  -> "Provisional"
      - 2 = Verified by EEA   -> "Verified"
      - 3 = Verified by member state -> "Verified"
    See docs/superpowers/plans/2026-04-07-eea-sonitus-sources.md for the
    full research notes on this.
"""

import math
import warnings
from logging import getLogger

import pandas as pd
import requests

from ..decorators import retry_on_network_error
from ..types import (
    METADATA_COLUMNS,
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

# EEA Verification codes -> Aeolus ratification values
VERIFICATION_MAP = {
    1: "Provisional",
    2: "Verified",
    3: "Verified",
}

# Dataset ID: E1a (primary validated assessment data)
DATASET_E1A = 1

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
    """Convert (min_lon, min_lat, max_lon, max_lat) to ESRI envelope JSON.

    The ESRI service expects Web Mercator coordinates, but also accepts
    a spatial reference parameter to specify the input CRS.
    """
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
