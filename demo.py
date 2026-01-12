#!/usr/bin/env python3
"""
Aeolus Comprehensive Feature Demonstration

This script demonstrates all major features of Aeolus in a structured way.
Each section can be run independently to showcase specific functionality.

Run with: python demo.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path if running from repo
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd

import aeolus
from aeolus.transforms import (
    add_column,
    compose,
    filter_rows,
    melt_measurands,
    pipe,
    select_columns,
    sort_values,
)


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_subsection(title: str):
    """Print a formatted subsection header."""
    print(f"\n--- {title} ---\n")


def demo_1_list_sources():
    """Demonstrate listing available data sources."""
    print_section("DEMO 1: List Available Data Sources")

    sources = aeolus.list_sources()
    print(f"Found {len(sources)} registered data sources:\n")

    for i, source in enumerate(sources, 1):
        info = aeolus.get_source_info(source)
        api_key_req = "Yes" if info["requires_api_key"] else "No"
        print(f"  {i}. {info['name']:30s} (API key required: {api_key_req})")

    print("\n💡 Tip: Use aeolus.list_sources() to see what networks are available.")


def demo_2_get_metadata():
    """Demonstrate fetching site metadata."""
    print_section("DEMO 2: Get Site Metadata")

    print("Fetching metadata for AURN network...")
    metadata = aeolus.get_metadata("AURN")

    print(f"\n✓ Retrieved {len(metadata):,} monitoring sites\n")

    print("Available columns:")
    for col in metadata.columns:
        print(f"  • {col}")

    print("\n" + "-" * 80)
    print("Sample sites (first 5):")
    print("-" * 80)

    sample = metadata.head(5)[
        ["site_code", "site_name", "location_type", "latitude", "longitude"]
    ]
    print(sample.to_string(index=False))

    # Show location type breakdown
    print("\n" + "-" * 80)
    print("Sites by location type:")
    print("-" * 80)
    type_counts = metadata["location_type"].value_counts()
    for loc_type, count in type_counts.head(10).items():
        print(f"  {loc_type:30s}: {count:4d} sites")

    print(
        "\n💡 Tip: Filter metadata to find specific types of sites before downloading."
    )


def demo_3_simple_download():
    """Demonstrate simple data download."""
    print_section("DEMO 3: Simple Data Download")

    print("Downloading 3 days of data from Marylebone Road (MY1)...")
    print("Site: MY1 (Marylebone Road, London - one of the busiest roads in UK)")
    print("Period: 3 days")

    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 3)

    data = aeolus.download(
        sources="AURN", sites=["MY1"], start_date=start, end_date=end
    )

    print(f"\n✓ Downloaded {len(data):,} measurements\n")

    print("Data columns:")
    for col in data.columns:
        print(f"  • {col}")

    print("\n" + "-" * 80)
    print("Sample data (first 10 rows):")
    print("-" * 80)

    sample = data.head(10)[["site_code", "date_time", "measurand", "value", "units"]]
    print(sample.to_string(index=False))

    # Show measurand breakdown
    print("\n" + "-" * 80)
    print("Measurements by pollutant:")
    print("-" * 80)
    measurand_counts = data["measurand"].value_counts()
    for measurand, count in measurand_counts.head(10).items():
        print(f"  {measurand:15s}: {count:4d} measurements")

    print("\n💡 Tip: Data is in long format - one row per measurement.")


def demo_4_multiple_sources():
    """Demonstrate downloading from multiple sources."""
    print_section("DEMO 4: Download from Multiple Sources")

    print("Downloading from three different networks:")
    print("  • AURN: MY1 (Marylebone Road, London)")
    print("  • SAQN: GLA4 (Glasgow)")
    print("  • WAQN: CDF (Cardiff)")
    print("Period: 2 days\n")

    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 2)

    data = aeolus.download(
        sources=["AURN", "SAQN", "WAQN"],
        sites=["MY1", "GLA4", "CDF"],
        start_date=start,
        end_date=end,
    )

    print(f"✓ Downloaded {len(data):,} total measurements\n")

    print("-" * 80)
    print("Breakdown by source network:")
    print("-" * 80)

    for source in data["source_network"].unique():
        source_data = data[data["source_network"] == source]
        sites = source_data["site_code"].unique()
        print(f"\n  {source}:")
        print(f"    Sites: {', '.join(sites)}")
        print(f"    Measurements: {len(source_data):,}")

        # Show measurands available
        measurands = source_data["measurand"].unique()
        print(f"    Pollutants: {len(measurands)} types")

    print("\n💡 Tip: Data from all sources is combined into one DataFrame.")


def demo_5_separate_sources():
    """Demonstrate keeping sources separate."""
    print_section("DEMO 5: Keep Sources Separate")

    print("Downloading from AURN and SAQN, keeping them separate...")
    print("Setting combine=False to get a dictionary of DataFrames\n")

    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 2)

    data_by_source = aeolus.download(
        sources=["AURN", "SAQN"],
        sites=["MY1", "GLA4"],
        start_date=start,
        end_date=end,
        combine=False,  # Get separate DataFrames
    )

    print(f"✓ Got dictionary with {len(data_by_source)} sources\n")

    print("-" * 80)
    print("Processing each source separately:")
    print("-" * 80)

    for source, df in data_by_source.items():
        print(f"\n  {source}:")
        print(f"    Records: {len(df):,}")
        print(f"    Sites: {', '.join(df['site_code'].unique())}")
        print(f"    Date range: {df['date_time'].min()} to {df['date_time'].max()}")

        # Calculate mean NO2 if available
        no2_data = df[df["measurand"] == "NO2"]
        if not no2_data.empty:
            mean_no2 = no2_data["value"].mean()
            print(f"    Mean NO2: {mean_no2:.2f} µg/m³")

    print(
        "\n💡 Tip: Use combine=False when you need to process each source differently."
    )


def demo_6_filter_transform():
    """Demonstrate filtering and transforming data."""
    print_section("DEMO 6: Filter and Transform Data")

    print("Downloading data and filtering for NO2 only...")

    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 3)

    # Download data
    data = aeolus.download(
        sources="AURN", sites=["MY1"], start_date=start, end_date=end
    )

    print(f"Original data: {len(data):,} measurements\n")

    # Create a transformation pipeline
    print("Applying transformation pipeline:")
    print("  1. Filter for NO2 only")
    print("  2. Remove null values")
    print("  3. Select specific columns")
    print("  4. Sort by date/time\n")

    no2_data = pipe(
        data,
        filter_rows(lambda df: df["measurand"] == "NO2"),
        filter_rows(lambda df: df["value"].notna()),
        select_columns("site_code", "date_time", "value", "units"),
        sort_values("date_time"),
    )

    print(f"✓ After filtering: {len(no2_data):,} NO2 measurements\n")

    print("-" * 80)
    print("Filtered NO2 data (first 10 rows):")
    print("-" * 80)
    print(no2_data.head(10).to_string(index=False))

    # Calculate statistics
    print("\n" + "-" * 80)
    print("NO2 Statistics:")
    print("-" * 80)
    print(f"  Mean:   {no2_data['value'].mean():.2f} µg/m³")
    print(f"  Median: {no2_data['value'].median():.2f} µg/m³")
    print(f"  Min:    {no2_data['value'].min():.2f} µg/m³")
    print(f"  Max:    {no2_data['value'].max():.2f} µg/m³")
    print(f"  Std:    {no2_data['value'].std():.2f} µg/m³")

    print("\n💡 Tip: Use pipe() to chain transformations together.")


def demo_7_composable_pipeline():
    """Demonstrate creating reusable transformation pipelines."""
    print_section("DEMO 7: Reusable Transformation Pipelines")

    print("Creating a reusable pipeline for NO2 analysis...\n")

    # Define a reusable pipeline
    no2_analysis_pipeline = compose(
        filter_rows(lambda df: df["measurand"] == "NO2"),
        filter_rows(lambda df: df["value"].notna()),
        add_column("hour", lambda df: df["date_time"].dt.hour),
        add_column("date", lambda df: df["date_time"].dt.date),
        select_columns("site_code", "date", "hour", "value", "units"),
        sort_values(["date", "hour"]),
    )

    print("Pipeline steps:")
    print("  1. Filter for NO2")
    print("  2. Remove nulls")
    print("  3. Extract hour from datetime")
    print("  4. Extract date from datetime")
    print("  5. Select relevant columns")
    print("  6. Sort by date and hour\n")

    # Download data
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 2)

    data = aeolus.download(
        sources="AURN", sites=["MY1"], start_date=start, end_date=end
    )

    # Apply the pipeline
    processed = no2_analysis_pipeline(data)

    print(f"✓ Processed {len(processed):,} measurements\n")

    print("-" * 80)
    print("Processed data (first 15 rows):")
    print("-" * 80)
    print(processed.head(15).to_string(index=False))

    # Calculate hourly averages
    hourly_avg = processed.groupby("hour", observed=True)["value"].mean()

    print("\n" + "-" * 80)
    print("NO2 by Hour of Day (hourly averages):")
    print("-" * 80)
    for hour, avg in hourly_avg.items():
        bar = "█" * int(avg / 5)  # Scale bar chart
        print(f"  {hour:02d}:00  {avg:6.2f} µg/m³  {bar}")

    print("\n💡 Tip: Create reusable pipelines with compose() for consistent analysis.")


def demo_8_metadata_filtering():
    """Demonstrate filtering metadata before download."""
    print_section("DEMO 8: Smart Downloads Using Metadata")

    print("Using metadata to select London sites for download...\n")

    # Get metadata
    metadata = aeolus.get_metadata("AURN")

    print(f"✓ Retrieved {len(metadata):,} total sites from AURN\n")

    # Use sites we know have data
    demo_sites = ["MY1", "LH2", "BX1"]  # Marylebone Road, Hillingdon, Bexley

    sites_filtered = metadata[metadata["site_code"].isin(demo_sites)].drop_duplicates(
        subset=["site_code"]
    )

    # Show the selected sites
    print("-" * 80)
    print("Selected London sites for demo:")
    print("-" * 80)
    sample = sites_filtered[
        ["site_code", "site_name", "location_type", "latitude", "longitude"]
    ]
    print(sample.to_string(index=False))

    # Download data for these sites
    site_codes = sites_filtered["site_code"].tolist()

    print(f"\n\nDownloading data for {len(site_codes)} sites: {', '.join(site_codes)}")
    print("Period: 2 days\n")

    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 2)

    data = aeolus.download(
        sources="AURN", sites=site_codes, start_date=start, end_date=end
    )

    print(f"✓ Downloaded {len(data):,} measurements\n")

    # Check if we got any data
    if data.empty:
        print("⚠️  No data available for these sites in this period.")
        print("    (This can happen if sites are inactive or data isn't available yet)")
        print(
            "\n💡 Tip: Filter metadata to target specific site types before downloading."
        )
        return

    # Show breakdown by site
    print("-" * 80)
    print("Data by site:")
    print("-" * 80)
    for site in data["site_code"].unique():
        site_data = data[data["site_code"] == site]
        site_info = sites_filtered[sites_filtered["site_code"] == site]
        if not site_info.empty:
            site_name = site_info["site_name"].iloc[0]
            location_type = site_info["location_type"].iloc[0]
            print(f"\n  {site} - {site_name} ({location_type})")
            print(f"    Measurements: {len(site_data):,}")
            print(
                f"    Pollutants: {', '.join(site_data['measurand'].unique()[:5])}..."
            )

    print("\n💡 Tip: Use metadata to find and filter sites before downloading data.")


def demo_9_time_series_analysis():
    """Demonstrate time series analysis."""
    print_section("DEMO 9: Time Series Analysis")

    print("Analyzing PM2.5 concentrations over time at Marylebone Road...\n")

    # Download a week of data
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 7)

    data = aeolus.download(
        sources="AURN", sites=["MY1"], start_date=start, end_date=end
    )

    # Filter for PM2.5
    pm25_data = pipe(
        data,
        filter_rows(lambda df: df["measurand"] == "PM2.5"),
        filter_rows(lambda df: df["value"].notna()),
        select_columns("date_time", "value", "units"),
        sort_values("date_time"),
    )

    print(f"✓ Retrieved {len(pm25_data):,} PM2.5 measurements\n")

    # Check if we got any data
    if pm25_data.empty:
        print("⚠️  No PM2.5 data available for this site in this period.")
        print("\n💡 Tip: Extract time features for temporal analysis.")
        return

    # Add time-based features
    pm25_data = pm25_data.copy()
    pm25_data["hour"] = pm25_data["date_time"].dt.hour
    pm25_data["day_of_week"] = pm25_data["date_time"].dt.day_name()
    pm25_data["date"] = pm25_data["date_time"].dt.date

    # Daily statistics
    print("-" * 80)
    print("Daily PM2.5 Statistics:")
    print("-" * 80)
    daily_stats = pm25_data.groupby("date", observed=True)["value"].agg(
        ["mean", "min", "max", "std"]
    )
    print(daily_stats.to_string())

    # Hourly pattern
    print("\n" + "-" * 80)
    print("Average PM2.5 by Hour (all days combined):")
    print("-" * 80)
    hourly_avg = pm25_data.groupby("hour", observed=True)["value"].mean()
    for hour, avg in hourly_avg.items():
        bar = "█" * int(avg / 2)
        print(f"  {hour:02d}:00  {avg:5.2f} µg/m³  {bar}")

    # Peak hours
    peak_hour = hourly_avg.idxmax()
    peak_value = hourly_avg.max()
    print(f"\n  Peak hour: {peak_hour:02d}:00 with {peak_value:.2f} µg/m³")

    print("\n💡 Tip: Extract time features for temporal analysis.")


def demo_10_multi_site_comparison():
    """Demonstrate comparing multiple sites."""
    print_section("DEMO 10: Multi-Site Comparison")

    print("Comparing NO2 levels across London sites...\n")

    # Define sites to compare
    sites = {
        "MY1": "Marylebone Road (Traffic)",
        "BX1": "Bexley (Suburban)",
        "LH2": "Hillingdon (Urban Background)",
    }

    print("Sites:")
    for code, description in sites.items():
        print(f"  • {code}: {description}")

    print("\nPeriod: 5 days\n")

    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 5)

    data = aeolus.download(
        sources="AURN", sites=list(sites.keys()), start_date=start, end_date=end
    )

    # Filter for NO2
    no2_data = data[data["measurand"] == "NO2"].copy()

    print(f"✓ Retrieved {len(no2_data):,} NO2 measurements\n")

    # Check if we got any data
    if no2_data.empty:
        print("⚠️  No NO2 data available for these sites in this period.")
        print("\n💡 Tip: Compare sites to understand spatial variation in air quality.")
        return

    # Calculate statistics by site
    print("-" * 80)
    print("NO2 Statistics by Site:")
    print("-" * 80)

    for site_code, description in sites.items():
        site_data = no2_data[no2_data["site_code"] == site_code]

        if not site_data.empty:
            print(f"\n  {site_code} - {description}")
            print(f"    Mean:   {site_data['value'].mean():6.2f} µg/m³")
            print(f"    Median: {site_data['value'].median():6.2f} µg/m³")
            print(f"    Min:    {site_data['value'].min():6.2f} µg/m³")
            print(f"    Max:    {site_data['value'].max():6.2f} µg/m³")
            print(f"    Count:  {len(site_data):,} measurements")

    # Ranking
    print("\n" + "-" * 80)
    print("Sites Ranked by Mean NO2 (highest to lowest):")
    print("-" * 80)

    site_means = (
        no2_data.groupby("site_code", observed=True)["value"]
        .mean()
        .sort_values(ascending=False)
    )

    for i, (site_code, mean_value) in enumerate(site_means.items(), 1):
        description = sites.get(site_code, "Unknown")
        bar = "█" * int(mean_value / 5)
        print(
            f"  {i}. {site_code} ({description[:30]:30s})  {mean_value:6.2f} µg/m³  {bar}"
        )

    print("\n💡 Tip: Compare sites to understand spatial variation in air quality.")


def demo_11_error_handling():
    """Demonstrate error handling and resilience."""
    print_section("DEMO 11: Error Handling and Resilience")

    print("Testing error handling with mix of valid and invalid requests...\n")

    print_subsection("Test 1: Invalid source name")
    try:
        aeolus.download("FAKE_SOURCE", ["MY1"], datetime.now(), datetime.now())
    except ValueError as e:
        print(f"✓ Caught error: {e}\n")

    print_subsection("Test 2: Multiple sources, one fails")
    print("Requesting from AURN (valid) and SAQN with invalid site...")

    data = aeolus.download(
        sources=["AURN"],
        sites=["MY1", "FAKE_SITE_999"],  # One valid, one invalid
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 1),
    )

    print(f"\n✓ Downloaded {len(data):,} measurements from valid sites")
    print("  (Invalid sites logged warnings but didn't stop the download)\n")

    print_subsection("Test 3: Automatic retries on network issues")
    print("Retry logic is automatic and transparent:")
    print("  • Connection errors → retry up to 3 times")
    print("  • Timeouts → retry with exponential backoff")
    print("  • Server errors (5xx) → retry")
    print("  • Client errors (4xx) → no retry (it's our fault!)")

    print("\n💡 Tip: Aeolus handles transient errors gracefully.")


def demo_12_advanced_transforms():
    """Demonstrate advanced transformation patterns."""
    print_section("DEMO 12: Advanced Transformations")

    print("Demonstrating advanced data transformation patterns...\n")

    # Download data
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 2)

    data = aeolus.download(
        sources="AURN", sites=["MY1"], start_date=start, end_date=end
    )

    print_subsection("Pattern 1: Add calculated columns")

    enhanced_data = pipe(
        data,
        add_column("hour", lambda df: df["date_time"].dt.hour),
        add_column("is_rush_hour", lambda df: df["hour"].isin([7, 8, 9, 17, 18, 19])),
        add_column("value_squared", lambda df: df["value"] ** 2),
    )

    print("Added columns: hour, is_rush_hour, value_squared")
    print(
        f"Sample:\n{enhanced_data[['date_time', 'hour', 'is_rush_hour', 'measurand', 'value']].head(5).to_string(index=False)}\n"
    )

    print_subsection("Pattern 2: Complex filtering")

    rush_hour_pollution = pipe(
        enhanced_data,
        filter_rows(lambda df: df["is_rush_hour"] == True),
        filter_rows(lambda df: df["measurand"].isin(["NO2", "PM2.5", "PM10"])),
        filter_rows(lambda df: df["value"] > 0),
    )

    print(f"Filtered to {len(rush_hour_pollution):,} rush hour pollution measurements")
    print("(Rush hours: 7-9 AM, 5-7 PM, pollutants: NO2, PM2.5, PM10)\n")

    print_subsection("Pattern 3: Aggregation pipeline")

    # Group and aggregate
    hourly_summary = (
        rush_hour_pollution.groupby(["hour", "measurand"], observed=True)["value"]
        .agg(["mean", "count"])
        .reset_index()
    )

    print("Rush hour pollution summary:")
    print(hourly_summary.to_string(index=False))

    print("\n💡 Tip: Chain transformations to build complex analysis pipelines.")


def main():
    """Run all demonstrations."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  AEOLUS COMPREHENSIVE FEATURE DEMONSTRATION".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("║" + "  UK Air Quality Data Made Simple".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")

    print("\n⚠️  This demo downloads real data from UK air quality networks.")
    print("    Network requests may take a few seconds per demonstration.")
    print("\n    Press Ctrl+C at any time to stop.\n")

    input("Press Enter to begin the demonstration...")

    try:
        # Run all demos
        demo_1_list_sources()
        input("\n\nPress Enter to continue to next demo...")

        demo_2_get_metadata()
        input("\n\nPress Enter to continue to next demo...")

        demo_3_simple_download()
        input("\n\nPress Enter to continue to next demo...")

        demo_4_multiple_sources()
        input("\n\nPress Enter to continue to next demo...")

        demo_5_separate_sources()
        input("\n\nPress Enter to continue to next demo...")

        demo_6_filter_transform()
        input("\n\nPress Enter to continue to next demo...")

        demo_7_composable_pipeline()
        input("\n\nPress Enter to continue to next demo...")

        demo_8_metadata_filtering()
        input("\n\nPress Enter to continue to next demo...")

        demo_9_time_series_analysis()
        input("\n\nPress Enter to continue to next demo...")

        demo_10_multi_site_comparison()
        input("\n\nPress Enter to continue to next demo...")

        demo_11_error_handling()
        input("\n\nPress Enter to continue to next demo...")

        demo_12_advanced_transforms()

        # Final summary
        print_section("DEMONSTRATION COMPLETE")

        print("✓ You've seen all major Aeolus features!\n")

        print("Key Takeaways:")
        print("  1. Simple API: aeolus.download() is all you need")
        print("  2. Multiple sources: Combine networks effortlessly")
        print("  3. Transformations: Use pipe() and compose() for data processing")
        print("  4. Metadata: Filter sites before downloading")
        print("  5. Error handling: Automatic retries and graceful failures")
        print("  6. Time series: Extract temporal features easily")
        print("  7. Comparison: Analyze multiple sites together")
        print("  8. Flexibility: Combine or separate sources as needed\n")

        print("Next Steps:")
        print("  • Try the examples with your own sites and date ranges")
        print("  • Explore the transform functions in aeolus.transforms")
        print("  • Read the README.md for more usage patterns")
        print("  • Check example.py for additional code samples\n")

        print("Happy analyzing! 📊🌍\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Demonstration interrupted by user.\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error during demonstration: {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
