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
Matplotlib-based plotting functions for air quality data.

These functions provide simple, publication-ready visualisations
with sensible defaults. Each returns a matplotlib Figure that can
be saved, displayed, or further customised.
"""

from typing import Literal

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .prepare import (
    AQICardSpec,
    TimeSeriesSpec,
    prepare_aqi_card,
    prepare_timeseries,
)
from .theme import (
    AEOLUS_6_BAND,
    COLOUR_GUIDELINE,
    COLOUR_TEXT,
    FIGURE_SIZES,
    LINE_WIDTH_MEDIUM,
    LINE_WIDTH_THIN,
    SLS_CHARCOAL,
    apply_aeolus_style,
    needs_dark_text,
)

# =============================================================================
# Pollutant Colours (for multi-line plots)
# =============================================================================

# Distinct colours for different pollutants when plotting multiple
POLLUTANT_COLOURS = {
    "NO2": "#3B82F6",  # Blue
    "PM2.5": "#8B5CF6",  # Purple
    "PM10": "#A855F7",  # Lighter purple
    "O3": "#06B6D4",  # Cyan
    "SO2": "#F59E0B",  # Amber
    "CO": "#6B7280",  # Grey
    "NH3": "#10B981",  # Green
    "Pb": "#EF4444",  # Red
}

# Fallback colours for unknown pollutants
FALLBACK_COLOURS = [
    "#3B82F6",
    "#8B5CF6",
    "#06B6D4",
    "#F59E0B",
    "#EF4444",
    "#10B981",
    "#6366F1",
    "#EC4899",
]


def _get_pollutant_colour(pollutant: str, index: int = 0) -> str:
    """Get a colour for a pollutant, with fallback."""
    if pollutant in POLLUTANT_COLOURS:
        return POLLUTANT_COLOURS[pollutant]
    return FALLBACK_COLOURS[index % len(FALLBACK_COLOURS)]


# =============================================================================
# Time Series Plot
# =============================================================================


def plot_timeseries(
    data: pd.DataFrame,
    pollutants: list[str] | None = None,
    downsample: bool | int = True,
    show_bands: str | None = None,
    guideline: float | None = None,
    guideline_label: str | None = None,
    title: str | None = None,
    figsize: tuple[float, float] | str | None = None,
    ax: plt.Axes | None = None,
    apply_style: bool = True,
) -> plt.Figure:
    """
    Plot a time series of air quality data.

    Args:
        data: DataFrame from aeolus.download() with columns:
              date_time, measurand, value, units
        pollutants: List of pollutants to plot (default: all)
        downsample: True for auto (~2000 points), False for none,
                   or int for specific target
        show_bands: AQI index name to show coloured background bands
                   (e.g., "UK_DAQI"). Currently shows legend only.
        guideline: Horizontal line value for threshold/guideline
        guideline_label: Label for guideline line
        title: Plot title (auto-generated if None)
        figsize: Figure size as (width, height) in inches, or preset name
                ("single_column", "double_column", "wide", "presentation")
        ax: Existing Axes to plot on (creates new figure if None)
        apply_style: Apply Aeolus matplotlib style (default True)

    Returns:
        matplotlib Figure

    Example:
        >>> import aeolus
        >>> from aeolus import viz
        >>>
        >>> data = aeolus.download("AURN", ["MY1"], start, end)
        >>> fig = viz.plot_timeseries(data, pollutants=["NO2", "PM2.5"])
        >>> fig.savefig("timeseries.png", dpi=300)
    """
    if apply_style:
        apply_aeolus_style()

    # Prepare data
    spec = prepare_timeseries(
        data=data,
        pollutants=pollutants,
        downsample=downsample,
        aqi_bands=show_bands,
        guideline=guideline,
        guideline_label=guideline_label,
        title=title,
    )

    # Create figure if needed
    if ax is None:
        if figsize is None:
            figsize = FIGURE_SIZES["wide"]
        elif isinstance(figsize, str):
            figsize = FIGURE_SIZES.get(figsize, FIGURE_SIZES["wide"])

        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    # Plot each pollutant
    lines = []
    for i, pollutant in enumerate(spec.pollutants):
        if pollutant not in spec.data.columns:
            continue

        colour = _get_pollutant_colour(pollutant, i)
        (line,) = ax.plot(
            spec.data["date_time"],
            spec.data[pollutant],
            label=pollutant,
            color=colour,
            linewidth=LINE_WIDTH_MEDIUM,
        )
        lines.append(line)

    # Add guideline if specified
    if spec.guideline_value is not None:
        label = spec.guideline_label or f"Guideline ({spec.guideline_value})"
        ax.axhline(
            y=spec.guideline_value,
            color=COLOUR_GUIDELINE,
            linestyle="--",
            linewidth=LINE_WIDTH_THIN,
            label=label,
            zorder=1,
        )

    # Labels and title
    ax.set_xlabel("Date/Time")
    ax.set_ylabel(spec.ylabel)

    if spec.title:
        ax.set_title(spec.title)
    elif spec.site_name:
        ax.set_title(spec.site_name)

    # Legend
    if len(spec.pollutants) > 1 or spec.guideline_value is not None:
        ax.legend(loc="upper right", framealpha=0.9)

    # Add AQI band legend if requested
    if spec.aqi_bands:
        _add_aqi_legend(ax, spec.aqi_bands)

    # Downsampling notice (as text annotation)
    if spec.was_downsampled:
        notice = f"Showing {spec.display_points:,} of {spec.original_points:,} points"
        ax.annotate(
            notice,
            xy=(1, 0),
            xycoords="axes fraction",
            xytext=(-5, 5),
            textcoords="offset points",
            fontsize=7,
            color="#999999",
            ha="right",
            va="bottom",
        )

    # Format x-axis dates nicely
    fig.autofmt_xdate()

    plt.tight_layout()

    return fig


def _add_aqi_legend(ax: plt.Axes, bands: list[dict]) -> None:
    """Add a small AQI colour legend to the plot."""
    patches = [
        mpatches.Patch(color=band["colour"], label=band["label"]) for band in bands
    ]

    # Add as second legend
    legend = ax.legend(
        handles=patches,
        loc="upper left",
        fontsize=7,
        title="AQI Bands",
        title_fontsize=8,
        framealpha=0.9,
    )
    ax.add_artist(legend)

    # Restore original legend if it exists
    ax.legend(loc="upper right", framealpha=0.9)


# =============================================================================
# AQI Card
# =============================================================================


def plot_aqi_card(
    value: int | float,
    category: str,
    index: str = "UK_DAQI",
    title: str | None = None,
    subtitle: str | None = None,
    figsize: tuple[float, float] = (2.5, 2.5),
    official_colours: bool = False,
    show_category: bool = True,
    ax: plt.Axes | None = None,
) -> plt.Figure:
    """
    Create an AQI card display - a large value with coloured background.

    This is designed for infographic-style communication, showing
    a single AQI value prominently with its category.

    Args:
        value: AQI value to display
        category: AQI category name (e.g., "Low", "Good", "Moderate")
        index: AQI index name for colour lookup
        title: Text above the card (e.g., "Your average was:")
        subtitle: Text below the category
        figsize: Figure size in inches
        official_colours: Use official regulatory colours instead of Aeolus palette
        show_category: Show category name below value
        ax: Existing Axes to use (creates new figure if None)

    Returns:
        matplotlib Figure

    Example:
        >>> from aeolus import viz
        >>> fig = viz.plot_aqi_card(45, "Moderate", title="Daily AQI")
        >>> fig.savefig("aqi_card.png", dpi=300)
    """
    # Prepare specification
    spec = prepare_aqi_card(
        value=value,
        category=category,
        index=index,
        title=title,
        subtitle=subtitle,
        official_colours=official_colours,
    )

    # Create figure
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    # Fill background with AQI colour
    ax.set_facecolor(spec.colour)

    # Remove axes
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Calculate positions
    center_y = 0.5
    if title:
        center_y = 0.45

    # Add value (large, centered)
    value_text = (
        str(int(value))
        if isinstance(value, float) and value == int(value)
        else str(value)
    )
    ax.text(
        0.5,
        center_y,
        value_text,
        ha="center",
        va="center",
        fontsize=48,
        fontweight="bold",
        color=spec.text_colour,
        transform=ax.transAxes,
    )

    # Add category below value
    if show_category:
        ax.text(
            0.5,
            center_y - 0.2,
            f"({category})",
            ha="center",
            va="center",
            fontsize=12,
            color=spec.text_colour,
            transform=ax.transAxes,
        )

    # Add title above (outside the coloured area if possible)
    if title:
        ax.text(
            0.5,
            0.92,
            title,
            ha="center",
            va="top",
            fontsize=11,
            color=spec.text_colour,
            transform=ax.transAxes,
        )

    # Add subtitle below
    if subtitle:
        ax.text(
            0.5,
            0.12,
            subtitle,
            ha="center",
            va="bottom",
            fontsize=9,
            color=spec.text_colour,
            transform=ax.transAxes,
        )

    plt.tight_layout(pad=0.5)

    return fig


# =============================================================================
# Comparison Cards (side by side)
# =============================================================================


def plot_aqi_comparison(
    before_value: int | float,
    before_category: str,
    after_value: int | float,
    after_category: str,
    index: str = "UK_DAQI",
    before_title: str = "Before",
    after_title: str = "After",
    figsize: tuple[float, float] = (5, 2.5),
    official_colours: bool = False,
) -> plt.Figure:
    """
    Create a before/after AQI comparison with two cards side by side.

    Args:
        before_value: AQI value for "before" card
        before_category: Category for "before" card
        after_value: AQI value for "after" card
        after_category: Category for "after" card
        index: AQI index name for colour lookup
        before_title: Title for left card
        after_title: Title for right card
        figsize: Figure size in inches
        official_colours: Use official regulatory colours

    Returns:
        matplotlib Figure
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

    plot_aqi_card(
        before_value,
        before_category,
        index,
        title=before_title,
        official_colours=official_colours,
        ax=ax1,
    )

    plot_aqi_card(
        after_value,
        after_category,
        index,
        title=after_title,
        official_colours=official_colours,
        ax=ax2,
    )

    plt.tight_layout()

    return fig
