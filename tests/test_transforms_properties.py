"""Hypothesis property-based tests for aeolus.transforms module."""

from __future__ import annotations

import pytest
from hypothesis import given, assume
from hypothesis import strategies as st
import pandas as pd

from aeolus.transforms import (
    pipe,
    compose,
    rename_columns,
    add_column,
    drop_columns,
    select_columns,
    filter_rows,
    melt_measurands,
    drop_duplicates,
    reset_index,
    sort_values,
    categorise_columns,
)
from conftest_strategies import aeolus_dataframes, wide_dataframes

pytestmark = pytest.mark.property


# ---------------------------------------------------------------------------
# Composition Laws
# ---------------------------------------------------------------------------


class TestCompositionLaws:
    """Verify algebraic properties of pipe() and compose()."""

    @given(df=aeolus_dataframes(min_rows=0, max_rows=20))
    def test_identity(self, df: pd.DataFrame) -> None:
        """pipe(df) with no functions returns df unchanged."""
        result = pipe(df)
        pd.testing.assert_frame_equal(result, df)

    @given(df=aeolus_dataframes(min_rows=1, max_rows=20))
    def test_single_function_equivalence(self, df: pd.DataFrame) -> None:
        """pipe(df, f) produces the same result as f(df)."""
        f = add_column("test_col", "hello")
        result_pipe = pipe(df, f)
        result_direct = f(df)
        pd.testing.assert_frame_equal(result_pipe, result_direct)

    @given(df=aeolus_dataframes(min_rows=1, max_rows=20))
    def test_compose_equals_pipe(self, df: pd.DataFrame) -> None:
        """compose(f, g)(df) == pipe(df, f, g)."""
        f = add_column("extra", "x")
        g = drop_columns("units")
        result_compose = compose(f, g)(df)
        result_pipe = pipe(df, f, g)
        pd.testing.assert_frame_equal(result_compose, result_pipe)

    @given(df=aeolus_dataframes(min_rows=1, max_rows=20))
    def test_associativity(self, df: pd.DataFrame) -> None:
        """compose(f, compose(g, h)) == compose(compose(f, g), h)."""
        f = add_column("a", 1)
        g = add_column("b", 2)
        h = add_column("c", 3)
        left = compose(f, compose(g, h))(df)
        right = compose(compose(f, g), h)(df)
        pd.testing.assert_frame_equal(left, right)


# ---------------------------------------------------------------------------
# Column Operations
# ---------------------------------------------------------------------------


class TestColumnOperations:
    """Verify column add/drop/select/rename invariants."""

    @given(df=aeolus_dataframes(min_rows=1, max_rows=20))
    def test_add_column_preserves_rows(self, df: pd.DataFrame) -> None:
        """Adding a column does not change row count."""
        result = add_column("new_col", 42)(df)
        assert len(result) == len(df)

    @given(df=aeolus_dataframes(min_rows=1, max_rows=20))
    def test_drop_nonexistent_is_noop(self, df: pd.DataFrame) -> None:
        """Dropping a column that does not exist returns df unchanged."""
        result = drop_columns("this_column_does_not_exist_xyz")(df)
        pd.testing.assert_frame_equal(result, df)

    @given(df=aeolus_dataframes(min_rows=1, max_rows=20))
    def test_select_subset_of_columns(self, df: pd.DataFrame) -> None:
        """select_columns returns only the requested (existing) columns."""
        result = select_columns("site_code", "value", "nonexistent")(df)
        assert set(result.columns) == {"site_code", "value"}

    @given(df=aeolus_dataframes(min_rows=1, max_rows=20))
    def test_drop_then_select_disjoint(self, df: pd.DataFrame) -> None:
        """drop('value') then select('value') yields no columns for 'value'."""
        result = pipe(df, drop_columns("value"), select_columns("value"))
        assert "value" not in result.columns

    @given(df=aeolus_dataframes(min_rows=1, max_rows=20))
    def test_rename_preserves_row_count(self, df: pd.DataFrame) -> None:
        """Renaming columns does not change row count."""
        result = rename_columns({"site_code": "station"})(df)
        assert len(result) == len(df)


# ---------------------------------------------------------------------------
# Melt Invariants
# ---------------------------------------------------------------------------


class TestMeltInvariants:
    """Verify melt_measurands shape and column invariants."""

    @given(df=wide_dataframes(min_rows=1, max_rows=20))
    def test_melt_row_count(self, df: pd.DataFrame) -> None:
        """n rows with m measurands produces n*m rows."""
        id_vars = ["date", "site"]
        measurands = [c for c in df.columns if c not in id_vars]
        assume(len(measurands) > 0)
        result = melt_measurands(id_vars=id_vars)(df)
        assert len(result) == len(df) * len(measurands)

    @given(df=wide_dataframes(min_rows=1, max_rows=20))
    def test_melt_preserves_id_vars(self, df: pd.DataFrame) -> None:
        """id_var columns survive the melt."""
        id_vars = ["date", "site"]
        result = melt_measurands(id_vars=id_vars)(df)
        for col in id_vars:
            assert col in result.columns

    @given(df=wide_dataframes(min_rows=1, max_rows=20))
    def test_melt_creates_measurand_column(self, df: pd.DataFrame) -> None:
        """Result has 'measurand' and 'value' columns."""
        id_vars = ["date", "site"]
        measurands = [c for c in df.columns if c not in id_vars]
        assume(len(measurands) > 0)
        result = melt_measurands(id_vars=id_vars)(df)
        assert "measurand" in result.columns
        assert "value" in result.columns


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Verify dedup idempotence and size invariants."""

    @given(df=aeolus_dataframes(min_rows=1, max_rows=20, messy=True))
    def test_idempotent(self, df: pd.DataFrame) -> None:
        """Dedup applied twice gives the same result as once."""
        once = drop_duplicates()(df)
        twice = drop_duplicates()(once)
        pd.testing.assert_frame_equal(once.reset_index(drop=True), twice.reset_index(drop=True))

    @given(df=aeolus_dataframes(min_rows=1, max_rows=20))
    def test_result_no_larger_than_input(self, df: pd.DataFrame) -> None:
        """Dedup never adds rows."""
        result = drop_duplicates()(df)
        assert len(result) <= len(df)


# ---------------------------------------------------------------------------
# Sort and Reset
# ---------------------------------------------------------------------------


class TestSortAndReset:
    """Verify sort and reset_index invariants."""

    @given(df=aeolus_dataframes(min_rows=1, max_rows=20))
    def test_sort_preserves_row_count(self, df: pd.DataFrame) -> None:
        """Sorting does not add or remove rows."""
        result = sort_values("site_code")(df)
        assert len(result) == len(df)

    @given(df=aeolus_dataframes(min_rows=1, max_rows=20))
    def test_reset_index_contiguous(self, df: pd.DataFrame) -> None:
        """After reset_index, index is 0..n-1."""
        result = pipe(df, sort_values("site_code"), reset_index())
        assert list(result.index) == list(range(len(result)))


# ---------------------------------------------------------------------------
# Categorise
# ---------------------------------------------------------------------------


class TestCategorise:
    """Verify categorise_columns preserves values."""

    @given(df=aeolus_dataframes(min_rows=1, max_rows=20))
    def test_categorise_preserves_values(self, df: pd.DataFrame) -> None:
        """Converting to categorical does not change values."""
        result = categorise_columns("measurand", "source_network")(df)
        for col in ["measurand", "source_network"]:
            pd.testing.assert_series_equal(
                result[col].astype(str),
                df[col].astype(str),
                check_names=True,
            )
