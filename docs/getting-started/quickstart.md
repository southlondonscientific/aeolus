# Quick Start

This guide will get you downloading air quality data in minutes.

## Your First Download

The simplest way to get started is with the UK AURN network, which doesn't require an API key:

```python
import aeolus
from datetime import datetime

# Download a month of data from two London sites
data = aeolus.download(
    sources="AURN",
    sites=["MY1", "KC1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

print(data.head())
```

## Understanding the Output

All data sources return a standardised pandas DataFrame with these columns:

| Column | Description |
|--------|-------------|
| `site_code` | Unique identifier for the monitoring site |
| `date_time` | Timestamp (start of measurement period) |
| `measurand` | Pollutant name (PM2.5, NO2, O3, etc.) |
| `value` | Measured concentration |
| `units` | Measurement units (typically µg/m³) |
| `source_network` | Data source identifier |
| `ratification` | Data quality flag |
| `created_at` | When the record was fetched |

## Finding Available Sites

Find monitoring sites near a location:

```python
# Find AURN sites within 20 km of central London
sites = aeolus.find_sites("AURN", near=(51.5074, -0.1278), radius_km=20)
print(sites[['site_code', 'site_name', 'distance_km']])
```

Or list all sites for a network:

```python
# Get metadata for all AURN sites
sites = aeolus.networks.get_metadata("AURN")
print(sites[['site_code', 'site_name', 'latitude', 'longitude']])
```

## Downloading from Multiple Sources

You can download from multiple sources in one call:

```python
data = aeolus.download(
    sources={"AURN": ["MY1"], "SAQN": ["ED3"]},
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

## Quick Data Overview

Use `summarise()` to see what's in your data:

```python
aeolus.summarise(data)
# Shows sites, pollutants, date ranges, record counts, and data capture
```

## Date Range Shorthand

For quick exploratory work, use `last=` instead of explicit dates:

```python
# Last 30 days of data
data = aeolus.download("AURN", ["MY1"], last="30d")

# Also: "2w" (weeks), "6m" (months), "1y" (years)
```

## Near-Real-Time Data

Get the latest readings from UK regulatory monitors:

```python
latest = aeolus.get_current("AURN", sites=["MY1", "KC1"])
print(latest[["site_code", "date_time", "measurand", "value"]])
```

## Next Steps

- [Configuration](configuration.md) - Set up API keys for more data sources
- [Data Sources](../guide/sources.md) - Learn about all available sources
- [Downloading Data](../guide/downloading.md) - Advanced download options
- [User Story Notebooks](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/) - 8 executable notebooks covering real-world workflows (NO2 comparison, compliance reporting, sensor validation, city rankings, exposure assessment, trend analysis, and more)
