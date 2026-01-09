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
Example usage of Aeolus functional API.

This script demonstrates how to use the new functional architecture to:
1. List available data sources
2. Fetch site metadata
3. Download air quality data
4. Use composable transformations
5. Work with multiple sources
"""

from datetime import datetime

# Import sources to trigger auto-registration
import aeolus.sources
from aeolus.registry import get_source, list_sources
from aeolus.transforms import compose, filter_rows, pipe, select_columns, sort_values


def example_1_list_sources():
    """Example 1: List all available data sources."""
    print("=" * 60)
    print("Example 1: Available Data Sources")
    print("=" * 60)

    sources = list_sources()
    print(f"Found {len(sources)} registered sources:\n")

    for source_name in sources:
        source = get_source(source_name)
        api_key = "Yes" if source["requires_api_key"] else "No"
        print(f"  • {source['name']:20s} (API key required: {api_key})")

    print()


def example_2_fetch_metadata():
    """Example 2: Fetch site metadata from AURN."""
    print("=" * 60)
    print("Example 2: Fetch Site Metadata")
    print("=" * 60)

    # Get the AURN source
    aurn = get_source("AURN")

    # Fetch all site metadata
    print("Fetching AURN site metadata...")
    metadata = aurn["fetch_metadata"]()

    print(f"✓ Retrieved {len(metadata)} sites\n")
    print("First 5 sites:")
    print(metadata[["site_code", "site_name", "location_type", "latitude", "longitude"]].head())
    print()


def example_3_fetch_data():
    """Example 3: Fetch air quality data for a specific site."""
    print("=" * 60)
    print("Example 3: Fetch Air Quality Data")
    print("=" * 60)

    # Get the AURN source
    aurn = get_source("AURN")

    # Fetch data for Marylebone Road (MY1) for January 2024
    print("Fetching data for MY1 (Marylebone Road), January 2024...")
    data = aurn["fetch_data"](
        sites=["MY1"],
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 7)  # Just one week for the example
    )

    print(f"✓ Retrieved {len(data)} measurements\n")
    print("Sample data:")
    print(data[["site_code", "date_time", "measurand", "value", "units"]].head(10))
    print()

    # Show summary statistics
    print("Measurands in this dataset:")
    measurand_counts = data["measurand"].value_counts()
    for measurand, count in measurand_counts.head(5).items():
        print(f"  • {measurand}: {count} measurements")
    print()


def example_4_use_transforms():
    """Example 4: Use composable transforms to process data."""
    print("=" * 60)
    print("Example 4: Composable Transformations")
    print("=" * 60)

    # Get the AURN source
    aurn = get_source("AURN")

    # Fetch some data
    print("Fetching data for MY1...")
    data = aurn["fetch_data"](
        sites=["MY1"],
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 3)
    )

    print(f"Original data: {len(data)} records\n")

    # Create a transformation pipeline to:
    # 1. Filter for NO2 only
    # 2. Remove null values
    # 3. Select specific columns
    # 4. Sort by datetime
    no2_pipeline = compose(
        filter_rows(lambda df: df["measurand"] == "NO2"),
        filter_rows(lambda df: df["value"].notna()),
        select_columns("site_code", "date_time", "value", "units"),
        sort_values("date_time")
    )

    # Apply the pipeline
    no2_data = no2_pipeline(data)

    print(f"After filtering for NO2: {len(no2_data)} records\n")
    print("NO2 measurements:")
    print(no2_data.head(10))
    print()

    # Calculate mean NO2
    mean_no2 = no2_data["value"].mean()
    print(f"Mean NO2 concentration: {mean_no2:.2f} µg/m³")
    print()


def example_5_multiple_sites():
    """Example 5: Fetch data from multiple sites and compare."""
    print("=" * 60)
    print("Example 5: Multiple Sites Comparison")
    print("=" * 60)

    # Get the AURN source
    aurn = get_source("AURN")

    # Fetch data for multiple London sites
    sites = ["MY1", "BX1", "CT2"]  # Marylebone Road, Bexley, Camden

    print(f"Fetching data for {len(sites)} sites: {', '.join(sites)}")
    print("Date range: Jan 1-3, 2024\n")

    data = aurn["fetch_data"](
        sites=sites,
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 3)
    )

    print(f"✓ Retrieved {len(data)} total measurements\n")

    # Calculate mean NO2 by site
    no2_data = data[data["measurand"] == "NO2"]
    mean_by_site = no2_data.groupby("site_code")["value"].mean()

    print("Mean NO2 concentration by site:")
    for site, mean_val in mean_by_site.items():
        print(f"  • {site}: {mean_val:.2f} µg/m³")
    print()


def example_6_using_pipe():
    """Example 6: Using pipe() for ad-hoc transformations."""
    print("=" * 60)
    print("Example 6: Using pipe() for Ad-hoc Processing")
    print("=" * 60)

    # Get the AURN source
    aurn = get_source("AURN")

    # Fetch and immediately process data using pipe
    print("Fetching and processing data in one go...\n")

    result = pipe(
        aurn["fetch_data"](
            sites=["MY1"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2)
        ),
        filter_rows(lambda df: df["measurand"].isin(["NO2", "PM2.5", "PM10"])),
        filter_rows(lambda df: df["value"].notna()),
        sort_values(["measurand", "date_time"])
    )

    print(f"Filtered data: {len(result)} records")
    print("\nRecords by pollutant:")
    print(result["measurand"].value_counts())
    print()


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  Aeolus Functional API - Examples".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    print("\n")

    try:
        example_1_list_sources()
        example_2_fetch_metadata()
        example_3_fetch_data()
        example_4_use_transforms()
        example_5_multiple_sites()
        example_6_using_pipe()

        print("=" * 60)
        print("All examples completed successfully! ✓")
        print("=" * 60)
        print()

    except Exception as e:
        print(f"\n✗ Example failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
