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
Data preparation utilities for visualisation.

This module handles the transformation of raw aeolus data into
formats suitable for plotting, including:
- Downsampling large datasets while preserving visual features
- Pivoting from long to wide format for multi-pollutant plots
- Extracting AQI band information for background shading
"""

import warnings
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

# =============================================================================
# Types
# =============================================================================


@dataclass
class TimeSeriesSpec:
    """
    Specification for a time series plot.

    This is the prepared data structure that gets passed to renderers.
    Separating preparation from rendering allows for future backend flexibility.
    """

    # Core data: datetime index, columns are pollutants
    data: pd.DataFrame

    # Metadata
    pollutants: list[str]
    units: dict[str, str]
    site_name: str | None = None

    # Display options
    title: str | None = None
    ylabel: str | None = None

    # AQI band information (if requested)
    aqi_index: str | None = None
    aqi_bands: list[dict] | None = None  # List of {low, high, colour, label}

    # Guideline/threshold line
    guideline_value: float | None = None
    guideline_label: str | None = None

    # Downsampling info
    was_downsampled: bool = False
    original_points: int = 0
    display_points: int = 0


@dataclass
class AQICardSpec:
    """
    Specification for an AQI card display.
    """

    value: int | float
    category: str
    colour: str
    text_colour: str  # Dark or light based on background

    title: str | None = None
    pollutant: str | None = None
    period: str | None = None  # e.g., "Daily average", "2024"

    # Optional sub-elements
    subtitle: str | None = None
    message: str | None = None


# =============================================================================
# Downsampling
# =============================================================================


def lttb_downsample(
    x: np.ndarray,
    y: np.ndarray,
    target_points: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Downsample using Largest Triangle Three Buckets (LTTB) algorithm.

    LTTB preserves the visual shape of the data better than simple
    decimation or averaging. It selects points that maximize the
    triangle area with their neighbors.

    Reference: Sveinn Steinarsson, "Downsampling Time Series for
    Visual Representation" (2013)

    Args:
        x: X values (typically timestamps as numeric)
        y: Y values (measurements)
        target_points: Desired number of output points

    Returns:
        Tuple of (downsampled_x, downsampled_y)
    """
    n = len(x)

    if target_points >= n:
        return x, y

    if target_points < 3:
        target_points = 3

    # Always keep first and last points
    sampled_x = [x[0]]
    sampled_y = [y[0]]

    # Bucket size
    bucket_size = (n - 2) / (target_points - 2)

    a = 0  # Index of previous selected point

    for i in range(target_points - 2):
        # Calculate bucket range
        bucket_start = int((i + 1) * bucket_size) + 1
        bucket_end = int((i + 2) * bucket_size) + 1
        bucket_end = min(bucket_end, n - 1)

        # Calculate average point in next bucket (for triangle calculation)
        next_bucket_start = int((i + 2) * bucket_size) + 1
        next_bucket_end = int((i + 3) * bucket_size) + 1
        next_bucket_end = min(next_bucket_end, n)

        if next_bucket_start < n:
            avg_x = np.mean(x[next_bucket_start:next_bucket_end])
            avg_y = np.mean(y[next_bucket_start:next_bucket_end])
        else:
            avg_x = x[-1]
            avg_y = y[-1]

        # Find point in current bucket that maximizes triangle area
        max_area = -1
        max_idx = bucket_start

        for j in range(bucket_start, bucket_end):
            # Triangle area using cross product
            area = abs((x[a] - avg_x) * (y[j] - y[a]) - (x[a] - x[j]) * (avg_y - y[a]))

            if area > max_area:
                max_area = area
                max_idx = j

        sampled_x.append(x[max_idx])
        sampled_y.append(y[max_idx])
        a = max_idx

    # Always include last point
    sampled_x.append(x[-1])
    sampled_y.append(y[-1])

    return np.array(sampled_x), np.array(sampled_y)


def downsample_timeseries(
    df: pd.DataFrame,
    datetime_col: str,
    value_col: str,
    target_points: int = 2000,
    method: Literal["lttb", "decimate", "mean"] = "lttb",
) -> pd.DataFrame:
    """
    Downsample a time series DataFrame.

    Args:
        df: DataFrame with datetime and value columns
        datetime_col: Name of datetime column
        value_col: Name of value column
        target_points: Target number of points
        method: Downsampling method
            - "lttb": Largest Triangle Three Buckets (preserves shape)
            - "decimate": Simple every-nth-point selection
            - "mean": Bucket averaging

    Returns:
        Downsampled DataFrame
    """
    if len(df) <= target_points:
        return df

    # Sort by datetime
    df = df.sort_values(datetime_col).copy()

    # Handle NaN values - LTTB needs complete data
    mask = df[value_col].notna()
    df_valid = df[mask]

    if len(df_valid) <= target_points:
        return df

    if method == "lttb":
        # Convert datetime to numeric for LTTB
        x = df_valid[datetime_col].astype(np.int64).values
        y = df_valid[value_col].values

        x_down, y_down = lttb_downsample(x, y, target_points)

        # Reconstruct DataFrame
        result = pd.DataFrame(
            {
                datetime_col: pd.to_datetime(x_down),
                value_col: y_down,
            }
        )

        # Preserve other columns from nearest original points
        # (simplified: just return the two key columns)
        return result

    elif method == "decimate":
        step = len(df_valid) // target_points
        return df_valid.iloc[::step].copy()

    elif method == "mean":
        # Resample to achieve target points
        duration = df_valid[datetime_col].max() - df_valid[datetime_col].min()
        freq_seconds = duration.total_seconds() / target_points
        freq = f"{int(freq_seconds)}s"

        df_valid = df_valid.set_index(datetime_col)
        result = df_valid[[value_col]].resample(freq).mean().dropna().reset_index()
        return result

    else:
        raise ValueError(f"Unknown downsampling method: {method}")


# =============================================================================
# Data Preparation for Time Series
# =============================================================================


def prepare_timeseries(
    data: pd.DataFrame,
    pollutants: list[str] | None = None,
    downsample: bool | int = True,
    aqi_bands: str | None = None,
    guideline: float | None = None,
    guideline_label: str | None = None,
    title: str | None = None,
) -> TimeSeriesSpec:
    """
    Prepare data for a time series plot.

    Transforms aeolus long-format data into a specification that
    can be rendered by any backend.

    Args:
        data: DataFrame from aeolus.download() with columns:
              date_time, measurand, value, units, (site_name)
        pollutants: List of pollutants to include (default: all)
        downsample: True for auto, False for none, or int for target points
        aqi_bands: AQI index name to show background bands (e.g., "UK_DAQI")
        guideline: Value for horizontal guideline/threshold line
        guideline_label: Label for guideline (e.g., "WHO AQG")
        title: Plot title

    Returns:
        TimeSeriesSpec ready for rendering
    """
    from .theme import AEOLUS_6_BAND, INDEX_COLOURS

    # Validate input
    required = {"date_time", "measurand", "value"}
    if not required.issubset(data.columns):
        missing = required - set(data.columns)
        raise ValueError(f"Data missing required columns: {missing}")

    # Filter to requested pollutants
    available_pollutants = data["measurand"].unique().tolist()

    if pollutants is None:
        pollutants = available_pollutants
    else:
        missing = set(pollutants) - set(available_pollutants)
        if missing:
            warnings.warn(f"Requested pollutants not in data: {missing}")
        pollutants = [p for p in pollutants if p in available_pollutants]

    if not pollutants:
        raise ValueError("No valid pollutants to plot")

    # Get units for each pollutant
    units = {}
    for p in pollutants:
        p_data = data[data["measurand"] == p]
        if "units" in p_data.columns:
            units[p] = p_data["units"].iloc[0] if len(p_data) > 0 else "?"
        else:
            units[p] = "?"

    # Get site name if available
    site_name = None
    if "site_name" in data.columns:
        sites = data["site_name"].unique()
        site_name = sites[0] if len(sites) == 1 else f"{len(sites)} sites"

    # Pivot to wide format (datetime index, pollutants as columns)
    filtered = data[data["measurand"].isin(pollutants)].copy()

    wide = filtered.pivot_table(
        index="date_time",
        columns="measurand",
        values="value",
        aggfunc="mean",  # Handle any duplicates
        observed=True,  # Only include observed categories
    ).reset_index()

    wide = wide.sort_values("date_time")

    # Track original size
    original_points = len(wide)

    # Downsampling
    was_downsampled = False
    if downsample:
        target = 2000 if downsample is True else int(downsample)

        if len(wide) > target:
            # For multiple pollutants, we downsample each independently
            # using LTTB, then take the union of all selected time points.
            # This preserves visual features (peaks, valleys) for ALL
            # pollutants, not just a reference pollutant.
            #
            # The trade-off: with N pollutants, we may get up to N * target
            # points in the worst case, but typically there's significant
            # overlap so the actual count is much lower.

            # Calculate per-pollutant target
            # Each pollutant gets the full target budget to ensure all
            # visual features are preserved. The union of selected points
            # typically has significant overlap, so actual count is usually
            # well under N * target points.
            per_pollutant_target = target

            all_selected_times = set()

            for p in pollutants:
                if p not in wide.columns:
                    continue

                p_df = wide[["date_time", p]].dropna()

                if len(p_df) <= per_pollutant_target:
                    # Keep all times for this pollutant
                    all_selected_times.update(p_df["date_time"].tolist())
                else:
                    # Downsample this pollutant independently
                    # Convert to int64 - pandas datetime64[us] gives microseconds
                    x = p_df["date_time"].astype(np.int64).values
                    y = p_df[p].values

                    x_down, _ = lttb_downsample(x, y, per_pollutant_target)
                    # Convert back to timestamps using same unit as source dtype
                    # datetime64[us] -> microseconds, datetime64[ns] -> nanoseconds
                    dt_unit = str(p_df["date_time"].dtype).split("[")[1].rstrip("]")
                    all_selected_times.update(
                        pd.to_datetime(x_down, unit=dt_unit).tolist()
                    )

            # Filter to union of all selected time points
            wide = wide[wide["date_time"].isin(all_selected_times)].copy()
            wide = wide.sort_values("date_time")

            was_downsampled = True

    display_points = len(wide)

    # Prepare AQI bands if requested
    aqi_band_list = None
    if aqi_bands:
        aqi_band_list = _get_aqi_bands(aqi_bands, pollutants)

    # Build ylabel
    if len(pollutants) == 1:
        ylabel = f"{pollutants[0]} ({units.get(pollutants[0], '')})"
    else:
        # Check if all units are the same
        unique_units = set(units.values())
        if len(unique_units) == 1:
            ylabel = f"Concentration ({list(unique_units)[0]})"
        else:
            ylabel = "Concentration"

    return TimeSeriesSpec(
        data=wide,
        pollutants=pollutants,
        units=units,
        site_name=site_name,
        title=title,
        ylabel=ylabel,
        aqi_index=aqi_bands,
        aqi_bands=aqi_band_list,
        guideline_value=guideline,
        guideline_label=guideline_label,
        was_downsampled=was_downsampled,
        original_points=original_points,
        display_points=display_points,
    )


def _get_aqi_bands(
    index: str,
    pollutants: list[str],
) -> list[dict] | None:
    """
    Get AQI band definitions for background shading.

    Returns bands appropriate for the pollutants being plotted.
    Currently simplified - returns bands for the first pollutant.
    """
    from ..metrics.indices import uk_daqi, us_epa
    from .theme import INDEX_COLOURS

    # For now, just return colour bands without concentration mapping
    # Full implementation would need to know which pollutant's scale to use

    if index == "UK_DAQI":
        colours = INDEX_COLOURS["UK_DAQI"]
        return [
            {"label": "Low", "colour": colours["Low"]},
            {"label": "Moderate", "colour": colours["Moderate"]},
            {"label": "High", "colour": colours["High"]},
            {"label": "Very High", "colour": colours["Very High"]},
        ]
    elif index == "US_EPA":
        colours = INDEX_COLOURS["US_EPA"]
        return [
            {"label": "Good", "colour": colours["Good"]},
            {"label": "Moderate", "colour": colours["Moderate"]},
            {
                "label": "Unhealthy for Sensitive Groups",
                "colour": colours["Unhealthy for Sensitive Groups"],
            },
            {"label": "Unhealthy", "colour": colours["Unhealthy"]},
            {"label": "Very Unhealthy", "colour": colours["Very Unhealthy"]},
            {"label": "Hazardous", "colour": colours["Hazardous"]},
        ]

    # Default: return None (no bands)
    return None


# =============================================================================
# Data Preparation for AQI Cards
# =============================================================================


def prepare_aqi_card(
    value: int | float,
    category: str,
    index: str = "UK_DAQI",
    title: str | None = None,
    pollutant: str | None = None,
    period: str | None = None,
    subtitle: str | None = None,
    official_colours: bool = False,
) -> AQICardSpec:
    """
    Prepare data for an AQI card display.

    Args:
        value: AQI value to display
        category: AQI category name (e.g., "Low", "Good")
        index: AQI index name for colour lookup
        title: Card title (e.g., "Your average was:")
        pollutant: Pollutant name if relevant
        period: Time period description
        subtitle: Additional text below the value
        official_colours: Use official regulatory colours

    Returns:
        AQICardSpec ready for rendering
    """
    from .theme import (
        SLS_CHARCOAL,
        get_colour_for_category,
        needs_dark_text,
    )

    colour = get_colour_for_category(category, index, official_colours)
    text_colour = SLS_CHARCOAL if needs_dark_text(colour) else "#FFFFFF"

    return AQICardSpec(
        value=value,
        category=category,
        colour=colour,
        text_colour=text_colour,
        title=title,
        pollutant=pollutant,
        period=period,
        subtitle=subtitle,
    )
