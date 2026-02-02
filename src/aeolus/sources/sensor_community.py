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
from ..transforms import add_column, compose, select_columns

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
            - site_name: Sensor location description (if available)
            - latitude: Sensor latitude
            - longitude: Sensor longitude
            - source_network: "Sensor.Community"
            - sensor_type: Type of sensor (e.g., "SDS011")
            - location_type: "outdoor" or "indoor"

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

        sensors[sensor_id] = {
            "site_code": sensor_id,
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "sensor_type": sensor_info.get("sensor_type", {}).get("name", "Unknown"),
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
# REAL-TIME DATA FETCHER
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

    This returns the most recent measurements from active sensors.

    Args:
        sensor_type: Filter by sensor type(s), e.g., "SDS011" or ["SDS011", "BME280"]
        country: Filter by country code(s), e.g., "GB" or ["GB", "DE", "FR"]
        area: Circular area filter as (latitude, longitude, radius_km)
        box: Bounding box filter as (lat1, lon1, lat2, lon2)
        averaging: Averaging period - "5min", "1h", or "24h" (default "5min")

    Returns:
        pd.DataFrame: Air quality data with standardized schema:
            - site_code: Sensor ID
            - date_time: Measurement timestamp
            - measurand: Pollutant/parameter measured
            - value: Measured value
            - units: Units of measurement
            - source_network: "Sensor.Community"
            - ratification: "Unvalidated" (citizen science data)
            - created_at: When record was fetched

    Example:
        >>> # Get current PM data for all UK sensors
        >>> data = fetch_sensor_community_realtime(
        ...     sensor_type="SDS011",
        ...     country="GB"
        ... )
        >>>
        >>> # Get 24-hour averages for sensors near Berlin
        >>> data = fetch_sensor_community_realtime(
        ...     area=(52.52, 13.405, 25),
        ...     averaging="24h"
        ... )
    """
    # Determine the endpoint based on averaging
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

    # Parse the response into records
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

        # Extract sensor values
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
# HISTORICAL DATA FETCHER
# ============================================================================


def fetch_sensor_community_data(
    sites: list[str] | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    sensor_type: str | list[str] | None = None,
    country: str | list[str] | None = None,
    area: tuple[float, float, float] | None = None,
    box: tuple[float, float, float, float] | None = None,
) -> pd.DataFrame:
    """
    Fetch air quality data from Sensor.Community.

    For real-time data (no dates specified), this calls the live API.
    For historical data, this downloads from the CSV archive.

    Args:
        sites: List of sensor IDs to fetch (optional, for historical data)
        start_date: Start of date range (for historical data)
        end_date: End of date range (for historical data)
        sensor_type: Filter by sensor type(s), e.g., "SDS011" or ["SDS011", "BME280"]
        country: Filter by country code(s), e.g., "GB" or ["GB", "DE", "FR"]
        area: Circular area filter as (latitude, longitude, radius_km)
        box: Bounding box filter as (lat1, lon1, lat2, lon2)

    Returns:
        pd.DataFrame: Air quality data with standardized schema:
            - site_code: Sensor ID
            - date_time: Measurement timestamp
            - measurand: Pollutant/parameter measured
            - value: Measured value
            - units: Units of measurement
            - source_network: "Sensor.Community"
            - ratification: "Unvalidated" (citizen science data)
            - created_at: When record was fetched

    Note:
        Historical archive data is available from 2015 onwards. The archive
        is updated daily around 8:00 AM UTC.

        For real-time data, use fetch_sensor_community_realtime() which
        provides more filtering options.

    Example:
        >>> from datetime import datetime
        >>> # Get historical data for specific sensors
        >>> data = fetch_sensor_community_data(
        ...     sites=["12345", "67890"],
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31),
        ...     sensor_type="SDS011"
        ... )
        >>>
        >>> # Get real-time data (no dates)
        >>> realtime = fetch_sensor_community_data(
        ...     country="GB",
        ...     sensor_type="SDS011"
        ... )
    """
    # If no dates specified, fetch real-time data
    if start_date is None and end_date is None:
        return fetch_sensor_community_realtime(
            sensor_type=sensor_type,
            country=country,
            area=area,
            box=box,
        )

    # For historical data, we need to download from the archive
    if start_date is None:
        start_date = end_date
    if end_date is None:
        end_date = start_date

    # Determine sensor types to fetch
    if sensor_type is None:
        # Default to PM sensors
        sensor_types = ["SDS011"]
        logger.info("No sensor_type specified, defaulting to SDS011 (PM sensors)")
    elif isinstance(sensor_type, str):
        sensor_types = [sensor_type]
    else:
        sensor_types = sensor_type

    all_data = []
    current_date = start_date

    while current_date <= end_date:
        for st in sensor_types:
            logger.info(
                f"Fetching {st} data for {current_date.strftime('%Y-%m-%d')}..."
            )

            df = _fetch_archive_day(current_date, st)

            if not df.empty:
                # Apply site filter if specified
                if sites:
                    df = df[df["site_code"].isin(sites)]

                # Apply country filter if specified
                if country:
                    countries = [country] if isinstance(country, str) else country
                    if "country" in df.columns:
                        df = df[df["country"].isin(countries)]

                # Apply geographic filters
                if area and "latitude" in df.columns and "longitude" in df.columns:
                    lat, lon, radius = area
                    df = _filter_by_distance(df, lat, lon, radius)

                if box and "latitude" in df.columns and "longitude" in df.columns:
                    lat1, lon1, lat2, lon2 = box
                    df = df[
                        (df["latitude"] >= min(lat1, lat2))
                        & (df["latitude"] <= max(lat1, lat2))
                        & (df["longitude"] >= min(lon1, lon2))
                        & (df["longitude"] <= max(lon1, lon2))
                    ]

                if not df.empty:
                    all_data.append(df)

        current_date += timedelta(days=1)

    if not all_data:
        return _empty_dataframe()

    result = pd.concat(all_data, ignore_index=True)

    # Select standard columns
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
    available_cols = [c for c in standard_cols if c in result.columns]

    return result[available_cols]


def _fetch_archive_day(date: datetime, sensor_type: str) -> pd.DataFrame:
    """
    Fetch one day of archive data for a specific sensor type.

    Args:
        date: The date to fetch
        sensor_type: The sensor type (e.g., "SDS011")

    Returns:
        pd.DataFrame: Parsed data for that day
    """
    date_str = date.strftime("%Y-%m-%d")
    filename = f"{date_str}_{sensor_type.lower()}.csv"
    url = f"{ARCHIVE_BASE}/{date_str}/{filename}"

    response = _make_request(url, timeout=60)
    if response is None:
        return pd.DataFrame()

    try:
        # Parse CSV from response content
        df = pd.read_csv(
            io.StringIO(response.text),
            sep=";",
            low_memory=False,
        )
    except Exception as e:
        warning(f"Failed to parse archive CSV for {date_str} {sensor_type}: {e}")
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    # Normalize the archive data
    return _normalize_archive_data(df, sensor_type)


def _normalize_archive_data(df: pd.DataFrame, sensor_type: str) -> pd.DataFrame:
    """
    Normalize archive CSV data to standard schema.

    Archive CSV columns typically include:
    sensor_id, sensor_type, location, lat, lon, timestamp, P1, P2, temperature, humidity, etc.
    """
    records = []
    fetch_time = datetime.now()

    # Determine which measurements this sensor type provides
    measurands = SENSOR_TYPE_MAP.get(sensor_type, [])

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
        sensor_id = str(row.get("sensor_id", ""))
        timestamp_str = row.get("timestamp")

        if not sensor_id:
            continue

        try:
            timestamp = pd.to_datetime(timestamp_str)
        except (ValueError, TypeError):
            continue

        # Extract latitude/longitude for potential filtering
        lat = row.get("lat")
        lon = row.get("lon")

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

            record = {
                "site_code": sensor_id,
                "date_time": timestamp,
                "measurand": measurand,
                "value": value,
                "units": units,
                "source_network": "Sensor.Community",
                "ratification": "Unvalidated",
                "created_at": fetch_time,
            }

            # Include location data for filtering
            if lat is not None and lon is not None:
                try:
                    record["latitude"] = float(lat)
                    record["longitude"] = float(lon)
                except (ValueError, TypeError):
                    pass

            # Include country for filtering
            if "location" in row and pd.notna(row.get("location")):
                record["country"] = str(row.get("location"))

            records.append(record)

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


def _filter_by_distance(
    df: pd.DataFrame, center_lat: float, center_lon: float, radius_km: float
) -> pd.DataFrame:
    """
    Filter DataFrame by distance from a center point.

    Uses the Haversine formula for accurate distance calculation.
    """
    import math

    def haversine_distance(lat1, lon1, lat2, lon2):
        """Calculate distance in km between two points."""
        R = 6371  # Earth's radius in km

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    # Calculate distance for each row
    distances = df.apply(
        lambda row: haversine_distance(
            center_lat, center_lon, row["latitude"], row["longitude"]
        ),
        axis=1,
    )

    return df[distances <= radius_km]


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
