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
EPA AirNow Data Source.

This module provides data fetchers for the EPA AirNow API, which provides
real-time and historical air quality data from over 2,500 monitoring stations
across the United States, Canada, and Mexico.

AirNow data includes observations for:
- Ozone (O3)
- PM2.5 and PM10
- NO2, SO2, CO

Note: AirNow data should be considered preliminary and subject to change.
For verified historical data, see the EPA AQS (Air Quality System) which
contains ratified data after 6+ months.

API Documentation: https://docs.airnowapi.org/
Data Coverage: United States, Canada, Mexico
"""

import os
from datetime import datetime, timedelta
from logging import getLogger, warning
from typing import Any

import pandas as pd
import requests

from ..decorators import retry_on_network_error
from ..registry import register_source

logger = getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# API configuration
API_BASE = "https://www.airnowapi.org/aq"

# Rate limit: 500 requests per hour per endpoint
# We'll be conservative with a simple delay
REQUEST_DELAY = 0.5  # seconds between requests

# Parameter name standardization
# Maps AirNow parameter names to Aeolus standard names
PARAMETER_MAP = {
    "O3": "O3",
    "OZONE": "O3",
    "PM2.5": "PM2.5",
    "PM10": "PM10",
    "NO2": "NO2",
    "SO2": "SO2",
    "CO": "CO",
}

# AQI category mapping
AQI_CATEGORIES = {
    1: "Good",
    2: "Moderate",
    3: "Unhealthy for Sensitive Groups",
    4: "Unhealthy",
    5: "Very Unhealthy",
    6: "Hazardous",
    7: "Unavailable",
}


# ============================================================================
# API CLIENT
# ============================================================================


def _get_api_key() -> str:
    """
    Get AirNow API key from environment.

    Returns:
        str: API key

    Raises:
        ValueError: If API key is not configured
    """
    api_key = os.getenv("AIRNOW_API_KEY")
    if not api_key:
        raise ValueError(
            "AirNow API key required. Set AIRNOW_API_KEY in .env file. "
            "Get your free key at: https://docs.airnowapi.org/account/request/"
        )
    return api_key


@retry_on_network_error
def _call_airnow_api(
    endpoint: str, params: dict | None = None, timeout: int = 60
) -> list[dict] | None:
    """
    Make a request to the AirNow API.

    Args:
        endpoint: API endpoint path (e.g., "observation/latLong/current")
        params: Query parameters (API key added automatically)
        timeout: Request timeout in seconds

    Returns:
        list: JSON response data, or None on error
    """
    api_key = _get_api_key()

    params = params or {}
    params["API_KEY"] = api_key
    params["format"] = "application/json"

    url = f"{API_BASE}/{endpoint}"

    try:
        response = requests.get(url, params=params, timeout=timeout)

        if response.status_code == 401:
            raise ValueError(
                "AirNow API authentication failed. Check your AIRNOW_API_KEY."
            )

        if response.status_code == 429:
            warning("AirNow rate limit exceeded. Consider reducing request frequency.")
            return None

        response.raise_for_status()

        data = response.json()

        # AirNow returns empty list for no data
        if not data:
            return []

        return data

    except requests.exceptions.Timeout:
        warning(f"AirNow API request timed out: {endpoint}")
        return None
    except requests.exceptions.RequestException as e:
        warning(f"AirNow API request failed: {e}")
        return None
    except ValueError as e:
        # JSON parsing error or auth error
        if "authentication" in str(e).lower():
            raise
        warning(f"Failed to parse AirNow response: {e}")
        return None


# ============================================================================
# METADATA FETCHER
# ============================================================================


def fetch_airnow_metadata(
    bbox: tuple[float, float, float, float] | None = None,
    bounding_box: tuple[float, float, float, float] | None = None,
    **filters,
) -> pd.DataFrame:
    """
    Fetch monitoring site metadata from AirNow.

    Note: AirNow doesn't have a dedicated metadata endpoint. This function
    fetches current observations and extracts unique site information.

    Args:
        bbox: Geographic bounds as (min_lon, min_lat, max_lon, max_lat).
              Standard format consistent with GeoJSON and shapely conventions.
              If not provided, defaults to continental US bounds.
        bounding_box: [Deprecated] Alias for `bbox`. Use `bbox` for consistency
                      with other sources.
        **filters: Additional filters (not currently used)

    Returns:
        pd.DataFrame: Site metadata with standardized schema:
            - site_code: Unique site identifier (derived from coordinates)
            - site_name: Reporting area name
            - latitude: Site latitude
            - longitude: Site longitude
            - state_code: US state code
            - source_network: "AirNow"

    Example:
        >>> # Get sites in California
        >>> metadata = fetch_airnow_metadata(
        ...     bbox=(-124.48, 32.53, -114.13, 42.01)
        ... )
    """
    # Handle bbox/bounding_box - prefer bbox, fall back to bounding_box for backwards compat
    if bbox is None and bounding_box is not None:
        bbox = bounding_box

    # Default to continental US if no bounding box provided
    if bbox is None:
        bbox = (-125.0, 24.0, -66.0, 50.0)

    min_lon, min_lat, max_lon, max_lat = bbox

    # Fetch current observations to get site list
    params = {
        "startDate": datetime.now().strftime("%Y-%m-%dT%H"),
        "endDate": datetime.now().strftime("%Y-%m-%dT%H"),
        "parameters": "OZONE,PM25,PM10,CO,NO2,SO2",
        "BBOX": f"{min_lon},{min_lat},{max_lon},{max_lat}",
        "dataType": "B",  # AQI and concentrations
        "verbose": "1",  # Include site details
    }

    data = _call_airnow_api("data/", params)

    if not data:
        return pd.DataFrame()

    # Extract unique sites
    sites = {}
    for obs in data:
        # Create a unique site code from lat/lon
        lat = obs.get("Latitude")
        lon = obs.get("Longitude")
        if lat is None or lon is None:
            continue

        site_code = f"{lat:.4f}_{lon:.4f}".replace("-", "m").replace(".", "d")

        if site_code in sites:
            continue

        sites[site_code] = {
            "site_code": site_code,
            "site_name": obs.get("SiteName", obs.get("ReportingArea", "")),
            "latitude": lat,
            "longitude": lon,
            "state_code": obs.get("StateCode", ""),
            "reporting_area": obs.get("ReportingArea", ""),
            "source_network": "AirNow",
        }

    if not sites:
        return pd.DataFrame()

    return pd.DataFrame(list(sites.values()))


# ============================================================================
# DATA FETCHER
# ============================================================================


def fetch_airnow_data(
    sites: list[str],
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    """
    Fetch air quality data from AirNow.

    Args:
        sites: List of site codes (format: "lat_lon" e.g., "34d0522_m118d2437")
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        pd.DataFrame: Air quality data with standardized schema:
            - site_code: Site identifier
            - date_time: Measurement timestamp (UTC)
            - measurand: Pollutant measured (e.g., "O3", "PM2.5")
            - value: Measured concentration
            - units: Units of measurement
            - source_network: "AirNow"
            - ratification: "Provisional" (AirNow data is preliminary)
            - created_at: When record was fetched

    Note:
        AirNow historical data is limited. For data older than ~45 days,
        consider using the EPA AQS API instead.

    Example:
        >>> from datetime import datetime
        >>> data = fetch_airnow_data(
        ...     sites=["34d0522_m118d2437"],
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 7)
        ... )
    """
    if not sites:
        return _empty_dataframe()

    # Parse site codes back to coordinates
    site_coords = {}
    for site_code in sites:
        try:
            lat_str, lon_str = site_code.split("_")
            lat = float(lat_str.replace("d", ".").replace("m", "-"))
            lon = float(lon_str.replace("d", ".").replace("m", "-"))
            site_coords[site_code] = (lat, lon)
        except (ValueError, AttributeError):
            warning(f"Invalid site code format: {site_code}")
            continue

    if not site_coords:
        return _empty_dataframe()

    all_data = []
    fetch_time = datetime.now()

    # AirNow historical endpoint works per-location
    # We need to query each site separately
    for site_code, (lat, lon) in site_coords.items():
        logger.info(f"Fetching AirNow data for site {site_code}...")

        site_data = _fetch_site_historical(
            lat, lon, site_code, start_date, end_date, fetch_time
        )

        if not site_data.empty:
            all_data.append(site_data)

    if not all_data:
        return _empty_dataframe()

    return pd.concat(all_data, ignore_index=True)


def _fetch_site_historical(
    lat: float,
    lon: float,
    site_code: str,
    start_date: datetime,
    end_date: datetime,
    fetch_time: datetime,
) -> pd.DataFrame:
    """
    Fetch historical data for a single site.

    AirNow's historical endpoint requires hourly queries, so we iterate
    through the date range.
    """
    records = []

    # AirNow data endpoint can handle date ranges with bounding box
    # Create a small bounding box around the site
    buffer = 0.01  # ~1km
    bbox = f"{lon - buffer},{lat - buffer},{lon + buffer},{lat + buffer}"

    # Query in daily chunks to stay within API limits
    current_date = start_date
    while current_date <= end_date:
        next_date = min(current_date + timedelta(days=1), end_date + timedelta(hours=1))

        params = {
            "startDate": current_date.strftime("%Y-%m-%dT00"),
            "endDate": next_date.strftime("%Y-%m-%dT00"),
            "parameters": "OZONE,PM25,PM10,CO,NO2,SO2",
            "BBOX": bbox,
            "dataType": "C",  # Concentrations only
            "verbose": "0",
        }

        data = _call_airnow_api("data/", params)

        if data:
            for obs in data:
                param = obs.get("Parameter", "")
                value = obs.get("Value")
                unit = obs.get("Unit", "")

                if value is None:
                    continue

                # Parse the datetime
                date_str = obs.get("UTC")
                if not date_str:
                    # Fall back to local time if UTC not available
                    date_str = (
                        obs.get("DateObserved", "")
                        + "T"
                        + obs.get("HourObserved", "00").zfill(2)
                    )

                try:
                    if "T" in str(date_str):
                        dt = pd.to_datetime(date_str)
                    else:
                        dt = pd.to_datetime(date_str)
                except (ValueError, TypeError):
                    continue

                # Standardize parameter name
                measurand = PARAMETER_MAP.get(param.upper(), param)

                # Standardize units
                if unit.upper() in ["UG/M3", "UG/M³"]:
                    unit = "ug/m3"
                elif unit.upper() == "PPB":
                    unit = "ppb"
                elif unit.upper() == "PPM":
                    unit = "ppm"

                records.append(
                    {
                        "site_code": site_code,
                        "date_time": dt,
                        "measurand": measurand,
                        "value": float(value),
                        "units": unit,
                        "source_network": "AirNow",
                        "ratification": "Provisional",
                        "created_at": fetch_time,
                    }
                )

        current_date = next_date

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


def _empty_dataframe() -> pd.DataFrame:
    """Return empty DataFrame with correct schema."""
    return pd.DataFrame(
        columns=[
            "site_code",
            "date_time",
            "measurand",
            "value",
            "units",
            "source_network",
            "ratification",
            "created_at",
        ]
    )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def fetch_airnow_current(
    latitude: float,
    longitude: float,
    distance: int = 25,
) -> pd.DataFrame:
    """
    Fetch current air quality observations near a location.

    This is a convenience function for getting the latest readings
    without needing to know specific site codes.

    Args:
        latitude: Location latitude
        longitude: Location longitude
        distance: Search radius in miles (default 25)

    Returns:
        pd.DataFrame: Current air quality data

    Example:
        >>> # Get current air quality near Los Angeles
        >>> data = fetch_airnow_current(34.0522, -118.2437)
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "distance": distance,
    }

    data = _call_airnow_api("observation/latLong/current/", params)

    if not data:
        return _empty_dataframe()

    records = []
    fetch_time = datetime.now()

    for obs in data:
        param = obs.get("ParameterName", "")
        aqi = obs.get("AQI")

        if aqi is None:
            continue

        # Create site code from coordinates
        lat = obs.get("Latitude", latitude)
        lon = obs.get("Longitude", longitude)
        site_code = f"{lat:.4f}_{lon:.4f}".replace("-", "m").replace(".", "d")

        # Parse observation time
        date_str = obs.get("DateObserved", "")
        hour = obs.get("HourObserved", 0)
        try:
            dt = pd.to_datetime(f"{date_str} {hour}:00:00")
        except (ValueError, TypeError):
            dt = fetch_time

        measurand = PARAMETER_MAP.get(param.upper(), param)

        records.append(
            {
                "site_code": site_code,
                "date_time": dt,
                "measurand": measurand,
                "value": float(aqi),
                "units": "AQI",
                "source_network": "AirNow",
                "ratification": "Provisional",
                "created_at": fetch_time,
                "category": obs.get("Category", {}).get("Name", ""),
            }
        )

    if not records:
        return _empty_dataframe()

    return pd.DataFrame(records)


# ============================================================================
# SOURCE REGISTRATION
# ============================================================================

register_source(
    "AIRNOW",
    {
        "type": "network",
        "name": "AirNow",
        "fetch_metadata": fetch_airnow_metadata,
        "fetch_data": fetch_airnow_data,
        "normalise": lambda df: df,  # Normalisation happens in fetch_airnow_data
        "requires_api_key": True,
    },
)
