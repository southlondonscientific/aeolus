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
Air Quality Index calculations and metrics.

This module provides functions to calculate various air quality indices
from data downloaded via aeolus.download().

Supported Indices:
    - UK_DAQI: UK Daily Air Quality Index (1-10 scale)
    - US_EPA: US EPA Air Quality Index (0-500 scale, with NowCast)
    - CHINA: China Air Quality Index (0-500 scale)
    - WHO: WHO Air Quality Guidelines (compliance checker)
    - EU_CAQI_ROADSIDE: European AQI for traffic stations (1-6 scale)
    - EU_CAQI_BACKGROUND: European AQI for background stations (1-6 scale)
    - INDIA_NAQI: India National Air Quality Index (0-500 scale)

Quick Start:
    >>> import aeolus
    >>> from aeolus import metrics
    >>>
    >>> # Download some data
    >>> data = aeolus.download("AURN", ["MY1"], start, end)
    >>>
    >>> # Get AQI summary
    >>> summary = metrics.aqi_summary(data, index="UK_DAQI")
    >>>
    >>> # Get monthly breakdown
    >>> monthly = metrics.aqi_summary(data, index="UK_DAQI", freq="M")
    >>>
    >>> # Check WHO guideline compliance
    >>> compliance = metrics.aqi_check_who(data)
    >>>
    >>> # List available indices
    >>> indices = metrics.list_indices()
"""

from typing import Literal

import pandas as pd

from .base import (
    AQIResult,
    IndexInfo,
    ensure_ugm3,
    get_available_pollutants,
    standardise_pollutant,
    validate_data,
)
from .indices import get_index
from .indices import list_indices as _list_indices

# Re-export key types
__all__ = [
    # Main API functions
    "aqi_summary",
    "aqi_timeseries",
    "aqi_check_who",
    "list_indices",
    "get_index_info",
    # Types
    "AQIResult",
    "IndexInfo",
]


# =============================================================================
# Public API
# =============================================================================


def list_indices() -> list[str]:
    """
    List all available AQI indices.

    Returns:
        List of index keys (e.g., ["UK_DAQI", "US_EPA", "CHINA", ...])

    Example:
        >>> metrics.list_indices()
        ['UK_DAQI', 'US_EPA', 'CHINA', 'WHO', 'EU_CAQI_ROADSIDE',
         'EU_CAQI_BACKGROUND', 'INDIA_NAQI']
    """
    return _list_indices()


def get_index_info(index: str) -> IndexInfo | None:
    """
    Get detailed information about an AQI index.

    Args:
        index: Index key (e.g., "UK_DAQI")

    Returns:
        IndexInfo dict with name, country, scale, pollutants, description, url
        or None if index not found

    Example:
        >>> info = metrics.get_index_info("UK_DAQI")
        >>> print(info["name"])
        'UK Daily Air Quality Index'
        >>> print(info["pollutants"])
        ['O3', 'NO2', 'SO2', 'PM2.5', 'PM10']
    """
    return get_index(index)


FreqType = Literal["D", "W", "M", "Q", "Y"] | None
FormatType = Literal["long", "wide"]


def aqi_summary(
    data: pd.DataFrame,
    index: str = "UK_DAQI",
    freq: FreqType = None,
    format: FormatType = "long",
    overall_only: bool = False,
    warn_low_coverage: bool = True,
    min_coverage: float = 0.75,
) -> pd.DataFrame:
    """
    Calculate AQI summary statistics for air quality data.

    This is the primary function for calculating AQI values from downloaded data.
    It handles the required averaging periods for each index and provides
    summary statistics over the requested time periods.

    Args:
        data: DataFrame from aeolus.download() with columns:
              site_code, date_time, measurand, value, units
        index: AQI index to use (default: "UK_DAQI")
               Options: UK_DAQI, US_EPA, CHINA, EU_CAQI_ROADSIDE,
                        EU_CAQI_BACKGROUND, INDIA_NAQI
        freq: Aggregation frequency:
              None = entire period (default)
              "D" = daily
              "W" = weekly
              "M" = monthly
              "Q" = quarterly
              "Y" = yearly
        format: Output format:
                "long" = one row per site/period/pollutant (default)
                "wide" = one row per site/period with pollutant columns
        overall_only: If True, only return overall AQI (not per-pollutant)
        warn_low_coverage: Warn when data coverage is below min_coverage
        min_coverage: Minimum coverage threshold (0-1) for warnings

    Returns:
        DataFrame with AQI summary statistics.

        Long format columns:
            site_code, period, pollutant, mean, median, p25, p75, min, max,
            aqi_value, aqi_category, coverage

        Wide format columns:
            site_code, period, {pollutant}_mean, {pollutant}_aqi, ...,
            overall_aqi, overall_category, dominant_pollutant

        overall_only format columns:
            site_code, period, aqi_value, aqi_category, dominant_pollutant

    Example:
        >>> import aeolus
        >>> from aeolus import metrics
        >>>
        >>> data = aeolus.download("AURN", ["MY1"], start, end)
        >>>
        >>> # Overall summary
        >>> summary = metrics.aqi_summary(data, index="UK_DAQI")
        >>>
        >>> # Monthly breakdown
        >>> monthly = metrics.aqi_summary(data, index="UK_DAQI", freq="M")
        >>>
        >>> # Just overall AQI values
        >>> simple = metrics.aqi_summary(data, index="UK_DAQI", overall_only=True)
    """
    import warnings

    # Validate input
    validate_data(data)

    # Get index info
    index_info = get_index(index)
    if index_info is None:
        available = list_indices()
        raise ValueError(f"Unknown index '{index}'. Available: {available}")

    # Import the appropriate index module
    index_module = _get_index_module(index)

    # Get available pollutants in data
    available_pollutants = get_available_pollutants(data)
    supported_pollutants = set(index_info["pollutants"])
    usable_pollutants = available_pollutants & supported_pollutants

    if not usable_pollutants:
        raise ValueError(
            f"No supported pollutants found in data. "
            f"Index {index} requires: {supported_pollutants}. "
            f"Data contains: {available_pollutants}"
        )

    # Warn about missing pollutants
    missing = supported_pollutants - available_pollutants
    if missing:
        warnings.warn(
            f"Data is missing pollutants for complete {index} calculation: {missing}. "
            f"AQI will be calculated using available pollutants only.",
            UserWarning,
            stacklevel=2,
        )

    # Prepare data
    df = data.copy()
    df["date_time"] = pd.to_datetime(df["date_time"])
    df["pollutant_std"] = df["measurand"].apply(standardise_pollutant)
    df = df[df["pollutant_std"].isin(usable_pollutants)]

    # Determine period grouping
    if freq is None:
        df["period"] = "all"
    else:
        df["period"] = df["date_time"].dt.to_period(freq).astype(str)

    # Group and calculate statistics
    results = []

    for (site, period, pollutant), group in df.groupby(
        ["site_code", "period", "pollutant_std"]
    ):
        # Convert units if needed
        values = []
        for _, row in group.iterrows():
            if pd.notna(row["value"]):
                val = ensure_ugm3(
                    row["value"],
                    pollutant,
                    row["units"],
                    warn=False,  # Suppress per-row warnings
                )
                values.append(val)

        if not values:
            continue

        values_series = pd.Series(values)

        # Calculate statistics
        stats = {
            "site_code": site,
            "period": period,
            "pollutant": pollutant,
            "mean": values_series.mean(),
            "median": values_series.median(),
            "p25": values_series.quantile(0.25),
            "p75": values_series.quantile(0.75),
            "min": values_series.min(),
            "max": values_series.max(),
        }

        # Calculate coverage
        if freq is not None:
            expected_hours = _get_expected_hours(freq)
            stats["coverage"] = len(values) / expected_hours
        else:
            # For "all" period, calculate based on date range
            date_range = df["date_time"].max() - df["date_time"].min()
            expected_hours = max(1, date_range.total_seconds() / 3600)
            stats["coverage"] = len(values) / expected_hours

        # Calculate AQI using the appropriate statistic for the index
        aqi_result = _calculate_pollutant_aqi(
            index_module,
            index,
            pollutant,
            stats,
        )

        stats["aqi_value"] = aqi_result.value
        stats["aqi_category"] = aqi_result.category

        results.append(stats)

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)

    # Check coverage and warn
    if warn_low_coverage and "coverage" in result_df.columns:
        low_coverage = result_df[result_df["coverage"] < min_coverage]
        if not low_coverage.empty:
            periods = low_coverage["period"].unique()
            warnings.warn(
                f"{len(periods)} period(s) have coverage below {min_coverage:.0%}. "
                f"Results may be unreliable. Suppress with warn_low_coverage=False.",
                UserWarning,
                stacklevel=2,
            )

    # Add overall AQI per site/period
    result_df = _add_overall_aqi(result_df)

    # Format output
    if overall_only:
        # Keep only overall rows
        overall_df = result_df[result_df["pollutant"] == "_overall"].copy()
        overall_df = overall_df.rename(columns={"pollutant": "dominant_pollutant"})
        # Get actual dominant pollutant
        overall_df["dominant_pollutant"] = overall_df.apply(
            lambda row: _get_dominant_pollutant(
                result_df, row["site_code"], row["period"]
            ),
            axis=1,
        )
        return overall_df[
            ["site_code", "period", "aqi_value", "aqi_category", "dominant_pollutant"]
        ]

    if format == "wide":
        return _to_wide_format(result_df)

    return result_df


def aqi_timeseries(
    data: pd.DataFrame,
    index: str = "UK_DAQI",
    include_rolling: bool = True,
) -> pd.DataFrame:
    """
    Calculate AQI values as a time series with proper rolling averages.

    This function calculates the appropriate rolling averages required by each
    index (e.g., 8-hour for O3, 24-hour for PM2.5) and returns AQI values
    for each timestamp where sufficient data is available.

    Args:
        data: DataFrame from aeolus.download()
        index: AQI index to use (default: "UK_DAQI")
        include_rolling: Include rolling average columns in output

    Returns:
        DataFrame with columns:
            site_code, date_time, pollutant, value, rolling_avg,
            aqi_value, aqi_category

        NaN values indicate insufficient data for the rolling calculation.

    Example:
        >>> ts = metrics.aqi_timeseries(data, index="UK_DAQI")
        >>> # Plot hourly AQI
        >>> ts.pivot(index="date_time", columns="pollutant", values="aqi_value").plot()
    """
    import warnings

    validate_data(data)

    index_info = get_index(index)
    if index_info is None:
        raise ValueError(f"Unknown index '{index}'. Available: {list_indices()}")

    index_module = _get_index_module(index)

    df = data.copy()
    df["date_time"] = pd.to_datetime(df["date_time"])
    df["pollutant_std"] = df["measurand"].apply(standardise_pollutant)
    df = df.sort_values(["site_code", "pollutant_std", "date_time"])

    results = []

    for (site, pollutant), group in df.groupby(["site_code", "pollutant_std"]):
        if pollutant is None:
            continue

        if pollutant not in index_info["pollutants"]:
            continue

        # Get averaging period for this pollutant
        avg_period = _get_averaging_period(index_module, pollutant)
        window_hours = _period_to_hours(avg_period)

        # Set datetime index for rolling
        group = group.set_index("date_time").sort_index()

        # Convert values to µg/m³
        group["value_ugm3"] = group.apply(
            lambda row: ensure_ugm3(row["value"], pollutant, row["units"], warn=False)
            if pd.notna(row["value"])
            else None,
            axis=1,
        )

        # Calculate rolling average
        group["rolling_avg"] = (
            group["value_ugm3"]
            .rolling(
                window=f"{window_hours}h",
                min_periods=int(window_hours * 0.75),  # 75% coverage
            )
            .mean()
        )

        # Calculate AQI for each row with valid rolling avg
        for dt, row in group.iterrows():
            if pd.isna(row["rolling_avg"]):
                aqi_val, aqi_cat = None, None
            else:
                try:
                    result = index_module.calculate(row["rolling_avg"], pollutant)
                    aqi_val, aqi_cat = result.value, result.category
                except Exception:
                    aqi_val, aqi_cat = None, None

            row_data = {
                "site_code": site,
                "date_time": dt,
                "pollutant": pollutant,
                "value": row["value_ugm3"],
                "aqi_value": aqi_val,
                "aqi_category": aqi_cat,
            }
            if include_rolling:
                row_data["rolling_avg"] = row["rolling_avg"]

            results.append(row_data)

    return pd.DataFrame(results)


def aqi_check_who(
    data: pd.DataFrame,
    target: Literal["AQG", "IT-1", "IT-2", "IT-3", "IT-4"] = "AQG",
    averaging_period: str | None = None,
) -> pd.DataFrame:
    """
    Check air quality data against WHO guidelines.

    Args:
        data: DataFrame from aeolus.download()
        target: WHO target level to check against:
                "AQG" = Air Quality Guideline (strictest, default)
                "IT-4" = Interim Target 4
                "IT-3" = Interim Target 3
                "IT-2" = Interim Target 2
                "IT-1" = Interim Target 1 (least strict)
        averaging_period: Override default averaging period
                         (default varies by pollutant)

    Returns:
        DataFrame with columns:
            site_code, pollutant, mean_concentration, guideline_value,
            meets_guideline, exceedance_ratio, message

    Example:
        >>> compliance = metrics.aqi_check_who(data)
        >>> print(compliance[["pollutant", "meets_guideline", "exceedance_ratio"]])
        >>>
        >>> # Check against less strict interim target
        >>> compliance_it1 = metrics.aqi_check_who(data, target="IT-1")
    """
    from .indices import who

    validate_data(data)

    df = data.copy()
    df["date_time"] = pd.to_datetime(df["date_time"])
    df["pollutant_std"] = df["measurand"].apply(standardise_pollutant)

    results = []

    for (site, pollutant), group in df.groupby(["site_code", "pollutant_std"]):
        if pollutant is None or pollutant not in who.GUIDELINES:
            continue

        # Convert values to proper units
        values = []
        for _, row in group.iterrows():
            if pd.notna(row["value"]):
                # WHO uses µg/m³ (mg/m³ for CO)
                if pollutant == "CO":
                    # Keep as mg/m³ if already in mg/m³
                    if row["units"].lower() in ("mg/m3", "mg/m³"):
                        values.append(row["value"])
                    else:
                        # Convert from µg/m³ to mg/m³
                        values.append(row["value"] / 1000)
                else:
                    val = ensure_ugm3(row["value"], pollutant, row["units"], warn=False)
                    values.append(val)

        if not values:
            continue

        mean_conc = sum(values) / len(values)

        try:
            result = who.check_guideline(
                mean_conc,
                pollutant,
                averaging_period,
                target,
            )

            results.append(
                {
                    "site_code": site,
                    "pollutant": pollutant,
                    "mean_concentration": mean_conc,
                    "guideline_value": result.guideline_value,
                    "meets_guideline": result.meets_guideline,
                    "exceedance_ratio": result.exceedance_ratio,
                    "message": result.message,
                }
            )
        except ValueError:
            # Target not available for this pollutant/period
            continue

    return pd.DataFrame(results)


# =============================================================================
# Internal Helpers
# =============================================================================


def _get_index_module(index: str):
    """Get the module for an index."""
    from .indices import china, eu_caqi, india_naqi, uk_daqi, us_epa, who

    modules = {
        "UK_DAQI": uk_daqi,
        "US_EPA": us_epa,
        "CHINA": china,
        "WHO": who,
        "EU_CAQI_ROADSIDE": eu_caqi,
        "EU_CAQI_BACKGROUND": eu_caqi,
        "INDIA_NAQI": india_naqi,
    }

    return modules.get(index)


def _get_averaging_period(index_module, pollutant: str) -> str:
    """Get the averaging period for a pollutant in an index."""
    if hasattr(index_module, "get_averaging_period"):
        return index_module.get_averaging_period(pollutant)
    return "24h"


def _period_to_hours(period: str) -> int:
    """Convert period string to hours."""
    period = period.lower().replace("hr", "h").replace("hour", "h")
    if period == "15min":
        return 1  # Treat as 1 hour minimum
    if period.endswith("h"):
        return int(period[:-1])
    if period.endswith("d") or period == "24h":
        return 24
    return 24  # Default


def _get_expected_hours(freq: str) -> int:
    """Get expected hours for a frequency."""
    expected = {
        "D": 24,
        "W": 168,
        "M": 720,  # ~30 days
        "Q": 2160,  # ~90 days
        "Y": 8760,  # 365 days
    }
    return expected.get(freq, 24)


def _calculate_pollutant_aqi(
    index_module,
    index: str,
    pollutant: str,
    stats: dict,
) -> AQIResult:
    """Calculate AQI for a pollutant using appropriate statistic."""
    # Different indices use different statistics
    # DAQI/EPA: typically use max of rolling averages
    # For summary purposes, we use the mean

    concentration = stats["mean"]

    try:
        return index_module.calculate(concentration, pollutant)
    except Exception:
        return AQIResult(
            value=None,
            category=None,
            color=None,
            pollutant=pollutant,
            concentration=concentration,
            unit="µg/m³",
        )


def _add_overall_aqi(df: pd.DataFrame) -> pd.DataFrame:
    """Add overall AQI rows for each site/period."""
    overall_rows = []

    for (site, period), group in df.groupby(["site_code", "period"]):
        # Overall AQI is the maximum across pollutants
        valid = group[group["aqi_value"].notna()]
        if valid.empty:
            continue

        max_row = valid.loc[valid["aqi_value"].idxmax()]

        overall_rows.append(
            {
                "site_code": site,
                "period": period,
                "pollutant": "_overall",
                "mean": None,
                "median": None,
                "p25": None,
                "p75": None,
                "min": None,
                "max": None,
                "coverage": None,
                "aqi_value": max_row["aqi_value"],
                "aqi_category": max_row["aqi_category"],
            }
        )

    if overall_rows:
        overall_df = pd.DataFrame(overall_rows)
        df = pd.concat([df, overall_df], ignore_index=True)

    return df


def _get_dominant_pollutant(df: pd.DataFrame, site: str, period: str) -> str:
    """Get the pollutant driving the overall AQI."""
    subset = df[
        (df["site_code"] == site)
        & (df["period"] == period)
        & (df["pollutant"] != "_overall")
    ]
    if subset.empty:
        return "unknown"

    max_idx = subset["aqi_value"].idxmax()
    return subset.loc[max_idx, "pollutant"]


def _to_wide_format(df: pd.DataFrame) -> pd.DataFrame:
    """Convert long format to wide format."""
    # Separate overall from pollutant rows
    overall = df[df["pollutant"] == "_overall"].copy()
    pollutants = df[df["pollutant"] != "_overall"].copy()

    # Pivot pollutant data
    if pollutants.empty:
        return overall

    # Create wide columns for each pollutant
    wide_data = []

    for (site, period), group in pollutants.groupby(["site_code", "period"]):
        row = {"site_code": site, "period": period}

        for _, poll_row in group.iterrows():
            poll = poll_row["pollutant"].lower().replace(".", "")
            row[f"{poll}_mean"] = poll_row["mean"]
            row[f"{poll}_aqi"] = poll_row["aqi_value"]

        # Add overall
        overall_row = overall[
            (overall["site_code"] == site) & (overall["period"] == period)
        ]
        if not overall_row.empty:
            row["overall_aqi"] = overall_row.iloc[0]["aqi_value"]
            row["overall_category"] = overall_row.iloc[0]["aqi_category"]
            row["dominant_pollutant"] = _get_dominant_pollutant(df, site, period)

        wide_data.append(row)

    return pd.DataFrame(wide_data)
