# Aeolus: download and standardise air quality data
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
AQI index implementations.

Each index module provides:
- INDEX_INFO: Metadata about the index
- BREAKPOINTS: Pollutant breakpoint definitions
- calculate(): Function to calculate AQI for a single concentration
- calculate_from_data(): Function to calculate AQI from a DataFrame
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..base import IndexInfo

# Registry of available indices
_INDICES: dict[str, "IndexInfo"] = {}


def register_index(key: str, info: "IndexInfo") -> None:
    """Register an AQI index."""
    _INDICES[key] = info


def get_index(key: str) -> "IndexInfo | None":
    """Get info about a registered index."""
    return _INDICES.get(key)


def list_indices() -> list[str]:
    """List all registered index keys."""
    return list(_INDICES.keys())


# Import indices to trigger registration
from . import (  # noqa: E402, F401
    china,
    eu_caqi,
    india_naqi,
    uk_daqi,
    us_epa,
    who,
)
