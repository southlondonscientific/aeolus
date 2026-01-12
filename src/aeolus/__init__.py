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
Aeolus: Download and standardise UK air quality data.

This package provides a simple interface for downloading air quality data
from multiple UK monitoring networks.

Quick Start:
    >>> import aeolus
    >>> from datetime import datetime
    >>>
    >>> # List available data sources
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

Main Functions:
    - list_sources(): List all available data sources
    - get_metadata(): Get site metadata from a source
    - download(): Download air quality data
    - get_sites(): Alias for get_metadata()
    - fetch(): Alias for download()

Supported Networks:
    - AURN (Automatic Urban and Rural Network)
    - SAQN (Scottish Air Quality Network)
    - WAQN (Wales Air Quality Network)
    - NI (Northern Ireland Air Quality Network)
    - AQE (Air Quality England)
    - LOCAL (Local Monitoring and Management networks)

For more details, see: https://github.com/southlondonscientific/aeolus
"""

__version__ = "0.1.1a"

# Import the clean public API
from .api import (
    download,
    download_all_sites,
    fetch,
    get_metadata,
    get_sites,
    get_source_info,
    list_sources,
)

# Backwards compatibility: import old functions
# These are deprecated but kept to avoid breaking existing code
from .database_operations import (
    add_data_to_database,
    add_sites_to_database,
)
from .database_operations import (
    get_site_metadata as db_get_site_metadata,
)
from .downloader import (
    download_breathe_london_data,
    download_regulatory_data,
    get_breathe_london_metadata,
    get_network_metadata,
    multiple_download_regulatory_data,
)
from .meteorology import get_meteo_data

# Define what gets exported with "from aeolus import *"
__all__ = [
    # Version
    "__version__",
    # New clean API (recommended)
    "list_sources",
    "get_metadata",
    "download",
    "get_source_info",
    "download_all_sites",
    "get_sites",
    "fetch",
    # Old API (backwards compatibility - deprecated)
    "get_network_metadata",
    "download_regulatory_data",
    "multiple_download_regulatory_data",
    "get_breathe_london_metadata",
    "download_breathe_london_data",
    "add_sites_to_database",
    "add_data_to_database",
    "db_get_site_metadata",
    "get_meteo_data",
]
