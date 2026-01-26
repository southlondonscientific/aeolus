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
Aeolus visual theme and colour palette.

This module defines the Aeolus colour palette for AQI visualisations,
designed in collaboration with South London Scientific. The palette is:
- Anchored to the SLS brand yellow (#F7B500)
- Vibrant and confident
- Accessible (colourblind-friendly progression)
- Suitable for both screen and print

The module also bundles IBM Plex Sans for consistent typography across
platforms. IBM Plex Sans is licensed under the SIL Open Font License.

The palette can be used directly, or official AQI colours can be
requested via the `official_colours` parameter in plotting functions.
"""

from pathlib import Path
from typing import Literal

# =============================================================================
# Font Configuration
# =============================================================================

# Path to bundled fonts
_FONTS_DIR = Path(__file__).parent / "fonts"

# Font registration state
_fonts_registered = False


def _register_fonts() -> bool:
    """
    Register IBM Plex Sans with matplotlib's font manager.

    This only needs to be called once per session. Returns True if
    fonts were successfully registered.
    """
    global _fonts_registered

    if _fonts_registered:
        return True

    try:
        import matplotlib.font_manager as fm

        # Find all TTF files in our fonts directory
        font_files = list(_FONTS_DIR.glob("*.ttf"))

        if not font_files:
            return False

        # Register each font file
        for font_path in font_files:
            fm.fontManager.addfont(str(font_path))

        _fonts_registered = True
        return True

    except Exception:
        # If font registration fails, we'll fall back to system fonts
        return False


def get_font_family() -> str:
    """
    Get the font family to use for plots.

    Returns IBM Plex Sans if available, otherwise falls back to
    system sans-serif fonts.
    """
    if _register_fonts():
        return "IBM Plex Sans"
    else:
        return "sans-serif"


# =============================================================================
# Brand Colours
# =============================================================================

# South London Scientific brand colours
SLS_YELLOW = "#F7B500"
SLS_CHARCOAL = "#4A4A4A"

# =============================================================================
# Aeolus AQI Palette (Option A - Vibrant)
# =============================================================================

# Core 6-band palette (US EPA / China / India style)
AEOLUS_6_BAND = {
    "good": "#10B981",  # Emerald green
    "moderate": "#F7B500",  # SLS Yellow
    "unhealthy_sensitive": "#F97316",  # Orange
    "unhealthy": "#EF4444",  # Red
    "very_unhealthy": "#BE185D",  # Magenta/rose
    "hazardous": "#6B21A8",  # Purple
}

# Extended palette for indices needing more gradations
AEOLUS_LIME = "#84CC16"  # Yellow-green for 5-band indices

# =============================================================================
# Index-Specific Mappings
# =============================================================================

# UK DAQI (4 bands, but numbered 1-10)
UK_DAQI_COLOURS = {
    "Low": AEOLUS_6_BAND["good"],
    "Moderate": AEOLUS_6_BAND["moderate"],
    "High": AEOLUS_6_BAND["unhealthy"],
    "Very High": AEOLUS_6_BAND["hazardous"],
}

# For the 1-10 scale, we interpolate within bands
UK_DAQI_BAND_COLOURS = {
    1: AEOLUS_6_BAND["good"],
    2: AEOLUS_6_BAND["good"],
    3: AEOLUS_6_BAND["good"],
    4: AEOLUS_6_BAND["moderate"],
    5: AEOLUS_6_BAND["moderate"],
    6: AEOLUS_6_BAND["moderate"],
    7: AEOLUS_6_BAND["unhealthy"],
    8: AEOLUS_6_BAND["unhealthy"],
    9: AEOLUS_6_BAND["unhealthy"],
    10: AEOLUS_6_BAND["hazardous"],
}

# US EPA (6 bands)
US_EPA_COLOURS = {
    "Good": AEOLUS_6_BAND["good"],
    "Moderate": AEOLUS_6_BAND["moderate"],
    "Unhealthy for Sensitive Groups": AEOLUS_6_BAND["unhealthy_sensitive"],
    "Unhealthy": AEOLUS_6_BAND["unhealthy"],
    "Very Unhealthy": AEOLUS_6_BAND["very_unhealthy"],
    "Hazardous": AEOLUS_6_BAND["hazardous"],
}

# China AQI (6 bands)
CHINA_AQI_COLOURS = {
    "Excellent": AEOLUS_6_BAND["good"],
    "Good": AEOLUS_6_BAND["moderate"],
    "Lightly Polluted": AEOLUS_6_BAND["unhealthy_sensitive"],
    "Moderately Polluted": AEOLUS_6_BAND["unhealthy"],
    "Heavily Polluted": AEOLUS_6_BAND["very_unhealthy"],
    "Severely Polluted": AEOLUS_6_BAND["hazardous"],
}

# EU CAQI (5 bands)
EU_CAQI_COLOURS = {
    "Very Low": AEOLUS_6_BAND["good"],
    "Low": AEOLUS_LIME,
    "Medium": AEOLUS_6_BAND["moderate"],
    "High": AEOLUS_6_BAND["unhealthy"],
    "Very High": AEOLUS_6_BAND["very_unhealthy"],
    "Extremely Poor": AEOLUS_6_BAND["hazardous"],
}

# India NAQI (6 bands)
INDIA_NAQI_COLOURS = {
    "Good": AEOLUS_6_BAND["good"],
    "Satisfactory": AEOLUS_LIME,
    "Moderately Polluted": AEOLUS_6_BAND["moderate"],
    "Poor": AEOLUS_6_BAND["unhealthy_sensitive"],
    "Very Poor": AEOLUS_6_BAND["very_unhealthy"],
    "Severe": AEOLUS_6_BAND["hazardous"],
}

# WHO compliance levels
WHO_COMPLIANCE_COLOURS = {
    "Meets AQG": AEOLUS_6_BAND["good"],
    "Meets IT-4": AEOLUS_LIME,
    "Meets IT-3": AEOLUS_6_BAND["moderate"],
    "Meets IT-2": AEOLUS_6_BAND["unhealthy_sensitive"],
    "Meets IT-1": AEOLUS_6_BAND["unhealthy"],
    "Exceeds IT-1": AEOLUS_6_BAND["very_unhealthy"],
}

# Master mapping from index name to colour dict
INDEX_COLOURS = {
    "UK_DAQI": UK_DAQI_COLOURS,
    "US_EPA": US_EPA_COLOURS,
    "CHINA": CHINA_AQI_COLOURS,
    "EU_CAQI_ROADSIDE": EU_CAQI_COLOURS,
    "EU_CAQI_BACKGROUND": EU_CAQI_COLOURS,
    "INDIA_NAQI": INDIA_NAQI_COLOURS,
    "WHO": WHO_COMPLIANCE_COLOURS,
}

# =============================================================================
# Official Colours (for when exact regulatory colours are required)
# =============================================================================

# These are imported from the metrics module when needed
# to avoid circular imports and keep this module lightweight


def get_official_colours(index: str) -> dict[str, str]:
    """
    Get official/regulatory colours for an AQI index.

    These are the exact colours specified by the regulatory body,
    which may not be as visually harmonious as the Aeolus palette.

    Args:
        index: Index name (UK_DAQI, US_EPA, etc.)

    Returns:
        Dict mapping category names to hex colour codes
    """
    # Import here to avoid circular dependency
    from ..metrics.indices import china, eu_caqi, india_naqi, uk_daqi, us_epa

    official = {
        "UK_DAQI": {cat: uk_daqi.COLORS[i] for i, cat in uk_daqi.CATEGORIES.items()},
        "US_EPA": us_epa.COLORS,
        "CHINA": china.COLORS,
        "EU_CAQI_ROADSIDE": {
            cat: eu_caqi.COLORS[i] for i, cat in eu_caqi.CATEGORIES.items()
        },
        "EU_CAQI_BACKGROUND": {
            cat: eu_caqi.COLORS[i] for i, cat in eu_caqi.CATEGORIES.items()
        },
        "INDIA_NAQI": india_naqi.COLORS,
    }

    if index not in official:
        raise ValueError(f"No official colours defined for {index}")

    return official[index]


# =============================================================================
# Colour Utilities
# =============================================================================


def get_colour_for_category(
    category: str,
    index: str = "US_EPA",
    official_colours: bool = False,
) -> str:
    """
    Get the colour for an AQI category.

    Args:
        category: Category name (e.g., "Good", "Moderate", "Low")
        index: AQI index name
        official_colours: If True, use official regulatory colours

    Returns:
        Hex colour code
    """
    if official_colours:
        colours = get_official_colours(index)
    else:
        colours = INDEX_COLOURS.get(index, US_EPA_COLOURS)

    return colours.get(category, SLS_CHARCOAL)


def get_colour_for_value(
    value: int,
    index: str = "UK_DAQI",
    official_colours: bool = False,
) -> str:
    """
    Get the colour for a numeric AQI value.

    Useful for UK DAQI where you have values 1-10.

    Args:
        value: AQI numeric value
        index: AQI index name
        official_colours: If True, use official regulatory colours

    Returns:
        Hex colour code
    """
    if index == "UK_DAQI":
        if official_colours:
            from ..metrics.indices import uk_daqi

            return uk_daqi.COLORS.get(value, SLS_CHARCOAL)
        else:
            return UK_DAQI_BAND_COLOURS.get(value, SLS_CHARCOAL)

    # For other indices, would need to map value to category first
    raise NotImplementedError(f"get_colour_for_value not yet implemented for {index}")


def needs_dark_text(hex_colour: str) -> bool:
    """
    Determine if a colour needs dark text for readability.

    Uses relative luminance calculation.

    Args:
        hex_colour: Hex colour code (with or without #)

    Returns:
        True if dark text should be used, False for light text
    """
    hex_colour = hex_colour.lstrip("#")
    r, g, b = (
        int(hex_colour[0:2], 16),
        int(hex_colour[2:4], 16),
        int(hex_colour[4:6], 16),
    )

    # Relative luminance formula
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255

    return luminance > 0.5


# =============================================================================
# Matplotlib Theme Settings
# =============================================================================

# Default figure sizes (inches) for common use cases
FIGURE_SIZES = {
    "single_column": (3.5, 2.5),  # Journal single column
    "double_column": (7.0, 4.0),  # Journal double column
    "presentation": (10, 6),  # Slides
    "square": (5, 5),  # Square format
    "wide": (10, 4),  # Wide timeseries
}

# Typography
FONT_FAMILY = "sans-serif"
FONT_SIZE_SMALL = 8
FONT_SIZE_MEDIUM = 10
FONT_SIZE_LARGE = 12
FONT_SIZE_TITLE = 14

# DPI settings
DPI_SCREEN = 100
DPI_PRINT = 300

# Line widths
LINE_WIDTH_THIN = 0.75
LINE_WIDTH_MEDIUM = 1.5
LINE_WIDTH_THICK = 2.5

# Colours for non-AQI elements
COLOUR_AXIS = SLS_CHARCOAL
COLOUR_GRID = "#E5E5E5"
COLOUR_TEXT = SLS_CHARCOAL
COLOUR_GUIDELINE = "#DC2626"  # Red for threshold/guideline lines


def apply_aeolus_style():
    """
    Apply the Aeolus visual style to matplotlib.

    Call this at the start of your script or notebook to set
    consistent styling for all plots. This registers IBM Plex Sans
    and configures matplotlib for publication-ready output.
    """
    import matplotlib.pyplot as plt

    # Register bundled fonts
    font_family = get_font_family()

    plt.rcParams.update(
        {
            # Figure
            "figure.facecolor": "white",
            "figure.dpi": DPI_SCREEN,
            "savefig.dpi": DPI_PRINT,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.1,
            # Fonts - use IBM Plex Sans if available
            "font.family": font_family,
            "font.size": FONT_SIZE_MEDIUM,
            "axes.titlesize": FONT_SIZE_TITLE,
            "axes.labelsize": FONT_SIZE_MEDIUM,
            "axes.titleweight": "medium",  # Use medium weight for titles
            "xtick.labelsize": FONT_SIZE_SMALL,
            "ytick.labelsize": FONT_SIZE_SMALL,
            "legend.fontsize": FONT_SIZE_SMALL,
            "legend.title_fontsize": FONT_SIZE_SMALL,
            # Axes
            "axes.facecolor": "white",
            "axes.edgecolor": COLOUR_AXIS,
            "axes.labelcolor": COLOUR_TEXT,
            "axes.linewidth": LINE_WIDTH_THIN,
            "axes.grid": True,
            "axes.axisbelow": True,
            # Grid
            "grid.color": COLOUR_GRID,
            "grid.linewidth": LINE_WIDTH_THIN,
            "grid.alpha": 0.7,
            # Ticks
            "xtick.color": COLOUR_AXIS,
            "ytick.color": COLOUR_AXIS,
            "xtick.direction": "out",
            "ytick.direction": "out",
            # Lines
            "lines.linewidth": LINE_WIDTH_MEDIUM,
            # Legend
            "legend.frameon": True,
            "legend.framealpha": 0.9,
            "legend.edgecolor": COLOUR_GRID,
            # Text rendering
            "text.antialiased": True,
        }
    )
