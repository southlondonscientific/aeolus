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
Aeolus: Download and standardise air quality data.

This package provides a unified interface for downloading air quality data
from networks and portals worldwide.

Organization:
    - Networks: Discrete monitoring networks (AURN, Breathe London, etc.)
    - Portals: Global data platforms (OpenAQ, PurpleAir, etc.)

Quick Start:
    >>> import aeolus
    >>> from datetime import datetime
    >>>
    >>> # List all sources
    >>> sources = aeolus.list_sources()
    >>>
    >>> # Networks - Get metadata and download
    >>> sites = aeolus.networks.get_metadata("AURN")
    >>> data = aeolus.networks.download("AURN", ["MY1"], start, end)
    >>>
    >>> # Portals - Search and download
    >>> locations = aeolus.portals.find_sites("OpenAQ", country="GB")
    >>> data = aeolus.portals.download("OpenAQ", ["2178"], start, end)
    >>>
    >>> # Convenience: Top-level download (single source)
    >>> data = aeolus.download("AURN", ["MY1"], start, end)
    >>>
    >>> # Multiple sources with explicit mapping
    >>> data = aeolus.download(
    ...     {"AURN": ["MY1"], "OpenAQ": ["2178"]},
    ...     start_date=start,
    ...     end_date=end
    ... )

Submodules:
    - aeolus.networks: Discrete monitoring networks
    - aeolus.portals: Global data portals
    - aeolus.transforms: Data transformation functions

Supported Networks:
    - AURN (UK Automatic Urban and Rural Network)
    - SAQN (Scottish Air Quality Network)
    - WAQN (Wales Air Quality Network)
    - NI (Northern Ireland Air Quality Network)
    - Breathe London (London sensor network)
    - And more...

Supported Portals:
    - OpenAQ (Global air quality data platform)

For more details, see: https://github.com/southlondonscientific/aeolus
"""

__version__ = "0.2.0"

# Import submodules for networks and portals
from . import networks, portals, transforms

# Import the clean public API
from .api import (
    download,
    fetch,
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
    # Submodules
    "networks",
    "portals",
    "transforms",
    # Top-level API (recommended)
    "list_sources",
    "download",
    "get_source_info",
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
