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

from .. import options
from ..types import AeolusDataWarning
from ..units import canonical_unit, canonical_units
from .base import MOLECULAR_WEIGHTS, ensure_ugm3_array, validate_data


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

def _time_average_columns() -> list[str]:
    mirror = ["source_network"] if options.legacy_columns else []
    return ["site_code", "date_time", "measurand", "value", "units", "network", *mirror, "data_capture"]


def _empty_time_average_df() -> pd.DataFrame:
    """Return an empty DataFrame with the time_average schema."""
    return pd.DataFrame(columns=_time_average_columns())


def _infer_data_frequency(series: pd.Series) -> pd.Timedelta:
    """Infer the most common data frequency from a datetime series."""
    diffs = series.sort_values().diff().dropna()
    # Zero-length gaps come from duplicate timestamps, never a real cadence
    diffs = diffs[diffs > pd.Timedelta(0)]
    if diffs.empty:
        return pd.Timedelta(hours=1)
    return diffs.mode().iloc[0]


_MASS_UNITS = ("mg/m3",)  # canonical spellings; see aeolus.units
_MIXING_RATIO_UNITS = ("ppb", "ppm")


def _unify_units(
    df: pd.DataFrame, to_ugm3: bool = False, across_sites: bool = False
) -> pd.DataFrame:
    """Put each pollutant's values on one scale before they are pooled.

    The ``units`` column is authoritative (sources label faithfully), so
    metrics and plots must honour it rather than assume µg/m³:

    - A pollutant reported in *more than one* unit — per site, or across the
      whole frame with ``across_sites=True`` — is converted to µg/m³.
    - ``to_ugm3=True`` also converts ppb/ppm, for callers whose thresholds are
      defined in µg/m³. mg/m³ is left alone: it is the conventional unit for CO.
    - Anything else is left exactly as the network reported it.

    Only rows that can actually be converted are relabelled; a gas with no
    molecular weight keeps its original unit (``ensure_ugm3_array`` warns).
    Expects a unique index. Returns a new frame only if something changed.
    """
    if "units" not in df.columns or df.empty:
        return df

    raw = df["units"]
    # The usual frame has one unit: nothing can be mixed, and unless the caller
    # needs ug/m3 and has something else, there is nothing to convert.
    distinct = {canonical_unit(u) for u in pd.unique(raw.astype(object)) if isinstance(u, str)}
    if len(distinct) <= 1 and (not to_ugm3 or distinct <= {"ug/m3"} or not distinct & set(_MIXING_RATIO_UNITS)):
        return df

    # Spelling variants (ug.m-3, µg/m³, ...) are one unit, not a mix
    lower = canonical_units(raw).where(raw.notna())

    keys = ["measurand"] if across_sites else ["site_code", "measurand"]
    labels = df[keys].astype(object).assign(_unit=lower)
    mixed = labels.groupby(keys, observed=True)["_unit"].transform("nunique") > 1

    wanted = mixed & (lower != "ug/m3")
    if to_ugm3:
        wanted |= lower.isin(_MIXING_RATIO_UNITS)
    has_weight = df["measurand"].astype(str).str.upper().isin(MOLECULAR_WEIGHTS)
    convertible = lower.isin(_MASS_UNITS) | (lower.isin(_MIXING_RATIO_UNITS) & has_weight)

    if mixed.any():
        affected = sorted(df.loc[mixed, "measurand"].astype(str).unique())
        warnings.warn(
            f"Mixed units for {affected}; converting to ug/m3 before pooling.",
            AeolusDataWarning,
            stacklevel=4,
        )
    unconvertible = wanted & ~convertible
    if unconvertible.any():
        affected = sorted(df.loc[unconvertible, "measurand"].astype(str).unique())
        warnings.warn(
            f"Cannot convert {affected} to ug/m3 (no molecular weight or unknown "
            "unit); those rows keep their reported units.",
            AeolusDataWarning,
            stacklevel=4,
        )

    rows = wanted & convertible
    if not rows.any():
        return df

    df = df.copy()
    df["value"] = df["value"].astype(float)
    df["units"] = raw.astype(object)  # may be categorical without an ug/m3 category
    for measurand in df.loc[rows, "measurand"].astype(str).unique():
        sel = rows & (df["measurand"].astype(str) == measurand)
        df.loc[sel, "value"] = ensure_ugm3_array(
            df.loc[sel, "value"].to_numpy(dtype=float), measurand, df.loc[sel, "units"]
        )
        df.loc[sel, "units"] = "ug/m3"
    return df


def _prepare_observations(df: pd.DataFrame, to_ugm3: bool = False) -> pd.DataFrame:
    """Make each (site, measurand, timestamp) a single observation in one unit.

    Units are unified per site (see :func:`_unify_units`). Duplicate
    (site_code, measurand, date_time) rows — typically from concatenating
    overlapping downloads — are then collapsed to their mean so they count
    once towards data capture and averages.
    """
    # Concatenated downloads repeat index labels; rows are addressed by label below
    df = _unify_units(df.reset_index(drop=True), to_ugm3=to_ugm3)

    key = ["site_code", "measurand", "date_time"]
    duplicated = df.duplicated(subset=key, keep=False)
    if duplicated.any():
        warnings.warn(
            f"{int(duplicated.sum())} rows share a duplicate (site_code, measurand, "
            "date_time); averaging each set into one observation.",
            AeolusDataWarning,
            stacklevel=3,
        )
        means = df.groupby(key, observed=True, sort=False)["value"].transform("mean")
        df = df.assign(value=means).drop_duplicates(subset=key, keep="first")

    return df


def _start_anchored(freq: str):
    """Return the left-closed, start-labelled equivalent of a resample frequency.

    Aeolus time bins are left-closed and labelled at their start. pandas'
    end-anchored offsets (ME/QE/YE, W) default to right-closed, end-labelled
    bins, so map them to the start-anchored offset covering the same periods.
    Tick frequencies ("D", "8h", ...) are already left-closed and unchanged.
    """
    legacy = {"M": "MS", "Q": "QS", "Y": "YS", "A": "YS"}
    offset = pd.tseries.frequencies.to_offset(legacy.get(freq, freq))
    offsets = pd.tseries.offsets
    if isinstance(offset, offsets.MonthEnd):
        return offsets.MonthBegin(offset.n)
    if isinstance(offset, offsets.QuarterEnd):
        return offsets.QuarterBegin(offset.n, startingMonth=offset.startingMonth % 12 + 1)
    if isinstance(offset, offsets.YearEnd):
        return offsets.YearBegin(offset.n, month=offset.month % 12 + 1)
    if isinstance(offset, offsets.Week) and offset.weekday is not None:
        # "W" (W-SUN) means weeks *ending* Sunday; the same weeks start Monday
        return offsets.Week(offset.n, weekday=(offset.weekday + 1) % 7)
    return offset


def _expected_observations(data_freq: pd.Timedelta, target_freq: str) -> float:
    """Calculate the expected number of observations in a target period.

    Used when the caller just needs a scalar "expected" (e.g. for reporting).
    For per-bin calculation (the right way for variable-length periods like
    MS, YS, Q) use :func:`_expected_observations_per_bin` instead.

    Kept as a thin wrapper over the per-bin helper for backwards compatibility.
    """
    target_td = pd.tseries.frequencies.to_offset(target_freq)
    # For fixed-length offsets, nanos gives us the duration directly
    if target_td is not None:
        try:
            target_duration = pd.Timedelta(target_td.nanos, unit="ns")
        except (AttributeError, ValueError):
            # Variable-length; fall back to a representative value
            target_duration = _APPROX_DURATION.get(
                target_freq, pd.Timedelta(days=1)
            )
    else:
        target_duration = _APPROX_DURATION.get(target_freq, pd.Timedelta(days=1))

    if data_freq.total_seconds() <= 0:
        return 1.0

    return target_duration / data_freq


# Approximate durations for variable-length periods. Only used by the
# scalar _expected_observations() fallback — per-bin calculation uses
# actual calendar durations, not these.
_APPROX_DURATION = {
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


def _expected_observations_per_bin(
    data_freq: pd.Timedelta,
    target_freq: str,
    bin_start_index: pd.DatetimeIndex,
) -> pd.Series:
    """Expected observation count for each resample bin, using the bin's
    actual calendar duration.

    Critical for variable-length periods:

    - **Months** vary 28-31 days (672-744 hours)
    - **Years** vary 365-366 days
    - **Quarters** vary 90-92 days
    - **Months containing DST transitions** gain or lose one hour

    Using a fixed 30-day approximation inflates data capture by up to ~3% on
    31-day months and deflates it on 28-day months, which pushes the
    LAQM 75%-capture threshold across the wrong boundary for months with
    genuinely marginal coverage.

    Returns a Series aligned with ``bin_start_index`` giving the expected
    number of observations per bin.
    """
    if data_freq.total_seconds() <= 0:
        return pd.Series(1.0, index=bin_start_index)

    # Compute each bin's actual end. For period-aligned offsets (MS, YS, QS,
    # W, D) the next bin's start *is* this bin's end, and pandas can give
    # us that via the offset arithmetic.
    offset = pd.tseries.frequencies.to_offset(target_freq)
    if offset is None:
        # Shouldn't happen for valid freq strings, but defensively return
        # the scalar approximation replicated across bins
        scalar = _expected_observations(data_freq, target_freq)
        return pd.Series(scalar, index=bin_start_index)

    # For each bin start, compute bin_end = bin_start + 1 * offset
    # This respects calendar arithmetic: e.g. MS + 1 month lands on the
    # first of the next month, handling 28-31 day variations and leap years.
    bin_ends = bin_start_index + offset
    bin_durations = bin_ends - bin_start_index
    return bin_durations / data_freq


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
        units, network, data_capture.
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

    from ..schema import with_network_column

    df = _prepare_observations(with_network_column(df))
    offset = _start_anchored(freq)

    def resampled(series: pd.Series):
        return series.resample(offset, closed="left", label="left")

    results = []

    for (site, measurand), group in df.groupby(
        ["site_code", "measurand"], observed=True
    ):
        g = group.set_index("date_time").sort_index()

        # Infer source data frequency for data capture calculation
        data_freq = _infer_data_frequency(group["date_time"])

        values = g["value"]

        # Apply aggregation
        if statistic == "mean":
            agg = resampled(values).mean()
        elif statistic == "max":
            agg = resampled(values).max()
        elif statistic == "min":
            agg = resampled(values).min()
        elif statistic == "median":
            agg = resampled(values).median()
        elif statistic == "sum":
            agg = resampled(values).sum(min_count=1)
        elif statistic == "std":
            agg = resampled(values).std()
        elif statistic == "percentile":
            agg = resampled(values).quantile(
                percentile / 100.0, interpolation="linear"
            )
        else:
            raise ValueError(f"Unknown statistic: {statistic}")

        counts = resampled(values).count()

        # Data capture: fraction of expected observations present.
        # Expected count is computed per-bin using each bin's actual
        # calendar duration — not a fixed 30-day / 365-day approximation.
        # This matters for monthly/yearly/quarterly aggregations where
        # period length varies (28-31 days, 365-366 days, etc.) and around
        # DST transitions where a month gains/loses an hour.
        expected = _expected_observations_per_bin(data_freq, offset, counts.index)
        with np.errstate(divide="ignore", invalid="ignore"):
            dc = counts / expected
        dc = dc.fillna(1.0 if len(counts) == 0 else 0.0)

        # Cap data capture at 1.0 (can exceed 1 at DST spring-forward when
        # pandas resamples a 23-hour period and data_freq divides it unevenly)
        dc = dc.clip(upper=1.0)

        # Apply threshold: set value to NaN where data capture is insufficient
        if data_thresh > 0:
            agg = agg.where(dc >= data_thresh)

        # Get representative units and network from the group
        units_val = group["units"].iloc[0] if "units" in group.columns else ""
        network_val = group["network"].iloc[0] if "network" in group.columns else ""

        period_df = pd.DataFrame(
            {
                "site_code": site,
                "date_time": agg.index,
                "measurand": measurand,
                "value": agg.values,
                "units": units_val,
                "network": network_val,
                "source_network": network_val,
                "data_capture": dc.values,
            }
        )

        results.append(period_df)

    if not results:
        return _empty_time_average_df()

    return pd.concat(results, ignore_index=True)[_time_average_columns()]


# =============================================================================
# aq_stats
# =============================================================================

_AQ_STATS_COLUMNS = [
    "site_code",
    "year",
    "pollutant",
    "units",
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

    # Limit values below are defined in ug/m3, so honour the units column first
    # (ppb/ppm are converted; CO in mg/m3 stays in mg/m3, as LAQM reports it)
    df = _prepare_observations(df, to_ugm3=True)

    results = []

    for (site, yr, meas), group in df.groupby(
        ["site_code", "year", "measurand"], observed=True
    ):
        g = group.set_index("date_time").sort_index()

        # Annual stats are defined for hourly data — sub-hourly inputs
        # would otherwise inflate data_capture above 1.0 and double-count
        # exceedance_hours_200. Resample to hourly means first.
        if len(g.index) >= 2:
            inferred_gap = g.index.to_series().diff().median()
            if (
                pd.notna(inferred_gap)
                and inferred_gap < pd.Timedelta(hours=1)
            ):
                g = (
                    g["value"]
                    .resample("1h")
                    .mean()
                    .to_frame("value")
                )

        values = g["value"].dropna()

        if values.empty:
            continue

        # Expected hours in this year
        hours_in_year = 8784 if calendar.isleap(yr) else 8760
        dc = min(len(values) / hours_in_year, 1.0)

        row = {
            "site_code": site,
            "year": yr,
            "pollutant": meas,
            "units": group["units"].iloc[0] if "units" in group.columns else "",
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
        row["p95"] = values.quantile(0.95, interpolation="linear")
        row["p99"] = values.quantile(0.99, interpolation="linear")

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
    df = _prepare_observations(df)

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

        # Infer data frequency for threshold calculation.
        # Uses per-bin expected counts so variable-length periods (months
        # of 28-31 days, leap years, DST transitions) get the correct
        # capture denominator — matches the behaviour of time_average().
        data_freq = _infer_data_frequency(site_df.reset_index()["date_time"])
        expected = _expected_observations_per_bin(data_freq, freq, agg_count.index)

        if data_thresh > 0:
            with np.errstate(divide="ignore", invalid="ignore"):
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
