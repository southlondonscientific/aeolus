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
OpenAQ data source using the official OpenAQ Python SDK.

This module provides data fetchers for OpenAQ, a global air quality data
platform aggregating data from over 100 countries.

SDK Documentation: https://python.openaq.org/
Data Platform: https://openaq.org/
"""

import logging
import os
from datetime import datetime

import pandas as pd
from openaq import OpenAQ

from ..registry import register_source
from ..transforms import add_column, compose, select_columns

logger = logging.getLogger(__name__)

# Parameter name standardization
# Maps OpenAQ parameter names to Aeolus standard names
PARAMETER_MAP = {
    "no2": "NO2",
    "pm25": "PM2.5",
    "pm10": "PM10",
    "o3": "O3",
    "so2": "SO2",
    "co": "CO",
    "bc": "BC",
    "no": "NO",
    "nox": "NOX",
    "pm1": "PM1",
    "ch4": "CH4",
}


# ============================================================================
# CLIENT MANAGEMENT
# ============================================================================


_client = None


def _get_client() -> OpenAQ:
    """
    Get an OpenAQ client instance (reuses existing client).

    Supports both OPENAQ_API_KEY (Aeolus convention) and OPENAQ-API-KEY (SDK convention).

    Returns:
        OpenAQ: Configured client instance

    Raises:
        ValueError: If no API key is found
    """
    global _client

    # Reuse existing client if available
    if _client is not None:
        return _client

    # Support both env var conventions
    api_key = os.getenv("OPENAQ_API_KEY") or os.getenv("OPENAQ-API-KEY")

    if not api_key:
        raise ValueError(
            "OpenAQ API key required. Set OPENAQ_API_KEY environment variable. "
            "Get a free key at: https://openaq.org/"
        )

    _client = OpenAQ(api_key=api_key)
    return _client


# ============================================================================
# METADATA FETCHER (Search)
# ============================================================================


def fetch_openaq_metadata(**filters) -> pd.DataFrame:
    """
    Search for monitoring locations on OpenAQ.

    Args:
        **filters: Search filters passed to the SDK
            - country: ISO country code (e.g., "GB", "US")
            - bbox: Bounding box tuple (min_lon, min_lat, max_lon, max_lat)
            - coordinates: Tuple of (latitude, longitude) for point search
            - radius: Search radius in meters (use with coordinates)
            - limit: Maximum results (default 100, max 1000)

    Returns:
        pd.DataFrame: Location metadata with columns:
            - site_code: OpenAQ location ID (use for download)
            - site_name: Human-readable name
            - latitude: Location latitude
            - longitude: Location longitude
            - country: Country code
            - parameters: List of available pollutants
            - source_network: Always "OpenAQ"

    Example:
        >>> locations = fetch_openaq_metadata(country="GB")
        >>> locations = fetch_openaq_metadata(bbox=(-0.5, 51.3, 0.3, 51.7))
    """
    if not filters:
        raise ValueError(
            "OpenAQ requires search filters. Examples:\n"
            "  fetch_openaq_metadata(country='GB')\n"
            "  fetch_openaq_metadata(bbox=(-0.5, 51.3, 0.3, 51.7))"
        )

    client = _get_client()

    # Map Aeolus filter names to SDK parameter names
    sdk_params = {}

    if "country" in filters:
        sdk_params["iso"] = filters["country"]

    if "bbox" in filters:
        # SDK requires tuple, but accept list for convenience
        bbox = filters["bbox"]
        sdk_params["bbox"] = tuple(bbox) if isinstance(bbox, list) else bbox

    if "coordinates" in filters:
        sdk_params["coordinates"] = filters["coordinates"]

    if "radius" in filters:
        sdk_params["radius"] = filters["radius"]

    sdk_params["limit"] = filters.get("limit", 100)

    # Call SDK
    response = client.locations.list(**sdk_params)

    # Convert to DataFrame
    if not response.results:
        return pd.DataFrame(
            columns=[
                "site_code",
                "site_name",
                "latitude",
                "longitude",
                "country",
                "parameters",
                "source_network",
            ]
        )

    records = []
    for loc in response.results:
        # Get parameter names from sensors
        parameters = []
        if hasattr(loc, "sensors") and loc.sensors:
            parameters = [s.parameter.name for s in loc.sensors if s.parameter]

        records.append(
            {
                "site_code": str(loc.id),
                "site_name": loc.name,
                "latitude": loc.coordinates.latitude if loc.coordinates else None,
                "longitude": loc.coordinates.longitude if loc.coordinates else None,
                "country": loc.country.code if loc.country else None,
                "parameters": parameters,
                "source_network": "OpenAQ",
            }
        )

    return pd.DataFrame(records)


# ============================================================================
# DATA FETCHER
# ============================================================================


def fetch_openaq_data(
    sites: list[str], start_date: datetime, end_date: datetime
) -> pd.DataFrame:
    """
    Fetch air quality data from OpenAQ.

    Args:
        sites: List of OpenAQ location IDs as strings
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        pd.DataFrame: Air quality data with standardized schema

    Example:
        >>> data = fetch_openaq_data(
        ...     sites=["2178"],
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31)
        ... )
    """
    client = _get_client()
    all_measurements = []

    for location_id in sites:
        location_id_int = int(location_id)
        logger.info(f"Fetching data for OpenAQ location {location_id}...")

        # Step 1: Get sensors for this location
        try:
            sensors_response = client.locations.sensors(location_id_int)
            sensors = sensors_response.results if sensors_response.results else []
        except Exception as e:
            logger.warning(f"Failed to get sensors for location {location_id}: {e}")
            continue

        if not sensors:
            logger.warning(f"No sensors found for location {location_id}")
            continue

        logger.info(f"Found {len(sensors)} sensors for location {location_id}")

        # Step 2: Fetch measurements for each sensor
        for sensor in sensors:
            sensor_id = sensor.id
            param_name = sensor.parameter.name if sensor.parameter else "unknown"

            logger.debug(f"Fetching data for sensor {sensor_id} ({param_name})")

            try:
                measurements = client.measurements.list(
                    sensors_id=sensor_id,
                    datetime_from=start_date,
                    datetime_to=end_date,
                    limit=1000,
                )

                if measurements.results:
                    for m in measurements.results:
                        all_measurements.append(
                            {
                                "location_id": location_id,
                                "sensor_id": sensor_id,
                                "parameter": param_name,
                                "value": m.value,
                                "datetime": m.period.datetime_to.utc
                                if m.period and m.period.datetime_to
                                else None,
                                "units": sensor.parameter.units
                                if sensor.parameter
                                else "",
                            }
                        )

                    logger.debug(
                        f"Sensor {sensor_id}: fetched {len(measurements.results)} measurements"
                    )

            except Exception as e:
                logger.warning(f"Failed to fetch data for sensor {sensor_id}: {e}")
                continue

    if not all_measurements:
        logger.warning("No measurements found for any location")
        return _empty_dataframe()

    # Convert to DataFrame and normalize
    df = pd.DataFrame(all_measurements)
    logger.info(f"Total measurements collected: {len(df)}")

    return _normalize(df)


# ============================================================================
# NORMALIZATION
# ============================================================================


def _empty_dataframe() -> pd.DataFrame:
    """Return empty DataFrame with standard schema."""
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


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize OpenAQ data to Aeolus standard schema."""

    # Rename columns
    df = df.rename(
        columns={
            "location_id": "site_code",
            "datetime": "date_time",
        }
    )

    # Standardize parameter names
    df["measurand"] = df["parameter"].str.lower().map(PARAMETER_MAP)
    mask = df["measurand"].isna()
    df.loc[mask, "measurand"] = df.loc[mask, "parameter"].str.upper()

    # Convert datetime
    df["date_time"] = pd.to_datetime(df["date_time"], errors="coerce")

    # Standardize units
    unit_map = {"µg/m³": "ug/m3", "μg/m³": "ug/m3"}
    df["units"] = df["units"].replace(unit_map)

    # Add standard columns
    df["source_network"] = "OpenAQ"
    df["ratification"] = "Unvalidated"
    df["created_at"] = datetime.now()

    # Drop rows with missing essential data
    df = df.dropna(subset=["date_time", "value", "measurand"])

    # Select final columns
    return df[
        [
            "site_code",
            "date_time",
            "measurand",
            "value",
            "units",
            "source_network",
            "ratification",
            "created_at",
        ]
    ]


# ============================================================================
# SOURCE REGISTRATION
# ============================================================================

register_source(
    "OPENAQ",
    {
        "type": "portal",
        "name": "OpenAQ",
        "search": fetch_openaq_metadata,
        "fetch_metadata": fetch_openaq_metadata,
        "fetch_data": fetch_openaq_data,
        "normalise": lambda df: df,  # Normalization happens in fetch_openaq_data
        "requires_api_key": True,
    },
)
