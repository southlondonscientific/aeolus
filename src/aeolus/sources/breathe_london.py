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
Breathe London Data Source.

This module provides data fetchers for Breathe London, a network of low-cost
air quality sensors deployed across London by the Environmental Research Group
at Imperial College London.

Breathe London provides high-resolution air quality data from hundreds of
sensors across London, measuring NO2, PM2.5, PM10, and other pollutants.

API Documentation: https://www.breathelondon.org/developers
Data License: Open Government Licence v3.0
"""

import os
from datetime import datetime
from logging import warning
from typing import Any

import pandas as pd
import requests

from ..decorators import retry_on_network_error
from ..registry import register_source
from ..transforms import add_column, compose, rename_columns, select_columns

# Configuration
BREATHE_LONDON_API_BASE = "https://breathe-london-7x54d7qf.ew.gateway.dev"

# Species/parameter name standardization
# Maps Breathe London species names to Aeolus standard names
SPECIES_MAP = {
    "NO2": "NO2",
    "PM2.5": "PM2.5",
    "PM10": "PM10",
    "NO": "NO",
    "O3": "O3",
    "CO": "CO",
}


# ============================================================================
# LOW-LEVEL API FUNCTIONS
# ============================================================================


@retry_on_network_error
def _call_breathe_london_api(endpoint: str, params: dict) -> dict:
    """
    Low-level Breathe London API caller with authentication and error handling.

    Args:
        endpoint: API endpoint (e.g., "ListSensors", "SensorData")
        params: Query parameters

    Returns:
        dict: JSON response from API

    Raises:
        requests.HTTPError: If API returns error status
        ValueError: If API key is not configured
    """
    # API key is required - read at call time for testability
    api_key = os.getenv("BL_API_KEY")
    if not api_key:
        raise ValueError(
            "Breathe London API key required. Set BL_API_KEY in .env file. "
            "Get free key at: https://www.breathelondon.org/developers"
        )

    headers = {"X-API-KEY": api_key, "Accept": "application/json"}

    url = f"{BREATHE_LONDON_API_BASE}/{endpoint}"

    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()

    return response.json()


# ============================================================================
# METADATA FETCHER
# ============================================================================


def fetch_breathe_london_metadata(**filters) -> pd.DataFrame:
    """
    Fetch site metadata from Breathe London API.

    Args:
        **filters: Optional filters for metadata query:
            - site: Site code
            - borough: Borough name
            - species: Pollutant species
            - sponsor: Site sponsor
            - facility: Facility type
            - latitude: Latitude (requires longitude and radius_km)
            - longitude: Longitude (requires latitude and radius_km)
            - radius_km: Search radius in km

    Returns:
        pd.DataFrame: Site metadata with standardized schema:
            - site_code: Unique site identifier
            - site_name: Human-readable site name
            - latitude: Site latitude
            - longitude: Site longitude
            - source_network: "Breathe London"

    Example:
        >>> # Get all sensors
        >>> metadata = fetch_breathe_london_metadata()
        >>>
        >>> # Get sensors in a specific borough
        >>> metadata = fetch_breathe_london_metadata(borough="Camden")
        >>>
        >>> # Get NO2 sensors within 5km of a point
        >>> metadata = fetch_breathe_london_metadata(
        ...     species="NO2",
        ...     latitude=51.5074,
        ...     longitude=-0.1278,
        ...     radius_km=5
        ... )
    """
    # Build query parameters from filters
    params = {}
    for key, value in filters.items():
        if value is not None:
            params[key] = value

    try:
        data = _call_breathe_london_api("ListSensors", params)
    except Exception as e:
        warning(f"Failed to fetch Breathe London metadata: {e}")
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(data)

    if df.empty:
        return df

    # Normalize column names
    normalizer = _create_metadata_normalizer()
    return normalizer(df)


def _create_metadata_normalizer():
    """
    Create normalization pipeline for Breathe London metadata.

    Transforms Breathe London's native schema into Aeolus standard schema.
    """
    return compose(
        rename_columns(
            {
                "SiteCode": "site_code",
                "SiteName": "site_name",
                "Latitude": "latitude",
                "Longitude": "longitude",
            }
        ),
        add_column("source_network", "Breathe London"),
        # Keep all original columns but ensure standard ones exist
        lambda df: df
        if all(col in df.columns for col in ["site_code", "site_name"])
        else df,
    )


# ============================================================================
# DATA FETCHER
# ============================================================================


def fetch_breathe_london_data(
    sites: list[str], start_date: datetime, end_date: datetime
) -> pd.DataFrame:
    """
    Fetch air quality data from Breathe London.

    This function downloads data from Breathe London's sensor network.
    Data is automatically normalized to match Aeolus standard schema.

    Args:
        sites: List of Breathe London site codes
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        pd.DataFrame: Air quality data with standardized schema:
            - site_code: Breathe London site code
            - date_time: Measurement timestamp
            - measurand: Pollutant measured (e.g., "NO2", "PM2.5")
            - value: Measured value
            - units: Units of measurement
            - source_network: "Breathe London"
            - ratification: Data quality flag
            - created_at: When record was fetched

    Note:
        - Breathe London API requires an API key (set BL_API_KEY in .env)
        - Get free API key at: https://www.breathelondon.org/developers
        - Returns hourly averages
        - Multiple sites are queried individually and results are combined
        - The API does not support multi-site queries in a single call

    Example:
        >>> from datetime import datetime
        >>> data = fetch_breathe_london_data(
        ...     sites=["BL0001"],
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31)
        ... )
    """
    # Note: API does not support multi-site queries in a single call
    # We need to query each site individually and combine results

    all_data = []
    normalizer = create_breathe_london_normalizer()

    for site in sites:
        # Build query parameters for this site
        # Note: API uses camelCase for parameters (SiteCode, startTime, endTime)
        params = {
            "SiteCode": site,  # Query one site at a time
            "startTime": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endTime": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        try:
            data = _call_breathe_london_api("SensorData", params)

            if data:
                # Convert to DataFrame and normalize
                df = pd.DataFrame(data)
                if not df.empty:
                    df = normalizer(df)
                    all_data.append(df)

        except Exception as e:
            warning(f"Failed to fetch Breathe London data for site {site}: {e}")
            # Continue with other sites even if one fails
            continue

    # Combine all site data
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        return combined_df
    else:
        return _empty_dataframe()


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
# SCHEMA NORMALIZATION
# ============================================================================


def create_breathe_london_normalizer():
    """
    Create normalization pipeline for Breathe London data.

    Transforms Breathe London's native schema into Aeolus standard schema.

    Returns:
        Normaliser: Composed transformation pipeline
    """

    def extract_and_rename_fields(df: pd.DataFrame) -> pd.DataFrame:
        """Extract and rename fields to standard names."""
        # Rename columns - API returns different field names
        column_map = {
            "SiteCode": "site_code",
            "DateTime": "date_time",  # API returns DateTime, not ReadingDateTime
            "Species": "measurand",
            "ScaledValue": "value",  # Use ScaledValue as the primary value
            "Units": "units",
        }

        # Only rename columns that exist
        rename_map = {k: v for k, v in column_map.items() if k in df.columns}
        df = df.rename(columns=rename_map)

        return df

    def standardize_species(df: pd.DataFrame) -> pd.DataFrame:
        """Standardize species names to Aeolus conventions."""
        if "measurand" in df.columns:
            # Map known species
            df["measurand"] = df["measurand"].map(SPECIES_MAP).fillna(df["measurand"])

        return df

    def parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
        """Convert timestamp strings to datetime."""
        if "date_time" in df.columns:
            df["date_time"] = pd.to_datetime(df["date_time"], errors="coerce")

        return df

    def add_quality_flag(df: pd.DataFrame) -> pd.DataFrame:
        """Add data quality information."""
        # Use RatificationStatus from API if available, otherwise mark as Unvalidated
        if "RatificationStatus" in df.columns:
            df["ratification"] = df["RatificationStatus"].fillna("Unvalidated")
            df = df.drop(columns=["RatificationStatus"])
        else:
            df["ratification"] = "Unvalidated"
        return df

    def standardize_units(df: pd.DataFrame) -> pd.DataFrame:
        """Standardize units format."""
        if "units" not in df.columns:
            df["units"] = ""
            return df

        # Convert API units format to ASCII
        # API returns units like "ug.m-3" which we convert to "ug/m3"
        unit_map = {
            "ug.m-3": "ug/m3",
            "µg/m³": "ug/m3",
            "μg/m³": "ug/m3",
            "ug/m³": "ug/m3",
            "ppm": "ppm",
            "ppb": "ppb",
        }

        df["units"] = df["units"].replace(unit_map).fillna("")
        return df

    def filter_invalid_rows(df: pd.DataFrame) -> pd.DataFrame:
        """Filter out rows with invalid or missing essential data."""
        # Drop rows with null values in essential columns
        essential_cols = ["date_time", "value", "measurand"]
        for col in essential_cols:
            if col in df.columns:
                df = df.dropna(subset=[col])

        return df

    # Compose the full pipeline
    return compose(
        extract_and_rename_fields,
        parse_timestamps,
        standardize_species,
        standardize_units,
        add_quality_flag,
        filter_invalid_rows,
        add_column("source_network", "Breathe London"),
        add_column("created_at", datetime.now()),
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
# SOURCE REGISTRATION
# ============================================================================

register_source(
    "BREATHE_LONDON",
    {
        "type": "network",
        "name": "Breathe London",
        "fetch_metadata": fetch_breathe_london_metadata,
        "fetch_data": fetch_breathe_london_data,
        "normalise": create_breathe_london_normalizer(),
        "requires_api_key": True,
    },
)
