"""
Tests for transforms.py - DataFrame transformation functions.

These are pure functions, so they're easy to test and provide high value.
"""

from datetime import datetime

import pandas as pd
import pytest

from aeolus.transforms import (
    add_column,
    compose,
    convert_timestamps,
    drop_columns,
    melt_measurands,
    pipe,
    rename_columns,
    reset_index,
    select_columns,
)

# ============================================================================
# Tests for pipe() and compose()
# ============================================================================


def test_pipe_applies_functions_in_order():
    """Test that pipe applies functions in the correct order."""
    df = pd.DataFrame({"a": [1, 2, 3]})

    # Apply two transformations
    result = pipe(
        df,
        lambda d: d.assign(b=d["a"] * 2),  # b = 2, 4, 6
        lambda d: d.assign(c=d["b"] + 1),  # c = 3, 5, 7
    )

    assert "b" in result.columns
    assert "c" in result.columns
    assert result["c"].tolist() == [3, 5, 7]


def test_pipe_with_empty_functions_returns_unchanged():
    """Test that pipe with no functions returns the original DataFrame."""
    df = pd.DataFrame({"a": [1, 2, 3]})
    result = pipe(df)

    pd.testing.assert_frame_equal(result, df)


def test_compose_creates_reusable_pipeline():
    """Test that compose creates a reusable transformation pipeline."""
    # Create a pipeline
    add_double = compose(
        lambda df: df.assign(doubled=df["value"] * 2),
        lambda df: df.assign(tripled=df["value"] * 3),
    )

    # Apply to first DataFrame
    df1 = pd.DataFrame({"value": [1, 2, 3]})
    result1 = add_double(df1)

    assert "doubled" in result1.columns
    assert "tripled" in result1.columns
    assert result1["doubled"].tolist() == [2, 4, 6]

    # Apply to second DataFrame (reusability)
    df2 = pd.DataFrame({"value": [10, 20]})
    result2 = add_double(df2)

    assert result2["doubled"].tolist() == [20, 40]


def test_compose_with_no_functions():
    """Test that compose with no functions returns identity function."""
    identity = compose()
    df = pd.DataFrame({"a": [1, 2, 3]})
    result = identity(df)

    pd.testing.assert_frame_equal(result, df)


# ============================================================================
# Tests for rename_columns()
# ============================================================================


def test_rename_columns_renames_specified_columns():
    """Test that rename_columns renames the specified columns."""
    df = pd.DataFrame({"old_name": [1, 2, 3], "other": [4, 5, 6]})

    transform = rename_columns({"old_name": "new_name"})
    result = transform(df)

    assert "new_name" in result.columns
    assert "old_name" not in result.columns
    assert "other" in result.columns
    assert result["new_name"].tolist() == [1, 2, 3]


def test_rename_columns_with_multiple_mappings():
    """Test renaming multiple columns at once."""
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})

    transform = rename_columns({"a": "x", "b": "y"})
    result = transform(df)

    assert "x" in result.columns
    assert "y" in result.columns
    assert "c" in result.columns  # unchanged
    assert "a" not in result.columns
    assert "b" not in result.columns


def test_rename_columns_with_nonexistent_column():
    """Test that renaming a non-existent column doesn't raise error."""
    df = pd.DataFrame({"a": [1, 2]})

    transform = rename_columns({"nonexistent": "new_name"})
    result = transform(df)  # Should not raise

    # Original columns should be unchanged
    assert "a" in result.columns
    assert "new_name" not in result.columns


def test_rename_columns_with_empty_mapping():
    """Test that empty mapping returns DataFrame unchanged."""
    df = pd.DataFrame({"a": [1, 2, 3]})

    transform = rename_columns({})
    result = transform(df)

    pd.testing.assert_frame_equal(result, df)


# ============================================================================
# Tests for add_column()
# ============================================================================


def test_add_column_with_static_value():
    """Test adding a column with a static value."""
    df = pd.DataFrame({"a": [1, 2, 3]})

    transform = add_column("source", "AURN")
    result = transform(df)

    assert "source" in result.columns
    assert result["source"].tolist() == ["AURN", "AURN", "AURN"]


def test_add_column_with_callable():
    """Test adding a column with a callable (computed value)."""
    df = pd.DataFrame({"value": [10, 20, 30]})

    transform = add_column("doubled", lambda d: d["value"] * 2)
    result = transform(df)

    assert "doubled" in result.columns
    assert result["doubled"].tolist() == [20, 40, 60]


def test_add_column_with_datetime():
    """Test adding a column with datetime value."""
    df = pd.DataFrame({"a": [1, 2]})
    now = datetime.now()

    transform = add_column("created_at", now)
    result = transform(df)

    assert "created_at" in result.columns
    assert all(result["created_at"] == now)


def test_add_column_overwrites_existing():
    """Test that add_column overwrites existing column."""
    df = pd.DataFrame({"a": [1, 2, 3]})

    transform = add_column("a", 99)
    result = transform(df)

    assert result["a"].tolist() == [99, 99, 99]


# ============================================================================
# Tests for select_columns()
# ============================================================================


def test_select_columns_selects_specified_columns():
    """Test selecting a subset of columns."""
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4]})

    transform = select_columns("a", "c")
    result = transform(df)

    assert list(result.columns) == ["a", "c"]
    assert result["a"].iloc[0] == 1
    assert result["c"].iloc[0] == 3


def test_select_columns_preserves_order():
    """Test that select_columns preserves the specified order."""
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})

    transform = select_columns("c", "a")
    result = transform(df)

    assert list(result.columns) == ["c", "a"]


def test_select_columns_with_nonexistent_column():
    """Test that selecting non-existent columns skips them."""
    df = pd.DataFrame({"a": [1], "b": [2]})

    transform = select_columns("a", "nonexistent", "b")
    result = transform(df)

    # Should only include columns that exist
    assert list(result.columns) == ["a", "b"]


def test_select_columns_with_all_nonexistent():
    """Test selecting only non-existent columns returns empty DataFrame."""
    df = pd.DataFrame({"a": [1], "b": [2]})

    transform = select_columns("x", "y", "z")
    result = transform(df)

    assert len(result.columns) == 0
    assert len(result) == len(df)  # Same number of rows


def test_select_columns_with_single_column():
    """Test selecting a single column."""
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})

    transform = select_columns("a")
    result = transform(df)

    assert list(result.columns) == ["a"]
    assert result["a"].tolist() == [1, 2, 3]


# ============================================================================
# Tests for drop_columns()
# ============================================================================


def test_drop_columns_removes_specified_columns():
    """Test that drop_columns removes the specified columns."""
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})

    transform = drop_columns("b")
    result = transform(df)

    assert "a" in result.columns
    assert "c" in result.columns
    assert "b" not in result.columns


def test_drop_columns_with_multiple_columns():
    """Test dropping multiple columns at once."""
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4]})

    transform = drop_columns("b", "d")
    result = transform(df)

    assert list(result.columns) == ["a", "c"]


def test_drop_columns_with_nonexistent_column():
    """Test that dropping non-existent columns doesn't raise error."""
    df = pd.DataFrame({"a": [1], "b": [2]})

    transform = drop_columns("nonexistent")
    result = transform(df)  # Should not raise

    # All original columns should remain
    assert list(result.columns) == ["a", "b"]


def test_drop_columns_with_all_columns():
    """Test dropping all columns returns empty DataFrame."""
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})

    transform = drop_columns("a", "b")
    result = transform(df)

    assert len(result.columns) == 0
    assert len(result) == 2  # Same number of rows


# ============================================================================
# Tests for convert_timestamps()
# ============================================================================


def test_convert_timestamps_from_unix_seconds():
    """Test converting Unix timestamps (seconds) to datetime."""
    df = pd.DataFrame({"date": [1672531200, 1672617600]})  # 2023-01-01, 2023-01-02

    transform = convert_timestamps("date", unit="s")
    result = transform(df)

    assert pd.api.types.is_datetime64_any_dtype(result["date"])
    assert result["date"].iloc[0] == pd.Timestamp("2023-01-01 00:00:00")
    assert result["date"].iloc[1] == pd.Timestamp("2023-01-02 00:00:00")


def test_convert_timestamps_from_string():
    """Test converting string dates to datetime."""
    df = pd.DataFrame({"date": ["2023-01-01", "2023-01-02", "2023-01-03"]})

    transform = convert_timestamps("date")
    result = transform(df)

    assert pd.api.types.is_datetime64_any_dtype(result["date"])
    assert result["date"].iloc[0] == pd.Timestamp("2023-01-01")


def test_convert_timestamps_handles_invalid_dates():
    """Test that invalid dates raise an error by default (strict parsing)."""
    df = pd.DataFrame({"date": ["2023-01-01", "invalid", "2023-01-03"]})

    transform = convert_timestamps("date")

    # By default, pd.to_datetime raises on invalid dates
    with pytest.raises(ValueError):
        transform(df)

    # But can be handled with errors='coerce'
    transform_coerce = convert_timestamps("date", errors="coerce")
    result = transform_coerce(df)

    # Should have NaT for invalid date
    assert pd.isna(result["date"].iloc[1])
    assert result["date"].iloc[0] == pd.Timestamp("2023-01-01")
    assert result["date"].iloc[2] == pd.Timestamp("2023-01-03")


def test_convert_timestamps_preserves_other_columns():
    """Test that converting timestamps doesn't affect other columns."""
    df = pd.DataFrame({"date": ["2023-01-01"], "value": [42]})

    transform = convert_timestamps("date")
    result = transform(df)

    assert "value" in result.columns
    assert result["value"].iloc[0] == 42


# ============================================================================
# Tests for melt_measurands()
# ============================================================================


def test_melt_measurands_converts_wide_to_long(sample_wide_df):
    """Test that melt_measurands converts wide format to long format."""
    # Sample has: date, site, NO2, PM10, PM2.5
    transform = melt_measurands(
        id_vars=["date", "site"], var_name="measurand", value_name="value"
    )
    result = transform(sample_wide_df)

    # Should have 5 timestamps × 3 pollutants = 15 rows
    assert len(result) == 15
    assert "measurand" in result.columns
    assert "value" in result.columns
    assert set(result["measurand"].unique()) == {"NO2", "PM10", "PM2.5"}


def test_melt_measurands_preserves_id_vars(sample_wide_df):
    """Test that id_vars are preserved after melting."""
    transform = melt_measurands(
        id_vars=["date", "site"], var_name="measurand", value_name="value"
    )
    result = transform(sample_wide_df)

    # Each original row should generate 3 melted rows (one per pollutant)
    assert result["site"].iloc[0] == "MY1"
    assert all(result.groupby("date").size() == 3)


def test_melt_measurands_with_single_id_var():
    """Test melting with a single id variable."""
    df = pd.DataFrame(
        {
            "date": ["2023-01-01", "2023-01-02"],
            "NO2": [45.2, 42.1],
            "PM10": [28.5, 30.1],
        }
    )

    transform = melt_measurands(
        id_vars=["date"], var_name="pollutant", value_name="conc"
    )
    result = transform(df)

    assert len(result) == 4  # 2 dates × 2 pollutants
    assert "pollutant" in result.columns
    assert "conc" in result.columns


def test_melt_measurands_handles_nulls():
    """Test that melt handles null values correctly."""
    df = pd.DataFrame(
        {
            "date": ["2023-01-01", "2023-01-02"],
            "NO2": [45.2, None],
            "PM10": [None, 30.1],
        }
    )

    transform = melt_measurands(
        id_vars=["date"], var_name="measurand", value_name="value"
    )
    result = transform(df)

    # Should still have all rows (including nulls)
    assert len(result) == 4
    assert result["value"].isna().sum() == 2


# ============================================================================
# Tests for reset_index()
# ============================================================================


def test_reset_index_resets_dataframe_index():
    """Test that reset_index resets the DataFrame index (drops by default)."""
    df = pd.DataFrame({"a": [1, 2, 3]})
    df = df.set_index("a")  # Set 'a' as index

    assert df.index.name == "a"

    # By default, drop=True (doesn't add index as column)
    transform = reset_index()
    result = transform(df)

    assert result.index.name is None
    assert list(result.index) == [0, 1, 2]
    # With drop=True, 'a' is not in columns
    assert "a" not in result.columns

    # With drop=False, it becomes a column
    transform_keep = reset_index(drop=False)
    result_keep = transform_keep(df)

    assert result_keep.index.name is None
    assert list(result_keep.index) == [0, 1, 2]
    assert "a" in result_keep.columns


def test_reset_index_with_custom_index():
    """Test resetting a DataFrame with a custom index."""
    df = pd.DataFrame({"value": [10, 20, 30]}, index=["x", "y", "z"])

    transform = reset_index()
    result = transform(df)

    assert list(result.index) == [0, 1, 2]
    assert result["value"].tolist() == [10, 20, 30]


# ============================================================================
# Integration Tests - Combining Multiple Transforms
# ============================================================================


def test_complete_normalization_pipeline():
    """Test a complete normalization pipeline with multiple transforms."""
    # Start with wide format data
    df = pd.DataFrame(
        {
            "date": [1672531200, 1672617600],  # Unix timestamps
            "site_id": ["MY1", "MY1"],
            "NO2": [45.2, 42.1],
            "PM10": [28.5, 30.1],
        }
    )

    # Create a complete pipeline
    normalize = compose(
        convert_timestamps("date", unit="s"),
        rename_columns({"site_id": "site_code"}),
        melt_measurands(
            id_vars=["date", "site_code"], var_name="measurand", value_name="value"
        ),
        add_column("units", "ug/m3"),
        add_column("source_network", "AURN"),
        select_columns(
            "date", "site_code", "measurand", "value", "units", "source_network"
        ),
    )

    result = normalize(df)

    # Check structure
    assert len(result) == 4  # 2 timestamps × 2 pollutants
    assert list(result.columns) == [
        "date",
        "site_code",
        "measurand",
        "value",
        "units",
        "source_network",
    ]

    # Check values
    assert result["site_code"].iloc[0] == "MY1"
    assert result["units"].iloc[0] == "ug/m3"
    assert result["source_network"].iloc[0] == "AURN"
    assert set(result["measurand"].unique()) == {"NO2", "PM10"}


def test_pipeline_with_drop_and_select():
    """Test combining drop_columns and select_columns."""
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4], "e": [5]})

    pipeline = compose(drop_columns("e"), select_columns("a", "c", "d"))

    result = pipeline(df)

    assert list(result.columns) == ["a", "c", "d"]


def test_empty_dataframe_through_pipeline(empty_df):
    """Test that empty DataFrames pass through pipelines without errors."""
    pipeline = compose(
        add_column("source", "TEST"),
        rename_columns({"site_code": "site"}),
        select_columns("date_time", "site", "measurand", "value", "source"),
    )

    result = pipeline(empty_df)

    assert len(result) == 0
    assert "source" in result.columns


# ============================================================================
# Edge Cases and Error Conditions
# ============================================================================


def test_transform_with_dataframe_copy():
    """Test that transforms don't modify the original DataFrame."""
    df = pd.DataFrame({"a": [1, 2, 3]})
    original_columns = df.columns.tolist()

    transform = add_column("b", 99)
    result = transform(df)

    # Original should be unchanged
    assert df.columns.tolist() == original_columns
    assert "b" not in df.columns

    # Result should have new column
    assert "b" in result.columns


def test_compose_with_failing_transform():
    """Test that errors in composed functions are propagated."""
    df = pd.DataFrame({"a": [1, 2, 3]})

    def failing_transform(d):
        raise ValueError("Intentional error")

    pipeline = compose(add_column("b", 1), failing_transform, add_column("c", 2))

    with pytest.raises(ValueError, match="Intentional error"):
        pipeline(df)


def test_rename_to_existing_column_name():
    """Test renaming a column to a name that already exists."""
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})

    transform = rename_columns({"a": "b"})
    result = transform(df)

    # Pandas will overwrite the existing 'b' column
    assert "b" in result.columns
    assert "a" not in result.columns
