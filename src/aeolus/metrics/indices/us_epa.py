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
US EPA Air Quality Index (AQI) implementation.

The US EPA AQI uses a 0-500 scale divided into six categories:
Good (0-50), Moderate (51-100), Unhealthy for Sensitive Groups (101-150),
Unhealthy (151-200), Very Unhealthy (201-300), Hazardous (301-500).

Updated May 2024 to implement stricter PM2.5 standards.

Reference: https://www.airnow.gov/aqi/aqi-basics/
CFR: 40 CFR Appendix G to Part 58

Includes NowCast algorithm for real-time PM and ozone reporting.

Pollutants and averaging periods:
- O3: 8-hour average (or 1-hour for AQI > 300)
- PM2.5: 24-hour average (NowCast for real-time)
- PM10: 24-hour average (NowCast for real-time)
- CO: 8-hour average
- SO2: 1-hour average
- NO2: 1-hour average

Note: O3 uses ppm, PM uses µg/m³, CO uses ppm, SO2/NO2 use ppb.
"""

from typing import Sequence

from ..base import AQIResult, Breakpoint, IndexInfo, calculate_aqi_from_breakpoints
from . import register_index

# =============================================================================
# Index Metadata
# =============================================================================

INDEX_INFO: IndexInfo = {
    "name": "US EPA Air Quality Index",
    "short_name": "AQI",
    "country": "United States",
    "scale_min": 0,
    "scale_max": 500,
    "pollutants": ["O3", "PM2.5", "PM10", "CO", "SO2", "NO2"],
    "description": (
        "The US EPA Air Quality Index (AQI) is a nationally uniform index for "
        "reporting daily air quality. It uses a 0-500 scale with six categories. "
        "Updated in May 2024 with stricter PM2.5 standards."
    ),
    "url": "https://www.airnow.gov/aqi/aqi-basics/",
    "source": "40 CFR Part 58, Appendix G - Uniform Air Quality Index (AQI) and Daily Reporting",
    "version": "May 6, 2024 (PM2.5 breakpoints revised)",
}

# Register this index
register_index("US_EPA", INDEX_INFO)


# =============================================================================
# Category Definitions
# =============================================================================

CATEGORIES = {
    (0, 50): "Good",
    (51, 100): "Moderate",
    (101, 150): "Unhealthy for Sensitive Groups",
    (151, 200): "Unhealthy",
    (201, 300): "Very Unhealthy",
    (301, 500): "Hazardous",
}

COLORS = {
    "Good": "#00E400",  # Green
    "Moderate": "#FFFF00",  # Yellow
    "Unhealthy for Sensitive Groups": "#FF7E00",  # Orange
    "Unhealthy": "#FF0000",  # Red
    "Very Unhealthy": "#8F3F97",  # Purple
    "Hazardous": "#7E0023",  # Maroon
}

HEALTH_MESSAGES = {
    "Good": ("Air quality is satisfactory, and air pollution poses little or no risk."),
    "Moderate": (
        "Air quality is acceptable. However, there may be a risk for some people, "
        "particularly those who are unusually sensitive to air pollution."
    ),
    "Unhealthy for Sensitive Groups": (
        "Members of sensitive groups may experience health effects. "
        "The general public is less likely to be affected."
    ),
    "Unhealthy": (
        "Some members of the general public may experience health effects; "
        "members of sensitive groups may experience more serious health effects."
    ),
    "Very Unhealthy": (
        "Health alert: The risk of health effects is increased for everyone."
    ),
    "Hazardous": (
        "Health warning of emergency conditions: everyone is more likely to be affected."
    ),
}


# =============================================================================
# Breakpoints
# =============================================================================
#
# Source: 40 CFR Part 58, Appendix G
# URL: https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-58/appendix-Appendix%20G%20to%20Part%2058
#
# Version: May 6, 2024 (effective date of PM2.5 revisions)
#
# PM2.5 breakpoints were revised in the February 2024 final rule:
# - Federal Register: 89 FR 16202 (February 7, 2024)
# - Previous "Good" was 0-12.0, now 0-9.0 µg/m³
# - See: https://www.epa.gov/system/files/documents/2024-02/pm-naaqs-air-quality-index-fact-sheet.pdf
#
# NowCast algorithm documented in:
# - https://www.epa.gov/sites/default/files/2018-01/documents/nowcastfactsheet.pdf
# - https://forum.airnowtech.org/t/the-nowcast-for-pm2-5-and-pm10/172
# =============================================================================

# Averaging periods for each pollutant
AVERAGING_PERIODS = {
    "O3": "8h",  # 8-hour average (1-hour for AQI > 300)
    "PM2.5": "24h",  # 24-hour average (or NowCast)
    "PM10": "24h",  # 24-hour average (or NowCast)
    "CO": "8h",  # 8-hour average
    "SO2": "1h",  # 1-hour average
    "NO2": "1h",  # 1-hour average
}

# Units for each pollutant (as used in breakpoints)
UNITS = {
    "O3": "ppm",
    "PM2.5": "µg/m³",
    "PM10": "µg/m³",
    "CO": "ppm",
    "SO2": "ppb",
    "NO2": "ppb",
}

# Truncation rules (decimal places to truncate to)
TRUNCATION = {
    "O3": 3,  # Truncate to 3 decimal places
    "PM2.5": 1,  # Truncate to 1 decimal place
    "PM10": 0,  # Truncate to integer
    "CO": 1,  # Truncate to 1 decimal place
    "SO2": 0,  # Truncate to integer
    "NO2": 0,  # Truncate to integer
}


def _make_breakpoint(
    low_conc: float,
    high_conc: float,
    low_aqi: int,
    high_aqi: int,
) -> Breakpoint:
    """Create a breakpoint with category and color derived from AQI range."""
    for (aqi_low, aqi_high), category in CATEGORIES.items():
        if aqi_low <= low_aqi <= aqi_high:
            return Breakpoint(
                low_conc=low_conc,
                high_conc=high_conc,
                low_aqi=low_aqi,
                high_aqi=high_aqi,
                category=category,
                color=COLORS[category],
            )
    # Fallback for edge cases
    return Breakpoint(
        low_conc=low_conc,
        high_conc=high_conc,
        low_aqi=low_aqi,
        high_aqi=high_aqi,
        category="Hazardous",
        color=COLORS["Hazardous"],
    )


# PM2.5 (µg/m³, 24-hour) - Updated May 2024
PM25_BREAKPOINTS = [
    _make_breakpoint(0.0, 9.0, 0, 50),
    _make_breakpoint(9.1, 35.4, 51, 100),
    _make_breakpoint(35.5, 55.4, 101, 150),
    _make_breakpoint(55.5, 125.4, 151, 200),
    _make_breakpoint(125.5, 225.4, 201, 300),
    _make_breakpoint(225.5, 325.4, 301, 400),
    _make_breakpoint(325.5, 500.4, 401, 500),
]

# PM10 (µg/m³, 24-hour)
PM10_BREAKPOINTS = [
    _make_breakpoint(0, 54, 0, 50),
    _make_breakpoint(55, 154, 51, 100),
    _make_breakpoint(155, 254, 101, 150),
    _make_breakpoint(255, 354, 151, 200),
    _make_breakpoint(355, 424, 201, 300),
    _make_breakpoint(425, 504, 301, 400),
    _make_breakpoint(505, 604, 401, 500),
]

# O3 (ppm, 8-hour) - Only valid for AQI 0-300
O3_8HR_BREAKPOINTS = [
    _make_breakpoint(0.000, 0.054, 0, 50),
    _make_breakpoint(0.055, 0.070, 51, 100),
    _make_breakpoint(0.071, 0.085, 101, 150),
    _make_breakpoint(0.086, 0.105, 151, 200),
    _make_breakpoint(0.106, 0.200, 201, 300),
]

# O3 (ppm, 1-hour) - Only valid for AQI 101-500
O3_1HR_BREAKPOINTS = [
    _make_breakpoint(0.125, 0.164, 101, 150),
    _make_breakpoint(0.165, 0.204, 151, 200),
    _make_breakpoint(0.205, 0.404, 201, 300),
    _make_breakpoint(0.405, 0.504, 301, 400),
    _make_breakpoint(0.505, 0.604, 401, 500),
]

# CO (ppm, 8-hour)
CO_BREAKPOINTS = [
    _make_breakpoint(0.0, 4.4, 0, 50),
    _make_breakpoint(4.5, 9.4, 51, 100),
    _make_breakpoint(9.5, 12.4, 101, 150),
    _make_breakpoint(12.5, 15.4, 151, 200),
    _make_breakpoint(15.5, 30.4, 201, 300),
    _make_breakpoint(30.5, 40.4, 301, 400),
    _make_breakpoint(40.5, 50.4, 401, 500),
]

# SO2 (ppb, 1-hour) - Only valid for AQI 0-200
SO2_1HR_BREAKPOINTS = [
    _make_breakpoint(0, 35, 0, 50),
    _make_breakpoint(36, 75, 51, 100),
    _make_breakpoint(76, 185, 101, 150),
    _make_breakpoint(186, 304, 151, 200),
]

# SO2 (ppb, 24-hour) - Only valid for AQI 201-500
SO2_24HR_BREAKPOINTS = [
    _make_breakpoint(305, 604, 201, 300),
    _make_breakpoint(605, 804, 301, 400),
    _make_breakpoint(805, 1004, 401, 500),
]

# NO2 (ppb, 1-hour)
NO2_BREAKPOINTS = [
    _make_breakpoint(0, 53, 0, 50),
    _make_breakpoint(54, 100, 51, 100),
    _make_breakpoint(101, 360, 101, 150),
    _make_breakpoint(361, 649, 151, 200),
    _make_breakpoint(650, 1249, 201, 300),
    _make_breakpoint(1250, 1649, 301, 400),
    _make_breakpoint(1650, 2049, 401, 500),
]

BREAKPOINTS = {
    "PM2.5": PM25_BREAKPOINTS,
    "PM10": PM10_BREAKPOINTS,
    "O3_8hr": O3_8HR_BREAKPOINTS,
    "O3_1hr": O3_1HR_BREAKPOINTS,
    "CO": CO_BREAKPOINTS,
    "SO2_1hr": SO2_1HR_BREAKPOINTS,
    "SO2_24hr": SO2_24HR_BREAKPOINTS,
    "NO2": NO2_BREAKPOINTS,
}


# =============================================================================
# Truncation
# =============================================================================


def truncate(value: float, decimal_places: int) -> float:
    """
    Truncate a value to a specified number of decimal places.

    Note: This truncates (floors toward zero), not rounds.
    """
    if decimal_places == 0:
        return float(int(value))
    factor = 10**decimal_places
    return float(int(value * factor)) / factor


# =============================================================================
# NowCast Algorithm
# =============================================================================


def calculate_nowcast(
    hourly_values: Sequence[float | None],
    pollutant: str,
) -> float | None:
    """
    Calculate NowCast concentration from hourly values.

    The NowCast algorithm produces a weighted average that responds faster
    to changing air quality conditions than a simple 12-hour average.

    Args:
        hourly_values: List of up to 12 hourly concentrations, most recent first.
                      None values indicate missing data.
        pollutant: Pollutant name (affects minimum weight factor)

    Returns:
        NowCast concentration, or None if insufficient data

    Reference:
        https://www.epa.gov/sites/default/files/2018-01/documents/nowcastfactsheet.pdf
    """
    # Need at least 2 of the 3 most recent hours
    recent_3 = hourly_values[:3]
    valid_recent = sum(1 for v in recent_3 if v is not None)
    if valid_recent < 2:
        return None

    # Need c1 or c2 to be valid
    if hourly_values[0] is None and hourly_values[1] is None:
        return None

    # Get valid values (up to 12 hours)
    values = []
    for i, v in enumerate(hourly_values[:12]):
        if v is not None:
            values.append((i, v))

    if len(values) < 2:
        return None

    # Calculate weight factor
    concentrations = [v for _, v in values]
    c_min = min(concentrations)
    c_max = max(concentrations)

    if c_max == 0:
        return 0.0

    w_star = c_min / c_max

    # Apply minimum weight factor (0.5 for PM, none for O3)
    if pollutant in ("PM2.5", "PM10"):
        w = max(w_star, 0.5)
    else:
        w = w_star

    # Calculate weighted average
    numerator = 0.0
    denominator = 0.0

    for i, c in values:
        weight = w**i
        numerator += weight * c
        denominator += weight

    if denominator == 0:
        return None

    return numerator / denominator


# =============================================================================
# Calculation Functions
# =============================================================================


def calculate(
    concentration: float,
    pollutant: str,
    averaging_period: str | None = None,
) -> AQIResult:
    """
    Calculate US EPA AQI for a single pollutant concentration.

    Args:
        concentration: Pollutant concentration in native units
                      (ppm for O3/CO, ppb for SO2/NO2, µg/m³ for PM)
        pollutant: Pollutant name (O3, PM2.5, PM10, CO, SO2, NO2)
        averaging_period: Override averaging period (e.g., "1h" for O3)

    Returns:
        AQIResult with AQI value (0-500), category, and color

    Raises:
        ValueError: If pollutant is not supported
    """
    pollutant_upper = pollutant.upper()
    if pollutant_upper == "PM2.5":
        pollutant_upper = "PM2.5"  # Preserve case

    if pollutant_upper not in UNITS:
        raise ValueError(
            f"Pollutant '{pollutant}' not supported by US EPA AQI. "
            f"Supported: {list(UNITS.keys())}"
        )

    # Truncate concentration
    decimal_places = TRUNCATION.get(pollutant_upper, 0)
    concentration_truncated = truncate(concentration, decimal_places)

    # Select appropriate breakpoints
    if pollutant_upper == "O3":
        # Use 8-hour by default, 1-hour for high concentrations
        if averaging_period == "1h" or concentration_truncated >= 0.125:
            breakpoints = O3_1HR_BREAKPOINTS
            # For 1-hour O3, only valid if concentration >= 0.125 ppm
            if concentration_truncated < 0.125:
                # Fall back to 8-hour
                breakpoints = O3_8HR_BREAKPOINTS
        else:
            breakpoints = O3_8HR_BREAKPOINTS
    elif pollutant_upper == "SO2":
        # Use 1-hour for AQI 0-200, 24-hour for higher
        if concentration_truncated <= 304:
            breakpoints = SO2_1HR_BREAKPOINTS
        else:
            breakpoints = SO2_24HR_BREAKPOINTS
    else:
        breakpoint_key = pollutant_upper
        if breakpoint_key not in BREAKPOINTS:
            breakpoint_key = pollutant_upper.replace(".", "")
        breakpoints = BREAKPOINTS.get(breakpoint_key, [])

    if not breakpoints:
        raise ValueError(f"No breakpoints found for {pollutant}")

    result = calculate_aqi_from_breakpoints(concentration_truncated, breakpoints)

    if result is None:
        # Concentration out of range - return max AQI
        return AQIResult(
            value=500,
            category="Hazardous",
            color=COLORS["Hazardous"],
            pollutant=pollutant_upper,
            concentration=concentration,
            unit=UNITS[pollutant_upper],
            message=HEALTH_MESSAGES["Hazardous"],
        )

    result.pollutant = pollutant_upper
    result.unit = UNITS[pollutant_upper]
    result.message = HEALTH_MESSAGES[result.category]
    return result


def get_averaging_period(pollutant: str) -> str:
    """
    Get the required averaging period for a pollutant.

    Args:
        pollutant: Pollutant name

    Returns:
        Averaging period string (e.g., "8h", "24h", "1h")
    """
    return AVERAGING_PERIODS.get(pollutant.upper(), "1h")


def get_unit(pollutant: str) -> str:
    """
    Get the unit for a pollutant as used in AQI calculation.

    Args:
        pollutant: Pollutant name

    Returns:
        Unit string (e.g., "ppm", "ppb", "µg/m³")
    """
    return UNITS.get(pollutant.upper(), "µg/m³")
