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
    SLS_LIGHT_GREY,
    apply_aeolus_style,
    get_aeolus_cmap,
    get_pollutant_colour,
    needs_dark_text,
)

# =============================================================================
# Helper Functions
# =============================================================================


def _get_site_label(data: pd.DataFrame) -> str | None:
    """
    Extract a site label from the data for use in titles.

    Returns:
        Site name if single site, "N sites" if multiple, None if no site info
    """
    if "site_name" in data.columns:
        sites = data["site_name"].dropna().unique()
        if len(sites) == 1:
            return str(sites[0])
        elif len(sites) > 1:
            return f"{len(sites)} sites"
    elif "site_code" in data.columns:
        sites = data["site_code"].dropna().unique()
        if len(sites) == 1:
            return str(sites[0])
        elif len(sites) > 1:
            return f"{len(sites)} sites"
    return None


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

        colour = get_pollutant_colour(pollutant, i)
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
            color=SLS_LIGHT_GREY,
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


# =============================================================================
# Distribution Plots (Boxplots / Violin)
# =============================================================================


def plot_distribution(
    data: pd.DataFrame,
    pollutant: str,
    group_by: Literal["site", "month", "weekday", "hour", "year"] = "site",
    style: Literal["box", "violin", "both"] = "box",
    show_points: bool = False,
    show_mean: bool = True,
    title: str | None = None,
    figsize: tuple[float, float] | str | None = None,
    ax: plt.Axes | None = None,
    apply_style: bool = True,
) -> plt.Figure:
    """
    Plot distribution of a pollutant grouped by a categorical variable.

    Creates boxplots or violin plots showing the distribution of
    concentrations across sites, months, days of week, or hours.

    Args:
        data: DataFrame from aeolus.download() with columns:
              date_time, measurand, value, units, (site_name/site_code)
        pollutant: Pollutant to plot (e.g., "PM2.5", "NO2")
        group_by: How to group the data:
            - "site": By monitoring site
            - "month": By month (1-12)
            - "weekday": By day of week (Mon-Sun)
            - "hour": By hour of day (0-23)
            - "year": By year
        style: Plot style - "box", "violin", or "both"
        show_points: Overlay individual data points (jittered)
        show_mean: Show mean as a marker on each box/violin
        title: Plot title (auto-generated if None)
        figsize: Figure size as (width, height) or preset name
        ax: Existing Axes to plot on
        apply_style: Apply Aeolus matplotlib style

    Returns:
        matplotlib Figure

    Example:
        >>> fig = viz.plot_distribution(data, "NO2", group_by="month")
        >>> fig.savefig("no2_monthly_distribution.png")
    """
    if apply_style:
        apply_aeolus_style()

    # Filter to requested pollutant
    df = data[data["measurand"] == pollutant].copy()
    if df.empty:
        raise ValueError(f"No data found for pollutant: {pollutant}")

    # Ensure datetime
    df["date_time"] = pd.to_datetime(df["date_time"])

    # Create grouping variable
    if group_by == "site":
        if "site_name" in df.columns:
            df["group"] = df["site_name"]
        elif "site_code" in df.columns:
            df["group"] = df["site_code"]
        else:
            raise ValueError(
                "Data must have 'site_name' or 'site_code' for group_by='site'"
            )
        x_label = "Site"
        order = None  # Keep original order
    elif group_by == "month":
        df["group"] = df["date_time"].dt.month
        x_label = "Month"
        order = list(range(1, 13))
    elif group_by == "weekday":
        df["group"] = df["date_time"].dt.dayofweek
        x_label = "Day of Week"
        order = list(range(7))
    elif group_by == "hour":
        df["group"] = df["date_time"].dt.hour
        x_label = "Hour of Day"
        order = list(range(24))
    elif group_by == "year":
        df["group"] = df["date_time"].dt.year
        x_label = "Year"
        order = sorted(df["date_time"].dt.year.unique())
    else:
        raise ValueError(f"Unknown group_by: {group_by}")

    # Get unique groups in order
    if order is None:
        groups = df["group"].unique()
    else:
        groups = [g for g in order if g in df["group"].values]

    # Prepare data for plotting
    plot_data = [df[df["group"] == g]["value"].dropna().values for g in groups]

    # Create figure
    if ax is None:
        if figsize is None:
            # Adaptive width based on number of groups
            width = max(6, min(12, len(groups) * 0.5))
            figsize = (width, 4)
        elif isinstance(figsize, str):
            figsize = FIGURE_SIZES.get(figsize, FIGURE_SIZES["wide"])
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    # Get colour for this pollutant
    colour = get_pollutant_colour(pollutant)

    # Plot based on style
    positions = np.arange(len(groups))

    if style in ("box", "both"):
        # Refined boxplot styling - slimmer boxes, subtle outliers
        flierprops = dict(
            marker="o",
            markerfacecolor="none",
            markeredgecolor=SLS_LIGHT_GREY,
            markeredgewidth=0.5,
            markersize=3,
            alpha=0.6,
        )
        bp = ax.boxplot(
            plot_data,
            positions=positions,
            widths=0.5 if style == "box" else 0.25,
            patch_artist=True,
            showfliers=not show_points,  # Hide outliers if showing all points
            flierprops=flierprops,
        )
        # Style the boxes - lighter fill, thinner lines
        for patch in bp["boxes"]:
            patch.set_facecolor(colour)
            patch.set_alpha(0.5 if style == "both" else 0.65)
            patch.set_linewidth(LINE_WIDTH_THIN)
            patch.set_edgecolor(colour)
        for element in ["whiskers", "caps"]:
            for line in bp[element]:
                line.set_color(colour)
                line.set_linewidth(LINE_WIDTH_THIN)
        for median in bp["medians"]:
            median.set_color("white")
            median.set_linewidth(LINE_WIDTH_MEDIUM)

    if style in ("violin", "both"):
        # Filter out empty arrays for violin plot
        valid_data = [(p, d) for p, d in zip(positions, plot_data) if len(d) > 0]
        if valid_data:
            valid_positions, valid_plot_data = zip(*valid_data)
            vp = ax.violinplot(
                valid_plot_data,
                positions=valid_positions,
                widths=0.8 if style == "violin" else 0.6,
                showmeans=False,
                showmedians=style == "violin",
            )
            # Style violins
            for body in vp["bodies"]:
                body.set_facecolor(colour)
                body.set_alpha(0.4 if style == "both" else 0.7)
                body.set_edgecolor(colour)

    # Show individual points
    if show_points:
        for i, (pos, vals) in enumerate(zip(positions, plot_data)):
            if len(vals) > 0:
                # Jitter x positions
                jitter = np.random.uniform(-0.15, 0.15, len(vals))
                ax.scatter(
                    pos + jitter,
                    vals,
                    alpha=0.3,
                    s=8,
                    color=colour,
                    zorder=1,
                )

    # Show means
    if show_mean:
        means = [np.mean(d) if len(d) > 0 else np.nan for d in plot_data]
        ax.scatter(
            positions,
            means,
            marker="D",
            s=30,
            color="white",
            edgecolor=SLS_CHARCOAL,
            linewidth=1.5,
            zorder=10,
            label="Mean",
        )

    # Labels
    ax.set_xticks(positions)
    if group_by == "weekday":
        ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    elif group_by == "month":
        ax.set_xticklabels(["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    else:
        ax.set_xticklabels(
            groups,
            rotation=45 if group_by == "site" else 0,
            ha="right" if group_by == "site" else "center",
        )

    ax.set_xlabel(x_label)

    # Get units
    units = df["units"].iloc[0] if "units" in df.columns else ""
    ax.set_ylabel(f"{pollutant} ({units})" if units else pollutant)

    # Title
    if title:
        ax.set_title(title)
    else:
        site_label = _get_site_label(data)
        if site_label:
            ax.set_title(f"{pollutant} Distribution by {x_label} - {site_label}")
        else:
            ax.set_title(f"{pollutant} Distribution by {x_label}")

    if show_mean:
        ax.legend(loc="upper right", framealpha=0.9)

    plt.tight_layout()

    return fig


# =============================================================================
# Temporal Pattern Plots
# =============================================================================


def plot_diurnal(
    data: pd.DataFrame,
    pollutants: list[str] | None = None,
    show_ci: bool = True,
    ci_level: float = 0.95,
    show_range: bool = False,
    title: str | None = None,
    figsize: tuple[float, float] | str | None = None,
    ax: plt.Axes | None = None,
    apply_style: bool = True,
) -> plt.Figure:
    """
    Plot diurnal (hourly) patterns showing average concentration by hour of day.

    This is one of the most useful plots for understanding pollution sources -
    traffic-related pollutants (NO2, PM) typically show rush hour peaks.

    Args:
        data: DataFrame from aeolus.download()
        pollutants: List of pollutants to plot (default: all)
        show_ci: Show confidence interval band around the mean
        ci_level: Confidence level (default 0.95 = 95%)
        show_range: Show min-max range instead of CI
        title: Plot title
        figsize: Figure size
        ax: Existing Axes to plot on
        apply_style: Apply Aeolus matplotlib style

    Returns:
        matplotlib Figure

    Example:
        >>> fig = viz.plot_diurnal(data, pollutants=["NO2", "O3"])
        >>> fig.savefig("diurnal_pattern.png")
    """
    if apply_style:
        apply_aeolus_style()

    # Get available pollutants
    available = data["measurand"].unique().tolist()
    if pollutants is None:
        pollutants = available
    else:
        pollutants = [p for p in pollutants if p in available]

    if not pollutants:
        raise ValueError("No valid pollutants found in data")

    # Ensure datetime
    df = data.copy()
    df["date_time"] = pd.to_datetime(df["date_time"])
    df["hour"] = df["date_time"].dt.hour

    # Create figure
    if ax is None:
        if figsize is None:
            figsize = FIGURE_SIZES.get("wide", (10, 4))
        elif isinstance(figsize, str):
            figsize = FIGURE_SIZES.get(figsize, FIGURE_SIZES["wide"])
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    hours = np.arange(24)

    for i, pollutant in enumerate(pollutants):
        p_data = df[df["measurand"] == pollutant]
        colour = get_pollutant_colour(pollutant, i)

        # Calculate statistics by hour
        hourly = p_data.groupby("hour")["value"].agg(
            ["mean", "std", "count", "min", "max"]
        )

        # Plot mean line
        ax.plot(
            hours,
            hourly["mean"],
            color=colour,
            linewidth=LINE_WIDTH_MEDIUM,
            label=pollutant,
            marker="o",
            markersize=4,
        )

        # Add uncertainty band
        if show_range:
            ax.fill_between(
                hours,
                hourly["min"],
                hourly["max"],
                color=colour,
                alpha=0.2,
            )
        elif show_ci:
            # Calculate confidence interval
            from scipy import stats

            ci_mult = stats.t.ppf((1 + ci_level) / 2, hourly["count"] - 1)
            ci = ci_mult * hourly["std"] / np.sqrt(hourly["count"])
            ci = ci.fillna(0)

            ax.fill_between(
                hours,
                hourly["mean"] - ci,
                hourly["mean"] + ci,
                color=colour,
                alpha=0.2,
            )

    # Labels
    ax.set_xlabel("Hour of Day")
    ax.set_xticks(hours[::2])  # Every 2 hours
    ax.set_xticklabels([f"{h:02d}:00" for h in hours[::2]])

    # Y label with units if single pollutant
    if len(pollutants) == 1:
        units = (
            df[df["measurand"] == pollutants[0]]["units"].iloc[0]
            if "units" in df.columns
            else ""
        )
        ax.set_ylabel(f"{pollutants[0]} ({units})" if units else pollutants[0])
    else:
        ax.set_ylabel("Concentration")

    # Title
    if title:
        ax.set_title(title)
    else:
        site_label = _get_site_label(data)
        if site_label:
            ax.set_title(f"Diurnal Pattern - {site_label}")
        else:
            ax.set_title("Diurnal Pattern")

    ax.legend(loc="upper right", framealpha=0.9)
    ax.set_xlim(-0.5, 23.5)

    plt.tight_layout()

    return fig


def plot_weekly(
    data: pd.DataFrame,
    pollutants: list[str] | None = None,
    show_ci: bool = True,
    title: str | None = None,
    figsize: tuple[float, float] | str | None = None,
    ax: plt.Axes | None = None,
    apply_style: bool = True,
) -> plt.Figure:
    """
    Plot weekly patterns showing average concentration by day of week.

    Useful for identifying weekend effects - many pollutants show lower
    concentrations on weekends due to reduced traffic and industrial activity.

    Args:
        data: DataFrame from aeolus.download()
        pollutants: List of pollutants to plot (default: all)
        show_ci: Show 95% confidence interval
        title: Plot title
        figsize: Figure size
        ax: Existing Axes to plot on
        apply_style: Apply Aeolus matplotlib style

    Returns:
        matplotlib Figure

    Example:
        >>> fig = viz.plot_weekly(data, pollutants=["NO2", "PM2.5"])
        >>> fig.savefig("weekly_pattern.png")
    """
    if apply_style:
        apply_aeolus_style()

    # Get available pollutants
    available = data["measurand"].unique().tolist()
    if pollutants is None:
        pollutants = available
    else:
        pollutants = [p for p in pollutants if p in available]

    if not pollutants:
        raise ValueError("No valid pollutants found in data")

    df = data.copy()
    df["date_time"] = pd.to_datetime(df["date_time"])
    df["weekday"] = df["date_time"].dt.dayofweek

    # Create figure
    if ax is None:
        if figsize is None:
            figsize = (8, 4)
        elif isinstance(figsize, str):
            figsize = FIGURE_SIZES.get(figsize, (8, 4))
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    days = np.arange(7)
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    width = 0.8 / len(pollutants)

    for i, pollutant in enumerate(pollutants):
        p_data = df[df["measurand"] == pollutant]
        colour = get_pollutant_colour(pollutant, i)

        daily = p_data.groupby("weekday")["value"].agg(["mean", "std", "count"])

        # Position bars
        pos = days + (i - len(pollutants) / 2 + 0.5) * width

        if show_ci:
            from scipy import stats

            ci_mult = stats.t.ppf(0.975, daily["count"] - 1)
            ci = ci_mult * daily["std"] / np.sqrt(daily["count"])
            ci = ci.fillna(0)
            yerr = ci
        else:
            yerr = None

        ax.bar(
            pos,
            daily["mean"],
            width=width,
            color=colour,
            alpha=0.8,
            label=pollutant,
            yerr=yerr,
            capsize=3,
            error_kw={"linewidth": 1, "capthick": 1},
        )

    ax.set_xlabel("Day of Week")
    ax.set_xticks(days)
    ax.set_xticklabels(day_labels)

    if len(pollutants) == 1:
        units = (
            df[df["measurand"] == pollutants[0]]["units"].iloc[0]
            if "units" in df.columns
            else ""
        )
        ax.set_ylabel(f"{pollutants[0]} ({units})" if units else pollutants[0])
    else:
        ax.set_ylabel("Concentration")

    if title:
        ax.set_title(title)
    else:
        site_label = _get_site_label(data)
        if site_label:
            ax.set_title(f"Weekly Pattern - {site_label}")
        else:
            ax.set_title("Weekly Pattern")

    ax.legend(loc="upper right", framealpha=0.9)

    plt.tight_layout()

    return fig


def plot_monthly(
    data: pd.DataFrame,
    pollutants: list[str] | None = None,
    show_ci: bool = True,
    style: Literal["bar", "line"] = "bar",
    title: str | None = None,
    figsize: tuple[float, float] | str | None = None,
    ax: plt.Axes | None = None,
    apply_style: bool = True,
) -> plt.Figure:
    """
    Plot monthly/seasonal patterns showing average concentration by month.

    Useful for identifying seasonal patterns - O3 typically peaks in summer,
    while PM and NO2 often peak in winter.

    Args:
        data: DataFrame from aeolus.download()
        pollutants: List of pollutants to plot (default: all)
        show_ci: Show 95% confidence interval
        style: "bar" for bar chart, "line" for line plot
        title: Plot title
        figsize: Figure size
        ax: Existing Axes to plot on
        apply_style: Apply Aeolus matplotlib style

    Returns:
        matplotlib Figure

    Example:
        >>> fig = viz.plot_monthly(data, pollutants=["O3", "NO2"])
        >>> fig.savefig("seasonal_pattern.png")
    """
    if apply_style:
        apply_aeolus_style()

    available = data["measurand"].unique().tolist()
    if pollutants is None:
        pollutants = available
    else:
        pollutants = [p for p in pollutants if p in available]

    if not pollutants:
        raise ValueError("No valid pollutants found in data")

    df = data.copy()
    df["date_time"] = pd.to_datetime(df["date_time"])
    df["month"] = df["date_time"].dt.month

    if ax is None:
        if figsize is None:
            figsize = (10, 4)
        elif isinstance(figsize, str):
            figsize = FIGURE_SIZES.get(figsize, (10, 4))
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    months = np.arange(1, 13)
    month_labels = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]

    if style == "bar":
        width = 0.8 / len(pollutants)

        for i, pollutant in enumerate(pollutants):
            p_data = df[df["measurand"] == pollutant]
            colour = get_pollutant_colour(pollutant, i)

            monthly = p_data.groupby("month")["value"].agg(["mean", "std", "count"])

            pos = months + (i - len(pollutants) / 2 + 0.5) * width

            if show_ci:
                from scipy import stats

                ci_mult = stats.t.ppf(0.975, monthly["count"] - 1)
                ci = ci_mult * monthly["std"] / np.sqrt(monthly["count"])
                ci = ci.fillna(0)
                yerr = ci
            else:
                yerr = None

            ax.bar(
                pos,
                monthly["mean"],
                width=width,
                color=colour,
                alpha=0.8,
                label=pollutant,
                yerr=yerr,
                capsize=2,
                error_kw={"linewidth": 1, "capthick": 1},
            )

    else:  # line style
        for i, pollutant in enumerate(pollutants):
            p_data = df[df["measurand"] == pollutant]
            colour = get_pollutant_colour(pollutant, i)

            monthly = p_data.groupby("month")["value"].agg(["mean", "std", "count"])

            ax.plot(
                months,
                monthly["mean"],
                color=colour,
                linewidth=LINE_WIDTH_MEDIUM,
                label=pollutant,
                marker="o",
                markersize=5,
            )

            if show_ci:
                from scipy import stats

                ci_mult = stats.t.ppf(0.975, monthly["count"] - 1)
                ci = ci_mult * monthly["std"] / np.sqrt(monthly["count"])
                ci = ci.fillna(0)

                ax.fill_between(
                    months,
                    monthly["mean"] - ci,
                    monthly["mean"] + ci,
                    color=colour,
                    alpha=0.2,
                )

    ax.set_xlabel("Month")
    ax.set_xticks(months)
    ax.set_xticklabels(month_labels)

    if len(pollutants) == 1:
        units = (
            df[df["measurand"] == pollutants[0]]["units"].iloc[0]
            if "units" in df.columns
            else ""
        )
        ax.set_ylabel(f"{pollutants[0]} ({units})" if units else pollutants[0])
    else:
        ax.set_ylabel("Concentration")

    if title:
        ax.set_title(title)
    else:
        site_label = _get_site_label(data)
        if site_label:
            ax.set_title(f"Seasonal Pattern - {site_label}")
        else:
            ax.set_title("Seasonal Pattern")

    ax.legend(loc="upper right", framealpha=0.9)

    if style == "line":
        ax.set_xlim(0.5, 12.5)

    plt.tight_layout()

    return fig


# =============================================================================
# Calendar Heatmap
# =============================================================================


def plot_calendar(
    data: pd.DataFrame,
    pollutant: str,
    year: int | None = None,
    cmap: str | None = None,
    title: str | None = None,
    figsize: tuple[float, float] | None = None,
    apply_style: bool = True,
) -> plt.Figure:
    """
    Plot a calendar heatmap showing daily values for a year.

    Similar to GitHub contribution graphs, this shows data density
    and patterns across an entire year at a glance.

    Args:
        data: DataFrame from aeolus.download()
        pollutant: Pollutant to display
        year: Year to display (default: most recent in data)
        cmap: Matplotlib colormap name (default: "aeolus" palette).
              Use any matplotlib colormap name to override.
        title: Plot title
        figsize: Figure size (default auto-calculated)
        apply_style: Apply Aeolus matplotlib style

    Returns:
        matplotlib Figure

    Example:
        >>> fig = viz.plot_calendar(data, "PM2.5", year=2023)
        >>> fig.savefig("pm25_calendar_2023.png")
    """
    if apply_style:
        apply_aeolus_style()

    # Use Aeolus colormap by default
    if cmap is None:
        cmap = get_aeolus_cmap()

    df = data[data["measurand"] == pollutant].copy()
    if df.empty:
        raise ValueError(f"No data found for pollutant: {pollutant}")

    df["date_time"] = pd.to_datetime(df["date_time"])
    df["date"] = df["date_time"].dt.date

    # Get daily means
    daily = df.groupby("date")["value"].mean()

    # Determine year
    if year is None:
        year = pd.to_datetime(daily.index).year.max()

    # Filter to requested year
    daily = daily[pd.to_datetime(daily.index).year == year]

    if daily.empty:
        raise ValueError(f"No data found for year {year}")

    # Create date range for the full year
    start_date = pd.Timestamp(f"{year}-01-01")
    end_date = pd.Timestamp(f"{year}-12-31")
    all_dates = pd.date_range(start_date, end_date, freq="D")

    # Reindex to full year
    daily = daily.reindex(all_dates.date, fill_value=np.nan)

    # Build calendar matrix (weeks x days)
    # ISO week starts on Monday
    first_day = all_dates[0]
    first_weekday = first_day.weekday()  # 0=Monday

    # Pad the beginning to align with week start
    n_days = len(all_dates) + first_weekday
    n_weeks = (n_days + 6) // 7

    # Create matrix
    cal_matrix = np.full((7, n_weeks), np.nan)

    for i, (date, value) in enumerate(zip(all_dates, daily.values)):
        week = (i + first_weekday) // 7
        day = (i + first_weekday) % 7
        cal_matrix[day, week] = value

    # Create figure
    if figsize is None:
        figsize = (12, 2.5)

    fig, ax = plt.subplots(figsize=figsize)

    # Plot heatmap
    im = ax.imshow(
        cal_matrix,
        cmap=cmap,
        aspect="auto",
        interpolation="nearest",
    )

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    units = df["units"].iloc[0] if "units" in df.columns else ""
    cbar.set_label(f"{pollutant} ({units})" if units else pollutant)

    # Y-axis: days of week
    ax.set_yticks(range(7))
    ax.set_yticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])

    # X-axis: months
    month_starts = []
    month_labels = []
    for month in range(1, 13):
        month_start = pd.Timestamp(f"{year}-{month:02d}-01")
        if month_start >= start_date:
            day_of_year = (month_start - start_date).days
            week = (day_of_year + first_weekday) // 7
            month_starts.append(week)
            month_labels.append(month_start.strftime("%b"))

    ax.set_xticks(month_starts)
    ax.set_xticklabels(month_labels)

    # Title
    if title:
        ax.set_title(title)
    else:
        site_label = _get_site_label(data)
        if site_label:
            ax.set_title(f"{pollutant} Daily Average ({year}) - {site_label}")
        else:
            ax.set_title(f"{pollutant} Daily Average - {year}")

    plt.tight_layout()

    return fig
