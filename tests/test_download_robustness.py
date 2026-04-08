"""Hypothesis property tests for download pipeline robustness.

These tests throw messy, adversarial DataFrames at core pipeline functions
to verify they don't crash or silently corrupt data.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from aeolus.transforms import (
    pipe,
    compose,
    drop_duplicates,
    sort_values,
    reset_index,
    filter_rows,
    select_columns,
    categorise_columns,
)
from aeolus.api import summarise, _parse_last
from aeolus.types import DATA_COLUMNS
from conftest_strategies import aeolus_dataframes

pytestmark = pytest.mark.property

# Key columns used for deduplication (site + time + measurand)
_DEDUP_COLS = ["site_code", "date_time", "measurand"]


# ============================================================================
# Normalisation Pipeline Robustness
# ============================================================================


class TestNormalisationPipelineRobustness:
    """Property tests for the composable transform pipeline."""

    @given(df=aeolus_dataframes(messy=True))
    @settings(max_examples=80, deadline=None)
    def test_full_pipeline_does_not_crash(self, df: pd.DataFrame) -> None:
        """A realistic normalisation pipeline never crashes on messy data."""
        pipeline = compose(
            drop_duplicates(subset=_DEDUP_COLS),
            sort_values(["site_code", "date_time"]),
            reset_index(),
            categorise_columns("site_code", "measurand", "source_network"),
        )
        result = pipeline(df)

        assert isinstance(result, pd.DataFrame)
        assert len(result) <= len(df)

    @given(df=aeolus_dataframes(messy=True))
    @settings(max_examples=80, deadline=None)
    def test_dedup_then_schema_check(self, df: pd.DataFrame) -> None:
        """After dedup and select_columns, all 8 standard columns are present."""
        pipeline = compose(
            drop_duplicates(subset=_DEDUP_COLS),
            select_columns(*DATA_COLUMNS),
        )
        result = pipeline(df)

        for col in DATA_COLUMNS:
            assert col in result.columns, f"Missing column: {col}"

    @given(df=aeolus_dataframes(messy=True))
    @settings(max_examples=80, deadline=None)
    def test_empty_df_through_pipeline(self, df: pd.DataFrame) -> None:
        """Filter to impossible condition, dedup, reset -- result is empty."""
        pipeline = compose(
            filter_rows(lambda d: d["value"] > 999999),
            drop_duplicates(subset=_DEDUP_COLS),
            reset_index(),
        )
        result = pipeline(df)

        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ============================================================================
# Summarise Robustness
# ============================================================================


class TestSummariseRobustness:
    """Property tests for the summarise() convenience function."""

    @given(df=aeolus_dataframes(messy=True, min_rows=0))
    @settings(max_examples=80, deadline=None)
    def test_summarise_does_not_crash(self, df: pd.DataFrame) -> None:
        """summarise() handles any valid-schema DataFrame without crashing."""
        result = summarise(df)
        assert isinstance(result, pd.DataFrame)
        if df.empty:
            assert result.empty

    @given(df=aeolus_dataframes(messy=True, min_rows=1))
    @settings(max_examples=80, deadline=None)
    def test_summarise_data_capture_bounded(self, df: pd.DataFrame) -> None:
        """data_capture is between 0 and 1 inclusive when result is non-empty."""
        result = summarise(df)
        if not result.empty:
            assert (result["data_capture"] >= 0).all()
            assert (result["data_capture"] <= 1).all()

    @given(df=aeolus_dataframes(messy=True, min_rows=1))
    @settings(max_examples=80, deadline=None)
    def test_summarise_valid_count_lte_records(self, df: pd.DataFrame) -> None:
        """valid <= records for all rows."""
        result = summarise(df)
        if not result.empty:
            assert (result["valid"] <= result["records"]).all()


# ============================================================================
# NaN Handling
# ============================================================================


class TestNaNHandling:
    """Property tests for NaN preservation and removal."""

    @given(df=aeolus_dataframes(messy=True, min_rows=1))
    @settings(max_examples=80, deadline=None)
    def test_nan_values_preserved_through_transforms(self, df: pd.DataFrame) -> None:
        """NaN count in 'value' column unchanged after sort + reset_index."""
        nan_before = df["value"].isna().sum()

        pipeline = compose(
            sort_values(["site_code", "date_time"]),
            reset_index(),
        )
        result = pipeline(df)

        nan_after = result["value"].isna().sum()
        assert nan_before == nan_after

    @given(df=aeolus_dataframes(messy=True, min_rows=1))
    @settings(max_examples=80, deadline=None)
    def test_filter_notna_removes_nans(self, df: pd.DataFrame) -> None:
        """filter_rows(lambda d: d['value'].notna()) removes all NaNs."""
        result = pipe(df, filter_rows(lambda d: d["value"].notna()))
        assert result["value"].isna().sum() == 0


# ============================================================================
# Duplicate Handling
# ============================================================================


class TestDuplicateHandling:
    """Property tests for deduplication behaviour."""

    @given(df=aeolus_dataframes(messy=True, min_rows=1))
    @settings(max_examples=80, deadline=None)
    def test_dedup_is_idempotent(self, df: pd.DataFrame) -> None:
        """Dedup on key cols twice == once."""
        dedup = drop_duplicates(subset=_DEDUP_COLS)
        once = dedup(df)
        twice = dedup(once)

        pd.testing.assert_frame_equal(
            once.reset_index(drop=True),
            twice.reset_index(drop=True),
        )

    @given(df=aeolus_dataframes(messy=False, min_rows=1))
    @settings(max_examples=80, deadline=None)
    def test_explicit_duplicates_removed(self, df: pd.DataFrame) -> None:
        """Concat df with itself, dedup -- recovers original row count."""
        # The input may already contain duplicates, so dedup it first
        dedup = drop_duplicates()
        baseline = dedup(df)
        doubled = pd.concat([df, df], ignore_index=True)
        deduped = dedup(doubled)
        assert len(deduped) == len(baseline)


# ============================================================================
# _parse_last Robustness
# ============================================================================

# Safe units that won't overflow for values up to 365
_SAFE_UNITS = ["d", "day", "days", "h", "hr", "hours", "w", "week", "weeks"]

_LAST_PATTERN = re.compile(
    r"^(\d+)\s*(min|mins|minute|minutes|h|hr|hrs|hour|hours"
    r"|d|day|days|w|week|weeks|m|month|months|y|year|years)$",
    re.I,
)


class TestParseLastRobustness:
    """Property tests for the _parse_last date shorthand parser."""

    @given(
        n=st.integers(min_value=1, max_value=365),
        unit=st.sampled_from(_SAFE_UNITS),
    )
    @settings(max_examples=80, deadline=None)
    def test_valid_shorthand_returns_two_datetimes(self, n: int, unit: str) -> None:
        """Valid shorthand produces start < end."""
        start, end = _parse_last(f"{n}{unit}")
        assert start < end

    @given(text=st.text(min_size=1, max_size=20))
    @settings(max_examples=80, deadline=None)
    def test_invalid_shorthand_raises(self, text: str) -> None:
        """Random text that doesn't match the pattern raises ValueError."""
        assume(not _LAST_PATTERN.match(text.strip()))
        with pytest.raises(ValueError):
            _parse_last(text)
