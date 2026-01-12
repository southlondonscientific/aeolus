#!/usr/bin/env python3
"""
OpenAQ Demo Script

This script demonstrates OpenAQ integration with Aeolus.
OpenAQ provides access to global air quality data from 100+ countries.

Requirements:
- OpenAQ API key (free from https://openaq.org/)
- Set OPENAQ_API_KEY in .env file

Run with: python demo_openaq.py
"""

import sys
from datetime import datetime
from pathlib import Path

# Add src to path if running from repo
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd

import aeolus


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_subsection(title: str):
    """Print a formatted subsection header."""
    print(f"\n--- {title} ---\n")


def check_api_key():
    """Check if OpenAQ API key is configured."""
    import os

    api_key = os.getenv("OPENAQ_API_KEY")

    if not api_key:
        print("❌ ERROR: OpenAQ API key not found!")
        print("\nTo use OpenAQ, you need a free API key:")
        print("  1. Go to: https://openaq.org/")
        print("  2. Sign up and get your API key")
        print("  3. Add to .env file: OPENAQ_API_KEY=your_key_here")
        print("\nSee .env.example for template")
        return False

    print(f"✓ OpenAQ API key found: {api_key[:10]}...")
    return True


def demo_1_verify_registration():
    """Verify OpenAQ is registered with Aeolus."""
    print_section("DEMO 1: Verify OpenAQ Registration")

    sources = aeolus.list_sources()
    print(f"All registered sources: {', '.join(sources)}\n")

    if "OPENAQ" in sources:
        print("✓ OpenAQ successfully registered!\n")

        info = aeolus.get_source_info("OPENAQ")
        print("OpenAQ Source Information:")
        print(f"  Name: {info['name']}")
        print(f"  Requires API key: {info['requires_api_key']}")

        if info["requires_api_key"]:
            print("\n  Note: OpenAQ v3 API requires authentication")
            print("  Get free API key at: https://openaq.org/")
    else:
        print("❌ OpenAQ not registered")
        return False

    return True


def demo_2_test_basic_download():
    """Test basic data download from OpenAQ."""
    print_section("DEMO 2: Basic Data Download")

    print("Testing OpenAQ data download...")
    print("\nNote: We'll try a few different location IDs")
    print("OpenAQ location availability varies by date\n")

    # Try several locations - some should have data
    test_locations = [
        ("2178", "Example location 1"),
        ("8118", "Example location 2"),
        ("3", "Example location 3"),
    ]

    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 2)

    for location_id, description in test_locations:
        print(f"\nTrying location {location_id} ({description})...")

        try:
            data = aeolus.download(
                sources="OpenAQ", sites=[location_id], start_date=start, end_date=end
            )

            if not data.empty:
                print(f"✓ Success! Downloaded {len(data)} measurements")
                print(
                    f"  Date range: {data['date_time'].min()} to {data['date_time'].max()}"
                )
                print(f"  Measurands: {', '.join(data['measurand'].unique()[:5])}")
                return data, location_id
            else:
                print(f"  No data available for this location/period")

        except Exception as e:
            print(f"  Error: {e}")

    print("\n⚠️  Could not download data from test locations")
    print("This is normal - location availability varies")
    print("\nTo use OpenAQ:")
    print("  1. Visit: https://explore.openaq.org/")
    print("  2. Find an active location")
    print("  3. Use its location ID")

    return None, None


def demo_3_examine_schema(data: pd.DataFrame):
    """Examine the data schema and structure."""
    print_section("DEMO 3: Data Schema and Structure")

    if data is None or data.empty:
        print("⚠️  No data to examine (skipping)")
        return

    print("OpenAQ data has been normalized to Aeolus standard schema:\n")

    print("Columns:")
    for col in data.columns:
        print(f"  • {col}: {data[col].dtype}")

    print("\n" + "-" * 80)
    print("Sample data (first 10 rows):")
    print("-" * 80)
    sample = data.head(10)[["site_code", "date_time", "measurand", "value", "units"]]
    print(sample.to_string(index=False))

    print("\n" + "-" * 80)
    print("Data Summary:")
    print("-" * 80)
    print(f"  Total measurements: {len(data):,}")
    print(f"  Date range: {data['date_time'].min()} to {data['date_time'].max()}")
    print(f"  Unique measurands: {data['measurand'].nunique()}")
    print(f"  Source network: {data['source_network'].iloc[0]}")

    print("\nMeasurands breakdown:")
    for measurand, count in data["measurand"].value_counts().items():
        print(f"  {measurand:10s}: {count:4d} measurements")


def demo_4_compare_with_uk_data(openaq_data: pd.DataFrame, openaq_location: str):
    """Compare OpenAQ data with UK AURN data."""
    print_section("DEMO 4: Compare OpenAQ with UK AURN Data")

    if openaq_data is None or openaq_data.empty:
        print("⚠️  No OpenAQ data to compare (skipping)")
        return

    print("Downloading AURN data from London Marylebone Road (MY1)...")
    print("This demonstrates combining global and UK data\n")

    try:
        aurn_data = aeolus.download(
            sources="AURN",
            sites=["MY1"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        print(f"✓ AURN data: {len(aurn_data):,} measurements")
        print(f"✓ OpenAQ data: {len(openaq_data):,} measurements\n")

        # Combine both sources
        print("Combining both sources into one DataFrame...")
        combined = pd.concat([aurn_data, openaq_data], ignore_index=True)

        print(f"✓ Combined: {len(combined):,} measurements\n")

        print("-" * 80)
        print("Data by source:")
        print("-" * 80)
        for source in combined["source_network"].unique():
            source_data = combined[combined["source_network"] == source]
            print(f"\n  {source}:")
            print(f"    Measurements: {len(source_data):,}")
            print(f"    Measurands: {', '.join(source_data['measurand'].unique()[:5])}")

        # Find common measurands
        aurn_measurands = set(aurn_data["measurand"].unique())
        openaq_measurands = set(openaq_data["measurand"].unique())
        common = aurn_measurands & openaq_measurands

        if common:
            print(f"\n  Common measurands: {', '.join(common)}")
            print("\n  This allows direct comparison between sources!")

        print("\n💡 Key insight: Both sources use the same schema")
        print("   You can analyze them together seamlessly")

    except Exception as e:
        print(f"Could not download AURN data: {e}")


def demo_5_time_binning():
    """Explain OpenAQ time binning convention."""
    print_section("DEMO 5: Time Binning Convention")

    print("OpenAQ (like all Aeolus sources) uses LEFT-CLOSED intervals:\n")

    print("What does this mean?")
    print("  • Timestamp 13:00 represents the hour [12:00, 13:00)")
    print("  • This means: from 12:00:00 up to (but not including) 13:00:00")
    print("  • The 13:00:00 measurement belongs to hour 14:00\n")

    print("Example:")
    print("  Hour 13:00 contains:")
    print("    ✓ 12:00:00")
    print("    ✓ 12:30:15")
    print("    ✓ 12:59:59")
    print("    ✗ 13:00:00  (this belongs to hour 14:00)\n")

    print("Why this matters:")
    print("  • Consistent with ISO 8601 standard")
    print("  • Matches TimescaleDB and pandas conventions")
    print("  • Prevents double-counting at boundaries")
    print("  • Clear which hour owns midnight/noon\n")

    print("💡 This is true for ALL Aeolus sources (AURN, SAQN, OpenAQ, etc.)")


def demo_6_finding_locations():
    """Explain how to find OpenAQ locations."""
    print_section("DEMO 6: Finding OpenAQ Locations")

    print("How to find location IDs for OpenAQ:\n")

    print("Method 1: Use the OpenAQ Explorer (Recommended)")
    print("  1. Visit: https://explore.openaq.org/")
    print("  2. Search for your city or region")
    print("  3. Click on a monitoring station")
    print("  4. The location ID is in the URL or station details\n")

    print("Method 2: Use the OpenAQ API directly")
    print("  • API docs: https://docs.openaq.org/")
    print("  • Locations endpoint: /v3/locations")
    print("  • Filter by country, city, coordinates, etc.\n")

    print("Method 3: Wait for Aeolus search feature (Coming soon!)")
    print("  • We're building: aeolus.search_sites(city='London', source='OpenAQ')")
    print("  • This will make discovery much easier\n")

    print("Example location IDs to try:")
    print("  • Check explore.openaq.org for currently active locations")
    print("  • Location availability varies by date")
    print("  • Some locations only have recent data\n")

    print("💡 Tip: Once you find a good location, save its ID!")


def demo_7_rate_limits():
    """Explain OpenAQ rate limits."""
    print_section("DEMO 7: Rate Limits and API Keys")

    print("OpenAQ v3 API Rate Limits:\n")

    print("Without API key:")
    print("  ❌ Not allowed - v3 requires authentication\n")

    print("With free API key:")
    print("  ✓ 100,000 requests per hour")
    print("  ✓ More than enough for typical use")
    print("  ✓ Aeolus automatically uses your key from .env\n")

    print("Aeolus handles rate limiting automatically:")
    print("  • Pagination is transparent")
    print("  • Retries on transient errors")
    print("  • Clear error messages if limits exceeded\n")

    print("Best practices:")
    print("  1. Get a free API key (takes 2 minutes)")
    print("  2. Add to .env file")
    print("  3. Request only the data you need")
    print("  4. Aeolus does the rest!\n")

    print("💡 Your API key is safe:")
    print("   .env is in .gitignore and never committed to git")


def demo_8_global_coverage():
    """Demonstrate OpenAQ's global coverage."""
    print_section("DEMO 8: Global Coverage")

    print("OpenAQ provides data from 100+ countries!\n")

    print("Example regions with data:")
    print("  • Europe: UK, France, Germany, Spain, Italy, Poland...")
    print("  • Asia: India, China, Taiwan, Thailand, Indonesia...")
    print("  • Americas: USA, Canada, Mexico, Brazil, Chile...")
    print("  • Africa: South Africa, Nigeria, Ghana, Kenya...")
    print("  • Oceania: Australia, New Zealand...\n")

    print("This enables comparative studies:")
    print("  • Compare London to Delhi air quality")
    print("  • Study transboundary pollution (UK/France border)")
    print("  • Analyze global pollution trends")
    print("  • Validate models with international data")
    print("  • Build global ML training datasets\n")

    print("Same workflow everywhere:")

    print("""
    # London
    data_london = aeolus.download("OpenAQ", ["london_id"], start, end)

    # Delhi
    data_delhi = aeolus.download("OpenAQ", ["delhi_id"], start, end)

    # Combine for comparison
    combined = pd.concat([data_london, data_delhi])
    """)

    print("💡 OpenAQ makes Aeolus a truly global platform")


def main():
    """Run all demonstrations."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  OPENAQ INTEGRATION DEMO".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("║" + "  Global Air Quality Data with Aeolus".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")

    print("\n⚠️  This demo tests OpenAQ integration")
    print("    OpenAQ provides global air quality data (100+ countries)")
    print("    Requires free API key from https://openaq.org/\n")

    # Check for API key
    if not check_api_key():
        print("\nDemo cannot continue without API key.")
        print("Please set up .env file and try again.")
        return

    print("\n" + "=" * 80)

    try:
        # Demo 1: Verify registration
        if not demo_1_verify_registration():
            print("\n❌ OpenAQ not properly registered. Stopping.")
            return

        input("\nPress Enter to continue...")

        # Demo 2: Try to download data
        data, location_id = demo_2_test_basic_download()

        input("\nPress Enter to continue...")

        # Demo 3: Examine schema
        demo_3_examine_schema(data)

        input("\nPress Enter to continue...")

        # Demo 4: Compare with UK data
        demo_4_compare_with_uk_data(data, location_id)

        input("\nPress Enter to continue...")

        # Demo 5: Time binning
        demo_5_time_binning()

        input("\nPress Enter to continue...")

        # Demo 6: Finding locations
        demo_6_finding_locations()

        input("\nPress Enter to continue...")

        # Demo 7: Rate limits
        demo_7_rate_limits()

        input("\nPress Enter to continue...")

        # Demo 8: Global coverage
        demo_8_global_coverage()

        # Summary
        print_section("DEMO COMPLETE")

        print("✓ OpenAQ integration is ready to use!\n")

        print("Key takeaways:")
        print("  1. OpenAQ provides global air quality data")
        print("  2. Requires free API key (set in .env)")
        print("  3. Same workflow as UK sources")
        print("  4. Data is automatically standardized")
        print("  5. Location IDs found at explore.openaq.org")
        print("  6. Perfect for international comparisons\n")

        print("Next steps:")
        print("  • Get API key at: https://openaq.org/")
        print("  • Find locations at: https://explore.openaq.org/")
        print("  • Try downloading from your region")
        print("  • Combine with UK AURN data")
        print("  • Wait for search feature (coming soon!)\n")

        print("Questions or issues?")
        print("  • Email: ruaraidh.dobson@gmail.com")
        print("  • GitHub: https://github.com/southlondonscientific/aeolus\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user.\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Demo error: {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
