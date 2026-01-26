# Aeolus: download UK and standardise air quality data
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
Composable DataFrame transformation functions.

This module provides small, pure functions that transform DataFrames in
predictable ways. Functions can be composed together using `pipe()` or
`compose()` to build complex data processing pipelines.

All transformer functions follow the pattern:
    - Take configuration as arguments
    - Return a function that transforms a DataFrame
    - Are pure (no side effects)
    - Are composable

Example:
    >>> normalise = compose(
    ...     rename_columns({"old": "new"}),
    ...     add_column("source", "AURN"),
    ...     convert_timestamps("date_time", unit="s")
    ... )
    >>> df_normalised = normalise(df_raw)
"""

from datetime import datetime
from functools import reduce
from typing import Any, Callable

import pandas as pd

from .types import Transformer


def pipe(df: pd.DataFrame, *functions: Transformer) -> pd.DataFrame:
    """
    Apply a series of transformation functions to a DataFrame in sequence.

    This is the fundamental composition function - it takes a DataFrame and
    applies each function in order, passing the result to the next function.

    Args:
        df: Input DataFrame
        *functions: Variable number of transformer functions to apply

    Returns:
        pd.DataFrame: Transformed DataFrame after all functions applied

    Example:
        >>> result = pipe(
        ...     df,
        ...     rename_columns({"site": "site_code"}),
        ...     add_column("network", "AURN"),
        ...     drop_columns("unused_col")
        ... )
    """
    return reduce(lambda data, func: func(data), functions, df)


def compose(*functions: Transformer) -> Transformer:
    """
    Compose multiple transformer functions into a single function.

    Returns a new function that applies all the given functions in sequence.
    This is useful for creating reusable transformation pipelines.

    Args:
        *functions: Variable number of transformer functions to compose

    Returns:
        Transformer: A new function that applies all transformations

    Example:
        >>> normalise_aurn = compose(
        ...     rename_columns({"site": "site_code"}),
        ...     add_column("source_network", "AURN")
        ... )
        >>> df_normalised = normalise_aurn(df_raw)
    """

    def composed(df: pd.DataFrame) -> pd.DataFrame:
        return pipe(df, *functions)

    return composed


def rename_columns(mapping: dict[str, str]) -> Transformer:
    """
    Return a function that renames DataFrame columns.

    Args:
        mapping: Dictionary mapping old column names to new column names

    Returns:
        Transformer: Function that renames columns according to mapping

    Example:
        >>> transform = rename_columns({"site": "site_code", "date": "date_time"})
        >>> df_renamed = transform(df)
    """

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        return df.rename(columns=mapping)

    return transform


def add_column(name: str, value: Any | Callable[[pd.DataFrame], Any]) -> Transformer:
    """
    Return a function that adds a new column to a DataFrame.

    The value can be either:
    - A static value (string, number, etc.) applied to all rows
    - A callable that takes the DataFrame and returns a value or Series

    Args:
        name: Name of the new column
        value: Static value or callable that generates the column values

    Returns:
        Transformer: Function that adds the specified column

    Example:
        >>> # Static value
        >>> transform1 = add_column("source_network", "AURN")
        >>>
        >>> # Computed value
        >>> transform2 = add_column("year", lambda df: df["date_time"].dt.year)
        >>>
        >>> # Current timestamp
        >>> transform3 = add_column("created_at", lambda df: datetime.now())
    """

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        if callable(value):
            return df.assign(**{name: value(df)})
        else:
            return df.assign(**{name: value})

    return transform


def drop_columns(*columns: str) -> Transformer:
    """
    Return a function that drops specified columns from a DataFrame.

    Only drops columns that exist in the DataFrame - silently ignores
    columns that don't exist (to make pipelines more robust).

    Args:
        *columns: Variable number of column names to drop

    Returns:
        Transformer: Function that drops the specified columns

    Example:
        >>> transform = drop_columns("temp_col", "unused_col", "debug_info")
        >>> df_cleaned = transform(df)
    """

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        cols_to_drop = [col for col in columns if col in df.columns]
        if not cols_to_drop:
            return df
        return df.drop(columns=cols_to_drop)

    return transform


def convert_timestamps(column: str, **kwargs) -> Transformer:
    """
    Return a function that converts a column to datetime type.

    Args:
        column: Name of the column to convert
        **kwargs: Additional arguments passed to pd.to_datetime()
            Common options:
            - unit: 's' for seconds, 'ms' for milliseconds
            - format: strftime format string
            - utc: True to treat as UTC

    Returns:
        Transformer: Function that converts the specified column to datetime

    Example:
        >>> # Convert Unix timestamps
        >>> transform1 = convert_timestamps("date_time", unit="s")
        >>>
        >>> # Parse formatted strings
        >>> transform2 = convert_timestamps("date_time", format="%Y-%m-%d %H:%M:%S")
    """

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        return df.assign(**{column: pd.to_datetime(df[column], **kwargs)})

    return transform


def filter_rows(predicate: Callable[[pd.DataFrame], pd.Series]) -> Transformer:
    """
    Return a function that filters DataFrame rows based on a condition.

    Args:
        predicate: Function that takes a DataFrame and returns a boolean Series

    Returns:
        Transformer: Function that filters rows where predicate is True

    Example:
        >>> # Keep only rows where value is not null
        >>> transform1 = filter_rows(lambda df: df["value"].notna())
        >>>
        >>> # Keep only NO2 measurements
        >>> transform2 = filter_rows(lambda df: df["measurand"] == "NO2")
    """

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        return df[predicate(df)]

    return transform


def melt_measurands(
    id_vars: list[str],
    measurands: list[str] | None = None,
    var_name: str = "measurand",
    value_name: str = "value",
) -> Transformer:
    """
    Return a function that melts wide data to long format.

    This is commonly used to convert regulatory data where each measurand
    is a separate column into the standard long format where measurand
    names become values in a single column.

    Args:
        id_vars: Columns to keep as identifiers (not melted)
        measurands: List of columns to melt. If None, melts all columns not in id_vars
        var_name: Name for the variable column (default: "measurand")
        value_name: Name for the value column (default: "value")

    Returns:
        Transformer: Function that melts the DataFrame from wide to long format

    Example:
        >>> # Melt all measurand columns
        >>> transform = melt_measurands(
        ...     id_vars=["site_code", "date_time"],
        ...     measurands=["NO2", "O3", "PM2.5"]
        ... )
        >>> df_long = transform(df_wide)
    """

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        value_vars = measurands
        if value_vars is None:
            # Melt all columns except id_vars
            value_vars = [col for col in df.columns if col not in id_vars]
        else:
            # Only melt measurands that actually exist in the DataFrame
            value_vars = [col for col in value_vars if col in df.columns]

        if not value_vars:
            return df

        return pd.melt(
            df,
            id_vars=id_vars,
            value_vars=value_vars,
            var_name=var_name,
            value_name=value_name,
        )

    return transform


def drop_duplicates(
    subset: list[str] | None = None, keep: str = "first"
) -> Transformer:
    """
    Return a function that drops duplicate rows from a DataFrame.

    Args:
        subset: Column labels to consider for identifying duplicates.
                If None, uses all columns.
        keep: Which duplicates to keep - 'first', 'last', or False (drop all)

    Returns:
        Transformer: Function that drops duplicate rows

    Example:
        >>> # Drop duplicate measurements at same site/time
        >>> transform = drop_duplicates(subset=["site_code", "date_time", "measurand"])
        >>> df_deduped = transform(df)
    """

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        return df.drop_duplicates(subset=subset, keep=keep)

    return transform


def reset_index(drop: bool = True) -> Transformer:
    """
    Return a function that resets the DataFrame index.

    Args:
        drop: If True, do not insert index as a column in the new DataFrame

    Returns:
        Transformer: Function that resets the index

    Example:
        >>> transform = reset_index()
        >>> df_reset = transform(df)
    """

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        return df.reset_index(drop=drop)

    return transform


def sort_values(by: str | list[str], ascending: bool = True) -> Transformer:
    """
    Return a function that sorts a DataFrame by specified column(s).

    Args:
        by: Column name or list of column names to sort by
        ascending: Sort ascending (True) or descending (False)

    Returns:
        Transformer: Function that sorts the DataFrame

    Example:
        >>> # Sort by date
        >>> transform1 = sort_values("date_time")
        >>>
        >>> # Sort by site, then date
        >>> transform2 = sort_values(["site_code", "date_time"])
    """

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        return df.sort_values(by=by, ascending=ascending)

    return transform


def fillna(
    value: Any | dict[str, Any] | None = None, method: str | None = None
) -> Transformer:
    """
    Return a function that fills NA/NaN values in a DataFrame.

    Args:
        value: Value to use to fill holes, or dict mapping column names to fill values
        method: Method to use for filling ('ffill', 'bfill', etc.)

    Returns:
        Transformer: Function that fills NA values

    Example:
        >>> # Fill all NaN with 0
        >>> transform1 = fillna(0)
        >>>
        >>> # Fill different columns with different values
        >>> transform2 = fillna({"value": 0, "ratification": "Unknown"})
    """

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        if method is not None:
            return df.fillna(method=method)
        return df.fillna(value)

    return transform


def select_columns(*columns: str) -> Transformer:
    """
    Return a function that selects only specified columns from a DataFrame.

    Only selects columns that exist in the DataFrame - silently ignores
    columns that don't exist.

    Args:
        *columns: Variable number of column names to select

    Returns:
        Transformer: Function that selects the specified columns

    Example:
        >>> transform = select_columns("site_code", "date_time", "measurand", "value")
        >>> df_subset = transform(df)
    """

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        cols_to_select = [col for col in columns if col in df.columns]
        return df[cols_to_select]

    return transform


def apply_function(func: Callable[[pd.DataFrame], pd.DataFrame]) -> Transformer:
    """
    Wrap an arbitrary function as a Transformer.

    This is useful for incorporating custom logic into a pipeline without
    writing a full transformer function.

    Args:
        func: Function that takes and returns a DataFrame

    Returns:
        Transformer: The wrapped function

    Example:
        >>> # Apply custom logic inline
        >>> transform = apply_function(
        ...     lambda df: df[df["value"] > 0]
        ... )
    """

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        return func(df)

    return transform


def categorise_columns(*columns: str) -> Transformer:
    """
    Convert specified columns to categorical dtype for memory efficiency.

    Categorical columns store each unique value once and use integer codes
    for references, dramatically reducing memory for columns with repeated
    string values (e.g., site_name, measurand, units).

    Args:
        *columns: Column names to convert to categorical

    Returns:
        Transformer: Function that converts columns to categorical

    Example:
        >>> transform = categorise_columns("site_name", "measurand", "units")
        >>> df = transform(df)  # Reduces memory usage significantly
    """

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in columns:
            if col in df.columns:
                df[col] = df[col].astype("category")
        return df

    return transform
