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
Portal Data Sources.

Portals are global data platforms aggregating air quality data from multiple sources:
- OpenAQ (Global air quality data from 100+ countries)
- PurpleAir (Crowdsourced sensor network) [Coming soon]
- AirGradient (DIY sensor platform) [Coming soon]

Portals have potentially millions of locations globally, requiring search/discovery
patterns rather than complete listing.

Usage:
    >>> import aeolus
    >>>
    >>> # Search for locations (filters required)
    >>> sites = aeolus.portals.find_sites("OpenAQ", country="GB")
    >>>
    >>> # Download data
    >>> location_ids = sites["location_id"].tolist()
    >>> data = aeolus.portals.download("OpenAQ", location_ids, start, end)
"""

from .api import download, find_sites, list_portals

__all__ = ["find_sites", "download", "list_portals"]
