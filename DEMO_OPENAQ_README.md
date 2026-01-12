# OpenAQ Demo Script

This demo script specifically tests and demonstrates OpenAQ integration with Aeolus.

## What is OpenAQ?

OpenAQ is a global air quality data platform providing access to monitoring data from over 100 countries. It aggregates data from government monitoring networks, research institutions, and low-cost sensor networks worldwide.

- Website: https://openaq.org/
- Explorer: https://explore.openaq.org/
- API Docs: https://docs.openaq.org/

## Requirements

### 1. API Key (Required)

OpenAQ v3 API requires authentication. Get a free API key:

1. Visit: https://openaq.org/
2. Sign up for a free account
3. Generate your API key
4. Add to `.env` file:

```bash
OPENAQ_API_KEY=your_key_here
```

**Note:** The `.env` file is git-ignored for security.

### 2. Python Dependencies

All dependencies are included with Aeolus:
```bash
pip install -e .
```

## Running the Demo

```bash
python demo_openaq.py
```

The demo is interactive and will pause between sections.

## What the Demo Shows

### Demo 1: Verify Registration
- Checks OpenAQ is registered with Aeolus
- Shows source information

### Demo 2: Basic Data Download
- Tests downloading data from OpenAQ
- Tries multiple location IDs
- Shows how to handle data availability

### Demo 3: Data Schema
- Examines the standardized data structure
- Shows column types and sample data
- Demonstrates schema consistency

### Demo 4: Compare with UK Data
- Downloads both OpenAQ and AURN data
- Combines them into one DataFrame
- Shows how sources work together

### Demo 5: Time Binning Convention
- Explains left-closed interval notation
- Shows how timestamps work
- Clarifies [12:00, 13:00) convention

### Demo 6: Finding Locations
- How to discover OpenAQ location IDs
- Using the OpenAQ Explorer
- Preview of upcoming search feature

### Demo 7: Rate Limits
- API key requirements
- Rate limit information
- How Aeolus handles limits automatically

### Demo 8: Global Coverage
- Examples of available regions
- Use cases for international data
- Comparative study examples

## Finding Location IDs

OpenAQ uses numeric location IDs. To find them:

### Method 1: OpenAQ Explorer (Easiest)
1. Go to: https://explore.openaq.org/
2. Search for your city or region
3. Click on a monitoring station
4. The location ID is shown in the station details

### Method 2: API Directly
Use the OpenAQ API to search:
```python
import requests
import os

headers = {"X-API-Key": os.getenv("OPENAQ_API_KEY")}
response = requests.get(
    "https://api.openaq.org/v3/locations",
    params={"country": "GB", "city": "London"},
    headers=headers
)
locations = response.json()["results"]
for loc in locations:
    print(f"ID: {loc['id']}, Name: {loc['name']}")
```

### Method 3: Wait for Aeolus Search (Coming Soon!)
```python
# Future feature
sites = aeolus.search_sites(
    sources="OpenAQ",
    city="London",
    parameter="NO2"
)
```

## Example Usage

Once you have location IDs:

```python
import aeolus
from datetime import datetime

# Download from any OpenAQ location
data = aeolus.download(
    sources="OpenAQ",
    sites=["2178", "8118"],  # Your location IDs
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Data is standardized and ready for analysis
print(data.head())
```

## Troubleshooting

### "OpenAQ API key not found"
- Check that `.env` file exists in the aeolus directory
- Verify `OPENAQ_API_KEY=your_key` is set
- No spaces around the `=` sign
- No quotes needed (but they're okay)

### "Location not found" or "No data available"
- Location IDs change over time
- Not all locations have data for all dates
- Check https://explore.openaq.org/ for active locations
- Try different date ranges

### "Rate limit exceeded"
- You've made too many requests
- Wait an hour or reduce request frequency
- With API key: 100,000 requests/hour (very generous)

### API returns 404
- Location may not exist
- Location may not have data for the requested period
- Try exploring OpenAQ website first

## Data Notes

### Time Resolution
- Default: Hourly averages
- OpenAQ also has daily, monthly, yearly aggregations
- Raw data (as-reported) available

### Data Quality
- OpenAQ includes both validated and unvalidated data
- Quality flags are preserved in the `ratification` column
- Government monitors typically have higher quality

### Coverage
- 100+ countries
- Tens of thousands of monitoring locations
- Mix of government and community sensors
- Historical depth varies by location

## What's Next?

After running the demo:

1. **Get real location IDs** from https://explore.openaq.org/
2. **Download data** from your region of interest
3. **Combine with UK data** for comparative analysis
4. **Wait for search feature** to make discovery easier

## Support

Questions or issues?
- Email: ruaraidh.dobson@gmail.com
- GitHub: https://github.com/southlondonscientific/aeolus

## Related Documentation

- Main README: `../README.md`
- Main demo: `../demo.py`
- Changes log: `../CHANGES.md`
- API examples: `../example.py`
