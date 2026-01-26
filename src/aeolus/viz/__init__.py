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
Aeolus visualisation module.

Provides simple, publication-ready visualisations for air quality data
with sensible defaults and the Aeolus colour palette.

Quick start:
    >>> import aeolus
    >>> from aeolus import viz
    >>>
    >>> data = aeolus.download("AURN", ["MY1"], start, end)
    >>> fig = viz.plot_timeseries(data)
    >>> fig.savefig("timeseries.png", dpi=300)

The module uses the Aeolus colour palette by default, designed for
both screen and print. Official AQI colours can be requested via
the `official_colours` parameter.

Available functions:
    - plot_timeseries: Time series line chart with optional AQI bands
    - plot_aqi_card: Large AQI value display with colour background
    - plot_aqi_comparison: Before/after AQI card comparison
    - plot_distribution: Boxplots/violin plots by site, time period, etc.
    - plot_diurnal: Hourly patterns (shows rush hour effects)
    - plot_weekly: Day-of-week patterns (shows weekend effects)
    - plot_monthly: Monthly/seasonal patterns
    - plot_calendar: Calendar heatmap for a year
    - apply_aeolus_style: Apply Aeolus visual style to matplotlib

Colour palette:
    - theme.AEOLUS_6_BAND: Core 6-colour AQI palette
    - theme.get_colour_for_category: Get colour for a category name
    - theme.apply_aeolus_style: Apply consistent matplotlib styling
"""

from .plots import (
    plot_aqi_card,
    plot_aqi_comparison,
    plot_calendar,
    plot_distribution,
    plot_diurnal,
    plot_monthly,
    plot_timeseries,
    plot_weekly,
)
from .theme import (
    # Palette
    AEOLUS_6_BAND,
    AEOLUS_LIME,
    CHINA_AQI_COLOURS,
    EU_CAQI_COLOURS,
    FIGURE_SIZES,
    # Index mappings
    INDEX_COLOURS,
    INDIA_NAQI_COLOURS,
    SLS_CHARCOAL,
    # Brand colours
    SLS_YELLOW,
    UK_DAQI_COLOURS,
    US_EPA_COLOURS,
    WHO_COMPLIANCE_COLOURS,
    # Matplotlib
    apply_aeolus_style,
    # Utilities
    get_colour_for_category,
    get_colour_for_value,
    get_official_colours,
    needs_dark_text,
)

__all__ = [
    # Plotting functions
    "plot_timeseries",
    "plot_aqi_card",
    "plot_aqi_comparison",
    "plot_distribution",
    "plot_diurnal",
    "plot_weekly",
    "plot_monthly",
    "plot_calendar",
    # Brand
    "SLS_YELLOW",
    "SLS_CHARCOAL",
    # Palette
    "AEOLUS_6_BAND",
    "AEOLUS_LIME",
    # Index mappings
    "INDEX_COLOURS",
    "UK_DAQI_COLOURS",
    "US_EPA_COLOURS",
    "CHINA_AQI_COLOURS",
    "EU_CAQI_COLOURS",
    "INDIA_NAQI_COLOURS",
    "WHO_COMPLIANCE_COLOURS",
    # Utilities
    "get_colour_for_category",
    "get_colour_for_value",
    "get_official_colours",
    "needs_dark_text",
    # Matplotlib
    "apply_aeolus_style",
    "FIGURE_SIZES",
]
