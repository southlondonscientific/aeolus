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
PurpleAir Data Source.

This module provides data fetchers for PurpleAir, a global network of low-cost
air quality sensors with over 30,000 sensors worldwide.

PurpleAir sensors measure PM1.0, PM2.5, PM10, temperature, humidity, and pressure.
They use dual laser counters for redundancy and improved accuracy.

API Documentation: https://api.purpleair.com/
Developer Portal: https://develop.purpleair.com/
Data License: See PurpleAir Terms of Service

QA/QC Methodology: See REFERENCES.md for sources.
"""

import os
from datetime import datetime, timezone
from logging import getLogger, warning
from typing import Any

import pandas as pd

from ..decorators import retry_on_network_error
from ..registry import register_source
from ..transforms import add_column, compose, select_columns

logger = getLogger(__name__)

# Parameter name standardization
# Maps PurpleAir field names to Aeolus standard names
PARAMETER_MAP = {
    "pm1.0_atm": "PM1",
    "pm1.0_cf_1": "PM1",
    "pm2.5_atm": "PM2.5",
    "pm2.5_cf_1": "PM2.5",
    "pm2.5_alt": "PM2.5",
    "pm10.0_atm": "PM10",
    "pm10.0_cf_1": "PM10",
    "humidity": "Humidity",
    "temperature": "Temperature",
    "pressure": "Pressure",
    "voc": "VOC",
    "ozone1": "O3",
}

# Default fields to request for historical data
# Using _atm variants which are more commonly used
# We request both A and B channels to allow for QA
DEFAULT_HISTORY_FIELDS = (
    "pm2.5_atm_a,pm2.5_atm_b,"
    "pm10.0_atm_a,pm10.0_atm_b,"
    "pm1.0_atm_a,pm1.0_atm_b,"
    "humidity_a,humidity_b,"
    "temperature_a,temperature_b"
)

# Fields to request for metadata
METADATA_FIELDS = (
    "name,latitude,longitude,altitude,location_type,"
    "last_seen,date_created,private,model,hardware"
)

# ============================================================================
# QA/QC THRESHOLDS
# ============================================================================
# These thresholds are based on community-validated methodology.
# See REFERENCES.md for sources.

# PM concentration bounds (µg/m³)
PM_LOWER_DETECTION_LIMIT = 0.3  # Below this is noise
PM_UPPER_SATURATION_LIMIT = 1000.0  # Above this sensor saturates

# Channel agreement thresholds
# For low concentrations (<100 µg/m³): use absolute threshold
PM_LOW_CONCENTRATION_THRESHOLD = 100.0  # µg/m³
PM_ABSOLUTE_AGREEMENT_THRESHOLD = 10.0  # µg/m³ - channels must agree within this

# For high concentrations (≥100 µg/m³): use relative threshold
PM_RELATIVE_AGREEMENT_THRESHOLD = 0.10  # 10% - channels must agree within this


# ============================================================================
# API CLIENT
# ============================================================================


def _get_purpleair_client():
    """
    Get a PurpleAir API client with authentication.

    Returns:
        PurpleAirReadAPI: Authenticated API client

    Raises:
        ValueError: If API key is not configured
    """
    from purpleair_api.PurpleAirAPI import PurpleAirReadAPI

    api_key = os.getenv("PURPLEAIR_API_KEY")
    if not api_key:
        raise ValueError(
            "PurpleAir API key required. Set PURPLEAIR_API_KEY in .env file. "
            "Get your free key at: https://develop.purpleair.com/"
        )

    return PurpleAirReadAPI(api_key)


# ============================================================================
# METADATA FETCHER
# ============================================================================


@retry_on_network_error
def fetch_purpleair_metadata(**filters) -> pd.DataFrame:
    """
    Fetch sensor metadata from PurpleAir API.

    Args:
        **filters: Optional filters for metadata query:
            - bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat)
                   This is the standard format used across all Aeolus sources.
            - location_type: 0 for outdoor, 1 for indoor
            - max_age: Maximum age of sensor data in seconds (default 604800 = 1 week)
            - show_only: Comma-separated list of sensor indices to include

            Legacy parameters (still supported):
            - nwlat, nwlng, selat, selng: Individual bounding box corners

    Returns:
        pd.DataFrame: Sensor metadata with standardized schema:
            - site_code: Unique sensor index (as string)
            - site_name: Human-readable sensor name
            - latitude: Sensor latitude
            - longitude: Sensor longitude
            - source_network: "PurpleAir"
            - location_type: "outdoor" or "indoor"
            - altitude: Altitude in feet (if available)
            - last_seen: Last data timestamp
            - date_created: Sensor registration date

    Note:
        - PurpleAir has 30,000+ sensors globally
        - Use bounding box filters to limit results to a geographic area
        - Without filters, returns sensors active in the last week

    Example:
        >>> # Get all outdoor sensors in London area (standard bbox format)
        >>> metadata = fetch_purpleair_metadata(
        ...     bbox=(-0.5, 51.3, 0.3, 51.7),
        ...     location_type=0  # outdoor only
        ... )
        >>>
        >>> # Get specific sensors by index
        >>> metadata = fetch_purpleair_metadata(show_only="131075,131079")
    """
    try:
        client = _get_purpleair_client()
    except ValueError as e:
        warning(str(e))
        return pd.DataFrame()

    # Build API parameters
    params = {
        "fields": METADATA_FIELDS,
    }

    # Handle standard bbox format: (min_lon, min_lat, max_lon, max_lat)
    # Convert to PurpleAir's nw/se format
    if "bbox" in filters and filters["bbox"] is not None:
        min_lon, min_lat, max_lon, max_lat = filters["bbox"]
        params["nwlat"] = max_lat  # North = max latitude
        params["nwlng"] = min_lon  # West = min longitude
        params["selat"] = min_lat  # South = min latitude
        params["selng"] = max_lon  # East = max longitude

    # Map other filter names to API parameters (including legacy bbox params)
    filter_map = {
        "nwlat": "nwlat",
        "nwlng": "nwlng",
        "selat": "selat",
        "selng": "selng",
        "location_type": "location_type",
        "max_age": "max_age",
        "show_only": "show_only",
    }

    for key, api_key in filter_map.items():
        if key in filters and filters[key] is not None:
            params[api_key] = filters[key]

    try:
        response = client.request_multiple_sensors_data(**params)
    except Exception as e:
        warning(f"Failed to fetch PurpleAir metadata: {e}")
        return pd.DataFrame()

    if not response or "data" not in response:
        return pd.DataFrame()

    # Convert response to DataFrame
    # Response format: {"fields": [...], "data": [[...], [...], ...]}
    fields = response.get("fields", [])
    data = response.get("data", [])

    if not data:
        return pd.DataFrame()

    # Use fields directly from API response (sensor_index is included)
    df = pd.DataFrame(data, columns=fields)

    # Normalize to standard schema
    normalizer = _create_metadata_normalizer()
    return normalizer(df)


def _create_metadata_normalizer():
    """
    Create normalization pipeline for PurpleAir metadata.

    Transforms PurpleAir's native schema into Aeolus standard schema.
    """

    def rename_and_convert(df: pd.DataFrame) -> pd.DataFrame:
        """Rename columns to standard names and convert types."""
        df = df.copy()

        # Rename columns
        df["site_code"] = df["sensor_index"].astype(str)
        df["site_name"] = df.get("name", "")

        # Convert location_type from int to string
        if "location_type" in df.columns:
            df["location_type"] = (
                df["location_type"].map({0: "outdoor", 1: "indoor"}).fillna("unknown")
            )

        # Convert timestamps
        if "last_seen" in df.columns:
            df["last_seen"] = pd.to_datetime(df["last_seen"], unit="s", utc=True, errors="coerce")
        if "date_created" in df.columns:
            df["date_created"] = pd.to_datetime(
                df["date_created"], unit="s", utc=True, errors="coerce"
            )

        return df

    return compose(
        rename_and_convert,
        add_column("source_network", "PurpleAir"),
    )


# ============================================================================
# DATA FETCHER
# ============================================================================


@retry_on_network_error
def fetch_purpleair_data(
    sites: list[str],
    start_date: datetime,
    end_date: datetime,
    raw: bool = False,
    include_flagged: bool = True,
) -> pd.DataFrame:
    """
    Fetch air quality data from PurpleAir.

    This function downloads historical data from PurpleAir sensors.
    Data is automatically normalized to match Aeolus standard schema.

    Args:
        sites: List of PurpleAir sensor indices as strings
               Find indices at: https://map.purpleair.com/
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)
        raw: If True, return raw wide-format data with individual channel
             columns (pm2.5_atm_a, pm2.5_atm_b, etc.) before QA/QC and
             normalization. Useful for custom analysis or applying
             alternative QA/QC methods.
        include_flagged: If True (default), include data that fails QA/QC
                        checks (flagged in ratification column). If False,
                        only return data that passes QA/QC.

    Returns:
        pd.DataFrame: Air quality data.

        If raw=False (default): Standardized schema with columns:
            - site_code: PurpleAir sensor index
            - date_time: Measurement timestamp
            - measurand: Pollutant measured (e.g., "PM2.5", "PM10")
            - value: Measured value (average of A and B channels if both valid)
            - units: Units of measurement
            - source_network: "PurpleAir"
            - ratification: Data quality flag (see Notes)
            - created_at: When record was fetched

        If raw=True: Wide-format data with columns:
            - sensor_index: PurpleAir sensor index
            - time_stamp: Unix timestamp
            - pm2.5_atm_a, pm2.5_atm_b: PM2.5 from each channel
            - pm10.0_atm_a, pm10.0_atm_b: PM10 from each channel
            - pm1.0_atm_a, pm1.0_atm_b: PM1 from each channel
            - humidity_a, humidity_b: Humidity from each channel
            - temperature_a, temperature_b: Temperature from each channel

    Note:
        QA/QC Flags (ratification column):
            - "Validated": Both channels valid and agree within thresholds
            - "Channel Disagreement": Both channels valid but disagree
            - "Single Channel (A)" or "Single Channel (B)": Only one channel valid
            - "Below Detection Limit": Value below 0.3 µg/m³
            - "Sensor Saturation": Value above 1000 µg/m³
            - "Invalid": Both channels invalid

        QA/QC Thresholds (for PM measurements):
            - Below 0.3 µg/m³: Flagged as below detection limit
            - 0.3-100 µg/m³: Channels must agree within ±10 µg/m³
            - 100-1000 µg/m³: Channels must agree within ±10%
            - Above 1000 µg/m³: Flagged as sensor saturation

        See REFERENCES.md for methodology sources.

    Example:
        >>> from datetime import datetime
        >>> # Standard normalized data
        >>> data = fetch_purpleair_data(
        ...     sites=["131075"],
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31)
        ... )
        >>>
        >>> # Raw data for custom analysis
        >>> raw_data = fetch_purpleair_data(
        ...     sites=["131075"],
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31),
        ...     raw=True
        ... )
        >>>
        >>> # Only validated data
        >>> clean_data = fetch_purpleair_data(
        ...     sites=["131075"],
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31),
        ...     include_flagged=False
        ... )
    """
    try:
        client = _get_purpleair_client()
    except ValueError as e:
        warning(str(e))
        return _empty_dataframe(raw=raw)

    all_data = []

    for sensor_index in sites:
        logger.info(f"Fetching PurpleAir data for sensor {sensor_index}...")

        try:
            # Convert to int for API
            sensor_idx = int(sensor_index)

            # Request historical data
            # Using 60-minute average for hourly data
            response = client.request_sensor_historic_data(
                sensor_index=sensor_idx,
                fields=DEFAULT_HISTORY_FIELDS,
                start_timestamp=int(start_date.timestamp()),
                end_timestamp=int(end_date.timestamp()),
                average=60,  # Hourly averages
            )

            if response and "data" in response:
                df = _parse_historic_response(response, sensor_index)
                if not df.empty:
                    all_data.append(df)
                    logger.debug(
                        f"Sensor {sensor_index}: fetched {len(df)} measurements"
                    )
            else:
                logger.warning(f"No data returned for sensor {sensor_index}")

        except Exception as e:
            warning(f"Failed to fetch PurpleAir data for sensor {sensor_index}: {e}")
            continue

    if not all_data:
        return _empty_dataframe(raw=raw)

    # Combine all sensor data
    combined = pd.concat(all_data, ignore_index=True)

    # Return raw data if requested
    if raw:
        return combined

    # Apply normalization pipeline
    normalizer = create_purpleair_normalizer()
    result = normalizer(combined)

    # Filter out flagged data if requested
    if not include_flagged:
        result = result[result["ratification"] == "Validated"]

    return result


def _parse_historic_response(response: dict, sensor_index: str) -> pd.DataFrame:
    """
    Parse the historic data response from PurpleAir API.

    The response has a specific structure with fields and data arrays.

    Args:
        response: API response dictionary
        sensor_index: The sensor index (for adding to records)

    Returns:
        pd.DataFrame: Parsed data with columns for each field
    """
    fields = response.get("fields", [])
    data = response.get("data", [])

    if not data or not fields:
        return pd.DataFrame()

    # Create DataFrame with field names as columns
    df = pd.DataFrame(data, columns=fields)

    # Add sensor index
    df["sensor_index"] = sensor_index

    return df


def _empty_dataframe(raw: bool = False) -> pd.DataFrame:
    """Return empty DataFrame with correct schema."""
    if raw:
        return pd.DataFrame(
            columns=[
                "sensor_index",
                "time_stamp",
                "pm2.5_atm_a",
                "pm2.5_atm_b",
                "pm10.0_atm_a",
                "pm10.0_atm_b",
                "pm1.0_atm_a",
                "pm1.0_atm_b",
                "humidity_a",
                "humidity_b",
                "temperature_a",
                "temperature_b",
            ]
        )
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
# SCHEMA NORMALIZATION
# ============================================================================


def create_purpleair_normalizer():
    """
    Create normalization pipeline for PurpleAir data.

    Transforms PurpleAir's wide format (one column per measurement)
    into Aeolus's long format (one row per measurement).

    Returns:
        Normaliser: Composed transformation pipeline
    """

    def melt_to_long_format(df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert wide format to long format.

        PurpleAir returns data in wide format with columns like:
        time_stamp, pm2.5_atm_a, pm2.5_atm_b, pm10.0_atm_a, etc.

        We need to:
        1. Average A and B channels where both valid
        2. Apply QA/QC checks
        3. Convert to long format with measurand column
        """
        records = []

        # Define the measurements we want to extract
        # Each tuple: (measurand_name, channel_a_field, channel_b_field, units, is_pm)
        measurements = [
            ("PM2.5", "pm2.5_atm_a", "pm2.5_atm_b", "ug/m3", True),
            ("PM10", "pm10.0_atm_a", "pm10.0_atm_b", "ug/m3", True),
            ("PM1", "pm1.0_atm_a", "pm1.0_atm_b", "ug/m3", True),
            ("Humidity", "humidity_a", "humidity_b", "%", False),
            ("Temperature", "temperature_a", "temperature_b", "F", False),
        ]

        for _, row in df.iterrows():
            timestamp = row.get("time_stamp")
            sensor_index = row.get("sensor_index")

            for measurand, field_a, field_b, units, is_pm in measurements:
                # Get values from both channels
                val_a = row.get(field_a)
                val_b = row.get(field_b)

                # Calculate the value and apply QA/QC
                if is_pm:
                    value, ratification = _calculate_pm_channel_value(val_a, val_b)
                else:
                    # For non-PM measurements, just average without QA/QC
                    value, ratification = _calculate_channel_value_simple(val_a, val_b)

                if value is not None:
                    records.append(
                        {
                            "sensor_index": sensor_index,
                            "time_stamp": timestamp,
                            "measurand": measurand,
                            "value": value,
                            "units": units,
                            "ratification": ratification,
                        }
                    )

        return pd.DataFrame(records)

    def parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
        """Convert timestamp to datetime."""
        if df.empty:
            return df

        df = df.copy()
        # PurpleAir returns timestamps as Unix timestamps
        df["date_time"] = pd.to_datetime(df["time_stamp"], unit="s", utc=True, errors="coerce")
        return df

    def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Rename columns to standard names."""
        if df.empty:
            return df

        df = df.copy()
        df["site_code"] = df["sensor_index"].astype(str)
        return df

    def convert_temperature(df: pd.DataFrame) -> pd.DataFrame:
        """Convert temperature from Fahrenheit to Celsius."""
        if df.empty:
            return df

        df = df.copy()
        temp_mask = df["measurand"] == "Temperature"
        df.loc[temp_mask, "value"] = (df.loc[temp_mask, "value"] - 32) * 5 / 9
        df.loc[temp_mask, "units"] = "C"
        return df

    # Compose the full pipeline
    return compose(
        melt_to_long_format,
        parse_timestamps,
        rename_columns,
        convert_temperature,
        add_column("source_network", "PurpleAir"),
        add_column("created_at", datetime.now(timezone.utc)),
        select_columns(
            "site_code",
            "date_time",
            "measurand",
            "value",
            "units",
            "source_network",
            "ratification",
            "created_at",
        ),
    )


def _calculate_pm_channel_value(
    val_a: float | None, val_b: float | None
) -> tuple[float | None, str]:
    """
    Calculate PM measurement value from dual channels with QA/QC.

    PurpleAir sensors have two laser counters (A and B) for redundancy.
    This function applies literature-based QA/QC thresholds:

    - Below 0.3 µg/m³: Flagged as below detection limit
    - 0.3-100 µg/m³: Channels must agree within ±10 µg/m³ (absolute)
    - 100-1000 µg/m³: Channels must agree within ±10% (relative)
    - Above 1000 µg/m³: Flagged as sensor saturation

    See REFERENCES.md for methodology sources.

    Args:
        val_a: Value from channel A (µg/m³)
        val_b: Value from channel B (µg/m³)

    Returns:
        Tuple of (value, ratification_status)
    """
    # Check for valid values (not None, not NaN)
    a_valid = val_a is not None and not pd.isna(val_a)
    b_valid = val_b is not None and not pd.isna(val_b)

    if not a_valid and not b_valid:
        return None, "Invalid"

    # Single channel case
    if not a_valid:
        return _apply_pm_bounds_check(val_b, "Single Channel (B)")
    if not b_valid:
        return _apply_pm_bounds_check(val_a, "Single Channel (A)")

    # Both channels valid - calculate average
    avg = (val_a + val_b) / 2

    # Check bounds
    if avg < PM_LOWER_DETECTION_LIMIT:
        return avg, "Below Detection Limit"
    if avg > PM_UPPER_SATURATION_LIMIT:
        return avg, "Sensor Saturation"

    # Check channel agreement based on concentration
    diff = abs(val_a - val_b)

    if avg < PM_LOW_CONCENTRATION_THRESHOLD:
        # Low concentration: use absolute threshold
        if diff <= PM_ABSOLUTE_AGREEMENT_THRESHOLD:
            return avg, "Validated"
        else:
            return avg, "Channel Disagreement"
    else:
        # High concentration: use relative threshold
        relative_diff = diff / avg
        if relative_diff <= PM_RELATIVE_AGREEMENT_THRESHOLD:
            return avg, "Validated"
        else:
            return avg, "Channel Disagreement"


def _apply_pm_bounds_check(value: float, base_flag: str) -> tuple[float | None, str]:
    """
    Apply PM bounds check to a single value.

    Args:
        value: PM value in µg/m³
        base_flag: Base flag to use if bounds check passes

    Returns:
        Tuple of (value, ratification_status)
    """
    if value < PM_LOWER_DETECTION_LIMIT:
        return value, "Below Detection Limit"
    if value > PM_UPPER_SATURATION_LIMIT:
        return value, "Sensor Saturation"
    return value, base_flag


def _calculate_channel_value_simple(
    val_a: float | None, val_b: float | None
) -> tuple[float | None, str]:
    """
    Calculate measurement value from dual channels without PM-specific QA/QC.

    Used for non-PM measurements (humidity, temperature) where the PM
    thresholds don't apply.

    Args:
        val_a: Value from channel A
        val_b: Value from channel B

    Returns:
        Tuple of (value, ratification_status)
    """
    # Check for valid values (not None, not NaN)
    a_valid = val_a is not None and not pd.isna(val_a)
    b_valid = val_b is not None and not pd.isna(val_b)

    if not a_valid and not b_valid:
        return None, "Invalid"

    if a_valid and b_valid:
        return (val_a + val_b) / 2, "Unvalidated"

    if a_valid:
        return val_a, "Single Channel (A)"
    else:
        return val_b, "Single Channel (B)"


# ============================================================================
# LEGACY FUNCTION FOR BACKWARD COMPATIBILITY
# ============================================================================


def _calculate_channel_value(
    val_a: float | None, val_b: float | None
) -> tuple[float | None, str]:
    """
    Legacy function - calls _calculate_pm_channel_value for backward compatibility.

    Deprecated: Use _calculate_pm_channel_value for PM measurements or
    _calculate_channel_value_simple for other measurements.
    """
    return _calculate_pm_channel_value(val_a, val_b)


# ============================================================================
# SOURCE REGISTRATION
# ============================================================================

register_source(
    "PURPLEAIR",
    {
        "type": "portal",
        "name": "PurpleAir",
        "fetch_metadata": fetch_purpleair_metadata,
        "fetch_data": fetch_purpleair_data,
        "normalise": create_purpleair_normalizer(),
        "requires_api_key": True,
    },
)
