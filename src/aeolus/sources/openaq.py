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
This module provides data fetchers for OpenAQ, a global air quality data
platform aggregating data from over 100 countries.

OpenAQ provides access to both government monitoring stations and low-cost
sensor networks worldwide.

API Documentation: https://docs.openaq.org/
Data Platform: https://openaq.org/
"""

import os
import warnings
from datetime import datetime
from logging import warning
from typing import Any

import pandas as pd
import requests

from ..decorators import retry_on_network_error
from ..registry import register_source
from ..transforms import add_column, compose, rename_columns, select_columns

# Configuration
OPENAQ_API_BASE = "https://api.openaq.org/v3"

# Parameter name standardization
# Maps OpenAQ parameter names to Aeolus standard names
PARAMETER_MAP = {
    "no2": "NO2",
    "pm25": "PM2.5",
    "pm10": "PM10",
    "o3": "O3",
    "so2": "SO2",
    "co": "CO",
    "bc": "BC",  # Black Carbon
    "no": "NO",
    "nox": "NOX",
    "pm1": "PM1",
    "ch4": "CH4",  # Methane
    "um003": "PM0.3",
    "um005": "PM0.5",
    "um010": "PM1.0",
    "um025": "PM2.5",
    "um100": "PM10",
}


# ============================================================================
# LOW-LEVEL API FUNCTIONS
# ============================================================================


@retry_on_network_error
def _call_openaq_api(endpoint: str, params: dict) -> dict:
    """
    Low-level OpenAQ API caller with authentication and error handling.

    Args:
        endpoint: API endpoint (e.g., "locations", "measurements")
        params: Query parameters

    Returns:
        dict: JSON response from API

    Raises:
        requests.HTTPError: If API returns error status
    """
    headers = {"Accept": "application/json"}

    # API key is required for OpenAQ v3 - read at call time for testability
    api_key = os.getenv("OPENAQ_API_KEY")
    if not api_key:
        raise ValueError(
            "OpenAQ API key required. Set OPENAQ_API_KEY in .env file. "
            "Get free key at: https://openaq.org/"
        )

    headers["X-API-Key"] = api_key

    url = f"{OPENAQ_API_BASE}/{endpoint}"

    response = requests.get(url, params=params, headers=headers, timeout=30)

    # Handle rate limiting and errors
    if response.status_code == 429:
        raise requests.HTTPError(
            "OpenAQ rate limit exceeded. "
            "Try requesting less data or wait before retrying."
        )

    if response.status_code == 404:
        # Location or data not found - this is common, not an error
        return {"results": [], "meta": {"found": 0, "pages": 0}}

    response.raise_for_status()
    return response.json()


def _paginate_openaq(endpoint: str, params: dict, max_pages: int | None = None):
    """
    Handle OpenAQ pagination automatically.

    OpenAQ returns max 100 records per page. This generator yields all results
    by automatically fetching subsequent pages.

    Args:
        endpoint: API endpoint
        params: Query parameters
        max_pages: Maximum pages to fetch (None = all pages)

    Yields:
        Individual records from all pages
    """
    import logging

    logger = logging.getLogger(__name__)

    page = 1
    fetched_pages = 0

    while True:
        # Add pagination params
        params_with_page = {**params, "page": page, "limit": 100}

        try:
            data = _call_openaq_api(endpoint, params_with_page)
            logger.debug(
                f"Fetched page {page} from {endpoint}, got {len(data.get('results', []))} results"
            )
        except requests.HTTPError as e:
            warning(f"Failed to fetch page {page} from OpenAQ: {e}")
            break

        # Check if we got results
        if "results" not in data or not data["results"]:
            break

        # Yield all results from this page
        yield from data["results"]

        fetched_pages += 1

        # Check if we should continue
        meta = data.get("meta", {})
        found = meta.get("found", 0)
        limit = meta.get("limit", 100)

        # Handle case where 'found' might be a string
        try:
            found_int = int(found) if found else 0
        except (ValueError, TypeError):
            logger.warning(
                f"Could not convert 'found' to int: {found} (type: {type(found)})"
            )
            found_int = 0

        # Handle case where 'limit' might be a string
        try:
            limit_int = int(limit) if limit else 100
        except (ValueError, TypeError):
            logger.warning(
                f"Could not convert 'limit' to int: {limit} (type: {type(limit)})"
            )
            limit_int = 100

        # Calculate total pages based on actual limit from API
        total_pages = (found_int + limit_int - 1) // limit_int if limit_int > 0 else 1
        logger.debug(
            f"Page {page}/{total_pages}, found={found}, limit={limit}, fetched_pages={fetched_pages}"
        )

        if page >= total_pages:
            break

        if max_pages and fetched_pages >= max_pages:
            break

        page += 1


def _get_sensors_for_location(location_id: int) -> list[dict]:
    """
    Get all sensors for a given location.

    OpenAQ v3 requires fetching sensors first, then querying measurements
    for each sensor.

    Args:
        location_id: OpenAQ location ID

    Returns:
        list[dict]: List of sensor records with id, name, parameter info
    """
    try:
        data = _call_openaq_api(f"locations/{location_id}/sensors", {})
        return data.get("results", [])
    except Exception as e:
        warning(f"Failed to fetch sensors for location {location_id}: {e}")
        return []


# ============================================================================
# DATA FETCHER
# ============================================================================


def fetch_openaq_data(
    sites: list[str], start_date: datetime, end_date: datetime
) -> pd.DataFrame:
    """
    Fetch air quality data from OpenAQ.

    This function downloads data from OpenAQ's global air quality platform.
    Data is automatically normalized to match Aeolus standard schema.

    Args:
        sites: List of OpenAQ location IDs as strings
               Find IDs at: https://openaq.org/
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        pd.DataFrame: Air quality data with standardized schema:
            - site_code: OpenAQ location ID
            - date_time: Measurement timestamp (end of averaging period)
            - measurand: Pollutant measured (e.g., "NO2", "PM2.5")
            - value: Measured value
            - units: Units of measurement
            - source_network: "OpenAQ"
            - ratification: Data quality flag
            - created_at: When record was fetched

    Note:
        - OpenAQ v3 API requires an API key (set OPENAQ_API_KEY in .env)
        - Get free API key at: https://openaq.org/
        - Returns hourly averages by default
        - Automatically handles pagination
        - Timestamps follow left-closed interval convention:
          13:00 represents data from [12:00, 13:00)
        - Location IDs can be found at: https://explore.openaq.org/
        - OpenAQ v3 uses a two-step process: first get sensors, then measurements

    Example:
        >>> from datetime import datetime
        >>> data = fetch_openaq_data(
        ...     sites=["2178"],  # London Marylebone Road
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31)
        ... )
    """
    import logging

    logger = logging.getLogger(__name__)

    all_measurements = []

    for location_id in sites:
        location_id_int = int(location_id)

        # Step 1: Get all sensors for this location
        logger.info(f"Fetching sensors for OpenAQ location {location_id}...")
        sensors = _get_sensors_for_location(location_id_int)

        if not sensors:
            warning(f"No sensors found for OpenAQ location {location_id}")
            continue

        logger.info(f"Found {len(sensors)} sensors for location {location_id}")

        # Step 2: Fetch measurements for each sensor
        for sensor in sensors:
            sensor_id = sensor["id"]
            parameter_name = sensor.get("parameter", {}).get("name", "unknown")

            logger.debug(
                f"Fetching data for sensor {sensor_id} (parameter: {parameter_name})"
            )

            # Parameters for OpenAQ API v3 sensor measurements endpoint
            params = {
                "datetime_from": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "datetime_to": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

            try:
                # Fetch all pages for this sensor
                endpoint = f"sensors/{sensor_id}/hours"  # Use hourly aggregated data
                measurements = list(_paginate_openaq(endpoint, params))

                logger.debug(
                    f"Sensor {sensor_id}: fetched {len(measurements)} measurements"
                )

                if measurements:
                    # Extract only needed fields to avoid nested object issues
                    for m in measurements:
                        # Skip measurements with no value
                        if m.get("value") is None:
                            continue

                        # Extract the essential fields we need
                        clean_measurement = {
                            "locations_id": location_id_int,
                            "value": m.get("value"),
                            "parameter": sensor.get("parameter", {}),
                            "period": m.get("period", {}),
                        }
                        all_measurements.append(clean_measurement)

            except Exception as e:
                warning(f"Failed to fetch data for sensor {sensor_id}: {e}")
                import traceback

                logger.debug(f"Full traceback: {traceback.format_exc()}")
                continue

    if not all_measurements:
        # Return empty DataFrame with correct schema
        logger.warning(
            f"No measurements found for any location. Total sites tried: {len(sites)}"
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

    # Convert to DataFrame and normalize
    logger.info(f"Total measurements collected: {len(all_measurements)}")

    # Debug: show structure of first measurement
    if all_measurements:
        logger.debug(f"Sample measurement keys: {all_measurements[0].keys()}")
        logger.debug(f"Sample locations_id: {all_measurements[0].get('locations_id')}")
        logger.debug(f"Sample value: {all_measurements[0].get('value')}")
        logger.debug(
            f"Sample parameter type: {type(all_measurements[0].get('parameter'))}"
        )
        logger.debug(f"Sample parameter: {all_measurements[0].get('parameter')}")
        logger.debug(f"Sample period type: {type(all_measurements[0].get('period'))}")
        logger.debug(
            f"Sample period keys: {all_measurements[0].get('period', {}).keys() if isinstance(all_measurements[0].get('period'), dict) else 'NOT A DICT'}"
        )

    df = pd.DataFrame(all_measurements)
    logger.debug(f"Raw DataFrame columns: {df.columns.tolist()}")
    logger.debug(f"Raw DataFrame shape: {df.shape}")

    # Debug: show data types
    logger.debug(f"DataFrame dtypes:\n{df.dtypes}")

    # Debug: Check for any list columns
    logger.debug(f"Type of df.columns: {type(df.columns)}")
    logger.debug(f"df.columns as list: {list(df.columns)}")

    for col in df.columns:
        logger.debug(f"Examining column: {col} (type: {type(col)})")
        sample_val = df[col].iloc[0] if len(df) > 0 else None
        logger.debug(
            f"Column '{col}' sample type: {type(sample_val)}, value: {str(sample_val)[:100]}"
        )

    try:
        # Apply normalization pipeline
        normalizer = create_openaq_normalizer()
        normalized = normalizer(df)
        logger.info(f"Normalized DataFrame shape: {normalized.shape}")
        return normalized
    except Exception as e:
        logger.error(f"Error during normalization: {e}")
        import traceback

        logger.error(f"Full traceback: {traceback.format_exc()}")
        # Show problematic data
        if not df.empty:
            logger.error(f"DataFrame columns: {df.columns.tolist()}")
            logger.error(f"DataFrame shape: {df.shape}")
            logger.error(f"Column types: {[(col, type(col)) for col in df.columns]}")
            try:
                logger.debug(f"First row:\n{df.iloc[0]}")
                logger.debug(f"First row dtypes:\n{df.iloc[0].apply(type)}")
            except Exception as e2:
                logger.error(f"Could not display first row: {e2}")
        raise


# ============================================================================
# SCHEMA NORMALIZATION
# ============================================================================


def create_openaq_normalizer():
    """
    Create normalization pipeline for OpenAQ data.

    Transforms OpenAQ's native schema into Aeolus standard schema.

    Returns:
        Normaliser: Composed transformation pipeline
    """

    def extract_fields(df: pd.DataFrame) -> pd.DataFrame:
        """Extract nested fields from OpenAQ response."""
        import logging

        logger = logging.getLogger(__name__)

        # Extract location ID
        df["site_code"] = df["locations_id"].astype(str)

        # Extract timestamp from period.datetimeTo.utc
        def extract_timestamp(period):
            if not isinstance(period, dict):
                return None
            datetime_to = period.get("datetimeTo")
            if not isinstance(datetime_to, dict):
                return None
            return datetime_to.get("utc")

        df["date_time"] = df["period"].apply(extract_timestamp)

        # Extract units from parameter.units BEFORE converting parameter to string
        def extract_units(param):
            if isinstance(param, dict):
                return param.get("units", "")
            return ""

        df["units"] = df["parameter"].apply(extract_units)

        # Extract parameter name from parameter.name (converts to string)
        def extract_param_name(param):
            if isinstance(param, dict):
                return param.get("name", "unknown")
            return str(param)

        df["parameter"] = df["parameter"].apply(extract_param_name)

        return df

    def standardize_parameter(df: pd.DataFrame) -> pd.DataFrame:
        """Standardize parameter names to Aeolus conventions."""
        # Ensure parameter is string
        df["parameter"] = df["parameter"].astype(str)

        # Map to standard names (parameter is already a string from extract_fields)
        df["measurand"] = df["parameter"].str.lower().map(PARAMETER_MAP)

        # If parameter not in map, use uppercase version
        mask = df["measurand"].isna()
        df.loc[mask, "measurand"] = df.loc[mask, "parameter"].str.upper()

        return df

    def add_quality_flag(df: pd.DataFrame) -> pd.DataFrame:
        """Extract data quality information."""
        # OpenAQ v3 hourly data doesn't have isValid, use a default
        # Could check flagInfo.hasFlags in the future
        df["ratification"] = "Unvalidated"
        return df

    def clean_units(df: pd.DataFrame) -> pd.DataFrame:
        """Standardize units format."""
        # OpenAQ uses µg/m³, we use ug/m3 for ASCII compatibility
        unit_map = {
            "µg/m³": "ug/m3",
            "μg/m³": "ug/m3",
            "micrograms/m3": "ug/m3",
            "ppm": "ppm",
            "ppb": "ppb",
        }

        df["units"] = df["units"].replace(unit_map)
        return df

    def drop_complex_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Drop any columns with complex nested objects before final selection."""
        import logging

        logger = logging.getLogger(__name__)

        # Keep only simple columns
        columns_to_keep = [
            "site_code",
            "date_time",
            "measurand",
            "value",
            "units",
            "parameter",
            "locations_id",
            "ratification",
            "source_network",
            "created_at",
        ]

        # Only keep columns that exist and are in our whitelist
        keep_cols = [col for col in df.columns if col in columns_to_keep]
        logger.debug(f"Columns before drop: {df.columns.tolist()}")
        logger.debug(f"Keeping columns: {keep_cols}")

        return df[keep_cols]

    # Compose the full pipeline
    return compose(
        extract_fields,
        standardize_parameter,
        add_quality_flag,
        clean_units,
        lambda df: df.assign(
            date_time=pd.to_datetime(df["date_time"], errors="coerce")
        ),
        lambda df: df.dropna(
            subset=["date_time", "value", "measurand"]
        ),  # Drop rows with missing essential data
        add_column("source_network", "OpenAQ"),
        add_column("created_at", datetime.now()),  # Use static value, not lambda
        drop_complex_columns,  # Drop any remaining complex columns
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


# ============================================================================
# METADATA FETCHER (Basic Implementation)
# ============================================================================


def fetch_openaq_metadata(**filters) -> pd.DataFrame:
    """
    Fetch site metadata from OpenAQ.

    This is a basic implementation. For now, returns empty DataFrame.
    Use https://openaq.org/ to find location IDs.

    Future enhancement: Implement full search functionality.

    Returns:
        pd.DataFrame: Empty DataFrame (for now)
    """
    # TODO: Implement when adding search functionality
    return pd.DataFrame()


# ============================================================================
# SOURCE REGISTRATION
# ============================================================================

register_source(
    "OPENAQ",
    {
        "type": "portal",
        "name": "OpenAQ",
        "search": fetch_openaq_metadata,  # Portal search function
        "fetch_metadata": fetch_openaq_metadata,  # Keep for backward compatibility
        "fetch_data": fetch_openaq_data,
        "normalise": create_openaq_normalizer(),
        "requires_api_key": True,  # OpenAQ v3 API requires authentication
    },
)
