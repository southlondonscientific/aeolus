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
European Air Quality Index (EAQI) implementation.

The EAQI (formerly CAQI - Common Air Quality Index) uses a 1-6 scale:
1 (Good), 2 (Fair), 3 (Moderate), 4 (Poor), 5 (Very Poor), 6 (Extremely Poor).

Two variants are provided:
- EU_CAQI_ROADSIDE (Traffic): Requires NO2 and PM (PM2.5 or PM10)
- EU_CAQI_BACKGROUND: Requires NO2, O3, and PM (PM2.5 or PM10)

Reference: https://airindex.eea.europa.eu/AQI/index.html

All pollutants use hourly averaging periods.
All concentrations in µg/m³.
"""

from ..base import AQIResult, Breakpoint, IndexInfo, calculate_aqi_from_breakpoints
from . import register_index

# =============================================================================
# Index Metadata
# =============================================================================

ROADSIDE_INFO: IndexInfo = {
    "name": "European Air Quality Index (Roadside/Traffic)",
    "short_name": "EAQI-R",
    "country": "European Union",
    "scale_min": 1,
    "scale_max": 6,
    "pollutants": ["NO2", "PM2.5", "PM10"],
    "description": (
        "The European Air Quality Index for traffic/roadside stations. "
        "Requires NO2 and PM data. Uses a 1-6 scale from Good to Extremely Poor."
    ),
    "url": "https://airindex.eea.europa.eu/AQI/index.html",
    "source": "CITEAIR Project - Common Air Quality Index (CAQI)",
    "version": "2014 (updated with PM2.5)",
}

BACKGROUND_INFO: IndexInfo = {
    "name": "European Air Quality Index (Background)",
    "short_name": "EAQI-B",
    "country": "European Union",
    "scale_min": 1,
    "scale_max": 6,
    "pollutants": ["NO2", "O3", "PM2.5", "PM10", "SO2"],
    "description": (
        "The European Air Quality Index for background/industrial stations. "
        "Requires NO2, O3, and PM data. Uses a 1-6 scale from Good to Extremely Poor."
    ),
    "url": "https://airindex.eea.europa.eu/AQI/index.html",
    "source": "CITEAIR Project - Common Air Quality Index (CAQI)",
    "version": "2014 (updated with PM2.5)",
}

# Register both indices
register_index("EU_CAQI_ROADSIDE", ROADSIDE_INFO)
register_index("EU_CAQI_BACKGROUND", BACKGROUND_INFO)


# =============================================================================
# Category Definitions
# =============================================================================

CATEGORIES = {
    1: "Good",
    2: "Fair",
    3: "Moderate",
    4: "Poor",
    5: "Very Poor",
    6: "Extremely Poor",
}

COLORS = {
    1: "#50F0E6",  # Cyan/turquoise - Good
    2: "#50CCAA",  # Teal - Fair
    3: "#F0E641",  # Yellow - Moderate
    4: "#FF5050",  # Red - Poor
    5: "#960032",  # Dark red - Very Poor
    6: "#7D2181",  # Purple - Extremely Poor
}

HEALTH_MESSAGES = {
    "Good": "Air quality is good. Enjoy your usual outdoor activities.",
    "Fair": "Air quality is fair. Enjoy your usual outdoor activities.",
    "Moderate": (
        "Air quality is moderate. Consider reducing intense outdoor activities "
        "if you experience symptoms."
    ),
    "Poor": (
        "Air quality is poor. Consider reducing intense activities outdoors. "
        "Sensitive groups should reduce physical exertion."
    ),
    "Very Poor": (
        "Air quality is very poor. Reduce physical activities outdoors. "
        "Sensitive groups should avoid physical exertion outdoors."
    ),
    "Extremely Poor": (
        "Air quality is extremely poor. Avoid physical activities outdoors. "
        "Sensitive groups should stay indoors and keep activity levels low."
    ),
}


# =============================================================================
# Breakpoints
# =============================================================================
#
# Source: CITEAIR Project - Common Air Quality Index
# URL: https://www.europarl.europa.eu/meetdocs/2004_2009/documents/dv/citeair_/citeair_en.pdf
#
# Academic reference:
# Van den Elshout, S., Barber, K., & Léger, K. (2014). "CAQI Common Air Quality
# Index—Update with PM2.5 and sensitivity analysis." Science of The Total
# Environment, 488-489, 461-468. https://doi.org/10.1016/j.scitotenv.2013.10.060
#
# Version: 2014 (PM2.5 update)
# Note: The EU also has a newer European Air Quality Index (EAQI) from 2017
# which differs from CAQI. We implement the more widely-documented CAQI.
# =============================================================================

# All pollutants use hourly averages
AVERAGING_PERIODS = {
    "NO2": "1h",
    "O3": "1h",
    "PM2.5": "1h",
    "PM10": "1h",
    "SO2": "1h",
}


def _make_breakpoints(ranges: list[tuple[float, float]]) -> list[Breakpoint]:
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


# NO2 (µg/m³, 1-hour)
NO2_BREAKPOINTS = _make_breakpoints(
    [
        (0, 40),  # 1 - Good
        (40.1, 90),  # 2 - Fair
        (90.1, 120),  # 3 - Moderate
        (120.1, 230),  # 4 - Poor
        (230.1, 340),  # 5 - Very Poor
        (340.1, 1000),  # 6 - Extremely Poor
    ]
)

# O3 (µg/m³, 1-hour)
O3_BREAKPOINTS = _make_breakpoints(
    [
        (0, 50),  # 1 - Good
        (50.1, 100),  # 2 - Fair
        (100.1, 130),  # 3 - Moderate
        (130.1, 240),  # 4 - Poor
        (240.1, 380),  # 5 - Very Poor
        (380.1, 800),  # 6 - Extremely Poor
    ]
)

# PM10 (µg/m³, 1-hour) - Note: Some sources show daily averages, using hourly here
PM10_BREAKPOINTS = _make_breakpoints(
    [
        (0, 20),  # 1 - Good
        (20.1, 40),  # 2 - Fair
        (40.1, 50),  # 3 - Moderate
        (50.1, 100),  # 4 - Poor
        (100.1, 150),  # 5 - Very Poor
        (150.1, 1200),  # 6 - Extremely Poor
    ]
)

# PM2.5 (µg/m³, 1-hour)
PM25_BREAKPOINTS = _make_breakpoints(
    [
        (0, 10),  # 1 - Good
        (10.1, 20),  # 2 - Fair
        (20.1, 25),  # 3 - Moderate
        (25.1, 50),  # 4 - Poor
        (50.1, 75),  # 5 - Very Poor
        (75.1, 800),  # 6 - Extremely Poor
    ]
)

# SO2 (µg/m³, 1-hour)
SO2_BREAKPOINTS = _make_breakpoints(
    [
        (0, 100),  # 1 - Good
        (100.1, 200),  # 2 - Fair
        (200.1, 350),  # 3 - Moderate
        (350.1, 500),  # 4 - Poor
        (500.1, 750),  # 5 - Very Poor
        (750.1, 1250),  # 6 - Extremely Poor
    ]
)

BREAKPOINTS = {
    "NO2": NO2_BREAKPOINTS,
    "O3": O3_BREAKPOINTS,
    "PM10": PM10_BREAKPOINTS,
    "PM2.5": PM25_BREAKPOINTS,
    "SO2": SO2_BREAKPOINTS,
}

# Required pollutants for each variant
REQUIRED_ROADSIDE = {"NO2"}  # Plus PM (either PM2.5 or PM10)
REQUIRED_BACKGROUND = {"NO2", "O3"}  # Plus PM (either PM2.5 or PM10)


# =============================================================================
# Calculation Functions
# =============================================================================


def calculate(
    concentration: float,
    pollutant: str,
) -> AQIResult:
    """
    Calculate EU CAQI sub-index for a single pollutant concentration.

    Args:
        concentration: Pollutant concentration in µg/m³
        pollutant: Pollutant name (NO2, O3, PM2.5, PM10, SO2)

    Returns:
        AQIResult with index value (1-6), category, and color

    Raises:
        ValueError: If pollutant is not supported
    """
    pollutant_upper = pollutant.upper()
    if pollutant_upper == "PM2.5":
        pollutant_upper = "PM2.5"

    if pollutant_upper not in BREAKPOINTS:
        raise ValueError(
            f"Pollutant '{pollutant}' not supported by EU CAQI. "
            f"Supported: {list(BREAKPOINTS.keys())}"
        )

    result = calculate_aqi_from_breakpoints(
        concentration,
        BREAKPOINTS[pollutant_upper],
    )

    if result is None:
        # Concentration out of range - return worst category
        return AQIResult(
            value=6,
            category="Extremely Poor",
            color=COLORS[6],
            pollutant=pollutant_upper,
            concentration=concentration,
            unit="µg/m³",
            message=HEALTH_MESSAGES["Extremely Poor"],
        )

    result.pollutant = pollutant_upper
    result.message = HEALTH_MESSAGES[result.category]
    return result


def calculate_roadside(
    concentrations: dict[str, float],
) -> AQIResult:
    """
    Calculate overall EU CAQI for a roadside/traffic station.

    Requires NO2 and at least one PM measurement (PM2.5 or PM10).
    Returns the worst (highest) sub-index.

    Args:
        concentrations: Dict mapping pollutant names to concentrations (µg/m³)

    Returns:
        AQIResult with overall index value and dominant pollutant

    Raises:
        ValueError: If required pollutants are missing
    """
    # Check required pollutants
    available = set(
        k.upper() if k.upper() != "PM2.5" else "PM2.5" for k in concentrations.keys()
    )

    if "NO2" not in available:
        raise ValueError("EU CAQI Roadside requires NO2 data")

    if "PM2.5" not in available and "PM10" not in available:
        raise ValueError("EU CAQI Roadside requires PM2.5 or PM10 data")

    # Calculate sub-indices
    results = {}
    for pollutant, conc in concentrations.items():
        poll_upper = pollutant.upper()
        if poll_upper == "PM2.5":
            poll_upper = "PM2.5"
        if poll_upper in BREAKPOINTS:
            results[poll_upper] = calculate(conc, poll_upper)

    # Find worst (highest value)
    worst = max(results.values(), key=lambda r: r.value or 0)

    return AQIResult(
        value=worst.value,
        category=worst.category,
        color=worst.color,
        pollutant=worst.pollutant,  # Dominant pollutant
        concentration=worst.concentration,
        unit="µg/m³",
        message=worst.message,
    )


def calculate_background(
    concentrations: dict[str, float],
) -> AQIResult:
    """
    Calculate overall EU CAQI for a background station.

    Requires NO2, O3, and at least one PM measurement (PM2.5 or PM10).
    Returns the worst (highest) sub-index.

    Args:
        concentrations: Dict mapping pollutant names to concentrations (µg/m³)

    Returns:
        AQIResult with overall index value and dominant pollutant

    Raises:
        ValueError: If required pollutants are missing
    """
    # Check required pollutants
    available = set(
        k.upper() if k.upper() != "PM2.5" else "PM2.5" for k in concentrations.keys()
    )
    if "NO2" not in available:
        raise ValueError("EU CAQI Background requires NO2 data")

    if "O3" not in available:
        raise ValueError("EU CAQI Background requires O3 data")

    if "PM2.5" not in available and "PM10" not in available:
        raise ValueError("EU CAQI Background requires PM2.5 or PM10 data")

    # Calculate sub-indices
    results = {}
    for pollutant, conc in concentrations.items():
        poll_upper = pollutant.upper()
        if poll_upper == "PM2.5":
            poll_upper = "PM2.5"
        if poll_upper in BREAKPOINTS:
            results[poll_upper] = calculate(conc, poll_upper)

    # Find worst (highest value)
    worst = max(results.values(), key=lambda r: r.value or 0)

    return AQIResult(
        value=worst.value,
        category=worst.category,
        color=worst.color,
        pollutant=worst.pollutant,  # Dominant pollutant
        concentration=worst.concentration,
        unit="µg/m³",
        message=worst.message,
    )


def get_averaging_period(pollutant: str) -> str:
    """Get the required averaging period for a pollutant."""
    return AVERAGING_PERIODS.get(pollutant.upper(), "1h")
