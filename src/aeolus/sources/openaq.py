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
OpenAQ Data Source.

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
OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY")  # Optional - for higher rate limits

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

    # API key is required for OpenAQ v3
    if not OPENAQ_API_KEY:
        raise ValueError(
            "OpenAQ API key required. Set OPENAQ_API_KEY in .env file. "
            "Get free key at: https://openaq.org/"
        )

    headers["X-API-Key"] = OPENAQ_API_KEY

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
    page = 1
    fetched_pages = 0

    while True:
        # Add pagination params
        params_with_page = {**params, "page": page, "limit": 100}

        try:
            data = _call_openaq_api(endpoint, params_with_page)
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
        total_pages = meta.get("found", 0) // 100 + 1

        if page >= total_pages:
            break

        if max_pages and fetched_pages >= max_pages:
            break

        page += 1


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

    Example:
        >>> from datetime import datetime
        >>> data = fetch_openaq_data(
        ...     sites=["2178"],  # London Marylebone Road
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31)
        ... )
    """
    all_measurements = []

    for location_id in sites:
        # Parameters for OpenAQ API v3
        params = {
            "locations_id": int(location_id),  # OpenAQ v3 uses integer IDs
            "date_from": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date_to": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "period_name": "hour",  # Hourly averages (opinionated default)
        }

        try:
            # Fetch all pages for this location
            measurements = list(_paginate_openaq("measurements", params))

            if measurements:
                all_measurements.extend(measurements)
            else:
                warning(f"No data found for OpenAQ location {location_id}")

        except Exception as e:
            warning(f"Failed to fetch data for OpenAQ location {location_id}: {e}")
            continue

    if not all_measurements:
        # Return empty DataFrame with correct schema
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
    df = pd.DataFrame(all_measurements)

    # Apply normalization pipeline
    normalizer = create_openaq_normalizer()
    return normalizer(df)


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
        # Extract location ID
        df["site_code"] = df["locations_id"].astype(str)

        # Extract timestamp (OpenAQ v3 format)
        # period.datetimeFrom.utc is the start of the period
        # period.datetimeTo.utc is the end (which we use as the timestamp)
        df["date_time"] = df["period"].apply(
            lambda x: x.get("datetimeTo", {}).get("utc", None)
            if isinstance(x, dict)
            else None
        )

        # Extract parameter name
        df["parameter"] = df["parameter"].apply(
            lambda x: x.get("name", "unknown") if isinstance(x, dict) else str(x)
        )

        # Extract units
        df["units"] = df["parameter"].apply(
            lambda x: x.get("units", "") if isinstance(x, dict) else ""
        )

        # Handle case where units is nested
        if "units" in df.columns:
            df["units"] = df["units"].fillna("")

        return df

    def standardize_parameter(df: pd.DataFrame) -> pd.DataFrame:
        """Standardize parameter names to Aeolus conventions."""
        df["measurand"] = df["parameter"].str.lower().map(PARAMETER_MAP)

        # If parameter not in map, use uppercase version
        mask = df["measurand"].isna()
        df.loc[mask, "measurand"] = df.loc[mask, "parameter"].str.upper()

        return df

    def add_quality_flag(df: pd.DataFrame) -> pd.DataFrame:
        """Extract data quality information."""
        # OpenAQ v3 has isValid flag
        if "isValid" in df.columns:
            df["ratification"] = df["isValid"].apply(
                lambda x: "Validated" if x else "Unvalidated"
            )
        else:
            df["ratification"] = "Unknown"

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

    # Compose the full pipeline
    return compose(
        extract_fields,
        standardize_parameter,
        add_quality_flag,
        clean_units,
        lambda df: df.assign(date_time=pd.to_datetime(df["date_time"])),
        add_column("source_network", "OpenAQ"),
        add_column("created_at", lambda df: datetime.now()),
        select_columns(
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
        "name": "OpenAQ",
        "fetch_metadata": fetch_openaq_metadata,
        "fetch_data": fetch_openaq_data,
        "normalise": create_openaq_normalizer(),
        "requires_api_key": True,  # OpenAQ v3 API requires authentication
    },
)
