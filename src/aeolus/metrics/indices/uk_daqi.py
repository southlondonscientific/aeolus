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
UK Daily Air Quality Index (DAQI) implementation.

The DAQI was introduced by DEFRA in 2012, replacing the older UK Air Quality Index.
It uses a 1-10 scale divided into four bands: Low (1-3), Moderate (4-6),
High (7-9), and Very High (10).

Reference: https://uk-air.defra.gov.uk/air-pollution/daqi

Pollutants and averaging periods:
- O3: 8-hour running mean
- NO2: 1-hour mean
- SO2: 15-minute mean
- PM2.5: 24-hour mean
- PM10: 24-hour mean

All concentrations are in µg/m³.
"""

from ..base import AQIResult, Breakpoint, IndexInfo, calculate_aqi_from_breakpoints
from . import register_index

# =============================================================================
# Index Metadata
# =============================================================================

INDEX_INFO: IndexInfo = {
    "name": "UK Daily Air Quality Index",
    "short_name": "DAQI",
    "country": "United Kingdom",
    "scale_min": 1,
    "scale_max": 10,
    "pollutants": ["O3", "NO2", "SO2", "PM2.5", "PM10"],
    "description": (
        "The UK Daily Air Quality Index (DAQI) provides a simple 1-10 scale "
        "to communicate air quality levels. Developed by DEFRA and recommended "
        "by COMEAP, it uses four bands: Low (1-3), Moderate (4-6), High (7-9), "
        "and Very High (10)."
    ),
    "url": "https://uk-air.defra.gov.uk/air-pollution/daqi",
    "source": "DEFRA/COMEAP - Update on Implementation of the Daily Air Quality Index (April 2013)",
    "version": "April 2013 (current)",
}

# Register this index
register_index("UK_DAQI", INDEX_INFO)


# =============================================================================
# Band Definitions
# =============================================================================

# Colors from UK-AIR official styling
COLORS = {
    1: "#9CFF9C",  # Light green
    1: "#9CFF9C",  # Light green
    2: "#31FF00",  # Green
    3: "#31CF00",  # Dark green
    4: "#FFFF00",  # Yellow
    5: "#FFCF00",  # Amber
    6: "#FF9A00",  # Orange
    7: "#FF6464",  # Light red
    8: "#FF0000",  # Red
    9: "#990000",  # Dark red
    10: "#CE30FF",  # Purple
}

CATEGORIES = {
    1: "Low",
    2: "Low",
    3: "Low",
    4: "Moderate",
    5: "Moderate",
    6: "Moderate",
    7: "High",
    8: "High",
    9: "High",
    10: "Very High",
}

HEALTH_MESSAGES = {
    "Low": "Enjoy your usual outdoor activities.",
    "Moderate": (
        "Adults and children with lung problems, and adults with heart problems, "
        "who experience symptoms, should consider reducing strenuous physical "
        "activity, particularly outdoors."
    ),
    "High": (
        "Adults and children with lung problems, and adults with heart problems, "
        "should reduce strenuous physical exertion, particularly outdoors, "
        "and particularly if they experience symptoms. People with asthma may "
        "find they need to use their reliever inhaler more often. Older people "
        "should also reduce physical exertion."
    ),
    "Very High": (
        "Adults and children with lung problems, adults with heart problems, "
        "and older people, should avoid strenuous physical activity. People "
        "with asthma may find they need to use their reliever inhaler more often."
    ),
}


# =============================================================================
# Breakpoints
# =============================================================================
#
# Source: DEFRA "Update on Implementation of the Daily Air Quality Index"
# URL: https://uk-air.defra.gov.uk/assets/documents/reports/cat14/
#      1304251155_Update_on_Implementation_of_the_DAQI_April_2013_Final.pdf
#
# Version: April 2013 (current as of January 2025)
# Note: UK DAQI is under review and breakpoints may change. Check DEFRA for updates.
#
# All concentrations in µg/m³. Values are rounded to nearest integer before lookup.
# =============================================================================

# Averaging periods for each pollutant
AVERAGING_PERIODS = {
    "O3": "8h",  # 8-hour running mean
    "NO2": "1h",  # 1-hour mean
    "SO2": "15min",  # 15-minute mean
    "PM2.5": "24h",  # 24-hour mean
    "PM10": "24h",  # 24-hour mean
}


def _make_breakpoints(
    ranges: list[tuple[float, float]],
) -> list[Breakpoint]:
    """Create breakpoint list from concentration ranges."""
    breakpoints = []
    for i, (low, high) in enumerate(ranges, start=1):
        breakpoints.append(
            Breakpoint(
                low_conc=low,
                high_conc=high,
                low_aqi=i,
                high_aqi=i,
                category=CATEGORIES[i],
                color=COLORS[i],
            )
        )
    return breakpoints


# O3: 8-hour running mean (µg/m³)
O3_BREAKPOINTS = _make_breakpoints(
    [
        (0, 33),  # 1 - Low
        (34, 66),  # 2 - Low
        (67, 100),  # 3 - Low
        (101, 120),  # 4 - Moderate
        (121, 140),  # 5 - Moderate
        (141, 160),  # 6 - Moderate
        (161, 187),  # 7 - High
        (188, 213),  # 8 - High
        (214, 240),  # 9 - High
        (241, 9999),  # 10 - Very High
    ]
)

# NO2: 1-hour mean (µg/m³)
NO2_BREAKPOINTS = _make_breakpoints(
    [
        (0, 67),  # 1 - Low
        (68, 134),  # 2 - Low
        (135, 200),  # 3 - Low
        (201, 267),  # 4 - Moderate
        (268, 334),  # 5 - Moderate
        (335, 400),  # 6 - Moderate
        (401, 467),  # 7 - High
        (468, 534),  # 8 - High
        (535, 600),  # 9 - High
        (601, 9999),  # 10 - Very High
    ]
)

# SO2: 15-minute mean (µg/m³)
SO2_BREAKPOINTS = _make_breakpoints(
    [
        (0, 88),  # 1 - Low
        (89, 177),  # 2 - Low
        (178, 266),  # 3 - Low
        (267, 354),  # 4 - Moderate
        (355, 443),  # 5 - Moderate
        (444, 532),  # 6 - Moderate
        (533, 710),  # 7 - High
        (711, 887),  # 8 - High
        (888, 1064),  # 9 - High
        (1065, 9999),  # 10 - Very High
    ]
)

# PM2.5: 24-hour mean (µg/m³)
PM25_BREAKPOINTS = _make_breakpoints(
    [
        (0, 11),  # 1 - Low
        (12, 23),  # 2 - Low
        (24, 35),  # 3 - Low
        (36, 41),  # 4 - Moderate
        (42, 47),  # 5 - Moderate
        (48, 53),  # 6 - Moderate
        (54, 58),  # 7 - High
        (59, 64),  # 8 - High
        (65, 70),  # 9 - High
        (71, 9999),  # 10 - Very High
    ]
)

# PM10: 24-hour mean (µg/m³)
PM10_BREAKPOINTS = _make_breakpoints(
    [
        (0, 16),  # 1 - Low
        (17, 33),  # 2 - Low
        (34, 50),  # 3 - Low
        (51, 58),  # 4 - Moderate
        (59, 66),  # 5 - Moderate
        (67, 75),  # 6 - Moderate
        (76, 83),  # 7 - High
        (84, 91),  # 8 - High
        (92, 100),  # 9 - High
        (101, 9999),  # 10 - Very High
    ]
)

BREAKPOINTS = {
    "O3": O3_BREAKPOINTS,
    "NO2": NO2_BREAKPOINTS,
    "SO2": SO2_BREAKPOINTS,
    "PM2.5": PM25_BREAKPOINTS,
    "PM10": PM10_BREAKPOINTS,
}


# =============================================================================
# Calculation Functions
# =============================================================================


def calculate(
    concentration: float,
    pollutant: str,
) -> AQIResult:
    """
    Calculate UK DAQI for a single pollutant concentration.

    Note: The concentration should already be the appropriate average
    (8-hour for O3, 1-hour for NO2, etc.) in µg/m³.

    Args:
        concentration: Pollutant concentration in µg/m³
        pollutant: Pollutant name (O3, NO2, SO2, PM2.5, PM10)

    Returns:
        AQIResult with DAQI value (1-10), category, and color

    Raises:
        ValueError: If pollutant is not supported
    """
    if pollutant not in BREAKPOINTS:
        raise ValueError(
            f"Pollutant '{pollutant}' not supported by UK DAQI. "
            f"Supported: {list(BREAKPOINTS.keys())}"
        )

    # Round concentration to nearest integer as per DAQI specification
    concentration_rounded = round(concentration)

    result = calculate_aqi_from_breakpoints(
        concentration_rounded,
        BREAKPOINTS[pollutant],
    )

    if result is None:
        # Should not happen with our 9999 upper bounds, but handle gracefully
        return AQIResult(
            value=10,
            category="Very High",
            color=COLORS[10],
            pollutant=pollutant,
            concentration=concentration,
            unit="µg/m³",
            message=HEALTH_MESSAGES["Very High"],
        )

    result.pollutant = pollutant
    result.message = HEALTH_MESSAGES[result.category]
    return result


def get_averaging_period(pollutant: str) -> str:
    """
    Get the required averaging period for a pollutant.

    Args:
        pollutant: Pollutant name

    Returns:
        Averaging period string (e.g., "8h", "24h", "1h", "15min")
    """
    return AVERAGING_PERIODS.get(pollutant, "1h")


def calculate_array(
    concentrations: "np.ndarray",
    pollutant: str,
) -> tuple["np.ndarray", "np.ndarray"]:
    """
    Vectorized UK DAQI calculation for an array of concentrations.

    This is much faster than calling calculate() in a loop.

    Args:
        concentrations: Array of pollutant concentrations in µg/m³
        pollutant: Pollutant name (O3, NO2, SO2, PM2.5, PM10)

    Returns:
        Tuple of (aqi_values, categories) arrays.
        aqi_values contains NaN where concentration is invalid.
        categories contains category strings (or None where invalid).
    """
    import numpy as np

    from ..base import calculate_aqi_from_breakpoints_array

    if pollutant not in BREAKPOINTS:
        raise ValueError(
            f"Pollutant '{pollutant}' not supported by UK DAQI. "
            f"Supported: {list(BREAKPOINTS.keys())}"
        )

    # Round concentrations as per DAQI specification
    concentrations_rounded = np.round(concentrations)

    # Get breakpoints for this pollutant
    breakpoints = BREAKPOINTS[pollutant]

    # Calculate AQI values and category indices
    aqi_values, category_indices = calculate_aqi_from_breakpoints_array(
        concentrations_rounded, breakpoints
    )

    # Map category indices to category names
    categories = np.array([None] * len(concentrations), dtype=object)
    for i, bp in enumerate(breakpoints):
        mask = category_indices == i
        categories[mask] = bp["category"]

    # Handle out-of-range (very high concentrations) -> Very High
    out_of_range = category_indices == -1
    if np.any(out_of_range):
        # Check if it's because concentration is too high (not NaN)
        high_mask = out_of_range & ~np.isnan(concentrations)
        aqi_values[high_mask] = 10
        categories[high_mask] = "Very High"

    return aqi_values, categories
