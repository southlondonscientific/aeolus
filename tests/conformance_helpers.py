"""Reusable assertion helpers for validating live-downloaded air quality data.

Each function checks one aspect of conformance and raises ``AssertionError``
with a descriptive message that includes the *source* name.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from aeolus.types import DATA_COLUMNS, METADATA_COLUMNS
from aeolus.transforms import (
    pipe,
    drop_duplicates,
    sort_values,
    reset_index,
    categorise_columns,
)

# ---------------------------------------------------------------------------
# Physical-plausibility bounds  (lower, upper) in ug/m3
# ---------------------------------------------------------------------------
_BOUNDS: dict[str, tuple[float, float]] = {
    "PM2.5": (-10, 2000),   # small negatives from instrument baseline drift
    "PM10": (-10, 5000),
    "NO2": (-10, 1000),
    "O3": (-10, 600),
    "SO2": (-50, 2000),     # some networks report larger negative baselines
    "CO": (-50, 50000),
}
_DEFAULT_BOUNDS: tuple[float, float] = (-100, 100_000)

# Required metadata columns (excludes 'measurands' which is optional in some
# older metadata frames).
_META_REQUIRED = ["site_code", "latitude", "longitude", "source_network"]


# ============================================================================
# Schema assertions
# ============================================================================

def assert_data_schema(df: pd.DataFrame, source: str) -> None:
    """Assert all 8 DATA_COLUMNS are present."""
    missing = set(DATA_COLUMNS) - set(df.columns)
    assert not missing, f"[{source}] data missing columns: {sorted(missing)}"


def assert_metadata_schema(df: pd.DataFrame, source: str) -> None:
    """Assert required metadata columns are present."""
    missing = set(_META_REQUIRED) - set(df.columns)
    assert not missing, f"[{source}] metadata missing columns: {sorted(missing)}"


# ============================================================================
# Dtype assertions
# ============================================================================

def assert_data_dtypes(df: pd.DataFrame, source: str) -> None:
    """Assert correct dtypes for data columns. Skipped when *df* is empty."""
    if df.empty:
        return

    # date_time should be datetime and timezone-aware
    dt = df["date_time"]
    assert pd.api.types.is_datetime64_any_dtype(dt), (
        f"[{source}] date_time is not datetime (dtype={dt.dtype})"
    )
    assert getattr(dt.dt, "tz", None) is not None, (
        f"[{source}] date_time is not timezone-aware"
    )

    # value should be numeric
    assert pd.api.types.is_numeric_dtype(df["value"]), (
        f"[{source}] value is not numeric (dtype={df['value'].dtype})"
    )

    # string-like columns
    for col in ("site_code", "measurand", "source_network"):
        dtype = df[col].dtype
        ok = (
            pd.api.types.is_string_dtype(dtype)
            or pd.api.types.is_object_dtype(dtype)
            or pd.api.types.is_categorical_dtype(dtype)
        )
        assert ok, f"[{source}] {col} has unexpected dtype {dtype}"


def assert_metadata_dtypes(df: pd.DataFrame, source: str) -> None:
    """Assert latitude/longitude are numeric. Skipped when *df* is empty."""
    if df.empty:
        return

    for col in ("latitude", "longitude"):
        if col in df.columns:
            assert pd.api.types.is_numeric_dtype(df[col]), (
                f"[{source}] {col} is not numeric (dtype={df[col].dtype})"
            )


# ============================================================================
# Physical plausibility
# ============================================================================

def assert_physical_plausibility(df: pd.DataFrame, source: str) -> None:
    """Per-measurand bounds check on *value* column."""
    if df.empty:
        return

    for measurand, grp in df.groupby("measurand"):
        # Only check known air quality measurands — skip meteorological
        # parameters like Pressure, Temperature, Humidity
        if str(measurand) not in _BOUNDS:
            continue
        lo, hi = _BOUNDS[str(measurand)]
        vals = grp["value"].dropna()
        if vals.empty:
            continue
        below = (vals < lo).sum()
        above = (vals > hi).sum()
        assert below == 0, (
            f"[{source}] {measurand}: {below} values below {lo}"
        )
        assert above == 0, (
            f"[{source}] {measurand}: {above} values above {hi}"
        )


def assert_coordinates_valid(df: pd.DataFrame, source: str) -> None:
    """Assert latitude in [-90, 90] and longitude in [-180, 180]."""
    if "latitude" not in df.columns or "longitude" not in df.columns:
        return

    lat = df["latitude"].dropna()
    lon = df["longitude"].dropna()

    if lat.empty and lon.empty:
        return

    if not lat.empty:
        bad_lat = ((lat < -90) | (lat > 90)).sum()
        assert bad_lat == 0, (
            f"[{source}] {bad_lat} latitudes outside [-90, 90]"
        )

    if not lon.empty:
        bad_lon = ((lon < -180) | (lon > 180)).sum()
        assert bad_lon == 0, (
            f"[{source}] {bad_lon} longitudes outside [-180, 180]"
        )


# ============================================================================
# Pipeline survival
# ============================================================================

def assert_survives_pipeline(df: pd.DataFrame, source: str) -> None:
    """Assert data survives a standard normalisation pipeline."""
    if df.empty:
        return

    result = pipe(
        df,
        drop_duplicates(subset=["site_code", "date_time", "measurand"]),
        sort_values(["site_code", "date_time"]),
        reset_index(),
        categorise_columns("site_code", "measurand", "source_network"),
    )

    assert isinstance(result, pd.DataFrame), (
        f"[{source}] pipeline did not return a DataFrame"
    )
    assert len(result) <= len(df), (
        f"[{source}] pipeline produced more rows ({len(result)}) than input ({len(df)})"
    )
    assert len(result) > 0, (
        f"[{source}] pipeline produced zero rows"
    )


def assert_summarise_valid(df: pd.DataFrame, source: str) -> None:
    """Assert ``aeolus.api.summarise()`` produces a valid summary."""
    if df.empty:
        return

    # Import inside function to avoid circular imports
    from aeolus.api import summarise

    summary = summarise(df)

    assert not summary.empty, f"[{source}] summarise() returned empty"
    assert (summary["valid"] <= summary["records"]).all(), (
        f"[{source}] summarise(): some valid > records"
    )
    assert (summary["data_capture"] >= 0).all(), (
        f"[{source}] summarise(): negative data_capture"
    )


# ============================================================================
# Cache roundtrip
# ============================================================================

def assert_cache_roundtrip(df: pd.DataFrame, source: str) -> None:
    """Assert data survives a Parquet write/read roundtrip."""
    if df.empty:
        return

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "roundtrip.parquet"
        df.to_parquet(path)
        back = pd.read_parquet(path)

    assert len(back) == len(df), (
        f"[{source}] cache roundtrip changed row count: {len(df)} -> {len(back)}"
    )
    assert set(back.columns) == set(df.columns), (
        f"[{source}] cache roundtrip changed columns"
    )
    # Timezone must survive
    if "date_time" in back.columns and not back.empty:
        assert getattr(back["date_time"].dt, "tz", None) is not None, (
            f"[{source}] cache roundtrip lost timezone on date_time"
        )


# ============================================================================
# Combined runners
# ============================================================================

def run_data_conformance(df: pd.DataFrame, source: str) -> None:
    """Run all data-conformance assertions."""
    assert_data_schema(df, source)
    assert_data_dtypes(df, source)
    assert_physical_plausibility(df, source)
    assert_survives_pipeline(df, source)
    assert_summarise_valid(df, source)
    assert_cache_roundtrip(df, source)


def run_metadata_conformance(df: pd.DataFrame, source: str) -> None:
    """Run all metadata-conformance assertions."""
    assert_metadata_schema(df, source)
    assert_metadata_dtypes(df, source)
    assert_coordinates_valid(df, source)
