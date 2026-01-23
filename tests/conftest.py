"""
Pytest configuration and shared fixtures.

This module provides common fixtures and utilities used across all tests.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
import rdata

# ============================================================================
# Path Fixtures
# ============================================================================


@pytest.fixture
def fixtures_dir():
    """Return path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def aurn_fixtures_dir(fixtures_dir):
    """Return path to AURN fixtures directory."""
    return fixtures_dir / "aurn"


# ============================================================================
# Data Fixtures - Raw RData
# ============================================================================


@pytest.fixture
def my1_rdata_path(aurn_fixtures_dir):
    """Return path to MY1 2023 RData fixture."""
    return aurn_fixtures_dir / "MY1_2023.RData"


@pytest.fixture
def my1_raw_data(my1_rdata_path):
    """
    Load raw MY1 data from RData fixture.

    Returns a DataFrame with the raw structure as it comes from the RData file,
    before any Aeolus normalization.
    """
    parsed = rdata.parser.parse_file(my1_rdata_path)
    converted = rdata.conversion.convert(parsed)
    df = pd.DataFrame(converted[next(iter(converted))])

    # Convert date from Unix timestamp
    df["date"] = pd.to_datetime(df["date"], unit="s")

    return df


@pytest.fixture
def my1_january(my1_raw_data):
    """Return MY1 data filtered to January 2023 only."""
    return my1_raw_data[
        (my1_raw_data["date"] >= "2023-01-01") & (my1_raw_data["date"] < "2023-02-01")
    ]


# ============================================================================
# Sample DataFrames for Testing Transforms
# ============================================================================


@pytest.fixture
def sample_wide_df():
    """
    Sample DataFrame in wide format (one row per timestamp, columns for pollutants).

    This mimics the structure of regulatory network data before melting.
    """
    return pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=5, freq="h"),
            "site": ["MY1"] * 5,
            "NO2": [45.2, 42.1, 38.9, 41.5, 43.2],
            "PM10": [28.5, 30.1, 25.8, 27.3, 29.0],
            "PM2.5": [18.2, 19.5, 16.9, 17.8, 18.9],
        }
    )


@pytest.fixture
def sample_long_df():
    """
    Sample DataFrame in long format (one row per measurement).

    This is the target format after normalization.
    """
    return pd.DataFrame(
        {
            "date_time": pd.to_datetime(
                [
                    "2023-01-01 00:00:00",
                    "2023-01-01 00:00:00",
                    "2023-01-01 00:00:00",
                    "2023-01-01 01:00:00",
                    "2023-01-01 01:00:00",
                ]
            ),
            "site_code": ["MY1", "MY1", "MY1", "MY1", "MY1"],
            "measurand": ["NO2", "PM10", "PM2.5", "NO2", "PM10"],
            "value": [45.2, 28.5, 18.2, 42.1, 30.1],
            "units": ["ug/m3", "ug/m3", "ug/m3", "ug/m3", "ug/m3"],
            "source_network": ["AURN", "AURN", "AURN", "AURN", "AURN"],
        }
    )


@pytest.fixture
def sample_df_with_nulls():
    """Sample DataFrame with null values for testing null handling."""
    return pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=5, freq="h"),
            "site": ["MY1", "MY1", None, "MY1", "MY1"],
            "NO2": [45.2, None, 38.9, 41.5, None],
            "PM10": [28.5, 30.1, None, 27.3, 29.0],
        }
    )


@pytest.fixture
def empty_df():
    """Empty DataFrame with expected columns for testing edge cases."""
    return pd.DataFrame(
        columns=["date_time", "site_code", "measurand", "value", "units"]
    )


# ============================================================================
# Mock Data for API Testing
# ============================================================================


@pytest.fixture
def mock_openaq_sensor_response():
    """Mock OpenAQ API response for sensors endpoint."""
    return {
        "meta": {"name": "openaq-api", "page": 1, "limit": 100, "found": 3},
        "results": [
            {
                "id": 7117,
                "name": "PM2.5",
                "parameter": {"id": 2, "name": "pm25", "units": "µg/m³"},
            },
            {
                "id": 7118,
                "name": "NO2",
                "parameter": {"id": 19, "name": "no2", "units": "µg/m³"},
            },
            {
                "id": 7119,
                "name": "O3",
                "parameter": {"id": 5, "name": "o3", "units": "µg/m³"},
            },
        ],
    }


@pytest.fixture
def mock_openaq_measurements_response():
    """Mock OpenAQ API response for hourly measurements endpoint."""
    return {
        "meta": {"name": "openaq-api", "page": 1, "limit": 100, "found": 3},
        "results": [
            {
                "value": 23.5,
                "period": {
                    "label": "hour",
                    "interval": "1h",
                    "datetimeFrom": {
                        "utc": "2024-01-01T00:00:00Z",
                        "local": "2024-01-01T00:00:00+00:00",
                    },
                    "datetimeTo": {
                        "utc": "2024-01-01T01:00:00Z",
                        "local": "2024-01-01T01:00:00+00:00",
                    },
                },
                "flagInfo": {"hasFlags": False},
            },
            {
                "value": 24.1,
                "period": {
                    "label": "hour",
                    "interval": "1h",
                    "datetimeFrom": {
                        "utc": "2024-01-01T01:00:00Z",
                        "local": "2024-01-01T01:00:00+00:00",
                    },
                    "datetimeTo": {
                        "utc": "2024-01-01T02:00:00Z",
                        "local": "2024-01-01T02:00:00+00:00",
                    },
                },
                "flagInfo": {"hasFlags": False},
            },
            {
                "value": 22.8,
                "period": {
                    "label": "hour",
                    "interval": "1h",
                    "datetimeFrom": {
                        "utc": "2024-01-01T02:00:00Z",
                        "local": "2024-01-01T02:00:00+00:00",
                    },
                    "datetimeTo": {
                        "utc": "2024-01-01T03:00:00Z",
                        "local": "2024-01-01T03:00:00+00:00",
                    },
                },
                "flagInfo": {"hasFlags": False},
            },
        ],
    }


# ============================================================================
# Utility Functions
# ============================================================================


def assert_dataframes_equal(df1: pd.DataFrame, df2: pd.DataFrame, **kwargs):
    """
    Assert that two DataFrames are equal, with helpful error messages.

    Args:
        df1: First DataFrame
        df2: Second DataFrame
        **kwargs: Additional arguments to pass to pd.testing.assert_frame_equal
    """
    pd.testing.assert_frame_equal(df1, df2, **kwargs)


def assert_has_columns(df: pd.DataFrame, columns: list[str]):
    """
    Assert that DataFrame has all specified columns.

    Args:
        df: DataFrame to check
        columns: List of required column names
    """
    missing = set(columns) - set(df.columns)
    assert not missing, f"Missing columns: {missing}"


def assert_no_nulls(df: pd.DataFrame, columns: list[str] | None = None):
    """
    Assert that DataFrame has no null values in specified columns.

    Args:
        df: DataFrame to check
        columns: List of columns to check (None = all columns)
    """
    if columns is None:
        columns = df.columns.tolist()

    for col in columns:
        null_count = df[col].isna().sum()
        assert null_count == 0, f"Column '{col}' has {null_count} null values"


# Make utility functions available to tests
pytest.assert_dataframes_equal = assert_dataframes_equal
pytest.assert_has_columns = assert_has_columns
pytest.assert_no_nulls = assert_no_nulls
