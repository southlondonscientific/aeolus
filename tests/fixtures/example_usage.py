#!/usr/bin/env python3
"""
Example showing how to use test fixtures.

This demonstrates how to load and use the MY1_2023.RData fixture
in your tests.
"""

from pathlib import Path

import pandas as pd
import rdata


def example_load_my1_fixture():
    """Example: Load the MY1 2023 RData fixture."""
    # Get the fixture path
    fixture_dir = Path(__file__).parent
    fixture_path = fixture_dir / "aurn" / "MY1_2023.RData"

    print(f"Loading fixture from: {fixture_path}")

    # Parse the RData file (this is what Aeolus does internally)
    parsed = rdata.parser.parse_file(fixture_path)
    converted = rdata.conversion.convert(parsed)

    # RData returns a dict with one key - get the DataFrame
    df = pd.DataFrame(converted[next(iter(converted))])

    print(f"✓ Loaded {len(df)} rows")
    print(f"✓ Columns: {list(df.columns)}")

    # Convert date from Unix timestamp
    df["date"] = pd.to_datetime(df["date"], unit="s")
    print(f"✓ Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"✓ Site code: {df['code'].iloc[0]}")

    return df


def example_filter_data():
    """Example: Filter fixture data to a specific date range."""
    # Load raw fixture
    fixture_dir = Path(__file__).parent
    fixture_path = fixture_dir / "aurn" / "MY1_2023.RData"
    parsed = rdata.parser.parse_file(fixture_path)
    converted = rdata.conversion.convert(parsed)
    df = pd.DataFrame(converted[next(iter(converted))])

    # Convert date from Unix timestamp
    df["date"] = pd.to_datetime(df["date"], unit="s")

    # Filter to just January 2023
    january = df[(df["date"] >= "2023-01-01") & (df["date"] < "2023-02-01")]

    print(f"\n✓ Filtered to January: {len(january)} rows")
    print(f"✓ Date range: {january['date'].min()} to {january['date'].max()}")
    return january


def example_test_normalization():
    """Example: Test that normalization works correctly."""
    # Load raw fixture
    fixture_dir = Path(__file__).parent
    fixture_path = fixture_dir / "aurn" / "MY1_2023.RData"
    parsed = rdata.parser.parse_file(fixture_path)
    converted = rdata.conversion.convert(parsed)
    df = pd.DataFrame(converted[next(iter(converted))])

    # This is what you'd test in actual unit tests
    assert not df.empty, "DataFrame should not be empty"
    assert "date" in df.columns, "Should have 'date' column"
    assert "code" in df.columns, "Should have 'code' column"
    assert df["code"].iloc[0] == "MY1", "Site code should be MY1"

    # Check for expected pollutants
    assert "NO2" in df.columns, "Should have NO2 measurements"
    assert "PM10" in df.columns, "Should have PM10 measurements"
    assert "PM2.5" in df.columns, "Should have PM2.5 measurements"

    print("\n✓ All assertions passed!")


def example_pytest_fixture():
    """
    Example: How to use this as a pytest fixture.

    In your conftest.py, you would write:

    ```python
    import pytest
    from pathlib import Path
    import pandas as pd
    import rdata

    @pytest.fixture
    def my1_raw_data():
        '''Load raw MY1 data from fixture.'''
        fixture_path = Path(__file__).parent / "fixtures/aurn/MY1_2023.RData"
        parsed = rdata.parser.parse_file(fixture_path)
        converted = rdata.conversion.convert(parsed)
        return pd.DataFrame(converted[next(iter(converted))])

    @pytest.fixture
    def my1_january():
        '''Load MY1 data filtered to January 2023.'''
        # Use the my1_raw_data fixture
        df = my1_raw_data()
        df["date"] = pd.to_datetime(df["date"])
        return df[(df["date"] >= "2023-01-01") & (df["date"] < "2023-02-01")]
    ```

    Then in your tests:

    ```python
    def test_aurn_has_required_columns(my1_raw_data):
        assert "date" in my1_raw_data.columns
        assert "code" in my1_raw_data.columns
        assert "NO2" in my1_raw_data.columns

    def test_january_filtering(my1_january):
        assert len(my1_january) > 0
        assert my1_january["date"].min() >= pd.Timestamp("2023-01-01")
        assert my1_january["date"].max() < pd.Timestamp("2023-02-01")

    def test_site_code(my1_raw_data):
        assert my1_raw_data["code"].iloc[0] == "MY1"
    ```
    """
    print("\nSee docstring for pytest fixture examples!")


if __name__ == "__main__":
    print("=" * 60)
    print("Example 1: Load MY1 fixture")
    print("=" * 60)
    example_load_my1_fixture()

    print("\n" + "=" * 60)
    print("Example 2: Filter to specific date range")
    print("=" * 60)
    example_filter_data()

    print("\n" + "=" * 60)
    print("Example 3: Test normalization")
    print("=" * 60)
    example_test_normalization()

    print("\n" + "=" * 60)
    print("Example 4: Pytest fixture pattern")
    print("=" * 60)
    example_pytest_fixture()

    print("\n✅ All examples completed successfully!")
