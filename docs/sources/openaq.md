# OpenAQ

[OpenAQ](https://openaq.org/) is a global open data platform that aggregates air quality data from government agencies, research institutions, and other sources worldwide.

## Overview

- **Coverage**: 100+ countries
- **Data sources**: Government monitors, research stations, low-cost sensors
- **Data quality**: Varies by source (reference-grade to indicative)
- **API key**: Required

## Getting an API Key

1. Go to [OpenAQ Explorer](https://explore.openaq.org/)
2. Create a free account
3. Find your API key in account settings
4. Set the environment variable:

```bash
export OPENAQ_API_KEY=your_key_here
```

## Finding Sites

OpenAQ aggregates data from many sources, so site discovery is important:

```python
import aeolus

# Search for sites in a country
uk_sites = aeolus.portals.find_sites("OpenAQ", country="GB")

# Search within a bounding box (min_lat, min_lon, max_lat, max_lon)
london_sites = aeolus.portals.find_sites(
    "OpenAQ",
    bbox=(51.28, -0.51, 51.69, 0.34)
)

# Search by city
city_sites = aeolus.portals.find_sites("OpenAQ", city="London")
```

## Downloading Data

Use `portals.download()` with `location_ids`:

```python
import aeolus
from datetime import datetime

# Get location IDs from find_sites
locations = aeolus.portals.find_sites("OpenAQ", country="GB")
location_ids = locations["location_id"].tolist()[:5]  # First 5

# Download using portals.download
data = aeolus.portals.download(
    portal="OpenAQ",
    location_ids=location_ids,
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

Or use the top-level `download()` with the sources dict:

```python
data = aeolus.download(
    sources={"OpenAQ": location_ids},
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

## Pollutant Names

OpenAQ uses lowercase pollutant names:

| OpenAQ | Standard |
|--------|----------|
| pm25 | PM2.5 |
| pm10 | PM10 |
| no2 | NO2 |
| o3 | O3 |
| so2 | SO2 |
| co | CO |

Aeolus normalises these to the standard format automatically.

## Data Quality Considerations

OpenAQ aggregates data from diverse sources with varying quality:

- **Reference-grade**: Government regulatory monitors (high quality)
- **Low-cost sensors**: PurpleAir, Clarity, etc. (indicative quality)
- **Research stations**: Quality varies

Check the `source_network` column to understand data provenance.

## Rate Limits

OpenAQ has API rate limits. Aeolus handles these automatically with:

- Request throttling
- Automatic retry on rate limit errors
- Chunked downloads for large date ranges

## Example: Global Comparison

```python
import aeolus
from datetime import datetime

# Find sites in different countries
uk_sites = aeolus.portals.find_sites("OpenAQ", country="GB")
de_sites = aeolus.portals.find_sites("OpenAQ", country="DE")

# Get a few location IDs from each
location_ids = (
    uk_sites["location_id"].tolist()[:2] +
    de_sites["location_id"].tolist()[:2]
)

# Download data
data = aeolus.portals.download(
    portal="OpenAQ",
    location_ids=location_ids,
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Compare by site
data.groupby('site_name')['value'].describe()
```
