#!/usr/bin/env python3
"""
Stress testing for Aeolus with large synthetic datasets.

This module generates synthetic air quality data at various scales
to test memory usage, performance, and edge case handling.

Usage:
    python -m tests.stress_test [--rows N] [--profile]

Examples:
    python -m tests.stress_test --rows 1000000
    python -m tests.stress_test --rows 10000000 --profile
"""

import argparse
import gc
import sys
import time
from datetime import datetime, timedelta
from typing import Callable

import numpy as np
import pandas as pd

# =============================================================================
# Synthetic Data Generation
# =============================================================================


def generate_synthetic_data(
    n_rows: int | None = None,
    n_sites: int = 10,
    n_days: int | None = None,
    pollutants: list[str] | None = None,
    start_date: datetime | None = None,
    missing_rate: float = 0.05,
    include_outliers: bool = True,
    irregular_timestamps: bool = False,
    site_pollutant_coverage: str = "full",  # "full", "partial", "sparse"
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic air quality data for stress testing.

    Args:
        n_rows: Target number of rows (overrides n_sites/n_days calculation)
        n_sites: Number of monitoring sites
        n_days: Number of days of data per site
        pollutants: List of pollutants to include
        start_date: Start date for the data
        missing_rate: Fraction of values to set as NaN (0.0 to 1.0)
        include_outliers: Include extreme values (~1% of data)
        irregular_timestamps: Use irregular instead of hourly timestamps
        site_pollutant_coverage: How pollutants are distributed across sites
            - "full": All sites have all pollutants
            - "partial": Sites have random subsets (50-100%)
            - "sparse": Sites have minimal overlap (20-50%)
        seed: Random seed for reproducibility

    Returns:
        DataFrame in standard Aeolus format with columns:
        site_name, site_code, date_time, measurand, value,
        source_network, ratification, units, created_at
    """
    rng = np.random.default_rng(seed)

    # Defaults
    if pollutants is None:
        pollutants = ["NO2", "PM2.5", "PM10", "O3", "SO2", "CO", "NO", "NOX"]

    if start_date is None:
        start_date = datetime(2020, 1, 1)

    # Calculate dimensions
    if n_rows is not None:
        # Work backwards from target rows
        n_pollutants = len(pollutants)
        rows_per_site_pollutant = n_rows // (n_sites * n_pollutants)
        n_days = max(1, rows_per_site_pollutant // 24)
    elif n_days is None:
        n_days = 365  # Default to 1 year

    n_hours = n_days * 24

    # Generate site metadata
    site_names = [f"Test Site {i:03d}" for i in range(n_sites)]
    site_codes = [f"TS{i:03d}" for i in range(n_sites)]

    # Generate timestamps
    if irregular_timestamps:
        # Random timestamps within the period
        timestamps = [
            start_date + timedelta(hours=int(rng.integers(0, n_hours)))
            for _ in range(n_hours)
        ]
        timestamps = sorted(set(timestamps))
    else:
        # Regular hourly timestamps
        timestamps = [start_date + timedelta(hours=h) for h in range(n_hours)]

    # Determine which pollutants each site measures
    site_pollutants = {}
    for site_code in site_codes:
        if site_pollutant_coverage == "full":
            site_pollutants[site_code] = pollutants.copy()
        elif site_pollutant_coverage == "partial":
            # 50-100% of pollutants
            n_poll = rng.integers(len(pollutants) // 2, len(pollutants) + 1)
            site_pollutants[site_code] = list(
                rng.choice(pollutants, size=n_poll, replace=False)
            )
        else:  # sparse
            # 20-50% of pollutants
            n_poll = rng.integers(
                max(1, len(pollutants) // 5), max(2, len(pollutants) // 2) + 1
            )
            site_pollutants[site_code] = list(
                rng.choice(pollutants, size=n_poll, replace=False)
            )

    # Typical concentration ranges (μg/m³)
    pollutant_params = {
        "NO2": {"mean": 30, "std": 15, "min": 0, "max": 200},
        "PM2.5": {"mean": 12, "std": 8, "min": 0, "max": 100},
        "PM10": {"mean": 20, "std": 12, "min": 0, "max": 150},
        "O3": {"mean": 50, "std": 25, "min": 0, "max": 180},
        "SO2": {"mean": 5, "std": 3, "min": 0, "max": 50},
        "CO": {"mean": 0.5, "std": 0.3, "min": 0, "max": 5},
        "NO": {"mean": 20, "std": 15, "min": 0, "max": 150},
        "NOX": {"mean": 50, "std": 25, "min": 0, "max": 300},
    }

    # Build data rows
    rows = []
    for site_idx, (site_name, site_code) in enumerate(zip(site_names, site_codes)):
        for pollutant in site_pollutants[site_code]:
            params = pollutant_params.get(
                pollutant, {"mean": 25, "std": 10, "min": 0, "max": 100}
            )

            # Generate values with diurnal pattern
            n_ts = len(timestamps)
            base_values = rng.normal(params["mean"], params["std"], n_ts)

            # Add diurnal pattern (traffic peaks)
            hours = np.array([ts.hour for ts in timestamps])
            diurnal = 1 + 0.3 * np.sin((hours - 8) * np.pi / 12)  # Peak at 8am, 8pm
            values = base_values * diurnal

            # Add site-specific offset
            site_offset = rng.uniform(-0.2, 0.2) * params["mean"]
            values += site_offset

            # Clip to valid range
            values = np.clip(values, params["min"], params["max"])

            # Add outliers
            if include_outliers:
                n_outliers = int(n_ts * 0.01)
                outlier_idx = rng.choice(n_ts, size=n_outliers, replace=False)
                values[outlier_idx] = rng.uniform(
                    params["max"] * 0.8, params["max"] * 1.5, n_outliers
                )

            # Add missing values
            if missing_rate > 0:
                n_missing = int(n_ts * missing_rate)
                missing_idx = rng.choice(n_ts, size=n_missing, replace=False)
                values[missing_idx] = np.nan

            # Create rows for this site/pollutant combination
            for ts, val in zip(timestamps, values):
                rows.append(
                    {
                        "site_name": site_name,
                        "site_code": site_code,
                        "date_time": ts,
                        "measurand": pollutant,
                        "value": val,
                        "source_network": "SYNTHETIC",
                        "ratification": "None",
                        "units": "ug/m3" if pollutant != "CO" else "mg/m3",
                    }
                )

    # Create DataFrame
    df = pd.DataFrame(rows)

    # Add created_at
    df["created_at"] = datetime.now()

    # Convert to categorical for memory efficiency
    for col in [
        "site_name",
        "site_code",
        "measurand",
        "source_network",
        "ratification",
        "units",
    ]:
        df[col] = df[col].astype("category")

    # Shuffle rows to simulate real-world data ordering
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)

    return df


# =============================================================================
# Memory Profiling
# =============================================================================


def get_memory_mb() -> float:
    """Get current process memory usage in MB."""
    import os

    try:
        # Linux/Mac
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
    except ImportError:
        pass

    try:
        # Cross-platform fallback
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0


def profile_function(
    func: Callable, *args, label: str = "Operation", **kwargs
) -> tuple:
    """
    Profile a function's execution time and memory usage.

    Returns:
        Tuple of (result, elapsed_seconds, memory_delta_mb)
    """
    gc.collect()
    mem_before = get_memory_mb()
    start_time = time.perf_counter()

    result = func(*args, **kwargs)

    elapsed = time.perf_counter() - start_time
    gc.collect()
    mem_after = get_memory_mb()
    mem_delta = mem_after - mem_before

    print(f"  {label}: {elapsed:.2f}s, memory delta: {mem_delta:+.1f} MB")

    return result, elapsed, mem_delta


# =============================================================================
# Stress Tests
# =============================================================================


def stress_test_data_generation(n_rows: int, profile: bool = False):
    """Test synthetic data generation at scale."""
    print(f"\n{'=' * 60}")
    print(f"STRESS TEST: Data Generation ({n_rows:,} rows)")
    print("=" * 60)

    if profile:
        df, elapsed, mem_delta = profile_function(
            generate_synthetic_data, n_rows=n_rows, label="Generate data"
        )
    else:
        start = time.perf_counter()
        df = generate_synthetic_data(n_rows=n_rows)
        elapsed = time.perf_counter() - start
        print(f"  Generated in {elapsed:.2f}s")

    print(f"  Actual rows: {len(df):,}")
    print(f"  Memory usage: {df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB")
    print(f"  Sites: {df['site_code'].nunique()}")
    print(f"  Pollutants: {df['measurand'].nunique()}")
    print(f"  Date range: {df['date_time'].min()} to {df['date_time'].max()}")

    return df


def stress_test_viz_preparation(df: pd.DataFrame, profile: bool = False):
    """Test visualisation data preparation at scale."""
    print(f"\n{'=' * 60}")
    print(f"STRESS TEST: Visualisation Preparation ({len(df):,} rows)")
    print("=" * 60)

    from aeolus.viz.prepare import prepare_timeseries

    # Test with different downsampling targets
    for target in [1000, 5000, 10000]:
        label = f"prepare_timeseries (target={target})"
        if profile:
            result, elapsed, mem_delta = profile_function(
                prepare_timeseries, df, downsample=target, label=label
            )
        else:
            start = time.perf_counter()
            result = prepare_timeseries(df, downsample=target)
            elapsed = time.perf_counter() - start
            print(f"  {label}: {elapsed:.2f}s")

        print(f"    Output rows: {len(result.data):,}")


def stress_test_plotting(df: pd.DataFrame, profile: bool = False):
    """Test plotting functions at scale."""
    print(f"\n{'=' * 60}")
    print(f"STRESS TEST: Plotting Functions ({len(df):,} rows)")
    print("=" * 60)

    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt

    from aeolus import viz

    # Get a single pollutant for single-pollutant plots
    single_pollutant = df["measurand"].iloc[0]

    tests = [
        ("plot_timeseries", lambda: viz.plot_timeseries(df, downsample=2000)),
        ("plot_diurnal", lambda: viz.plot_diurnal(df)),
        ("plot_weekly", lambda: viz.plot_weekly(df)),
        ("plot_monthly", lambda: viz.plot_monthly(df)),
        ("plot_distribution", lambda: viz.plot_distribution(df, single_pollutant)),
        ("plot_calendar", lambda: viz.plot_calendar(df, single_pollutant)),
    ]

    for name, func in tests:
        try:
            if profile:
                fig, elapsed, mem_delta = profile_function(func, label=name)
            else:
                start = time.perf_counter()
                fig = func()
                elapsed = time.perf_counter() - start
                print(f"  {name}: {elapsed:.2f}s")
            plt.close(fig)
        except Exception as e:
            print(f"  {name}: FAILED - {e}")


def stress_test_metrics(df: pd.DataFrame, profile: bool = False):
    """Test metrics calculations at scale."""
    print(f"\n{'=' * 60}")
    print(f"STRESS TEST: Metrics Calculations ({len(df):,} rows)")
    print("=" * 60)

    from aeolus import metrics

    # Test different AQI indices
    indices = ["UK_DAQI", "US_EPA", "EU_CAQI_BACKGROUND"]

    for index in indices:
        label = f"aqi_timeseries ({index})"
        try:
            if profile:
                result, elapsed, mem_delta = profile_function(
                    metrics.aqi_timeseries, df, index=index, label=label
                )
            else:
                start = time.perf_counter()
                result = metrics.aqi_timeseries(df, index=index)
                elapsed = time.perf_counter() - start
                print(f"  {label}: {elapsed:.2f}s")
            print(f"    Output rows: {len(result):,}")
        except Exception as e:
            print(f"  {label}: FAILED - {e}")

    # Test summary statistics
    label = "aqi_summary"
    try:
        if profile:
            result, elapsed, mem_delta = profile_function(
                metrics.aqi_summary, df, index="UK_DAQI", label=label
            )
        else:
            start = time.perf_counter()
            result = metrics.aqi_summary(df, index="UK_DAQI")
            elapsed = time.perf_counter() - start
            print(f"  {label}: {elapsed:.2f}s")
    except Exception as e:
        print(f"  {label}: FAILED - {e}")


def stress_test_edge_cases(profile: bool = False):
    """Test edge cases and pathological data shapes."""
    print(f"\n{'=' * 60}")
    print("STRESS TEST: Edge Cases")
    print("=" * 60)

    import matplotlib

    from aeolus import viz

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Test 1: Single site, many pollutants
    print("\n  Case 1: Single site, 20 pollutants, 1 year")
    df = generate_synthetic_data(
        n_sites=1,
        n_days=365,
        pollutants=[f"POLL{i:02d}" for i in range(20)],
    )
    print(f"    Rows: {len(df):,}")
    try:
        fig = viz.plot_timeseries(df, downsample=2000)
        plt.close(fig)
        print("    plot_timeseries: OK")
    except Exception as e:
        print(f"    plot_timeseries: FAILED - {e}")

    # Test 2: Many sites, sparse pollutant coverage
    print("\n  Case 2: 100 sites, sparse pollutant coverage")
    df = generate_synthetic_data(
        n_sites=100,
        n_days=30,
        site_pollutant_coverage="sparse",
    )
    print(f"    Rows: {len(df):,}")
    try:
        fig = viz.plot_timeseries(df, downsample=2000)
        plt.close(fig)
        print("    plot_timeseries: OK")
    except Exception as e:
        print(f"    plot_timeseries: FAILED - {e}")

    # Test 3: High missing data rate
    print("\n  Case 3: 50% missing data")
    df = generate_synthetic_data(
        n_sites=5,
        n_days=90,
        missing_rate=0.5,
    )
    print(f"    Rows: {len(df):,}")
    print(
        f"    Missing values: {df['value'].isna().sum():,} ({df['value'].isna().mean() * 100:.0f}%)"
    )
    try:
        fig = viz.plot_diurnal(df)
        plt.close(fig)
        print("    plot_diurnal: OK")
    except Exception as e:
        print(f"    plot_diurnal: FAILED - {e}")

    # Test 4: Extreme values
    print("\n  Case 4: Extreme outliers")
    df = generate_synthetic_data(
        n_sites=3,
        n_days=30,
        include_outliers=True,
    )
    # Inject some really extreme values
    extreme_idx = df.sample(n=100).index
    df.loc[extreme_idx, "value"] = df.loc[extreme_idx, "value"] * 100
    print(f"    Value range: {df['value'].min():.1f} to {df['value'].max():.1f}")
    try:
        fig = viz.plot_distribution(df, df["measurand"].iloc[0])
        plt.close(fig)
        print("    plot_distribution: OK")
    except Exception as e:
        print(f"    plot_distribution: FAILED - {e}")

    # Test 5: Very short time series
    print("\n  Case 5: Very short time series (1 day)")
    df = generate_synthetic_data(
        n_sites=5,
        n_days=1,
    )
    print(f"    Rows: {len(df):,}")
    try:
        fig = viz.plot_timeseries(df, downsample=False)
        plt.close(fig)
        print("    plot_timeseries: OK")
    except Exception as e:
        print(f"    plot_timeseries: FAILED - {e}")

    # Test 6: Irregular timestamps
    print("\n  Case 6: Irregular timestamps")
    df = generate_synthetic_data(
        n_sites=3,
        n_days=30,
        irregular_timestamps=True,
    )
    print(f"    Rows: {len(df):,}")
    try:
        fig = viz.plot_timeseries(df, downsample=1000)
        plt.close(fig)
        print("    plot_timeseries: OK")
    except Exception as e:
        print(f"    plot_timeseries: FAILED - {e}")


def run_full_stress_test(n_rows: int = 1_000_000, profile: bool = False):
    """Run the complete stress test suite."""
    print("\n" + "=" * 60)
    print(f"AEOLUS STRESS TEST SUITE")
    print(f"Target rows: {n_rows:,}")
    print(f"Profiling: {'enabled' if profile else 'disabled'}")
    print("=" * 60)

    total_start = time.perf_counter()

    # Generate data
    df = stress_test_data_generation(n_rows, profile)

    # Run tests
    stress_test_viz_preparation(df, profile)
    stress_test_plotting(df, profile)
    stress_test_metrics(df, profile)

    # Edge cases (uses its own data)
    stress_test_edge_cases(profile)

    total_elapsed = time.perf_counter() - total_start
    print(f"\n{'=' * 60}")
    print(f"COMPLETE - Total time: {total_elapsed:.1f}s")
    print("=" * 60)


# =============================================================================
# CLI Entry Point
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Stress test Aeolus with large synthetic datasets"
    )
    parser.add_argument(
        "--rows",
        "-n",
        type=int,
        default=1_000_000,
        help="Target number of rows (default: 1,000,000)",
    )
    parser.add_argument(
        "--profile", "-p", action="store_true", help="Enable memory profiling"
    )
    parser.add_argument(
        "--edge-cases-only", "-e", action="store_true", help="Only run edge case tests"
    )

    args = parser.parse_args()

    if args.edge_cases_only:
        stress_test_edge_cases(args.profile)
    else:
        run_full_stress_test(args.rows, args.profile)


if __name__ == "__main__":
    main()
