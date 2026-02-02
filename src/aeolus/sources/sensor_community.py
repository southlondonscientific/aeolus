# Aeolus: download UK and standardise air quality data
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
Sensor.Community Data Source.

This module provides data fetchers for Sensor.Community (formerly luftdaten.info),
a global citizen science network of low-cost air quality sensors with over 35,000
sensors worldwide.

Sensor.Community sensors typically measure:
- PM2.5 and PM10 (using SDS011, PMS series, or similar sensors)
- Temperature, humidity, and pressure (using BME280, DHT22, etc.)

The API is completely open with no authentication required.

API Documentation: https://github.com/opendata-stuttgart/meta/wiki/EN-APIs
Data Archive: https://archive.sensor.community/
Map: https://maps.sensor.community/
"""

import io
import time
from datetime import datetime, timedelta
from logging import getLogger, warning
from typing import Any

import pandas as pd
import requests

from ..registry import register_source

logger = getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# API base URLs
DATA_API_BASE = "https://data.sensor.community"
ARCHIVE_BASE = "https://archive.sensor.community"

# User-Agent header (required by Sensor.Community as of Nov 2022)
USER_AGENT = "aeolus-aq/0.3.0 (https://github.com/southlondonscientific/aeolus; air quality research)"

# Rate limiting defaults (conservative since no official limits documented)
DEFAULT_RATE_LIMIT_REQUESTS = 10  # Max requests per period
DEFAULT_RATE_LIMIT_PERIOD = 60.0  # Period in seconds (10 requests per minute)
DEFAULT_REQUEST_DELAY = 1.0  # Minimum seconds between requests

# Sensor type mappings
# Maps Sensor.Community sensor types to the measurements they provide
SENSOR_TYPE_MAP = {
    # Particulate matter sensors
    "SDS011": ["PM2.5", "PM10"],
    "SDS021": ["PM2.5", "PM10"],
    "PMS1003": ["PM1", "PM2.5", "PM10"],
    "PMS3003": ["PM1", "PM2.5", "PM10"],
    "PMS5003": ["PM1", "PM2.5", "PM10"],
    "PMS6003": ["PM1", "PM2.5", "PM10"],
    "PMS7003": ["PM1", "PM2.5", "PM10"],
    "HPM": ["PM2.5", "PM10"],
    "SPS30": ["PM1", "PM2.5", "PM4", "PM10"],
    # Temperature/humidity/pressure sensors
    "BME280": ["Temperature", "Humidity", "Pressure"],
    "BMP280": ["Temperature", "Pressure"],
    "DHT22": ["Temperature", "Humidity"],
    "HTU21D": ["Temperature", "Humidity"],
    "SHT31": ["Temperature", "Humidity"],
    "DS18B20": ["Temperature"],
}

# Value name mappings from API to standard names
VALUE_NAME_MAP = {
    "P1": "PM10",
    "P2": "PM2.5",
    "P0": "PM1",
    "P4": "PM4",
    "temperature": "Temperature",
    "humidity": "Humidity",
    "pressure": "Pressure",
    "pressure_at_sealevel": "Pressure (Sea Level)",
}

# Units for each measurand
UNITS_MAP = {
    "PM1": "ug/m3",
    "PM2.5": "ug/m3",
    "PM4": "ug/m3",
    "PM10": "ug/m3",
    "Temperature": "C",
    "Humidity": "%",
    "Pressure": "Pa",
    "Pressure (Sea Level)": "Pa",
}

# Cache for sensor type lookups (sensor_id -> sensor_type)
_sensor_type_cache: dict[str, str] = {}


# ============================================================================
# RATE LIMITER
# ============================================================================


class RateLimiter:
    """
    Simple rate limiter to prevent overwhelming the Sensor.Community API.

    Uses a sliding window approach with configurable requests per period.
    """

    def __init__(
        self,
        max_requests: int = DEFAULT_RATE_LIMIT_REQUESTS,
        period: float = DEFAULT_RATE_LIMIT_PERIOD,
        min_delay: float = DEFAULT_REQUEST_DELAY,
    ):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum number of requests allowed per period
            period: Time period in seconds
            min_delay: Minimum delay between any two requests
        """
        self.max_requests = max_requests
        self.period = period
        self.min_delay = min_delay
        self.request_times: list[float] = []

    def wait_if_needed(self) -> None:
        """
        Wait if necessary to comply with rate limits.

        This method blocks until it's safe to make another request.
        """
        now = time.time()

        # Clean up old request times outside the window
        self.request_times = [t for t in self.request_times if now - t < self.period]

        # Check if we need to wait for the rate limit
        if len(self.request_times) >= self.max_requests:
            # Wait until the oldest request falls outside the window
            oldest = min(self.request_times)
            wait_time = self.period - (now - oldest)
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                now = time.time()
                self.request_times = [
                    t for t in self.request_times if now - t < self.period
                ]

        # Ensure minimum delay between requests
        if self.request_times:
            last_request = max(self.request_times)
            time_since_last = now - last_request
            if time_since_last < self.min_delay:
                sleep_time = self.min_delay - time_since_last
                logger.debug(f"Enforcing minimum delay, waiting {sleep_time:.2f}s")
                time.sleep(sleep_time)

        # Record this request
        self.request_times.append(time.time())


# Global rate limiter instance (can be disabled)
_rate_limiter: RateLimiter | None = RateLimiter()


def set_rate_limiting(
    enabled: bool = True,
    max_requests: int = DEFAULT_RATE_LIMIT_REQUESTS,
    period: float = DEFAULT_RATE_LIMIT_PERIOD,
    min_delay: float = DEFAULT_REQUEST_DELAY,
) -> None:
    """
    Configure rate limiting for Sensor.Community API requests.

    Rate limiting is enabled by default to be respectful to the community-run
    infrastructure. You can disable it if you have a specific need, but please
    be considerate of the shared resource.

    Args:
        enabled: Whether to enable rate limiting (default True)
        max_requests: Maximum requests per period (default 10)
        period: Period in seconds (default 60)
        min_delay: Minimum delay between requests in seconds (default 1.0)

    Example:
        >>> # Disable rate limiting (not recommended)
        >>> set_rate_limiting(enabled=False)
        >>>
        >>> # More aggressive rate limiting
        >>> set_rate_limiting(max_requests=5, period=60, min_delay=2.0)
        >>>
        >>> # Re-enable with defaults
        >>> set_rate_limiting(enabled=True)
    """
    global _rate_limiter
    if enabled:
        _rate_limiter = RateLimiter(max_requests, period, min_delay)
        logger.info(
            f"Rate limiting enabled: {max_requests} requests per {period}s, "
            f"min delay {min_delay}s"
        )
    else:
        _rate_limiter = None
        logger.warning(
            "Rate limiting disabled. Please be considerate of the "
            "community-run Sensor.Community infrastructure."
        )


def _apply_rate_limit() -> None:
    """Apply rate limiting if enabled."""
    if _rate_limiter is not None:
        _rate_limiter.wait_if_needed()


# ============================================================================
# HTTP CLIENT
# ============================================================================


def _make_request(url: str, timeout: int = 30) -> requests.Response | None:
    """
    Make an HTTP GET request with appropriate headers and error handling.

    Args:
        url: The URL to request
        timeout: Request timeout in seconds

    Returns:
        Response object if successful, None otherwise
    """
    _apply_rate_limit()

    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.Timeout:
        warning(f"Request timed out: {url}")
        return None
    except requests.exceptions.HTTPError as e:
        # Don't warn for 404s on archive files - they're expected for some sensors
        if e.response.status_code != 404:
            warning(f"HTTP error {e.response.status_code}: {url}")
        return None
    except requests.exceptions.RequestException as e:
        warning(f"Request failed: {e}")
        return None


# ============================================================================
# METADATA FETCHER
# ============================================================================


def fetch_sensor_community_metadata(
    sensor_type: str | list[str] | None = None,
    country: str | list[str] | None = None,
    area: tuple[float, float, float] | None = None,
    box: tuple[float, float, float, float] | None = None,
) -> pd.DataFrame:
    """
    Fetch sensor metadata from Sensor.Community API.

    This returns information about currently active sensors (those that have
    reported data in the last 5 minutes).

    Args:
        sensor_type: Filter by sensor type(s), e.g., "SDS011" or ["SDS011", "BME280"]
        country: Filter by country code(s), e.g., "GB" or ["GB", "DE", "FR"]
        area: Circular area filter as (latitude, longitude, radius_km)
        box: Bounding box filter as (lat1, lon1, lat2, lon2)

    Returns:
        pd.DataFrame: Sensor metadata with standardized schema:
            - site_code: Unique sensor ID (as string)
            - latitude: Sensor latitude
            - longitude: Sensor longitude
            - sensor_type: Type of sensor (e.g., "SDS011") - used internally
            - location_type: "outdoor" or "indoor"
            - country: Country code
            - source_network: "Sensor.Community"

    Example:
        >>> # Get all PM sensors in the UK
        >>> metadata = fetch_sensor_community_metadata(
        ...     sensor_type="SDS011",
        ...     country="GB"
        ... )
        >>>
        >>> # Get sensors in a 50km radius around London
        >>> metadata = fetch_sensor_community_metadata(
        ...     area=(51.5074, -0.1278, 50)
        ... )
    """
    global _sensor_type_cache

    # Build the filter query
    filters = []

    if sensor_type:
        if isinstance(sensor_type, str):
            sensor_type = [sensor_type]
        filters.append(f"type={','.join(sensor_type)}")

    if country:
        if isinstance(country, str):
            country = [country]
        filters.append(f"country={','.join(country)}")

    if area:
        lat, lon, radius = area
        filters.append(f"area={lat},{lon},{radius}")

    if box:
        lat1, lon1, lat2, lon2 = box
        filters.append(f"box={lat1},{lon1},{lat2},{lon2}")

    # Construct URL
    if filters:
        filter_query = "&".join(filters)
        url = f"{DATA_API_BASE}/airrohr/v1/filter/{filter_query}"
    else:
        # Get all sensors (this can be large!)
        url = f"{DATA_API_BASE}/static/v2/data.json"
        logger.warning(
            "Fetching all sensors without filters - this may return a large dataset"
        )

    response = _make_request(url)
    if response is None:
        return pd.DataFrame()

    try:
        data = response.json()
    except ValueError:
        warning("Failed to parse JSON response")
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    # Extract unique sensors from the response
    sensors = {}
    for entry in data:
        sensor_id = str(entry.get("sensor", {}).get("id", ""))
        if not sensor_id or sensor_id in sensors:
            continue

        location = entry.get("location", {})
        sensor_info = entry.get("sensor", {})
        sensor_type_name = sensor_info.get("sensor_type", {}).get("name", "Unknown")

        # Cache the sensor type for later data fetching
        _sensor_type_cache[sensor_id] = sensor_type_name

        sensors[sensor_id] = {
            "site_code": sensor_id,
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "sensor_type": sensor_type_name,
            "location_type": "indoor" if location.get("indoor") == 1 else "outdoor",
            "country": location.get("country", ""),
            "source_network": "Sensor.Community",
        }

    if not sensors:
        return pd.DataFrame()

    df = pd.DataFrame(list(sensors.values()))

    # Convert coordinates to numeric
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    return df


# ============================================================================
# SENSOR TYPE LOOKUP
# ============================================================================


def _get_sensor_types_for_sites(site_ids: list[str]) -> dict[str, str]:
    """
    Get sensor types for a list of site IDs.

    First checks the cache, then queries the API for any missing sensors.

    Args:
        site_ids: List of sensor IDs

    Returns:
        dict: Mapping of sensor_id -> sensor_type
    """
    global _sensor_type_cache

    result = {}
    missing = []

    # Check cache first
    for site_id in site_ids:
        if site_id in _sensor_type_cache:
            result[site_id] = _sensor_type_cache[site_id]
        else:
            missing.append(site_id)

    # If all found in cache, return
    if not missing:
        return result

    # Query the API to get sensor types for missing IDs
    # We need to fetch current data to determine sensor types
    logger.info(f"Looking up sensor types for {len(missing)} sensors...")

    # Fetch all current sensor data (this gives us type info)
    url = f"{DATA_API_BASE}/static/v2/data.json"
    response = _make_request(url, timeout=60)

    if response is not None:
        try:
            data = response.json()
            for entry in data:
                sensor_id = str(entry.get("sensor", {}).get("id", ""))
                if sensor_id in missing:
                    sensor_type = (
                        entry.get("sensor", {})
                        .get("sensor_type", {})
                        .get("name", "Unknown")
                    )
                    result[sensor_id] = sensor_type
                    _sensor_type_cache[sensor_id] = sensor_type
        except ValueError:
            pass

    # For any still missing, we'll have to try common sensor types
    still_missing = [s for s in missing if s not in result]
    if still_missing:
        logger.warning(
            f"Could not determine sensor type for {len(still_missing)} sensors. "
            "Will try common types (SDS011, BME280)."
        )
        # Mark as unknown - we'll try common types when fetching
        for site_id in still_missing:
            result[site_id] = "Unknown"

    return result


# ============================================================================
# HISTORICAL DATA FETCHER
# ============================================================================


def fetch_sensor_community_data(
    sites: list[str],
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    """
    Fetch air quality data from Sensor.Community.

    This function downloads historical data from the Sensor.Community archive.
    It automatically determines the sensor type for each site and fetches the
    appropriate data files.

    Args:
        sites: List of sensor IDs to fetch (use fetch_sensor_community_metadata
               to find sensor IDs)
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        pd.DataFrame: Air quality data with standardized schema:
            - site_code: Sensor ID
            - date_time: Measurement timestamp
            - measurand: Pollutant/parameter measured (e.g., "PM2.5", "PM10")
            - value: Measured value
            - units: Units of measurement
            - source_network: "Sensor.Community"
            - ratification: "Unvalidated" (citizen science data)
            - created_at: When record was fetched

    Note:
        Historical archive data is available from 2015 onwards. The archive
        is updated daily around 8:00 AM UTC.

    Example:
        >>> from datetime import datetime
        >>> import aeolus
        >>>
        >>> # Get sensors in the UK
        >>> metadata = aeolus.networks.get_metadata(
        ...     "SENSOR_COMMUNITY",
        ...     sensor_type="SDS011",
        ...     country="GB"
        ... )
        >>>
        >>> # Pick some sensors and download data
        >>> sites = metadata["site_code"].head(3).tolist()
        >>> data = aeolus.download(
        ...     "SENSOR_COMMUNITY",
        ...     sites,
        ...     datetime(2024, 1, 1),
        ...     datetime(2024, 1, 7)
        ... )
    """
    if not sites:
        return _empty_dataframe()

    # Look up sensor types for all requested sites
    sensor_types = _get_sensor_types_for_sites(sites)

    # Group sites by sensor type for efficient fetching
    sites_by_type: dict[str, list[str]] = {}
    unknown_sites: list[str] = []

    for site_id in sites:
        sensor_type = sensor_types.get(site_id, "Unknown")
        if sensor_type == "Unknown":
            unknown_sites.append(site_id)
        else:
            if sensor_type not in sites_by_type:
                sites_by_type[sensor_type] = []
            sites_by_type[sensor_type].append(site_id)

    all_data = []
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")

        # Fetch data for each sensor type group
        for sensor_type, type_sites in sites_by_type.items():
            for site_id in type_sites:
                df = _fetch_sensor_archive(current_date, sensor_type, site_id)
                if not df.empty:
                    all_data.append(df)

        # For unknown sensors, try common PM sensor types
        if unknown_sites:
            for site_id in unknown_sites:
                # Try SDS011 first (most common), then BME280
                for try_type in ["SDS011", "BME280", "PMS5003", "PMS7003"]:
                    df = _fetch_sensor_archive(current_date, try_type, site_id)
                    if not df.empty:
                        # Cache the successful type for future requests
                        _sensor_type_cache[site_id] = try_type
                        all_data.append(df)
                        break

        current_date += timedelta(days=1)

    if not all_data:
        return _empty_dataframe()

    result = pd.concat(all_data, ignore_index=True)

    # Ensure standard column order
    standard_cols = [
        "site_code",
        "date_time",
        "measurand",
        "value",
        "units",
        "source_network",
        "ratification",
        "created_at",
    ]

    return result[standard_cols]


def _fetch_sensor_archive(
    date: datetime, sensor_type: str, sensor_id: str
) -> pd.DataFrame:
    """
    Fetch archive data for a specific sensor on a specific date.

    The archive stores one CSV file per sensor per day:
    {date}_{sensor_type}_sensor_{sensor_id}.csv

    Args:
        date: The date to fetch
        sensor_type: The sensor type (e.g., "SDS011")
        sensor_id: The sensor ID

    Returns:
        pd.DataFrame: Parsed and normalized data
    """
    date_str = date.strftime("%Y-%m-%d")
    filename = f"{date_str}_{sensor_type.lower()}_sensor_{sensor_id}.csv"
    url = f"{ARCHIVE_BASE}/{date_str}/{filename}"

    response = _make_request(url, timeout=60)
    if response is None:
        return pd.DataFrame()

    try:
        df = pd.read_csv(
            io.StringIO(response.text),
            sep=";",
            low_memory=False,
        )
    except Exception as e:
        logger.debug(f"Failed to parse archive CSV {filename}: {e}")
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    return _normalize_sensor_data(df, sensor_type, sensor_id)


def _normalize_sensor_data(
    df: pd.DataFrame, sensor_type: str, sensor_id: str
) -> pd.DataFrame:
    """
    Normalize sensor CSV data to standard schema.

    Args:
        df: Raw CSV data
        sensor_type: The sensor type
        sensor_id: The sensor ID

    Returns:
        pd.DataFrame: Normalized data with standard schema
    """
    records = []
    fetch_time = datetime.now()

    # Determine which measurements this sensor type provides
    measurands = SENSOR_TYPE_MAP.get(sensor_type, ["PM2.5", "PM10"])

    # Map archive column names to our standard names
    archive_value_map = {
        "P1": "PM10",
        "P2": "PM2.5",
        "P0": "PM1",
        "temperature": "Temperature",
        "humidity": "Humidity",
        "pressure": "Pressure",
    }

    for _, row in df.iterrows():
        timestamp_str = row.get("timestamp")

        try:
            timestamp = pd.to_datetime(timestamp_str)
        except (ValueError, TypeError):
            continue

        for col, measurand in archive_value_map.items():
            if col not in df.columns:
                continue
            if measurand not in measurands:
                continue

            value = row.get(col)
            if pd.isna(value):
                continue

            try:
                value = float(value)
            except (ValueError, TypeError):
                continue

            units = UNITS_MAP.get(measurand, "")

            records.append(
                {
                    "site_code": sensor_id,
                    "date_time": timestamp,
                    "measurand": measurand,
                    "value": value,
                    "units": units,
                    "source_network": "Sensor.Community",
                    "ratification": "Unvalidated",
                    "created_at": fetch_time,
                }
            )

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
# REAL-TIME DATA FETCHER (for direct use, not via aeolus.download)
# ============================================================================


def fetch_sensor_community_realtime(
    sensor_type: str | list[str] | None = None,
    country: str | list[str] | None = None,
    area: tuple[float, float, float] | None = None,
    box: tuple[float, float, float, float] | None = None,
    averaging: str = "5min",
) -> pd.DataFrame:
    """
    Fetch real-time data from Sensor.Community API.

    This returns the most recent measurements from active sensors. Use this
    for real-time monitoring; for historical data, use aeolus.download().

    Args:
        sensor_type: Filter by sensor type(s), e.g., "SDS011" or ["SDS011", "BME280"]
        country: Filter by country code(s), e.g., "GB" or ["GB", "DE", "FR"]
        area: Circular area filter as (latitude, longitude, radius_km)
        box: Bounding box filter as (lat1, lon1, lat2, lon2)
        averaging: Averaging period - "5min", "1h", or "24h" (default "5min")

    Returns:
        pd.DataFrame: Air quality data with standardized schema

    Example:
        >>> from aeolus.sources.sensor_community import fetch_sensor_community_realtime
        >>>
        >>> # Get current PM data for all UK sensors
        >>> data = fetch_sensor_community_realtime(
        ...     sensor_type="SDS011",
        ...     country="GB"
        ... )
    """
    avg_endpoints = {
        "5min": "data.json",
        "1h": "data.1h.json",
        "24h": "data.24h.json",
    }

    if averaging not in avg_endpoints:
        raise ValueError(f"Invalid averaging: {averaging}. Use '5min', '1h', or '24h'")

    # Build the filter query
    filters = []

    if sensor_type:
        if isinstance(sensor_type, str):
            sensor_type = [sensor_type]
        filters.append(f"type={','.join(sensor_type)}")

    if country:
        if isinstance(country, str):
            country = [country]
        filters.append(f"country={','.join(country)}")

    if area:
        lat, lon, radius = area
        filters.append(f"area={lat},{lon},{radius}")

    if box:
        lat1, lon1, lat2, lon2 = box
        filters.append(f"box={lat1},{lon1},{lat2},{lon2}")

    # Construct URL
    if filters:
        filter_query = "&".join(filters)
        url = f"{DATA_API_BASE}/airrohr/v1/filter/{filter_query}"
    else:
        url = f"{DATA_API_BASE}/static/v2/{avg_endpoints[averaging]}"

    response = _make_request(url)
    if response is None:
        return _empty_dataframe()

    try:
        data = response.json()
    except ValueError:
        warning("Failed to parse JSON response")
        return _empty_dataframe()

    if not data:
        return _empty_dataframe()

    records = []
    fetch_time = datetime.now()

    for entry in data:
        sensor_id = str(entry.get("sensor", {}).get("id", ""))
        timestamp_str = entry.get("timestamp")

        if not sensor_id or not timestamp_str:
            continue

        try:
            timestamp = pd.to_datetime(timestamp_str)
        except (ValueError, TypeError):
            continue

        sensor_data_values = entry.get("sensordatavalues", [])
        for sdv in sensor_data_values:
            value_type = sdv.get("value_type", "")
            value = sdv.get("value")

            if value_type not in VALUE_NAME_MAP:
                continue

            try:
                value = float(value)
            except (ValueError, TypeError):
                continue

            measurand = VALUE_NAME_MAP[value_type]
            units = UNITS_MAP.get(measurand, "")

            records.append(
                {
                    "site_code": sensor_id,
                    "date_time": timestamp,
                    "measurand": measurand,
                    "value": value,
                    "units": units,
                    "source_network": "Sensor.Community",
                    "ratification": "Unvalidated",
                    "created_at": fetch_time,
                }
            )

    if not records:
        return _empty_dataframe()

    return pd.DataFrame(records)


# ============================================================================
# SOURCE REGISTRATION
# ============================================================================

register_source(
    "SENSOR_COMMUNITY",
    {
        "type": "network",
        "name": "Sensor.Community",
        "fetch_metadata": fetch_sensor_community_metadata,
        "fetch_data": fetch_sensor_community_data,
        "requires_api_key": False,
    },
)
