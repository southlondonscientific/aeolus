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
Data sources for Aeolus.

This package contains modules for fetching and normalising data from various
air quality monitoring networks. Each source module registers itself with the
global registry when imported.

Available sources are registered automatically when this package is imported.
"""

# Import source modules to trigger their registration
# As we add more sources, import them here
from . import (
    breathe_london,  # noqa: F401
    openaq,  # noqa: F401
    purpleair,  # noqa: F401
    regulatory,  # noqa: F401
)

__all__ = ["regulatory", "openaq", "breathe_london", "purpleair"]
