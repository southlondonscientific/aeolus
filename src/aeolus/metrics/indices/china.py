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
China Air Quality Index (AQI) implementation.

China's AQI uses a 0-500 scale divided into six categories:
Excellent (0-50), Good (51-100), Lightly Polluted (101-150),
Moderately Polluted (151-200), Heavily Polluted (201-300),
Severely Polluted (301-500).

Implemented by China's Ministry of Environmental Protection since January 2013.

Reference: HJ 633-2012 Technical Regulation on Ambient Air Quality Index

Pollutants:
- SO2: 24-hour or 1-hour average (µg/m³)
- NO2: 24-hour or 1-hour average (µg/m³)
- PM10: 24-hour average (µg/m³)
- PM2.5: 24-hour average (µg/m³)
- CO: 24-hour or 1-hour average (mg/m³)
- O3: 1-hour or 8-hour average (µg/m³)
"""

from ..base import AQIResult, Breakpoint, IndexInfo, calculate_aqi_from_breakpoints
from . import register_index

# =============================================================================
# Index Metadata
# =============================================================================

INDEX_INFO: IndexInfo = {
    "name": "China Air Quality Index",
    "short_name": "AQI",
    "country": "China",
    "scale_min": 0,
    "scale_max": 500,
    "pollutants": ["SO2", "NO2", "PM10", "PM2.5", "CO", "O3"],
    "description": (
        "China's Air Quality Index (AQI) uses a 0-500 scale with six categories. "
        "Implemented by the Ministry of Environmental Protection since 2013. "
        "The overall AQI is the maximum sub-index across all pollutants."
    ),
    "url": "https://aqihub.info/indices/china",
}

# Register this index
register_index("CHINA", INDEX_INFO)


# =============================================================================
# Category Definitions
# =============================================================================

CATEGORIES = {
    (0, 50): "Excellent",
    (51, 100): "Good",
    (101, 150): "Lightly Polluted",
    (151, 200): "Moderately Polluted",
    (201, 300): "Heavily Polluted",
    (301, 500): "Severely Polluted",
}

COLORS = {
    "Excellent": "#00E400",  # Green
    "Good": "#FFFF00",  # Yellow
    "Lightly Polluted": "#FF7E00",  # Orange
    "Moderately Polluted": "#FF0000",  # Red
    "Heavily Polluted": "#99004C",  # Purple
    "Severely Polluted": "#7E0023",  # Maroon
}

HEALTH_MESSAGES = {
    "Excellent": (
        "空气质量令人满意，基本无空气污染。"
        " (Air quality is satisfactory, basically no air pollution.)"
    ),
    "Good": (
        "空气质量可接受，但某些污染物可能对极少数异常敏感人群健康有较弱影响。"
        " (Air quality is acceptable, but some pollutants may have weak effects "
        "on a very small number of unusually sensitive people.)"
    ),
    "Lightly Polluted": (
        "易感人群症状有轻度加剧，健康人群出现刺激症状。"
        " (Sensitive groups may experience mild aggravation of symptoms. "
        "Healthy people may experience irritation.)"
    ),
    "Moderately Polluted": (
        "进一步加剧易感人群症状，可能对健康人群心脏、呼吸系统有影响。"
        " (Further aggravation of symptoms in sensitive groups. May affect "
        "the heart and respiratory system of healthy people.)"
    ),
    "Heavily Polluted": (
        "心脏病和肺病患者症状显著加剧，运动耐受力降低，健康人群普遍出现症状。"
        " (Significant aggravation of symptoms in heart and lung disease patients. "
        "Reduced exercise tolerance. General population may experience symptoms.)"
    ),
    "Severely Polluted": (
        "健康人群运动耐受力降低，有明显强烈症状，提前出现某些疾病。"
        " (Healthy people experience reduced exercise tolerance with strong symptoms. "
        "Some diseases may appear prematurely.)"
    ),
}


# =============================================================================
# Breakpoints
# =============================================================================

AVERAGING_PERIODS = {
    "SO2": "24h",  # 24-hour (or 1-hour)
    "NO2": "24h",  # 24-hour (or 1-hour)
    "PM10": "24h",  # 24-hour
    "PM2.5": "24h",  # 24-hour
    "CO": "24h",  # 24-hour (or 1-hour) - in mg/m³
    "O3": "8h",  # 8-hour (or 1-hour)
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
        category="Severely Polluted",
        color=COLORS["Severely Polluted"],
    )


# SO2 (µg/m³, 24-hour)
SO2_24HR_BREAKPOINTS = [
    _make_breakpoint(0, 50, 0, 50),
    _make_breakpoint(51, 150, 51, 100),
    _make_breakpoint(151, 475, 101, 150),
    _make_breakpoint(476, 800, 151, 200),
    _make_breakpoint(801, 1600, 201, 300),
    _make_breakpoint(1601, 2100, 301, 400),
    _make_breakpoint(2101, 2620, 401, 500),
]

# SO2 (µg/m³, 1-hour)
SO2_1HR_BREAKPOINTS = [
    _make_breakpoint(0, 150, 0, 50),
    _make_breakpoint(151, 500, 51, 100),
    _make_breakpoint(501, 650, 101, 150),
    _make_breakpoint(651, 800, 151, 200),
    # Note: 1-hour SO2 doesn't define values above AQI 200
]

# NO2 (µg/m³, 24-hour)
NO2_24HR_BREAKPOINTS = [
    _make_breakpoint(0, 40, 0, 50),
    _make_breakpoint(41, 80, 51, 100),
    _make_breakpoint(81, 180, 101, 150),
    _make_breakpoint(181, 280, 151, 200),
    _make_breakpoint(281, 565, 201, 300),
    _make_breakpoint(566, 750, 301, 400),
    _make_breakpoint(751, 940, 401, 500),
]

# NO2 (µg/m³, 1-hour)
NO2_1HR_BREAKPOINTS = [
    _make_breakpoint(0, 100, 0, 50),
    _make_breakpoint(101, 200, 51, 100),
    _make_breakpoint(201, 700, 101, 150),
    _make_breakpoint(701, 1200, 151, 200),
    _make_breakpoint(1201, 2340, 201, 300),
    _make_breakpoint(2341, 3090, 301, 400),
    _make_breakpoint(3091, 3840, 401, 500),
]

# PM10 (µg/m³, 24-hour)
PM10_BREAKPOINTS = [
    _make_breakpoint(0, 50, 0, 50),
    _make_breakpoint(51, 150, 51, 100),
    _make_breakpoint(151, 250, 101, 150),
    _make_breakpoint(251, 350, 151, 200),
    _make_breakpoint(351, 420, 201, 300),
    _make_breakpoint(421, 500, 301, 400),
    _make_breakpoint(501, 600, 401, 500),
]

# PM2.5 (µg/m³, 24-hour)
PM25_BREAKPOINTS = [
    _make_breakpoint(0, 35, 0, 50),
    _make_breakpoint(36, 75, 51, 100),
    _make_breakpoint(76, 115, 101, 150),
    _make_breakpoint(116, 150, 151, 200),
    _make_breakpoint(151, 250, 201, 300),
    _make_breakpoint(251, 350, 301, 400),
    _make_breakpoint(351, 500, 401, 500),
]

# CO (mg/m³, 24-hour) - Note: mg/m³ not µg/m³
CO_24HR_BREAKPOINTS = [
    _make_breakpoint(0, 2, 0, 50),
    _make_breakpoint(2.1, 4, 51, 100),
    _make_breakpoint(4.1, 14, 101, 150),
    _make_breakpoint(14.1, 24, 151, 200),
    _make_breakpoint(24.1, 36, 201, 300),
    _make_breakpoint(36.1, 48, 301, 400),
    _make_breakpoint(48.1, 60, 401, 500),
]

# CO (mg/m³, 1-hour)
CO_1HR_BREAKPOINTS = [
    _make_breakpoint(0, 5, 0, 50),
    _make_breakpoint(5.1, 10, 51, 100),
    _make_breakpoint(10.1, 35, 101, 150),
    _make_breakpoint(35.1, 60, 151, 200),
    _make_breakpoint(60.1, 90, 201, 300),
    _make_breakpoint(90.1, 120, 301, 400),
    _make_breakpoint(120.1, 150, 401, 500),
]

# O3 (µg/m³, 1-hour)
O3_1HR_BREAKPOINTS = [
    _make_breakpoint(0, 160, 0, 50),
    _make_breakpoint(161, 200, 51, 100),
    _make_breakpoint(201, 300, 101, 150),
    _make_breakpoint(301, 400, 151, 200),
    _make_breakpoint(401, 800, 201, 300),
    _make_breakpoint(801, 1000, 301, 400),
    _make_breakpoint(1001, 1200, 401, 500),
]

# O3 (µg/m³, 8-hour)
O3_8HR_BREAKPOINTS = [
    _make_breakpoint(0, 100, 0, 50),
    _make_breakpoint(101, 160, 51, 100),
    _make_breakpoint(161, 215, 101, 150),
    _make_breakpoint(216, 265, 151, 200),
    _make_breakpoint(266, 800, 201, 300),
    # Note: 8-hour O3 uses same breakpoints as 1-hour for AQI > 300
]

BREAKPOINTS = {
    "SO2_24hr": SO2_24HR_BREAKPOINTS,
    "SO2_1hr": SO2_1HR_BREAKPOINTS,
    "NO2_24hr": NO2_24HR_BREAKPOINTS,
    "NO2_1hr": NO2_1HR_BREAKPOINTS,
    "PM10": PM10_BREAKPOINTS,
    "PM2.5": PM25_BREAKPOINTS,
    "CO_24hr": CO_24HR_BREAKPOINTS,
    "CO_1hr": CO_1HR_BREAKPOINTS,
    "O3_1hr": O3_1HR_BREAKPOINTS,
    "O3_8hr": O3_8HR_BREAKPOINTS,
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
    Calculate China AQI for a single pollutant concentration.

    Args:
        concentration: Pollutant concentration
                      (µg/m³ for most pollutants, mg/m³ for CO)
        pollutant: Pollutant name (SO2, NO2, PM10, PM2.5, CO, O3)
        averaging_period: "24h", "8h", or "1h" (defaults vary by pollutant)

    Returns:
        AQIResult with AQI value (0-500), category, and color

    Raises:
        ValueError: If pollutant is not supported
    """
    pollutant_upper = pollutant.upper()
    if pollutant_upper == "PM2.5":
        pollutant_upper = "PM2.5"

    if pollutant_upper not in AVERAGING_PERIODS:
        raise ValueError(
            f"Pollutant '{pollutant}' not supported by China AQI. "
            f"Supported: {list(AVERAGING_PERIODS.keys())}"
        )

    # Determine averaging period
    if averaging_period is None:
        averaging_period = AVERAGING_PERIODS[pollutant_upper]

    # Select breakpoints based on pollutant and averaging period
    if pollutant_upper in ("PM10", "PM2.5"):
        breakpoint_key = pollutant_upper
    else:
        period_suffix = averaging_period.replace("h", "hr").replace("hour", "hr")
        breakpoint_key = f"{pollutant_upper}_{period_suffix}"

    breakpoints = BREAKPOINTS.get(breakpoint_key)

    if not breakpoints:
        raise ValueError(
            f"No breakpoints for {pollutant_upper} with {averaging_period} averaging. "
            f"Available: {list(BREAKPOINTS.keys())}"
        )

    result = calculate_aqi_from_breakpoints(concentration, breakpoints)

    if result is None:
        # Concentration out of range - return max
        return AQIResult(
            value=500,
            category="Severely Polluted",
            color=COLORS["Severely Polluted"],
            pollutant=pollutant_upper,
            concentration=concentration,
            unit="mg/m³" if pollutant_upper == "CO" else "µg/m³",
            message=HEALTH_MESSAGES["Severely Polluted"],
        )

    result.pollutant = pollutant_upper
    result.unit = "mg/m³" if pollutant_upper == "CO" else "µg/m³"
    result.message = HEALTH_MESSAGES[result.category]
    return result


def get_averaging_period(pollutant: str) -> str:
    """Get the default averaging period for a pollutant."""
    return AVERAGING_PERIODS.get(pollutant.upper(), "24h")
