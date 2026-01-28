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
| `site_name` | Human-readable site name |
| `date_time` | Timestamp (start of measurement period) |
| `measurand` | Pollutant name (PM2.5, NO2, O3, etc.) |
| `value` | Measured concentration |
| `units` | Measurement units (typically µg/m³) |
| `source_network` | Data source identifier |
| `ratification` | Data quality flag |

## Finding Available Sites

List all available sites for a network:

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

## Next Steps

- [Configuration](configuration.md) - Set up API keys for more data sources
- [Data Sources](../guide/sources.md) - Learn about all available sources
- [Downloading Data](../guide/downloading.md) - Advanced download options
