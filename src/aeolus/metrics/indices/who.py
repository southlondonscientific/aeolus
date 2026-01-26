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
WHO Air Quality Guidelines (2021) implementation.

The WHO guidelines are not an AQI per se, but rather recommended concentration
limits for protecting human health. This module provides functions to check
compliance with the guideline values and interim targets.

The 2021 guidelines significantly tightened limits from the 2005 version,
particularly for PM2.5 (5 µg/m³ annual, down from 10) and NO2 (10 µg/m³ annual,
down from 40).

Reference: https://www.who.int/publications/i/item/9789240034228

Interim Targets (IT-1 through IT-4) provide stepping stones for countries
with high pollution levels to progressively work toward the final guidelines.

Pollutants covered:
- PM2.5: Annual and 24-hour
- PM10: Annual and 24-hour
- O3: Peak season (8-hour)
- NO2: Annual and 24-hour
- SO2: 24-hour
- CO: 24-hour and 8-hour
"""

from dataclasses import dataclass
from typing import Literal

from ..base import IndexInfo
from . import register_index

# =============================================================================
# Index Metadata
# =============================================================================

INDEX_INFO: IndexInfo = {
    "name": "WHO Air Quality Guidelines",
    "short_name": "WHO",
    "country": "Global",
    "scale_min": 0,
    "scale_max": 1,  # Binary: meets/exceeds guideline
    "pollutants": ["PM2.5", "PM10", "O3", "NO2", "SO2", "CO"],
    "description": (
        "The WHO Global Air Quality Guidelines (2021) provide recommended "
        "concentration limits for protecting human health. Includes guideline "
        "values (AQG) and interim targets (IT-1 to IT-4) for progressive "
        "improvement."
    ),
    "url": "https://www.who.int/publications/i/item/9789240034228",
}

# Register this index
register_index("WHO", INDEX_INFO)


# =============================================================================
# Types
# =============================================================================

TargetLevel = Literal["AQG", "IT-1", "IT-2", "IT-3", "IT-4"]
AveragingPeriod = Literal["annual", "24h", "8h", "peak_season", "1h", "15min", "10min"]


@dataclass
class GuidelineResult:
    """Result of checking against WHO guidelines."""

    pollutant: str
    concentration: float
    unit: str
    averaging_period: AveragingPeriod
    target_level: TargetLevel
    guideline_value: float
    meets_guideline: bool
    exceedance_ratio: float  # concentration / guideline_value
    message: str


# =============================================================================
# Guideline Values (WHO 2021)
# =============================================================================

# All values in µg/m³ except CO which is in mg/m³

# PM2.5 Guidelines
PM25_GUIDELINES = {
    "annual": {
        "AQG": 5,
        "IT-4": 10,
        "IT-3": 15,
        "IT-2": 25,
        "IT-1": 35,
    },
    "24h": {
        "AQG": 15,
        "IT-4": 25,
        "IT-3": 37.5,
        "IT-2": 50,
        "IT-1": 75,
    },
}

# PM10 Guidelines
PM10_GUIDELINES = {
    "annual": {
        "AQG": 15,
        "IT-4": 20,
        "IT-3": 30,
        "IT-2": 50,
        "IT-1": 70,
    },
    "24h": {
        "AQG": 45,
        "IT-4": 50,
        "IT-3": 75,
        "IT-2": 100,
        "IT-1": 150,
    },
}

# O3 Guidelines (peak season = 6-month running average of daily 8-hr max)
O3_GUIDELINES = {
    "peak_season": {
        "AQG": 60,
        "IT-2": 70,
        "IT-1": 100,
    },
    "8h": {
        "AQG": 100,  # Daily 8-hour max, not to be exceeded
        "IT-2": 120,
        "IT-1": 160,
    },
}

# NO2 Guidelines
NO2_GUIDELINES = {
    "annual": {
        "AQG": 10,
        "IT-3": 20,
        "IT-2": 30,
        "IT-1": 40,
    },
    "24h": {
        "AQG": 25,
        "IT-3": 50,
        "IT-2": 75,
        "IT-1": 120,
    },
    "1h": {
        "AQG": 200,  # No interim targets for 1-hour
    },
}

# SO2 Guidelines
SO2_GUIDELINES = {
    "24h": {
        "AQG": 40,
        "IT-2": 50,
        "IT-1": 125,
    },
    "10min": {
        "AQG": 500,  # No interim targets for 10-minute
    },
}

# CO Guidelines (values in mg/m³, not µg/m³)
CO_GUIDELINES = {
    "24h": {
        "AQG": 4,  # mg/m³
    },
    "8h": {
        "AQG": 10,  # mg/m³
    },
    "1h": {
        "AQG": 35,  # mg/m³
    },
    "15min": {
        "AQG": 100,  # mg/m³
    },
}

# Combined guidelines dictionary
GUIDELINES = {
    "PM2.5": PM25_GUIDELINES,
    "PM10": PM10_GUIDELINES,
    "O3": O3_GUIDELINES,
    "NO2": NO2_GUIDELINES,
    "SO2": SO2_GUIDELINES,
    "CO": CO_GUIDELINES,
}

# Default averaging periods for each pollutant
DEFAULT_AVERAGING_PERIODS = {
    "PM2.5": "annual",
    "PM10": "annual",
    "O3": "8h",
    "NO2": "annual",
    "SO2": "24h",
    "CO": "24h",
}


# =============================================================================
# Calculation Functions
# =============================================================================


def check_guideline(
    concentration: float,
    pollutant: str,
    averaging_period: AveragingPeriod | None = None,
    target_level: TargetLevel = "AQG",
) -> GuidelineResult:
    """
    Check if a concentration meets a WHO guideline or interim target.

    Args:
        concentration: Pollutant concentration (µg/m³, or mg/m³ for CO)
        pollutant: Pollutant name (PM2.5, PM10, O3, NO2, SO2, CO)
        averaging_period: Averaging period (annual, 24h, 8h, etc.)
                         If None, uses default for pollutant
        target_level: Target to check against (AQG, IT-1, IT-2, IT-3, IT-4)

    Returns:
        GuidelineResult with compliance status and details

    Raises:
        ValueError: If pollutant, period, or target not supported
    """
    pollutant_upper = pollutant.upper()
    if pollutant_upper == "PM2.5":
        pollutant_upper = "PM2.5"

    if pollutant_upper not in GUIDELINES:
        raise ValueError(
            f"Pollutant '{pollutant}' not covered by WHO guidelines. "
            f"Supported: {list(GUIDELINES.keys())}"
        )

    # Get averaging period
    if averaging_period is None:
        averaging_period = DEFAULT_AVERAGING_PERIODS[pollutant_upper]

    pollutant_guidelines = GUIDELINES[pollutant_upper]

    if averaging_period not in pollutant_guidelines:
        raise ValueError(
            f"Averaging period '{averaging_period}' not available for {pollutant_upper}. "
            f"Available: {list(pollutant_guidelines.keys())}"
        )

    period_guidelines = pollutant_guidelines[averaging_period]

    if target_level not in period_guidelines:
        available = list(period_guidelines.keys())
        raise ValueError(
            f"Target level '{target_level}' not available for {pollutant_upper} {averaging_period}. "
            f"Available: {available}"
        )

    guideline_value = period_guidelines[target_level]
    meets = concentration <= guideline_value
    ratio = concentration / guideline_value if guideline_value > 0 else float("inf")

    # Generate message
    unit = "mg/m³" if pollutant_upper == "CO" else "µg/m³"
    if meets:
        message = (
            f"{pollutant_upper} concentration ({concentration:.1f} {unit}) meets "
            f"WHO {target_level} guideline ({guideline_value} {unit}) for {averaging_period} average."
        )
    else:
        pct_over = (ratio - 1) * 100
        message = (
            f"{pollutant_upper} concentration ({concentration:.1f} {unit}) exceeds "
            f"WHO {target_level} guideline ({guideline_value} {unit}) by {pct_over:.0f}%."
        )

    return GuidelineResult(
        pollutant=pollutant_upper,
        concentration=concentration,
        unit=unit,
        averaging_period=averaging_period,
        target_level=target_level,
        guideline_value=guideline_value,
        meets_guideline=meets,
        exceedance_ratio=ratio,
        message=message,
    )


def get_all_targets(
    concentration: float,
    pollutant: str,
    averaging_period: AveragingPeriod | None = None,
) -> dict[TargetLevel, GuidelineResult]:
    """
    Check concentration against all available WHO targets for a pollutant.

    Args:
        concentration: Pollutant concentration
        pollutant: Pollutant name
        averaging_period: Averaging period (uses default if None)

    Returns:
        Dict mapping target level to GuidelineResult
    """
    pollutant_upper = pollutant.upper()
    if pollutant_upper == "PM2.5":
        pollutant_upper = "PM2.5"

    if averaging_period is None:
        averaging_period = DEFAULT_AVERAGING_PERIODS.get(pollutant_upper, "24h")

    pollutant_guidelines = GUIDELINES.get(pollutant_upper, {})
    period_guidelines = pollutant_guidelines.get(averaging_period, {})

    results = {}
    for target_level in period_guidelines.keys():
        results[target_level] = check_guideline(
            concentration,
            pollutant_upper,
            averaging_period,
            target_level,
        )

    return results


def get_highest_met_target(
    concentration: float,
    pollutant: str,
    averaging_period: AveragingPeriod | None = None,
) -> TargetLevel | None:
    """
    Find the most stringent WHO target that a concentration meets.

    Args:
        concentration: Pollutant concentration
        pollutant: Pollutant name
        averaging_period: Averaging period (uses default if None)

    Returns:
        Most stringent target level met (AQG > IT-4 > IT-3 > IT-2 > IT-1),
        or None if no targets are met
    """
    results = get_all_targets(concentration, pollutant, averaging_period)

    # Order from most to least stringent
    target_order = ["AQG", "IT-4", "IT-3", "IT-2", "IT-1"]

    for target in target_order:
        if target in results and results[target].meets_guideline:
            return target

    return None


def get_guideline_value(
    pollutant: str,
    averaging_period: AveragingPeriod | None = None,
    target_level: TargetLevel = "AQG",
) -> float:
    """
    Get a specific WHO guideline value.

    Args:
        pollutant: Pollutant name
        averaging_period: Averaging period (uses default if None)
        target_level: Target level (AQG, IT-1, etc.)

    Returns:
        Guideline value in µg/m³ (or mg/m³ for CO)
    """
    pollutant_upper = pollutant.upper()
    if pollutant_upper == "PM2.5":
        pollutant_upper = "PM2.5"

    if averaging_period is None:
        averaging_period = DEFAULT_AVERAGING_PERIODS.get(pollutant_upper, "24h")

    return GUIDELINES[pollutant_upper][averaging_period][target_level]


def list_available_targets(
    pollutant: str,
    averaging_period: AveragingPeriod | None = None,
) -> list[TargetLevel]:
    """
    List available target levels for a pollutant and averaging period.

    Args:
        pollutant: Pollutant name
        averaging_period: Averaging period (uses default if None)

    Returns:
        List of available target levels
    """
    pollutant_upper = pollutant.upper()
    if pollutant_upper == "PM2.5":
        pollutant_upper = "PM2.5"

    if averaging_period is None:
        averaging_period = DEFAULT_AVERAGING_PERIODS.get(pollutant_upper, "24h")

    pollutant_guidelines = GUIDELINES.get(pollutant_upper, {})
    period_guidelines = pollutant_guidelines.get(averaging_period, {})

    return list(period_guidelines.keys())
