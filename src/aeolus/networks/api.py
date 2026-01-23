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
Networks API.

This module provides functions for interacting with discrete monitoring networks
operated by organizations (AURN, SAQN, Breathe London, etc.).

Networks are bounded entities with finite numbers of monitoring sites that can
be listed completely.
"""

from datetime import datetime

import pandas as pd

from ..registry import get_source


def get_metadata(network: str, **filters) -> pd.DataFrame:
    """
    Get monitoring site metadata for a network.

    Networks are discrete monitoring networks operated by organizations with
    finite numbers of sites that can be listed completely.

    Args:
        network: Network name ("AURN", "SAQN", "BREATHE_LONDON", etc.)
        **filters: Optional network-specific filters

    Returns:
        DataFrame with site metadata including:
            - site_code: Unique site identifier
            - site_name: Human-readable site name
            - latitude: Site latitude
            - longitude: Site longitude
            - source_network: Network name

    Raises:
        ValueError: If network is unknown or not a network type

    Examples:
        >>> # Get all AURN sites
        >>> sites = aeolus.networks.get_metadata("AURN")
        >>>
        >>> # Get Breathe London sites
        >>> sites = aeolus.networks.get_metadata("BREATHE_LONDON")
        >>>
        >>> # Some networks support filters
        >>> sites = aeolus.networks.get_metadata("BREATHE_LONDON", borough="Camden")
    """
    source_spec = get_source(network)

    if not source_spec:
        raise ValueError(f"Unknown network: {network}")

    # Verify it's a network
    source_type = source_spec.get("type", "network")
    if source_type != "network":
        raise ValueError(
            f"{network} is a {source_type}, not a network.\n"
            f"Use aeolus.portals.find_sites() for portals."
        )

    # Get metadata fetcher
    fetcher = source_spec.get("fetch_metadata")
    if not fetcher:
        raise ValueError(f"Network {network} does not support metadata fetching")

    return fetcher(**filters)


def download(
    network: str,
    sites: list[str],
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    """
    Download air quality data from a network.

    Args:
        network: Network name ("AURN", "SAQN", "BREATHE_LONDON", etc.)
        sites: List of site codes to download
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        DataFrame with standardized schema:
            - site_code: Site identifier
            - date_time: Measurement timestamp
            - measurand: Pollutant measured (e.g., "NO2", "PM2.5")
            - value: Measured value
            - units: Units of measurement
            - source_network: Network name
            - ratification: Data quality flag
            - created_at: When record was fetched

    Raises:
        ValueError: If network is unknown or not a network type

    Examples:
        >>> from datetime import datetime
        >>> data = aeolus.networks.download(
        ...     "AURN",
        ...     ["MY1", "MY2"],
        ...     datetime(2024, 1, 1),
        ...     datetime(2024, 1, 31)
        ... )
    """
    source_spec = get_source(network)

    if not source_spec:
        raise ValueError(f"Unknown network: {network}")

    # Verify it's a network
    source_type = source_spec.get("type", "network")
    if source_type != "network":
        raise ValueError(
            f"{network} is a {source_type}, not a network.\n"
            f"Use aeolus.portals.download() for portals."
        )

    # Get data fetcher
    fetcher = source_spec.get("fetch_data")
    if not fetcher:
        raise ValueError(f"Network {network} does not support data downloading")

    return fetcher(sites, start_date, end_date)


def list_networks() -> list[str]:
    """
    List all available networks.

    Returns:
        List of network names

    Examples:
        >>> networks = aeolus.networks.list_networks()
        >>> print(networks)
        ['AURN', 'SAQN', 'WAQN', 'NI', 'BREATHE_LONDON', ...]
    """
    from ..registry import SOURCES

    return [name for name, spec in SOURCES.items() if spec.get("type") == "network"]
