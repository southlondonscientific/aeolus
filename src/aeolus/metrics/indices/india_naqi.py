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
India National Air Quality Index (NAQI) implementation.

India's NAQI uses a 0-500 scale divided into six categories:
Good (0-50), Satisfactory (51-100), Moderately Polluted (101-200),
Poor (201-300), Very Poor (301-400), Severe (401-500).

Launched in September 2014 under the Swachh Bharat Abhiyan program.

Reference: Central Pollution Control Board (CPCB)
https://cpcb.nic.in/National-Air-Quality-Index/

Pollutants (8 total):
- PM2.5: 24-hour average (µg/m³)
- PM10: 24-hour average (µg/m³)
- SO2: 24-hour average (µg/m³)
- NO2: 24-hour average (µg/m³)
- CO: 8-hour average (mg/m³)
- O3: 8-hour average (µg/m³), 1-hour for higher bands
- NH3: 24-hour average (µg/m³)
- Pb: 24-hour average (µg/m³)

Note: Aeolus primarily handles PM2.5, PM10, SO2, NO2, CO, O3.
NH3 and Pb are less commonly available but supported.
"""

from ..base import AQIResult, Breakpoint, IndexInfo, calculate_aqi_from_breakpoints
from . import register_index

# =============================================================================
# Index Metadata
# =============================================================================

INDEX_INFO: IndexInfo = {
    "name": "India National Air Quality Index",
    "short_name": "NAQI",
    "country": "India",
    "scale_min": 0,
    "scale_max": 500,
    "pollutants": ["PM2.5", "PM10", "SO2", "NO2", "CO", "O3", "NH3", "Pb"],
    "description": (
        "India's National Air Quality Index (NAQI) uses a 0-500 scale with six "
        "categories. Launched in 2014, it covers eight pollutants. The overall "
        "AQI is the maximum sub-index across all measured pollutants."
    ),
    "url": "https://cpcb.nic.in/National-Air-Quality-Index/",
}

# Register this index
register_index("INDIA_NAQI", INDEX_INFO)


# =============================================================================
# Category Definitions
# =============================================================================

CATEGORIES = {
    (0, 50): "Good",
    (51, 100): "Satisfactory",
    (101, 200): "Moderately Polluted",
    (201, 300): "Poor",
    (301, 400): "Very Poor",
    (401, 500): "Severe",
}

COLORS = {
    "Good": "#009933",  # Green
    "Satisfactory": "#58FF09",  # Light green
    "Moderately Polluted": "#FFFF00",  # Yellow
    "Poor": "#FFA500",  # Orange
    "Very Poor": "#FF0000",  # Red
    "Severe": "#990000",  # Maroon
}

HEALTH_MESSAGES = {
    "Good": ("Minimal impact. Air quality is considered satisfactory."),
    "Satisfactory": ("May cause minor breathing discomfort to sensitive people."),
    "Moderately Polluted": (
        "May cause breathing discomfort to people with lung disease such as asthma, "
        "and discomfort to people with heart disease, children and older adults."
    ),
    "Poor": (
        "May cause breathing discomfort to people on prolonged exposure, "
        "and discomfort to people with heart disease with short exposure."
    ),
    "Very Poor": (
        "May cause respiratory illness to the people on prolonged exposure. "
        "Effect may be more pronounced in people with lung and heart diseases."
    ),
    "Severe": (
        "May cause respiratory effects even on healthy people and serious health "
        "impacts on people with lung/heart diseases. The health impacts may be "
        "experienced even during light physical activity."
    ),
}


# =============================================================================
# Breakpoints
# =============================================================================

AVERAGING_PERIODS = {
    "PM2.5": "24h",
    "PM10": "24h",
    "SO2": "24h",
    "NO2": "24h",
    "CO": "8h",  # mg/m³
    "O3": "8h",  # 8-hour for lower bands, 1-hour for higher
    "NH3": "24h",
    "Pb": "24h",
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
    return Breakpoint(
        low_conc=low_conc,
        high_conc=high_conc,
        low_aqi=low_aqi,
        high_aqi=high_aqi,
        category="Severe",
        color=COLORS["Severe"],
    )


# PM2.5 (µg/m³, 24-hour)
PM25_BREAKPOINTS = [
    _make_breakpoint(0, 30, 0, 50),
    _make_breakpoint(31, 60, 51, 100),
    _make_breakpoint(61, 90, 101, 200),
    _make_breakpoint(91, 120, 201, 300),
    _make_breakpoint(121, 250, 301, 400),
    _make_breakpoint(251, 500, 401, 500),
]

# PM10 (µg/m³, 24-hour)
PM10_BREAKPOINTS = [
    _make_breakpoint(0, 50, 0, 50),
    _make_breakpoint(51, 100, 51, 100),
    _make_breakpoint(101, 250, 101, 200),
    _make_breakpoint(251, 350, 201, 300),
    _make_breakpoint(351, 430, 301, 400),
    _make_breakpoint(431, 600, 401, 500),
]

# SO2 (µg/m³, 24-hour)
SO2_BREAKPOINTS = [
    _make_breakpoint(0, 40, 0, 50),
    _make_breakpoint(41, 80, 51, 100),
    _make_breakpoint(81, 380, 101, 200),
    _make_breakpoint(381, 800, 201, 300),
    _make_breakpoint(801, 1600, 301, 400),
    _make_breakpoint(1601, 2400, 401, 500),
]

# NO2 (µg/m³, 24-hour)
NO2_BREAKPOINTS = [
    _make_breakpoint(0, 40, 0, 50),
    _make_breakpoint(41, 80, 51, 100),
    _make_breakpoint(81, 180, 101, 200),
    _make_breakpoint(181, 280, 201, 300),
    _make_breakpoint(281, 400, 301, 400),
    _make_breakpoint(401, 600, 401, 500),
]

# CO (mg/m³, 8-hour) - Note: mg/m³ not µg/m³
CO_BREAKPOINTS = [
    _make_breakpoint(0, 1.0, 0, 50),
    _make_breakpoint(1.1, 2.0, 51, 100),
    _make_breakpoint(2.1, 10.0, 101, 200),
    _make_breakpoint(10.1, 17.0, 201, 300),
    _make_breakpoint(17.1, 34.0, 301, 400),
    _make_breakpoint(34.1, 50.0, 401, 500),
]

# O3 (µg/m³, 8-hour) - Only valid for AQI 0-300
O3_8HR_BREAKPOINTS = [
    _make_breakpoint(0, 50, 0, 50),
    _make_breakpoint(51, 100, 51, 100),
    _make_breakpoint(101, 168, 101, 200),
    _make_breakpoint(169, 208, 201, 300),
]

# O3 (µg/m³, 1-hour) - Only valid for AQI 301-500
O3_1HR_BREAKPOINTS = [
    _make_breakpoint(209, 748, 301, 400),
    _make_breakpoint(749, 1000, 401, 500),
]

# NH3 (µg/m³, 24-hour)
NH3_BREAKPOINTS = [
    _make_breakpoint(0, 200, 0, 50),
    _make_breakpoint(201, 400, 51, 100),
    _make_breakpoint(401, 800, 101, 200),
    _make_breakpoint(801, 1200, 201, 300),
    _make_breakpoint(1201, 1800, 301, 400),
    _make_breakpoint(1801, 2400, 401, 500),
]

# Pb - Lead (µg/m³, 24-hour)
PB_BREAKPOINTS = [
    _make_breakpoint(0, 0.5, 0, 50),
    _make_breakpoint(0.51, 1.0, 51, 100),
    _make_breakpoint(1.1, 2.0, 101, 200),
    _make_breakpoint(2.1, 3.0, 201, 300),
    _make_breakpoint(3.1, 3.5, 301, 400),
    _make_breakpoint(3.51, 5.0, 401, 500),
]

BREAKPOINTS = {
    "PM2.5": PM25_BREAKPOINTS,
    "PM10": PM10_BREAKPOINTS,
    "SO2": SO2_BREAKPOINTS,
    "NO2": NO2_BREAKPOINTS,
    "CO": CO_BREAKPOINTS,
    "O3_8hr": O3_8HR_BREAKPOINTS,
    "O3_1hr": O3_1HR_BREAKPOINTS,
    "NH3": NH3_BREAKPOINTS,
    "Pb": PB_BREAKPOINTS,
}


# =============================================================================
# Calculation Functions
# =============================================================================


def calculate(
    concentration: float,
    pollutant: str,
    averaging_period: str | None = None,
) -> AQIResult:
    """
    Calculate India NAQI for a single pollutant concentration.

    Args:
        concentration: Pollutant concentration
                      (µg/m³ for most pollutants, mg/m³ for CO)
        pollutant: Pollutant name (PM2.5, PM10, SO2, NO2, CO, O3, NH3, Pb)
        averaging_period: Override averaging period (mainly for O3: "8h" or "1h")

    Returns:
        AQIResult with AQI value (0-500), category, and color

    Raises:
        ValueError: If pollutant is not supported
    """
    pollutant_upper = pollutant.upper()
    if pollutant_upper == "PM2.5":
        pollutant_upper = "PM2.5"
    elif pollutant_upper == "PB":
        pollutant_upper = "Pb"

    if pollutant_upper not in AVERAGING_PERIODS:
        raise ValueError(
            f"Pollutant '{pollutant}' not supported by India NAQI. "
            f"Supported: {list(AVERAGING_PERIODS.keys())}"
        )

    # Handle O3 specially - uses 8-hour for lower AQI, 1-hour for higher
    if pollutant_upper == "O3":
        if averaging_period == "1h":
            breakpoints = O3_1HR_BREAKPOINTS
        elif averaging_period == "8h":
            breakpoints = O3_8HR_BREAKPOINTS
        else:
            # Try 8-hour first, fall back to 1-hour for high concentrations
            result = calculate_aqi_from_breakpoints(concentration, O3_8HR_BREAKPOINTS)
            if result is None and concentration >= 209:
                breakpoints = O3_1HR_BREAKPOINTS
            else:
                breakpoints = O3_8HR_BREAKPOINTS
    else:
        breakpoints = BREAKPOINTS.get(pollutant_upper, [])

    if not breakpoints:
        raise ValueError(f"No breakpoints found for {pollutant_upper}")

    result = calculate_aqi_from_breakpoints(concentration, breakpoints)

    if result is None:
        # Concentration out of range - return max
        return AQIResult(
            value=500,
            category="Severe",
            color=COLORS["Severe"],
            pollutant=pollutant_upper,
            concentration=concentration,
            unit="mg/m³" if pollutant_upper == "CO" else "µg/m³",
            message=HEALTH_MESSAGES["Severe"],
        )

    result.pollutant = pollutant_upper
    result.unit = "mg/m³" if pollutant_upper == "CO" else "µg/m³"
    result.message = HEALTH_MESSAGES[result.category]
    return result


def get_averaging_period(pollutant: str) -> str:
    """Get the default averaging period for a pollutant."""
    return AVERAGING_PERIODS.get(pollutant.upper(), "24h")
