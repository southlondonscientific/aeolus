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
AirQo Data Source.

This module provides data fetchers for AirQo, an air quality monitoring
network focused on African cities. AirQo operates 200+ low-cost sensors
across 16+ cities in Africa, providing PM2.5, PM10, and other pollutant data.

AirQo's mission is to bridge the air quality data gap in Africa, where
monitoring infrastructure is often limited.

API Documentation: https://docs.airqo.net/airqo-rest-api-documentation/
Data Platform: https://airqo.net/
"""

import os
from datetime import datetime, timezone
from logging import getLogger, warning
from typing import Any

logger = getLogger(__name__)

import pandas as pd
import requests

from ..decorators import retry_on_network_error
from ..registry import register_source
from ..transforms import add_column, compose, rename_columns, select_columns

# Configuration
AIRQO_API_BASE = "https://api.airqo.net/api/v2"

# Parameter name standardization
# Maps AirQo parameter names to Aeolus standard names
PARAMETER_MAP = {
    "pm2_5": "PM2.5",
    "pm10": "PM10",
    "no2": "NO2",
    "o3": "O3",
    "so2": "SO2",
    "co": "CO",
}


# ============================================================================
# LOW-LEVEL API FUNCTIONS
# ============================================================================


def _get_api_token() -> str:
    """
    Get AirQo API token from environment.

    Returns:
        str: API token

    Raises:
        ValueError: If token is not configured
    """
    token = os.getenv("AIRQO_API_KEY")
    if not token:
        raise ValueError(
            "AirQo API key required. Set AIRQO_API_KEY in .env file. "
            "Get free token at: https://analytics.airqo.net/ (register, then "
            "go to account settings > API tab to create a client application)"
        )
    return token


@retry_on_network_error
def _call_airqo_api(endpoint: str, params: dict | None = None) -> dict:
    """
    Low-level AirQo API caller with authentication and error handling.

    Args:
        endpoint: API endpoint (e.g., "devices/metadata/sites")
        params: Query parameters (token is added automatically)

    Returns:
        dict: JSON response from API

    Raises:
        requests.HTTPError: If API returns error status
        ValueError: If API token is not configured
    """
    token = _get_api_token()

    # Add token to params
    params = params or {}
    params["token"] = token

    headers = {"Accept": "application/json"}
    url = f"{AIRQO_API_BASE}/{endpoint}"

    response = requests.get(url, params=params, headers=headers, timeout=60)

    # Handle common errors
    if response.status_code == 401:
        raise ValueError(
            "AirQo API authentication failed. Check your AIRQO_API_KEY. "
            "You may need to regenerate your token at https://analytics.airqo.net/"
        )

    if response.status_code == 429:
        raise requests.HTTPError(
            "AirQo rate limit exceeded. Try requesting less data or wait before retrying."
        )

    response.raise_for_status()
    return response.json()


# ============================================================================
# METADATA FETCHER
# ============================================================================


def fetch_airqo_metadata(**filters) -> pd.DataFrame:
    """
    Fetch site metadata from AirQo API.

    Args:
        **filters: Optional filters for metadata query:
            - grid: Grid ID to filter by
            - country: Country name

    Returns:
        pd.DataFrame: Site metadata with standardized schema:
            - site_code: Unique site identifier
            - site_name: Human-readable site name
            - latitude: Site latitude
            - longitude: Site longitude
            - city: City name
            - country: Country name
            - source_network: "AirQo"

    Example:
        >>> # Get all sites
        >>> metadata = fetch_airqo_metadata()
        >>>
        >>> # List available grids first
        >>> grids = fetch_airqo_grids()
    """
    try:
        data = _call_airqo_api("devices/metadata/sites")
    except Exception as e:
        warning(f"Failed to fetch AirQo metadata: {e}")
        return pd.DataFrame()

    if not data.get("success") or "sites" not in data:
        warning(
            f"AirQo API returned unexpected response: {data.get('message', 'Unknown error')}"
        )
        return pd.DataFrame()

    sites = data["sites"]

    # If sites endpoint returns empty, try grids/summary as fallback
    # This can happen with some API tokens that have grid-level access
    if not sites:
        logger.info("Sites endpoint empty, trying grids/summary fallback...")
        try:
            grids_data = _call_airqo_api("devices/grids/summary")
            if grids_data.get("success") and grids_data.get("grids"):
                # Extract sites from grids
                all_sites = []
                for grid in grids_data["grids"]:
                    grid_sites = grid.get("sites", [])
                    grid_name = grid.get("name", grid.get("long_name", ""))
                    grid_id = grid.get("_id", "")
                    for site in grid_sites:
                        if isinstance(site, dict):
                            site["grid_name"] = grid_name
                            site["grid_id"] = grid_id
                            all_sites.append(site)
                        elif isinstance(site, str):
                            # Some grids just have site IDs
                            all_sites.append(
                                {
                                    "_id": site,
                                    "grid_name": grid_name,
                                    "grid_id": grid_id,
                                }
                            )
                sites = all_sites
                logger.info(f"Retrieved {len(sites)} sites from grids/summary")
        except Exception as e:
            logger.warning(f"Grids fallback also failed: {e}")

    if not sites:
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(sites)

    if df.empty:
        return df

    # Normalize to standard schema
    normalizer = _create_metadata_normalizer()
    normalized = normalizer(df)

    # Apply filters if provided
    if filters.get("country") and "country" in normalized.columns:
        normalized = normalized[
            normalized["country"].str.lower() == filters["country"].lower()
        ]

    return normalized


def fetch_airqo_grids() -> pd.DataFrame:
    """
    Fetch available grids (geographic regions) from AirQo.

    Grids are AirQo's way of organizing sites by geographic area.
    Use grid IDs to fetch measurements for all sites in a region.

    Returns:
        pd.DataFrame: Grid metadata with columns:
            - grid_id: Unique grid identifier
            - name: Grid name (e.g., "kampala", "nairobi")
            - admin_level: Administrative level
            - visibility: Public/private status

    Example:
        >>> grids = fetch_airqo_grids()
        >>> print(grids[['grid_id', 'name']])
    """
    try:
        data = _call_airqo_api("devices/metadata/grids")
    except Exception as e:
        warning(f"Failed to fetch AirQo grids: {e}")
        return pd.DataFrame()

    if not data.get("success") or "grids" not in data:
        return pd.DataFrame()

    grids = data["grids"]
    if not grids:
        return pd.DataFrame()

    df = pd.DataFrame(grids)

    # Rename _id to grid_id for clarity
    if "_id" in df.columns:
        df = df.rename(columns={"_id": "grid_id"})

    return df


def _create_metadata_normalizer():
    """
    Create normalization pipeline for AirQo metadata.

    Transforms AirQo's native schema into Aeolus standard schema.
    """

    def extract_location(df: pd.DataFrame) -> pd.DataFrame:
        """Extract latitude/longitude from nested structure if needed."""
        # AirQo returns approximate_latitude and approximate_longitude
        if "approximate_latitude" in df.columns:
            df["latitude"] = df["approximate_latitude"]
        if "approximate_longitude" in df.columns:
            df["longitude"] = df["approximate_longitude"]
        return df

    return compose(
        extract_location,
        rename_columns(
            {
                "_id": "site_code",
                "name": "site_name",
                "city": "city",
                "country": "country",
                "region": "region",
                "description": "description",
            }
        ),
        add_column("source_network", "AirQo"),
    )


# ============================================================================
# DATA FETCHER
# ============================================================================


def fetch_airqo_data(
    sites: list[str],
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    """
    Fetch air quality data from AirQo.

    This function downloads data from AirQo's sensor network in Africa.
    Data is automatically normalized to match Aeolus standard schema.

    Args:
        sites: List of AirQo site IDs. Use fetch_airqo_metadata() to find IDs.
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        pd.DataFrame: Air quality data with standardized schema:
            - site_code: AirQo site ID
            - site_name: Human-readable site name
            - date_time: Measurement timestamp
            - measurand: Pollutant measured (e.g., "PM2.5", "PM10")
            - value: Measured value
            - units: Units of measurement (ug/m3)
            - source_network: "AirQo"
            - ratification: Data quality flag
            - created_at: When record was fetched

    Note:
        - AirQo API requires an API key (set AIRQO_API_KEY in .env)
        - Get free token at: https://analytics.airqo.net/
        - Data is primarily PM2.5 and PM10 from low-cost sensors
        - Coverage is focused on African cities

    Example:
        >>> from datetime import datetime
        >>> # First, find available sites
        >>> metadata = fetch_airqo_metadata()
        >>> kampala_sites = metadata[metadata['city'] == 'Kampala']['site_code'].tolist()
        >>>
        >>> # Fetch data for those sites
        >>> data = fetch_airqo_data(
        ...     sites=kampala_sites[:5],  # First 5 sites
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 7)
        ... )
    """
    import logging

    logger = logging.getLogger(__name__)

    all_data = []
    normalizer = create_airqo_normalizer()

    # Format dates for API (YYYY-MM-DD or ISO format)
    start_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
    end_str = end_date.strftime("%Y-%m-%dT23:59:59.000Z")

    for site_id in sites:
        logger.debug(f"Fetching AirQo data for site {site_id}")

        try:
            # Use the historical measurements endpoint for specific site
            endpoint = f"devices/measurements/sites/{site_id}/historical"
            params = {
                "startTime": start_str,
                "endTime": end_str,
            }

            data = _call_airqo_api(endpoint, params)

            if not data.get("success"):
                logger.warning(
                    f"AirQo API error for site {site_id}: {data.get('message', 'Unknown')}"
                )
                continue

            measurements = data.get("measurements", [])
            if not measurements:
                logger.debug(f"No measurements found for site {site_id}")
                continue

            logger.debug(f"Found {len(measurements)} measurements for site {site_id}")

            # Convert to DataFrame and normalize
            df = pd.DataFrame(measurements)
            if not df.empty:
                df = normalizer(df)
                all_data.append(df)

        except Exception as e:
            warning(f"Failed to fetch AirQo data for site {site_id}: {e}")
            continue

    # Combine all site data
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        logger.info(f"Total AirQo measurements fetched: {len(combined_df)}")
        return combined_df
    else:
        return _empty_dataframe()


def fetch_airqo_data_by_grid(
    grid_id: str,
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    """
    Fetch air quality data for all sites in an AirQo grid.

    This is a convenience function that fetches data for all sites
    in a geographic grid at once.

    Args:
        grid_id: AirQo grid ID (use fetch_airqo_grids() to find IDs)
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        pd.DataFrame: Air quality data with standardized schema

    Example:
        >>> # Find available grids
        >>> grids = fetch_airqo_grids()
        >>> print(grids[['grid_id', 'name']])
        >>>
        >>> # Fetch data for Kampala grid
        >>> kampala_grid = grids[grids['name'] == 'kampala']['grid_id'].iloc[0]
        >>> data = fetch_airqo_data_by_grid(
        ...     grid_id=kampala_grid,
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 7)
        ... )
    """
    import logging

    logger = logging.getLogger(__name__)

    # Format dates for API
    start_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
    end_str = end_date.strftime("%Y-%m-%dT23:59:59.000Z")

    try:
        endpoint = f"devices/measurements/grids/{grid_id}/historical"
        params = {
            "startTime": start_str,
            "endTime": end_str,
        }

        data = _call_airqo_api(endpoint, params)

        if not data.get("success"):
            warning(
                f"AirQo API error for grid {grid_id}: {data.get('message', 'Unknown')}"
            )
            return _empty_dataframe()

        measurements = data.get("measurements", [])
        if not measurements:
            logger.info(f"No measurements found for grid {grid_id}")
            return _empty_dataframe()

        logger.info(f"Found {len(measurements)} measurements for grid {grid_id}")

        # Convert to DataFrame and normalize
        df = pd.DataFrame(measurements)
        normalizer = create_airqo_normalizer()
        return normalizer(df)

    except Exception as e:
        warning(f"Failed to fetch AirQo data for grid {grid_id}: {e}")
        return _empty_dataframe()


def _empty_dataframe() -> pd.DataFrame:
    """Return empty DataFrame with correct schema."""
    return pd.DataFrame(
        columns=[
            "site_code",
            "site_name",
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


def create_airqo_normalizer():
    """
    Create normalization pipeline for AirQo data.

    Transforms AirQo's native schema into Aeolus standard schema.
    AirQo returns measurements with PM2.5 and PM10 as separate fields,
    so we need to melt them into a long format.

    Returns:
        Normaliser: Composed transformation pipeline
    """

    def extract_site_info(df: pd.DataFrame) -> pd.DataFrame:
        """Extract site information from nested siteDetails."""
        if "siteDetails" in df.columns:
            # Extract site_code and site_name from nested dict
            df["site_code"] = df["siteDetails"].apply(
                lambda x: x.get("_id", "") if isinstance(x, dict) else ""
            )
            df["site_name"] = df["siteDetails"].apply(
                lambda x: x.get("formatted_name") or x.get("name", "")
                if isinstance(x, dict)
                else ""
            )
            df["city"] = df["siteDetails"].apply(
                lambda x: x.get("city", "") if isinstance(x, dict) else ""
            )
            df["country"] = df["siteDetails"].apply(
                lambda x: x.get("country", "") if isinstance(x, dict) else ""
            )
            df["latitude"] = df["siteDetails"].apply(
                lambda x: x.get("approximate_latitude") if isinstance(x, dict) else None
            )
            df["longitude"] = df["siteDetails"].apply(
                lambda x: x.get("approximate_longitude")
                if isinstance(x, dict)
                else None
            )
        elif "site_id" in df.columns:
            # Fallback if siteDetails not present
            df["site_code"] = df["site_id"].astype(str)
            df["site_name"] = ""

        return df

    def extract_pollutant_values(df: pd.DataFrame) -> pd.DataFrame:
        """Extract PM2.5 and PM10 values from nested structure."""
        # AirQo returns pm2_5 and pm10 as nested objects with 'value' key
        for pollutant in ["pm2_5", "pm10"]:
            if pollutant in df.columns:
                df[f"{pollutant}_value"] = df[pollutant].apply(
                    lambda x: x.get("value") if isinstance(x, dict) else x
                )

        return df

    def melt_pollutants(df: pd.DataFrame) -> pd.DataFrame:
        """Convert wide format (pm2_5, pm10 columns) to long format."""
        # Identify which pollutant value columns exist
        value_cols = [col for col in df.columns if col.endswith("_value")]

        if not value_cols:
            # No pollutant columns found - may already be in long format
            return df

        # Columns to keep as identifiers
        id_cols = [
            "site_code",
            "site_name",
            "time",
            "city",
            "country",
            "latitude",
            "longitude",
            "frequency",
            "aqi_category",
            "aqi_color",
        ]
        id_cols = [col for col in id_cols if col in df.columns]

        # Melt pollutant columns to long format
        melted = df.melt(
            id_vars=id_cols,
            value_vars=value_cols,
            var_name="measurand",
            value_name="value",
        )

        # Clean up measurand names (pm2_5_value -> PM2.5)
        melted["measurand"] = melted["measurand"].str.replace("_value", "")
        melted["measurand"] = (
            melted["measurand"].map(PARAMETER_MAP).fillna(melted["measurand"])
        )

        return melted

    def parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
        """Convert timestamp strings to datetime."""
        if "time" in df.columns:
            df["date_time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
        return df

    def add_units(df: pd.DataFrame) -> pd.DataFrame:
        """Add units column - AirQo PM data is in µg/m³."""
        df["units"] = "ug/m3"
        return df

    def add_quality_flag(df: pd.DataFrame) -> pd.DataFrame:
        """Add data quality information."""
        # AirQo low-cost sensor data is not officially ratified
        df["ratification"] = "Indicative"
        return df

    def filter_invalid_rows(df: pd.DataFrame) -> pd.DataFrame:
        """Filter out rows with invalid or missing essential data."""
        # Drop rows with null values in essential columns
        essential_cols = ["date_time", "value", "measurand"]
        for col in essential_cols:
            if col in df.columns:
                df = df.dropna(subset=[col])

        # Filter out zero/negative values (invalid readings)
        if "value" in df.columns:
            df = df[df["value"] > 0]

        return df

    # Compose the full pipeline
    return compose(
        extract_site_info,
        extract_pollutant_values,
        melt_pollutants,
        parse_timestamps,
        add_units,
        add_quality_flag,
        filter_invalid_rows,
        add_column("source_network", "AirQo"),
        add_column("created_at", datetime.now(timezone.utc)),
        select_columns(
            "site_code",
            "site_name",
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
# SOURCE REGISTRATION
# ============================================================================

register_source(
    "AIRQO",
    {
        "type": "network",
        "name": "AirQo",
        "fetch_metadata": fetch_airqo_metadata,
        "fetch_data": fetch_airqo_data,
        "normalise": create_airqo_normalizer(),
        "requires_api_key": True,
    },
)
