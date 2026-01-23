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
Network Data Sources.

Networks are discrete monitoring networks operated by organizations:
- AURN (UK Automatic Urban and Rural Network)
- SAQN (Scottish Air Quality Network)
- WAQN (Wales Air Quality Network)
- NI (Northern Ireland Air Quality Network)
- Breathe London (London sensor network)
- And more...

Networks have finite numbers of monitoring sites that can be listed completely.

Usage:
    >>> import aeolus
    >>>
    >>> # Get all sites in a network
    >>> sites = aeolus.networks.get_metadata("AURN")
    >>>
    >>> # Download data
    >>> data = aeolus.networks.download("AURN", ["MY1"], start, end)
"""

from .api import download, get_metadata, list_networks

__all__ = ["get_metadata", "download", "list_networks"]
