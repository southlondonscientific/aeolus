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
import warnings
from datetime import datetime, timezone
from logging import warning

import pandas as pd
import requests

from ..decorators import retry_on_network_error
from ..registry import register_source
from ..transforms import add_column, compose, rename_columns, select_columns
from ..types import AeolusDataWarning, empty_data_frame, empty_metadata_frame

# Configuration
BREATHE_LONDON_API_BASE = "https://breathe-london-7x54d7qf.ew.gateway.dev"

# Species/parameter name standardization.
#
# Breathe London's SensorData endpoint emits PM2.5 as "PM25" (no dot), plus
# DAQI-style 1-10 index ratings as "NO2Index" / "PM25Index" with units "DAQI"
# alongside the µg/m³ concentration rows. We must:
#
#   - Map "PM25" -> "PM2.5" so the standard schema's PM2.5 measurand is what
#     downstream code actually sees (was a silent silent-wrong-numbers bug:
#     "PM25" leaked through the .fillna fallback unchanged, dropping every
#     PM2.5 row for any consumer mapping on the documented standard name).
#   - Drop the *Index rows entirely. Their values are on a 1-10 categorical
#     scale, not µg/m³ — mixing them into the standard `value` column
#     corrupts any downstream mean/percentile/AQI computation.
#
# The PM2.5 / PM10 / NO / O3 / CO identity entries are kept defensively in
# case the API ever standardises spelling (currently only NO2 and PM25
# concentration rows are observed live, plus the two Index variants).
SPECIES_MAP = {
    "NO2": "NO2",
    "PM25": "PM2.5",
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
    Fetch site metadata from Breathe London.

    The Breathe London ``ListSensors`` endpoint does not accept any query
    parameters — it always returns the full sensor list and rejects any
    filter with ``400 Invalid parameter(s)``.  This function therefore
    fetches the full list and applies the documented filters
    *client-side* on the returned DataFrame.

    Args:
        **filters: Optional client-side filters:
            - site: Match a single ``site_code`` (case-insensitive).
            - borough: Match ``Borough`` (case-insensitive equality).
            - sponsor: Match ``SponsorName`` (case-insensitive equality).
            - facility: Match ``Facility`` (case-insensitive equality).
            - latitude, longitude, radius_km: Circular spatial filter.
              All three are required together.  Adds a ``distance_km``
              column and sorts nearest-first.

    Returns:
        pd.DataFrame: Site metadata with standardised schema:
            - site_code: Unique site identifier
            - site_name: Human-readable site name
            - latitude: Site latitude (numeric)
            - longitude: Site longitude (numeric)
            - source_network: "BREATHE_LONDON"
            Plus all original BL fields (Borough, Facility, SponsorName,
            SiteClassification, etc.) preserved unchanged.

    Example:
        >>> # Get all sensors
        >>> metadata = fetch_breathe_london_metadata()
        >>>
        >>> # Get sensors in a specific borough
        >>> metadata = fetch_breathe_london_metadata(borough="Camden")
        >>>
        >>> # Get sensors within 5km of a point
        >>> metadata = fetch_breathe_london_metadata(
        ...     latitude=51.5074, longitude=-0.1278, radius_km=5,
        ... )
    """
    # ListSensors rejects all query parameters; always call bare and
    # filter the response client-side.
    try:
        data = _call_breathe_london_api("ListSensors", {})
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        warning(f"Failed to fetch Breathe London metadata: {e}")
        warnings.warn(
            f"Failed to fetch Breathe London metadata: {e}",
            AeolusDataWarning,
            stacklevel=2,
        )
        return empty_metadata_frame()

    if not data:
        return empty_metadata_frame()

    df = pd.DataFrame(data)
    if df.empty:
        return empty_metadata_frame()

    df = _create_metadata_normaliser()(df)
    return _apply_metadata_filters(df, filters)


def _apply_metadata_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply client-side filters to normalised BL metadata."""
    if df.empty:
        return df

    site = filters.get("site")
    if site is not None and "site_code" in df.columns:
        df = df[df["site_code"].astype(str).str.casefold() == str(site).casefold()]

    for filter_key, column in (
        ("borough", "Borough"),
        ("sponsor", "SponsorName"),
        ("facility", "Facility"),
    ):
        value = filters.get(filter_key)
        if value is not None and column in df.columns:
            df = df[df[column].astype(str).str.casefold() == str(value).casefold()]

    lat = filters.get("latitude")
    lon = filters.get("longitude")
    radius_km = filters.get("radius_km")
    if lat is not None or lon is not None or radius_km is not None:
        if lat is None or lon is None or radius_km is None:
            raise ValueError(
                "latitude, longitude, and radius_km must all be provided together"
            )
        from ..geo import haversine_distance

        has_coords = df["latitude"].notna() & df["longitude"].notna()
        df = df[has_coords].copy()
        df["distance_km"] = df.apply(
            lambda row: haversine_distance(
                lat, lon, row["latitude"], row["longitude"]
            ),
            axis=1,
        )
        df = df[df["distance_km"] <= radius_km].sort_values("distance_km")

    if "species" in filters and filters["species"] is not None:
        warnings.warn(
            "fetch_breathe_london_metadata: 'species' filter is not supported — "
            "the ListSensors endpoint does not expose per-site measurands. "
            "Filter ignored.",
            AeolusDataWarning,
            stacklevel=2,
        )

    return df.reset_index(drop=True)


def _coerce_lat_lng(df: pd.DataFrame) -> pd.DataFrame:
    """Convert latitude/longitude columns to numeric — BL returns strings."""
    for col in ("latitude", "longitude"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _create_metadata_normaliser():
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
        _coerce_lat_lng,
        add_column("source_network", "BREATHE_LONDON"),
        add_column("measurands", None),
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
    Data is automatically normalised to match Aeolus standard schema.

    Args:
        sites: List of Breathe London site codes
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        pd.DataFrame: Air quality data with standardised schema:
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
    normaliser = create_breathe_london_normaliser()

    from ..progress import track

    for site in track(sites, "Downloading Breathe London"):
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
                # Convert to DataFrame and normalise
                df = pd.DataFrame(data)
                if not df.empty:
                    df = normaliser(df)
                    all_data.append(df)

        except (requests.RequestException, ValueError, KeyError, TypeError) as e:
            warning(f"Failed to fetch Breathe London data for site {site}: {e}")
            # Continue with other sites even if one fails
            continue

    # Combine all site data
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        return combined_df
    else:
        return empty_data_frame()




# ============================================================================
# SCHEMA NORMALIZATION
# ============================================================================


def create_breathe_london_normaliser():
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

    def standardise_species(df: pd.DataFrame) -> pd.DataFrame:
        """Standardise species names to Aeolus conventions and drop rows
        whose species isn't in ``SPECIES_MAP`` (notably ``NO2Index`` and
        ``PM25Index``, which are DAQI 1-10 ratings on a different value
        scale and would otherwise corrupt mean/percentile/AQI calculations
        against the standard µg/m³ value column).
        """
        if "measurand" in df.columns:
            df = df[df["measurand"].isin(SPECIES_MAP)].copy()
            df["measurand"] = df["measurand"].map(SPECIES_MAP)
        return df

    def parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
        """Convert timestamp strings to datetime."""
        if "date_time" in df.columns:
            df["date_time"] = pd.to_datetime(df["date_time"], utc=True, errors="coerce")

        return df

    def add_quality_flag(df: pd.DataFrame) -> pd.DataFrame:
        """Add data quality information."""
        # Use RatificationStatus from API if available, otherwise mark as Indicative
        if "RatificationStatus" in df.columns:
            df["ratification"] = df["RatificationStatus"].fillna("Indicative")
            df = df.drop(columns=["RatificationStatus"])
        else:
            df["ratification"] = "Indicative"
        return df

    def standardise_units(df: pd.DataFrame) -> pd.DataFrame:
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
        standardise_species,
        standardise_units,
        add_quality_flag,
        filter_invalid_rows,
        add_column("source_network", "BREATHE_LONDON"),
        # Lazy callable — evaluated per fetch, not frozen at module-import time.
        add_column("created_at", lambda df: datetime.now(timezone.utc)),
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
        "normalise": create_breathe_london_normaliser(),
        "requires_api_key": True,
        # ListSensors does not expose per-site measurands. Most BL nodes
        # report NO2 and PM2.5; declaring these lets find_sites(measurand=)
        # surface BL sites instead of silently dropping them.
        "default_measurands": ["NO2", "PM2.5"],
    },
)
