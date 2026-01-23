#!/usr/bin/env python3
"""
Download a small RData file for test fixtures.

This script downloads a single month of data from Marylebone Road (MY1)
to use as a test fixture for unit tests.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import requests

# Download one year of MY1 data (Marylebone Road, London)
# Using 2023 as a stable, complete year
# Format: {SITE}_{YEAR}.RData
URL = "https://uk-air.defra.gov.uk/openair/R_data/MY1_2023.RData"
OUTPUT_FILE = Path(__file__).parent / "aurn" / "MY1_2023.RData"

print(f"Downloading MY1 2023 data...")
print(f"URL: {URL}")
print(f"Output: {OUTPUT_FILE}")

try:
    response = requests.get(URL, timeout=60)
    response.raise_for_status()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_bytes(response.content)

    size_mb = len(response.content) / (1024 * 1024)
    print(f"✓ Downloaded {size_mb:.2f} MB")
    print(f"✓ Saved to {OUTPUT_FILE}")

    # Try to read it to verify it's valid
    try:
        import rdata

        parsed = rdata.parser.parse_file(OUTPUT_FILE)
        print(f"✓ File is valid RData")

        # Show what's inside
        print(f"\nContents:")
        for key in parsed.keys():
            print(f"  - {key}")
    except Exception as e:
        print(f"⚠️  Could not parse RData: {e}")
        print("   (File was still downloaded)")

except requests.RequestException as e:
    print(f"❌ Failed to download: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("SUCCESS: Downloaded MY1 data for 2023")
print("This file contains one year of hourly data from Marylebone Road")
print("Perfect size for test fixtures!")
print("=" * 60)
