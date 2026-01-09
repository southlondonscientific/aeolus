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
Core type definitions for Aeolus.

This module defines the standard schemas and type aliases used throughout
the package to ensure consistency across data sources.
"""

from datetime import datetime
from typing import Callable, TypeAlias, TypedDict

import pandas as pd


# Standardised record schemas
class SiteRecord(TypedDict, total=False):
    """
    Standard schema for air quality site metadata.

    Required fields:
        site_code: Unique identifier for the site
        site_name: Human-readable name of the site
        source_network: Name of the source network (e.g., "AURN", "Breathe London")

    Optional fields:
        latitude: Site latitude in decimal degrees
        longitude: Site longitude in decimal degrees
        location_type: Type of location (e.g., "Urban Background", "Roadside")
        owner: Organization that owns/operates the site
        sensor_model: Model of sensor used at the site
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """
    # Required fields
    site_code: str
    site_name: str
    source_network: str

    # Optional fields
    latitude: float | None
    longitude: float | None
    location_type: str | None
    owner: str | None
    sensor_model: str | None
    created_at: datetime
    updated_at: datetime


class DataRecord(TypedDict, total=False):
    """
    Standard schema for air quality measurement data.

    Required fields:
        site_code: Unique identifier for the site
        date_time: Timestamp of the measurement
        measurand: Pollutant or parameter measured (e.g., "NO2", "PM2.5")
        value: Measured value
        units: Units of measurement (e.g., "ug/m3", "ppb")
        source_network: Name of the source network

    Optional fields:
        ratification: Ratification status (e.g., "Ratified", "Provisional", "None")
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """
    # Required fields
    site_code: str
    date_time: datetime
    measurand: str
    value: float | None
    units: str
    source_network: str

    # Optional fields
    ratification: str
    created_at: datetime
    updated_at: datetime


# Function type aliases - these define the "interface" for data sources
MetadataFetcher: TypeAlias = Callable[..., pd.DataFrame]
"""
A function that fetches site metadata from a data source.

Args:
    **filters: Source-specific filters (e.g., site_code, borough, latitude/longitude)

Returns:
    pd.DataFrame: DataFrame conforming to SiteRecord schema
"""

DataFetcher: TypeAlias = Callable[[list[str], datetime, datetime], pd.DataFrame]
"""
A function that fetches air quality data from a data source.

Args:
    sites: List of site codes to fetch data for
    start_date: Start of date range
    end_date: End of date range

Returns:
    pd.DataFrame: DataFrame conforming to DataRecord schema
"""

Normaliser: TypeAlias = Callable[[pd.DataFrame], pd.DataFrame]
"""
A function that normalises raw data into the standard schema.

Args:
    df: Raw DataFrame from a data source

Returns:
    pd.DataFrame: Normalised DataFrame conforming to DataRecord or SiteRecord schema
"""

Transformer: TypeAlias = Callable[[pd.DataFrame], pd.DataFrame]
"""
A function that transforms a DataFrame (e.g., renaming columns, adding fields).

Args:
    df: Input DataFrame

Returns:
    pd.DataFrame: Transformed DataFrame
"""


class SourceSpec(TypedDict):
    """
    Specification for a data source.

    A SourceSpec is a bundle of functions that together define how to
    interact with a particular air quality data source.
    """
    name: str
    fetch_metadata: MetadataFetcher
    fetch_data: DataFetcher
    normalise: Normaliser
    requires_api_key: bool


# Standard column names - for reference and validation
SITE_COLUMNS = [
    "site_code",
    "site_name",
    "source_network",
    "latitude",
    "longitude",
    "location_type",
    "owner",
    "sensor_model",
    "created_at",
    "updated_at",
]

DATA_COLUMNS = [
    "site_code",
    "date_time",
    "measurand",
    "value",
    "units",
    "source_network",
    "ratification",
    "created_at",
    "updated_at",
]
