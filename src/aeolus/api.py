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
Clean, user-friendly public API for Aeolus.

This module provides simple functions for downloading and working with
UK air quality data. It abstracts away the internal registry and source
structure, giving users a straightforward interface.

Basic usage:
    >>> import aeolus
    >>>
    >>> # See what's available
    >>> sources = aeolus.list_sources()
    >>>
    >>> # Get site metadata
    >>> sites = aeolus.get_metadata("AURN")
    >>>
    >>> # Download data
    >>> data = aeolus.download(
    ...     sources=["AURN"],
    ...     sites=["MY1"],
    ...     start_date=datetime(2024, 1, 1),
    ...     end_date=datetime(2024, 1, 31)
    ... )
"""

from datetime import datetime
from typing import Any

import pandas as pd

# Import sources to trigger registration
from . import sources as _sources
from .registry import get_source, source_exists
from .registry import list_sources as _list_sources


def list_sources() -> list[str]:
    """
    List all available data sources.

    Returns:
        list[str]: List of registered source names

    Example:
        >>> sources = aeolus.list_sources()
        >>> print(sources)
        ['AQE', 'AURN', 'LMAM', 'LOCAL', 'NI', 'SAQD', 'SAQN', 'WAQN']
    """
    return _list_sources()


def get_metadata(source: str, **filters) -> pd.DataFrame:
    """
    Get site metadata from a data source.

    Args:
        source: Name of the data source (e.g., "AURN", "SAQN")
        **filters: Source-specific filters (currently not implemented for most sources)

    Returns:
        pd.DataFrame: Site metadata with columns:
            - site_code: Unique site identifier
            - site_name: Human-readable site name
            - latitude: Site latitude (decimal degrees)
            - longitude: Site longitude (decimal degrees)
            - source_network: Name of the source network
            - location_type: Type of location (e.g., "Urban Background")
            - owner: Organization operating the site

    Raises:
        ValueError: If source is not registered

    Example:
        >>> metadata = aeolus.get_metadata("AURN")
        >>> print(f"Found {len(metadata)} sites")
        >>> print(metadata.head())
    """
    source_obj = get_source(source)
    if source_obj is None:
        available = ", ".join(list_sources())
        raise ValueError(f"Source '{source}' not found. Available sources: {available}")

    fetch_metadata = source_obj["fetch_metadata"]
    return fetch_metadata(**filters)


def download(
    sources: list[str] | str,
    sites: list[str],
    start_date: datetime,
    end_date: datetime,
    combine: bool = True,
) -> pd.DataFrame | dict[str, pd.DataFrame]:
    """
    Download air quality data from one or more sources.

    This is the main function for downloading data. It handles multiple sources
    and sites, returning a standardized DataFrame.

    Args:
        sources: Source name(s) to download from (e.g., "AURN" or ["AURN", "SAQN"])
        sites: List of site codes to download (e.g., ["MY1", "BX1"])
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)
        combine: If True, combine all sources into one DataFrame.
                 If False, return dict with source names as keys.

    Returns:
        pd.DataFrame | dict[str, pd.DataFrame]: Air quality data with columns:
            - site_code: Site identifier
            - date_time: Measurement timestamp
            - measurand: Pollutant/parameter measured (e.g., "NO2", "PM2.5")
            - value: Measured value
            - units: Units of measurement (e.g., "ug/m3")
            - source_network: Name of source network
            - ratification: Ratification status
            - created_at: When record was created

    Raises:
        ValueError: If any source is not registered

    Example:
        >>> from datetime import datetime
        >>>
        >>> # Download from single source
        >>> data = aeolus.download(
        ...     sources="AURN",
        ...     sites=["MY1"],
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31)
        ... )
        >>>
        >>> # Download from multiple sources
        >>> data = aeolus.download(
        ...     sources=["AURN", "SAQN"],
        ...     sites=["MY1", "ED3"],
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31)
        ... )
        >>>
        >>> # Get separate DataFrames per source
        >>> data_by_source = aeolus.download(
        ...     sources=["AURN", "SAQN"],
        ...     sites=["MY1", "ED3"],
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31),
        ...     combine=False
        ... )
        >>> print(data_by_source.keys())  # dict_keys(['AURN', 'SAQN'])
    """
    # Normalize sources to list
    if isinstance(sources, str):
        sources = [sources]

    # Validate all sources exist
    for source in sources:
        if not source_exists(source):
            available = ", ".join(list_sources())
            raise ValueError(
                f"Source '{source}' not found. Available sources: {available}"
            )

    # Download from each source
    results = {}
    for source in sources:
        source_obj = get_source(source)
        fetch_data = source_obj["fetch_data"]

        try:
            df = fetch_data(sites, start_date, end_date)
            if not df.empty:
                results[source] = df
        except Exception as e:
            # Log warning but continue with other sources
            import warnings

            warnings.warn(f"Failed to download from {source}: {e}", UserWarning)

    # Return based on combine parameter
    if combine:
        if not results:
            return pd.DataFrame()
        return pd.concat(results.values(), ignore_index=True)
    else:
        return results


def get_source_info(source: str) -> dict[str, Any]:
    """
    Get information about a data source.

    Args:
        source: Name of the data source

    Returns:
        dict: Dictionary with source information:
            - name: Display name of the source
            - requires_api_key: Whether an API key is needed

    Raises:
        ValueError: If source is not registered

    Example:
        >>> info = aeolus.get_source_info("AURN")
        >>> print(info)
        {'name': 'AURN', 'requires_api_key': False}
    """
    source_obj = get_source(source)
    if source_obj is None:
        available = ", ".join(list_sources())
        raise ValueError(f"Source '{source}' not found. Available sources: {available}")

    return {
        "name": source_obj["name"],
        "requires_api_key": source_obj["requires_api_key"],
    }


def download_all_sites(
    source: str,
    start_date: datetime,
    end_date: datetime,
    location_types: list[str] | None = None,
) -> pd.DataFrame:
    """
    Download data for all sites from a source (optionally filtered by location type).

    This is a convenience function that first fetches metadata to get all site codes,
    then downloads data for all of them. Use with caution for large date ranges.

    Args:
        source: Name of the data source
        start_date: Start of date range
        end_date: End of date range
        location_types: Optional list of location types to filter by
                       (e.g., ["Urban Background", "Roadside"])

    Returns:
        pd.DataFrame: Combined data for all sites

    Warning:
        This can result in very large downloads. Consider using smaller date
        ranges or filtering by location_type.

    Example:
        >>> # Download all urban background sites
        >>> data = aeolus.download_all_sites(
        ...     source="AURN",
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 7),
        ...     location_types=["Urban Background"]
        ... )
    """
    # Get all site metadata
    metadata = get_metadata(source)

    # Filter by location type if specified
    if location_types is not None:
        if "location_type" in metadata.columns:
            metadata = metadata[metadata["location_type"].isin(location_types)]
        else:
            import warnings

            warnings.warn(
                f"location_type column not found in {source} metadata. "
                "Downloading all sites.",
                UserWarning,
            )

    # Get list of site codes
    sites = metadata["site_code"].unique().tolist()

    # Download data for all sites
    return download(
        sources=source, sites=sites, start_date=start_date, end_date=end_date
    )


# Convenience function aliases for common operations
def get_sites(source: str, **filters) -> pd.DataFrame:
    """
    Alias for get_metadata(). Get site information from a data source.

    Args:
        source: Name of the data source
        **filters: Source-specific filters

    Returns:
        pd.DataFrame: Site metadata

    Example:
        >>> sites = aeolus.get_sites("AURN")
    """
    return get_metadata(source, **filters)


def fetch(
    sources: list[str] | str,
    sites: list[str],
    start_date: datetime,
    end_date: datetime,
    **kwargs,
) -> pd.DataFrame:
    """
    Alias for download(). Download air quality data.

    Args:
        sources: Source name(s) to download from
        sites: List of site codes
        start_date: Start of date range
        end_date: End of date range
        **kwargs: Additional arguments passed to download()

    Returns:
        pd.DataFrame: Air quality data

    Example:
        >>> data = aeolus.fetch(
        ...     sources="AURN",
        ...     sites=["MY1"],
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31)
        ... )
    """
    return download(sources, sites, start_date, end_date, **kwargs)
