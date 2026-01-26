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
Base types, constants, and utilities for AQI calculations.

This module provides the foundation for all AQI index implementations,
including unit conversion, pollutant standardisation, and common types.
"""

import warnings
from dataclasses import dataclass
from typing import TypedDict

import pandas as pd

# =============================================================================
# Types
# =============================================================================


class Breakpoint(TypedDict):
    """A single AQI breakpoint definition."""

    low_conc: float  # Low concentration bound (inclusive)
    high_conc: float  # High concentration bound (inclusive)
    low_aqi: int  # Low AQI bound
    high_aqi: int  # High AQI bound
    category: str  # Category name (e.g., "Low", "Moderate", "High")
    color: str  # Hex color code for display


class IndexInfo(TypedDict):
    """Metadata about an AQI index."""

    name: str  # Full name of the index
    short_name: str  # Abbreviated name
    country: str  # Country or region
    scale_min: int  # Minimum possible value
    scale_max: int  # Maximum possible value
    pollutants: list[str]  # Supported pollutants
    description: str  # Brief description
    url: str  # Reference URL


@dataclass
class AQIResult:
    """Result of an AQI calculation for a single pollutant or overall."""

    value: int | None  # AQI value (None if cannot be calculated)
    category: str | None  # Category name
    color: str | None  # Hex color code
    pollutant: str  # Pollutant name (or "_overall")
    concentration: float | None  # Input concentration (after averaging)
    unit: str  # Unit of concentration
    message: str | None = None  # Optional health message


# =============================================================================
# Unit Conversion
# =============================================================================

# Molecular weights for gas pollutants (g/mol)
# Sources:
#   - NIST WebBook: https://webbook.nist.gov/chemistry/
#   - PubChem: https://pubchem.ncbi.nlm.nih.gov/
#
# Values (g/mol):
#   NO2: 46.0055 (NIST), rounded to 46.01
#   O3:  47.9982 (NIST), rounded to 48.00
#   SO2: 64.0638 (NIST), rounded to 64.07
#   CO:  28.0101 (NIST), rounded to 28.01
MOLECULAR_WEIGHTS = {
    "NO2": 46.01,
    "O3": 48.00,
    "SO2": 64.07,
    "CO": 28.01,
}

# Standard conditions for air quality conversions: 25°C (298.15K), 1 atm (101.325 kPa)
#
# Molar volume calculated from ideal gas law: V = nRT/P
#   V = (1 mol × 0.082057 L·atm/(mol·K) × 298.15 K) / 1 atm = 24.465 L/mol
#
# The value 24.45 L/mol is the widely-used rounded value in air quality science.
# This is the standard reference condition used by:
#   - UK DEFRA: https://uk-air.defra.gov.uk/
#   - US EPA for ambient air quality
#   - EU air quality directives
#
# Note: Some regulations use 20°C (293.15K), giving 24.04 L/mol.
# We use 25°C as it is the most common reference in international AQI standards.
MOLAR_VOLUME = 24.45


def ppb_to_ugm3(concentration: float, pollutant: str) -> float:
    """
    Convert concentration from ppb to µg/m³.

    Uses the formula: µg/m³ = ppb × (molecular_weight / molar_volume)
    at standard conditions (25°C, 1 atm).

    Reference:
        This is the standard conversion used in air quality science.
        See UK DEFRA technical guidance:
        https://uk-air.defra.gov.uk/assets/documents/reports/cat06/0502160851_Conversion_Factors_Between_ppb_and.pdf

    Example conversion factors (at 25°C, 1 atm):
        - NO2: 1 ppb = 1.88 µg/m³
        - O3:  1 ppb = 1.96 µg/m³
        - SO2: 1 ppb = 2.62 µg/m³
        - CO:  1 ppb = 1.15 µg/m³

    Args:
        concentration: Concentration in ppb
        pollutant: Pollutant name (NO2, O3, SO2, CO)

    Returns:
        Concentration in µg/m³

    Raises:
        ValueError: If pollutant is not a gas with known molecular weight
    """
    pollutant_upper = pollutant.upper()
    if pollutant_upper not in MOLECULAR_WEIGHTS:
        raise ValueError(
            f"Cannot convert {pollutant} from ppb to µg/m³. "
            f"Supported pollutants: {list(MOLECULAR_WEIGHTS.keys())}"
        )

    mw = MOLECULAR_WEIGHTS[pollutant_upper]
    return concentration * (mw / MOLAR_VOLUME)


def ugm3_to_ppb(concentration: float, pollutant: str) -> float:
    """
    Convert concentration from µg/m³ to ppb.

    Uses the formula: ppb = µg/m³ × (molar_volume / molecular_weight)
    at standard conditions (25°C, 1 atm).

    Args:
        concentration: Concentration in µg/m³
        pollutant: Pollutant name (NO2, O3, SO2, CO)

    Returns:
        Concentration in ppb

    Raises:
        ValueError: If pollutant is not a gas with known molecular weight
    """
    pollutant_upper = pollutant.upper()
    if pollutant_upper not in MOLECULAR_WEIGHTS:
        raise ValueError(
            f"Cannot convert {pollutant} from µg/m³ to ppb. "
            f"Supported pollutants: {list(MOLECULAR_WEIGHTS.keys())}"
        )

    mw = MOLECULAR_WEIGHTS[pollutant_upper]
    return concentration * (MOLAR_VOLUME / mw)


def ensure_ugm3(
    concentration: float,
    pollutant: str,
    current_unit: str,
    warn: bool = True,
) -> float:
    """
    Ensure concentration is in µg/m³, converting if necessary.

    Args:
        concentration: The concentration value
        pollutant: Pollutant name
        current_unit: Current unit of the concentration
        warn: Whether to warn about conversions

    Returns:
        Concentration in µg/m³
    """
    unit_lower = current_unit.lower().strip()

    # Already in µg/m³
    if unit_lower in ("ug/m3", "µg/m³", "ugm3", "µg/m3", "ug/m³"):
        return concentration

    # Convert from ppb
    if unit_lower in ("ppb", "parts per billion"):
        if warn:
            warnings.warn(
                f"Converting {pollutant} from ppb to µg/m³ for AQI calculation. "
                f"Conversion assumes standard conditions (25°C, 1 atm).",
                UserWarning,
                stacklevel=3,
            )
        return ppb_to_ugm3(concentration, pollutant)

    # Convert from ppm (CO is often reported in ppm)
    if unit_lower in ("ppm", "parts per million"):
        if warn:
            warnings.warn(
                f"Converting {pollutant} from ppm to µg/m³ for AQI calculation. "
                f"Conversion assumes standard conditions (25°C, 1 atm).",
                UserWarning,
                stacklevel=3,
            )
        # ppm to ppb, then ppb to µg/m³
        return ppb_to_ugm3(concentration * 1000, pollutant)

    # Convert from mg/m³
    if unit_lower in ("mg/m3", "mg/m³"):
        if warn:
            warnings.warn(
                f"Converting {pollutant} from mg/m³ to µg/m³ for AQI calculation.",
                UserWarning,
                stacklevel=3,
            )
        return concentration * 1000

    # Unknown unit - warn and assume µg/m³
    warnings.warn(
        f"Unknown unit '{current_unit}' for {pollutant}. "
        f"Assuming µg/m³ for AQI calculation.",
        UserWarning,
        stacklevel=3,
    )
    return concentration


# =============================================================================
# Pollutant Standardisation
# =============================================================================

# Map common pollutant names to standard forms
POLLUTANT_ALIASES = {
    # PM2.5 variants
    "pm2.5": "PM2.5",
    "pm25": "PM2.5",
    "PM25": "PM2.5",
    "pm 2.5": "PM2.5",
    "PM 2.5": "PM2.5",
    "fine particulate": "PM2.5",
    "fine particles": "PM2.5",
    # PM10 variants
    "pm10": "PM10",
    "PM 10": "PM10",
    "pm 10": "PM10",
    "coarse particulate": "PM10",
    # Ozone variants
    "o3": "O3",
    "ozone": "O3",
    "Ozone": "O3",
    "OZONE": "O3",
    # Nitrogen dioxide variants
    "no2": "NO2",
    "nitrogen dioxide": "NO2",
    "nitrogen_dioxide": "NO2",
    "Nitrogen Dioxide": "NO2",
    # Sulphur dioxide variants
    "so2": "SO2",
    "sulfur dioxide": "SO2",
    "sulphur dioxide": "SO2",
    "sulfur_dioxide": "SO2",
    "sulphur_dioxide": "SO2",
    "Sulfur Dioxide": "SO2",
    "Sulphur Dioxide": "SO2",
    # Carbon monoxide variants
    "co": "CO",
    "carbon monoxide": "CO",
    "carbon_monoxide": "CO",
    "Carbon Monoxide": "CO",
}


def standardise_pollutant(pollutant: str) -> str | None:
    """
    Standardise a pollutant name to its canonical form.

    Args:
        pollutant: Pollutant name in any common format

    Returns:
        Standardised pollutant name, or None if not recognised
    """
    # Check if already standard
    if pollutant in ("PM2.5", "PM10", "O3", "NO2", "SO2", "CO"):
        return pollutant

    # Check aliases
    return POLLUTANT_ALIASES.get(pollutant)


# =============================================================================
# Breakpoint Interpolation
# =============================================================================


def calculate_aqi_from_breakpoints(
    concentration: float,
    breakpoints: list[Breakpoint],
) -> AQIResult | None:
    """
    Calculate AQI value using linear interpolation between breakpoints.

    This is the standard EPA-style calculation used by most AQI systems:

    AQI = ((high_aqi - low_aqi) / (high_conc - low_conc)) * (conc - low_conc) + low_aqi

    Args:
        concentration: Pollutant concentration (must be in correct units)
        breakpoints: List of breakpoint definitions, sorted by concentration

    Returns:
        AQIResult with interpolated value, or None if concentration is out of range
    """
    for bp in breakpoints:
        if bp["low_conc"] <= concentration <= bp["high_conc"]:
            # Linear interpolation
            aqi_range = bp["high_aqi"] - bp["low_aqi"]
            conc_range = bp["high_conc"] - bp["low_conc"]

            if conc_range == 0:
                # Edge case: single-point breakpoint
                aqi_value = bp["low_aqi"]
            else:
                aqi_value = (aqi_range / conc_range) * (
                    concentration - bp["low_conc"]
                ) + bp["low_aqi"]

            return AQIResult(
                value=round(aqi_value),
                category=bp["category"],
                color=bp["color"],
                pollutant="",  # Set by caller
                concentration=concentration,
                unit="µg/m³",
            )

    # Concentration out of range
    return None


# =============================================================================
# Data Validation
# =============================================================================


def validate_data(df: pd.DataFrame) -> None:
    """
    Validate that a DataFrame has the required columns for AQI calculation.

    Args:
        df: Input DataFrame

    Raises:
        ValueError: If required columns are missing
    """
    required_columns = {"date_time", "measurand", "value", "units"}
    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"DataFrame missing required columns for AQI calculation: {missing}. "
            f"Expected columns from aeolus.download() output."
        )


def get_available_pollutants(df: pd.DataFrame) -> set[str]:
    """
    Get the set of standardised pollutants available in the data.

    Args:
        df: Input DataFrame with 'measurand' column

    Returns:
        Set of standardised pollutant names
    """
    pollutants = set()
    unknown = set()

    for measurand in df["measurand"].unique():
        standard = standardise_pollutant(measurand)
        if standard:
            pollutants.add(standard)
        else:
            unknown.add(measurand)

    if unknown:
        warnings.warn(
            f"Unknown pollutants will be skipped: {unknown}",
            UserWarning,
            stacklevel=2,
        )

    return pollutants
