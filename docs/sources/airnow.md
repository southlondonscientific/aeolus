# EPA AirNow

[AirNow](https://www.airnow.gov/) is a US Environmental Protection Agency (EPA) program providing real-time air quality data from over 2,500 monitoring stations across the United States, Canada, and Mexico.

## Overview

- **Coverage**: United States, Canada, Mexico (2,500+ stations)
- **Data**: Real-time observations and forecasts
- **Pollutants**: O3, PM2.5, PM10, NO2, SO2, CO
- **Data quality**: Provisional (preliminary, subject to change)
- **API key**: Required (free registration)

## Getting an API Key

1. Visit [https://docs.airnowapi.org/account/request/](https://docs.airnowapi.org/account/request/)
2. Create a free account
3. Add the key to your `.env` file:

```bash
AIRNOW_API_KEY=your-api-key-here
```

## Quick Start

```python
import aeolus
from datetime import datetime

# Get monitoring sites in California
metadata = aeolus.networks.get_metadata(
    "AIRNOW",
    bounding_box=(-124.48, 32.53, -114.13, 42.01)  # CA bounds
)

# Pick some sites
sites = metadata["site_code"].head(5).tolist()

# Download data
data = aeolus.download(
    "AIRNOW",
    sites,
    datetime(2024, 1, 1),
    datetime(2024, 1, 7)
)
```

## Finding Monitoring Sites

AirNow sites are identified by their coordinates, encoded as site codes:

```python
import aeolus

# Get sites in a geographic region
# bounding_box format: (min_lon, min_lat, max_lon, max_lat)
metadata = aeolus.networks.get_metadata(
    "AIRNOW",
    bounding_box=(-125.0, 24.0, -66.0, 50.0)  # Continental US
)

print(metadata[["site_code", "site_name", "state_code"]])
```

## Site Code Format

Site codes are derived from coordinates in the format `{lat}_{lon}` where:
- Decimal points are replaced with `d`
- Negative signs are replaced with `m`

For example: `34d0522_m118d2437` represents latitude 34.0522, longitude -118.2437 (Los Angeles).

## Downloading Data

### Historical Data

```python
import aeolus
from datetime import datetime

data = aeolus.download(
    "AIRNOW",
    ["34d0522_m118d2437"],  # Los Angeles
    datetime(2024, 1, 1),
    datetime(2024, 1, 7)
)
```

### Current Observations

For quick access to current air quality near a location:

```python
from aeolus.sources.airnow import fetch_airnow_current

# Get current AQI near Los Angeles
data = fetch_airnow_current(
    latitude=34.0522,
    longitude=-118.2437,
    distance=25  # miles
)

print(data[["measurand", "value", "units"]])
```

## Data Quality

AirNow data is marked as `ratification='Provisional'` because:

- Data is preliminary and subject to change
- Not intended for regulatory purposes
- For verified historical data, use EPA AQS (6+ month delay)

From the AirNow documentation:
> "Data and information reported to AirNow should be considered preliminary and subject to change. These data should not be used to formulate or support regulation, ascertain trends, or support any other government or public decision-making."

## Available Pollutants

| Pollutant | Description |
|-----------|-------------|
| O3 | Ozone |
| PM2.5 | Fine particulate matter |
| PM10 | Coarse particulate matter |
| NO2 | Nitrogen dioxide |
| SO2 | Sulfur dioxide |
| CO | Carbon monoxide |

## Rate Limits

- 500 requests per hour per endpoint
- Data updates hourly (typically 10-30 minutes past the hour)
- Cache responses when possible

## Historical Data Limitations

AirNow historical data is limited to approximately 45 days. For older data, consider:

- **EPA AQS**: Verified data with 6+ month delay
- **OpenAQ**: May have archived AirNow data

## Example: Multi-City Comparison

```python
import aeolus
from datetime import datetime

# Define cities by their approximate coordinates
cities = {
    "Los Angeles": (-118.24, 34.05),
    "New York": (-74.01, 40.71),
    "Chicago": (-87.63, 41.88),
}

# Get sites near each city
all_sites = []
for city, (lon, lat) in cities.items():
    metadata = aeolus.networks.get_metadata(
        "AIRNOW",
        bounding_box=(lon - 0.5, lat - 0.5, lon + 0.5, lat + 0.5)
    )
    if not metadata.empty:
        all_sites.extend(metadata["site_code"].head(2).tolist())

# Download data for all sites
data = aeolus.download(
    "AIRNOW",
    all_sites,
    datetime(2024, 1, 1),
    datetime(2024, 1, 7)
)

# Analyze PM2.5 across cities
pm25 = data[data["measurand"] == "PM2.5"]
print(pm25.groupby("site_code")["value"].mean())
```

## Resources

- [AirNow Website](https://www.airnow.gov/)
- [API Documentation](https://docs.airnowapi.org/)
- [Air Quality Index (AQI) Basics](https://www.airnow.gov/aqi/aqi-basics/)
- [EPA Air Quality System (AQS)](https://www.epa.gov/aqs) - For verified historical data
