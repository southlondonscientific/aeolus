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
Statistical analysis functions for air quality data.

Provides:
    - time_average: Flexible time averaging with data capture thresholds
    - aq_stats: Annual regulatory statistics (LAQM-style output)
    - trend: Theil-Sen non-parametric trend analysis with Mann-Kendall test
"""

from __future__ import annotations

import calendar
import warnings
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from .base import validate_data


# =============================================================================
# TrendResult dataclass
# =============================================================================


@dataclass
class TrendResult:
    """Result of a Theil-Sen trend analysis."""

    slope: float  # units/year
    slope_pct: float  # % change/year relative to mean
    intercept: float
    ci_lower: float  # lower CI on slope
    ci_upper: float  # upper CI on slope
    p_value: float  # Mann-Kendall p-value
    n_points: int
    avg_time: str
    deseasonalised: bool
    pollutant: str
    site_code: str
    mean_value: float
    first_year: int
    last_year: int


# =============================================================================
# time_average
# =============================================================================

_TIME_AVERAGE_COLUMNS = [
    "site_code",
    "date_time",
    "measurand",
    "value",
    "units",
    "source_network",
    "data_capture",
]


def _empty_time_average_df() -> pd.DataFrame:
    """Return an empty DataFrame with the time_average schema."""
    return pd.DataFrame(columns=_TIME_AVERAGE_COLUMNS)


def _infer_data_frequency(series: pd.Series) -> pd.Timedelta:
    """Infer the most common data frequency from a datetime series."""
    diffs = series.sort_values().diff().dropna()
    if diffs.empty:
        return pd.Timedelta(hours=1)
    return diffs.mode().iloc[0]


def _expected_observations(data_freq: pd.Timedelta, target_freq: str) -> float:
    """Calculate the expected number of observations in a target period."""
    target_td = pd.tseries.frequencies.to_offset(target_freq)
    # For variable-length periods like M or Y, use approximate durations
    approx = {
        "M": pd.Timedelta(days=30),
        "MS": pd.Timedelta(days=30),
        "ME": pd.Timedelta(days=30),
        "Y": pd.Timedelta(days=365),
        "YS": pd.Timedelta(days=365),
        "YE": pd.Timedelta(days=365),
        "Q": pd.Timedelta(days=91),
        "QS": pd.Timedelta(days=91),
        "QE": pd.Timedelta(days=91),
        "W": pd.Timedelta(days=7),
    }
    if target_td is not None:
        try:
            target_duration = pd.Timedelta(target_td.nanos, unit="ns")
        except (AttributeError, ValueError):
            target_duration = approx.get(target_freq, pd.Timedelta(days=1))
    else:
        target_duration = approx.get(target_freq, pd.Timedelta(days=1))

    if data_freq.total_seconds() <= 0:
        return 1.0

    return target_duration / data_freq


def time_average(
    data: pd.DataFrame,
    freq: str = "D",
    statistic: Literal[
        "mean", "max", "min", "median", "sum", "std", "percentile"
    ] = "mean",
    data_thresh: float = 0.75,
    percentile: float = 95.0,
    pollutants: list[str] | None = None,
) -> pd.DataFrame:
    """
    Time-average air quality data with data capture thresholds.

    Resamples hourly (or sub-hourly) data to a coarser time resolution,
    applying a minimum data capture threshold below which the averaged
    value is set to NaN. This is the foundation for regulatory statistics.

    Args:
        data: DataFrame from aeolus.download() with standard 8-column schema.
        freq: Target frequency string (pandas offset alias).
              Common values: "D" (daily), "8h" (8-hourly), "W" (weekly),
              "ME" (monthly), "YE" (yearly).
        statistic: Aggregation function to apply.
        data_thresh: Minimum fraction of valid observations required (0-1).
                     Periods below this threshold get value=NaN.
                     Set to 0 to disable thresholding.
        percentile: Percentile value when statistic="percentile" (0-100).
        pollutants: List of measurand names to include. None = all.

    Returns:
        DataFrame with columns: site_code, date_time, measurand, value,
        units, source_network, data_capture.
    """
    validate_data(data)

    if data.empty:
        return _empty_time_average_df()

    df = data.copy()
    df["date_time"] = pd.to_datetime(df["date_time"])

    if pollutants is not None:
        df = df[df["measurand"].isin(pollutants)]
        if df.empty:
            return _empty_time_average_df()

    results = []

    for (site, measurand), group in df.groupby(
        ["site_code", "measurand"], observed=True
    ):
        g = group.set_index("date_time").sort_index()

        # Infer source data frequency for data capture calculation
        data_freq = _infer_data_frequency(group["date_time"])
        expected = _expected_observations(data_freq, freq)

        values = g["value"]

        # Apply aggregation
        if statistic == "mean":
            agg = values.resample(freq).mean()
        elif statistic == "max":
            agg = values.resample(freq).max()
        elif statistic == "min":
            agg = values.resample(freq).min()
        elif statistic == "median":
            agg = values.resample(freq).median()
        elif statistic == "sum":
            agg = values.resample(freq).sum(min_count=1)
        elif statistic == "std":
            agg = values.resample(freq).std()
        elif statistic == "percentile":
            agg = values.resample(freq).quantile(percentile / 100.0)
        else:
            raise ValueError(f"Unknown statistic: {statistic}")

        counts = values.resample(freq).count()

        # Data capture: fraction of expected observations present
        if expected > 0:
            dc = counts / expected
        else:
            dc = pd.Series(1.0, index=counts.index)

        # Cap data capture at 1.0 (can exceed 1 for variable-length periods)
        dc = dc.clip(upper=1.0)

        # Apply threshold: set value to NaN where data capture is insufficient
        if data_thresh > 0:
            agg = agg.where(dc >= data_thresh)

        # Get representative units and source_network from the group
        units_val = group["units"].iloc[0] if "units" in group.columns else ""
        network_val = (
            group["source_network"].iloc[0]
            if "source_network" in group.columns
            else ""
        )

        period_df = pd.DataFrame(
            {
                "site_code": site,
                "date_time": agg.index,
                "measurand": measurand,
                "value": agg.values,
                "units": units_val,
                "source_network": network_val,
                "data_capture": dc.values,
            }
        )

        results.append(period_df)

    if not results:
        return _empty_time_average_df()

    return pd.concat(results, ignore_index=True)


# =============================================================================
# aq_stats
# =============================================================================

_AQ_STATS_COLUMNS = [
    "site_code",
    "year",
    "pollutant",
    "data_capture",
    "annual_mean",
    "max_hourly",
    "max_daily_mean",
    "max_8h_rolling_mean",
    "p95",
    "p99",
    "exceedance_hours_200",
    "exceedance_days_50",
    "exceedance_days_120",
]


def aq_stats(
    data: pd.DataFrame,
    year: int | list[int] | None = None,
    pollutant: str | list[str] | None = None,
    data_thresh: float = 0.75,
) -> pd.DataFrame:
    """
    Calculate annual regulatory air quality statistics.

    Produces one row per site/year/pollutant with statistics suitable for
    LAQM Annual Status Reports: annual mean, maxima, percentiles,
    data capture, and exceedance counts.

    Exceedance columns are pollutant-specific:
        - exceedance_hours_200: hours with concentration > 200 ug/m3 (NO2)
        - exceedance_days_50: days with daily mean > 50 ug/m3 (PM10)
        - exceedance_days_120: days where max 8-hour rolling mean > 120 ug/m3 (O3)

    Args:
        data: DataFrame from aeolus.download() with standard schema.
        year: Filter to specific year(s). None = all years in data.
        pollutant: Filter to specific pollutant(s). None = all.
        data_thresh: Minimum annual data capture for valid stats (0-1).
                     Below this threshold all stats are NaN.

    Returns:
        DataFrame with one row per site/year/pollutant.
    """
    validate_data(data)

    if data.empty:
        return pd.DataFrame(columns=_AQ_STATS_COLUMNS)

    df = data.copy()
    df["date_time"] = pd.to_datetime(df["date_time"])
    df["year"] = df["date_time"].dt.year

    # Apply filters
    if year is not None:
        if not isinstance(year, list):
            year = [int(year)]
        df = df[df["year"].isin(year)]

    if pollutant is not None:
        if isinstance(pollutant, str):
            pollutant = [pollutant]
        df = df[df["measurand"].isin(pollutant)]

    if df.empty:
        return pd.DataFrame(columns=_AQ_STATS_COLUMNS)

    results = []

    for (site, yr, meas), group in df.groupby(
        ["site_code", "year", "measurand"], observed=True
    ):
        g = group.set_index("date_time").sort_index()
        values = g["value"].dropna()

        if values.empty:
            continue

        # Expected hours in this year
        hours_in_year = 8784 if calendar.isleap(yr) else 8760
        dc = len(values) / hours_in_year

        row = {
            "site_code": site,
            "year": yr,
            "pollutant": meas,
            "data_capture": dc,
        }

        # If data capture is below threshold, all stats are NaN
        if dc < data_thresh:
            row.update(
                {
                    "annual_mean": np.nan,
                    "max_hourly": np.nan,
                    "max_daily_mean": np.nan,
                    "max_8h_rolling_mean": np.nan,
                    "p95": np.nan,
                    "p99": np.nan,
                    "exceedance_hours_200": np.nan,
                    "exceedance_days_50": np.nan,
                    "exceedance_days_120": np.nan,
                }
            )
            results.append(row)
            continue

        # Basic stats from hourly values
        row["annual_mean"] = values.mean()
        row["max_hourly"] = values.max()
        row["p95"] = values.quantile(0.95)
        row["p99"] = values.quantile(0.99)

        # Daily means (18/24 hour threshold per day)
        daily = values.resample("D").agg(["mean", "count"])
        daily_valid = daily[daily["count"] >= 18]
        row["max_daily_mean"] = (
            daily_valid["mean"].max() if not daily_valid.empty else np.nan
        )

        # 8-hour rolling mean (6/8 minimum periods)
        rolling_8h = values.rolling("8h", min_periods=6).mean()
        row["max_8h_rolling_mean"] = (
            rolling_8h.max() if not rolling_8h.empty else np.nan
        )

        # Exceedances (pollutant-specific, NaN for irrelevant pollutants)
        meas_upper = meas.upper()

        # NO2: hours > 200 ug/m3
        if meas_upper == "NO2":
            row["exceedance_hours_200"] = int((values > 200).sum())
        else:
            row["exceedance_hours_200"] = np.nan

        # PM10: days with daily mean > 50 ug/m3
        if meas_upper == "PM10":
            if not daily_valid.empty:
                row["exceedance_days_50"] = int(
                    (daily_valid["mean"] > 50).sum()
                )
            else:
                row["exceedance_days_50"] = 0
        else:
            row["exceedance_days_50"] = np.nan

        # O3: days where max rolling 8-hour > 120 ug/m3
        if meas_upper == "O3":
            daily_max_8h = rolling_8h.resample("D").max()
            row["exceedance_days_120"] = int(
                (daily_max_8h > 120).sum()
            )
        else:
            row["exceedance_days_120"] = np.nan

        results.append(row)

    if not results:
        return pd.DataFrame(columns=_AQ_STATS_COLUMNS)

    result_df = pd.DataFrame(results)
    # Ensure column order
    for col in _AQ_STATS_COLUMNS:
        if col not in result_df.columns:
            result_df[col] = np.nan
    return result_df[_AQ_STATS_COLUMNS]


# =============================================================================
# trend
# =============================================================================


def trend(
    data: pd.DataFrame,
    pollutant: str,
    avg_time: Literal["month", "season", "year"] = "month",
    deseason: bool = True,
    autocor: bool = False,
    data_thresh: float = 0.75,
    ci_level: float = 0.95,
) -> TrendResult | list[TrendResult]:
    """
    Non-parametric trend analysis using Theil-Sen slope and Mann-Kendall test.

    Aggregates data to the requested time resolution, optionally removes the
    seasonal cycle (STL decomposition via statsmodels), then fits a Theil-Sen
    robust regression line. Statistical significance is assessed with the
    Mann-Kendall test.

    Args:
        data: DataFrame from aeolus.download() with standard schema.
        pollutant: Measurand to analyse (e.g. "NO2", "PM2.5").
        avg_time: Aggregation period before fitting: "month", "season", "year".
        deseason: Remove seasonal cycle before fitting (requires statsmodels
                  for avg_time in ("month", "season"); ignored for "year").
        autocor: Apply autocorrelation correction to effective sample size.
        data_thresh: Minimum fraction of valid periods required per
                     aggregation window (0-1). Set to 0 to disable.
        ci_level: Confidence level for slope confidence interval.

    Returns:
        TrendResult for a single-site dataset, or list[TrendResult] for
        multi-site data.

    Raises:
        ValueError: If fewer than 6 data points remain after aggregation,
                    or if the requested pollutant is not in the data.
    """
    from scipy import stats as sp_stats

    validate_data(data)

    df = data[data["measurand"] == pollutant].copy()
    if df.empty:
        raise ValueError(f"No data found for pollutant: {pollutant}")

    df["date_time"] = pd.to_datetime(df["date_time"])

    sites = df["site_code"].unique()
    results = []

    for site in sites:
        site_df = df[df["site_code"] == site].set_index("date_time").sort_index()
        values = site_df["value"]

        # Aggregate to requested time resolution
        freq_map = {"month": "MS", "season": "QS-DEC", "year": "YS"}
        freq = freq_map[avg_time]

        agg_mean = values.resample(freq).mean()
        agg_count = values.resample(freq).count()

        # Infer data frequency for threshold calculation
        data_freq = _infer_data_frequency(site_df.reset_index()["date_time"])
        expected = _expected_observations(data_freq, freq)

        if expected > 0 and data_thresh > 0:
            dc = (agg_count / expected).clip(upper=1.0)
            agg_mean = agg_mean.where(dc >= data_thresh)

        # Drop NaN values
        agg_mean = agg_mean.dropna()

        if len(agg_mean) < 6:
            raise ValueError(
                f"Insufficient data for trend analysis at site {site}: "
                f"{len(agg_mean)} points (need >= 6) after {avg_time} aggregation."
            )

        y = agg_mean.values.copy()

        # Deseasonalisation
        deseasonalised = False
        if deseason and avg_time in ("month", "season"):
            period = 12 if avg_time == "month" else 4
            if len(y) >= 2 * period:
                try:
                    from statsmodels.tsa.seasonal import STL

                    stl = STL(
                        pd.Series(y, index=agg_mean.index),
                        period=period,
                        robust=True,
                    )
                    res = stl.fit()
                    y = res.trend + res.resid
                    deseasonalised = True
                except ImportError:
                    warnings.warn(
                        "statsmodels is not installed. Skipping deseasonalisation. "
                        "Install with: pip install statsmodels",
                        UserWarning,
                        stacklevel=2,
                    )
            else:
                warnings.warn(
                    f"Not enough data for deseasonalisation "
                    f"({len(y)} points, need >= {2 * period}). "
                    f"Skipping deseasonalisation.",
                    UserWarning,
                    stacklevel=2,
                )

        # Convert datetime index to fractional years
        dates = agg_mean.index
        x_years = (
            dates.year
            + (dates.dayofyear - 1) / 365.25
        ).values.astype(float)

        # Theil-Sen slope estimation
        alpha = 1 - ci_level
        ts_result = sp_stats.theilslopes(y, x_years, alpha=alpha)
        slope = ts_result.slope
        intercept = ts_result.intercept
        ci_low = ts_result.low_slope
        ci_high = ts_result.high_slope

        # Mann-Kendall test for significance
        tau, p_value = sp_stats.kendalltau(x_years, y)

        # Autocorrelation correction (effective sample size)
        if autocor and len(y) > 2:
            residuals = y - (slope * x_years + intercept)
            lag1 = np.corrcoef(residuals[:-1], residuals[1:])[0, 1]
            if not np.isnan(lag1) and abs(lag1) < 1:
                n_eff = len(y) * (1 - lag1) / (1 + lag1)
                n_eff = max(n_eff, 3)
                # Scale p-value approximately
                scale_factor = len(y) / n_eff
                p_value = min(1.0, p_value * scale_factor)

        mean_val = float(np.nanmean(y))
        slope_pct = (slope / mean_val * 100) if mean_val != 0 else np.nan

        results.append(
            TrendResult(
                slope=float(slope),
                slope_pct=float(slope_pct),
                intercept=float(intercept),
                ci_lower=float(ci_low),
                ci_upper=float(ci_high),
                p_value=float(p_value),
                n_points=len(y),
                avg_time=avg_time,
                deseasonalised=deseasonalised,
                pollutant=pollutant,
                site_code=str(site),
                mean_value=mean_val,
                first_year=int(dates.year.min()),
                last_year=int(dates.year.max()),
            )
        )

    if len(results) == 1:
        return results[0]
    return results
