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
Portals API.

This module provides functions for interacting with global data portals that
aggregate air quality data from multiple sources (OpenAQ, PurpleAir, etc.).

Portals are unbounded platforms with potentially millions of locations globally,
requiring search/discovery patterns rather than complete listing.
"""

from datetime import datetime

import pandas as pd

from ..registry import get_source


def find_sites(portal: str, **filters) -> pd.DataFrame:
    """
    Search for monitoring locations in a portal.

    Portals are global data platforms aggregating from multiple sources with
    potentially millions of locations. They require filters to narrow searches.

    Args:
        portal: Portal name ("OpenAQ", etc.)
        **filters: Portal-specific search filters (REQUIRED)
            OpenAQ examples:
                - country="GB" - Filter by country code
                - bbox=(min_lat, min_lon, max_lat, max_lon) - Bounding box
                - city="London" - City name
                - etc.

    Returns:
        DataFrame with location metadata including:
            - location_id: Unique location identifier (use for download)
            - location_name: Human-readable name
            - latitude: Location latitude
            - longitude: Location longitude
            - source_network: Original data source

    Raises:
        ValueError: If portal is unknown, not a portal type, or no filters provided

    Examples:
        >>> # Find OpenAQ locations in UK
        >>> locations = aeolus.portals.find_sites("OpenAQ", country="GB")
        >>>
        >>> # Find locations in bounding box
        >>> locations = aeolus.portals.find_sites(
        ...     "OpenAQ",
        ...     bbox=(51.28, -0.51, 51.69, 0.34)
        ... )
        >>>
        >>> # Extract location IDs for download
        >>> location_ids = locations["location_id"].tolist()
    """
    source_spec = get_source(portal)

    if not source_spec:
        raise ValueError(f"Unknown portal: {portal}")

    # Verify it's a portal
    source_type = source_spec.get("type", "portal")
    if source_type != "portal":
        raise ValueError(
            f"{portal} is a {source_type}, not a portal.\n"
            f"Use aeolus.networks.get_metadata() for networks."
        )

    # Portals require filters
    if not filters:
        raise ValueError(
            f"{portal} requires search filters.\n\n"
            f"Examples:\n"
            f"  aeolus.portals.find_sites('{portal}', country='GB')\n"
            f"  aeolus.portals.find_sites('{portal}', bbox=(min_lat, min_lon, max_lat, max_lon))\n\n"
            f"See documentation for available filters."
        )

    # Get search function
    search_func = source_spec.get("search") or source_spec.get("fetch_metadata")
    if not search_func:
        raise ValueError(f"Portal {portal} does not support location search")

    return search_func(**filters)


def download(
    portal: str,
    location_ids: list[str],
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    """
    Download air quality data from a portal.

    Args:
        portal: Portal name ("OpenAQ", etc.)
        location_ids: List of location IDs (obtained from find_sites())
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        DataFrame with standardized schema:
            - site_code: Location identifier
            - date_time: Measurement timestamp
            - measurand: Pollutant measured (e.g., "NO2", "PM2.5")
            - value: Measured value
            - units: Units of measurement
            - source_network: Original data source
            - ratification: Data quality flag
            - created_at: When record was fetched

    Raises:
        ValueError: If portal is unknown or not a portal type

    Examples:
        >>> from datetime import datetime
        >>>
        >>> # Step 1: Find locations
        >>> locations = aeolus.portals.find_sites("OpenAQ", country="GB")
        >>> location_ids = locations["location_id"].head(5).tolist()
        >>>
        >>> # Step 2: Download data
        >>> data = aeolus.portals.download(
        ...     "OpenAQ",
        ...     location_ids,
        ...     datetime(2024, 1, 1),
        ...     datetime(2024, 1, 31)
        ... )
    """
    source_spec = get_source(portal)

    if not source_spec:
        raise ValueError(f"Unknown portal: {portal}")

    # Verify it's a portal
    source_type = source_spec.get("type", "portal")
    if source_type != "portal":
        raise ValueError(
            f"{portal} is a {source_type}, not a portal.\n"
            f"Use aeolus.networks.download() for networks."
        )

    # Get data fetcher
    fetcher = source_spec.get("fetch_data")
    if not fetcher:
        raise ValueError(f"Portal {portal} does not support data downloading")

    return fetcher(location_ids, start_date, end_date)


def list_portals() -> list[str]:
    """
    List all available portals.

    Returns:
        List of portal names

    Examples:
        >>> portals = aeolus.portals.list_portals()
        >>> print(portals)
        ['OpenAQ']
    """
    from ..registry import SOURCES

    return [name for name, spec in SOURCES.items() if spec.get("type") == "portal"]
