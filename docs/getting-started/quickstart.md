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

Every download returns the same 13 columns (`aeolus.schema.DATA_COLUMNS`):

| Column | Description |
|--------|-------------|
| `site_code` | Unique identifier for the monitoring site |
| `network` | Which network produced the data (`AURN`, `LAQN`, `EEA`, ...) |
| `date_time` | Start of the averaging interval, tz-aware UTC (`13:00` covers 13:00–14:00) |
| `measurand` | Pollutant name (PM2.5, NO2, O3, ...) |
| `value` | Measured concentration |
| `units` | As the network reports them (`ug/m3`; `mg/m3` for CO; `ppb` for AirNow gases) |
| `qa_code` | The network's own quality token, verbatim (null where it publishes none) |
| `qa_tier` | Cross-network quality tier: `reference_full_qc`, `reference_provisional`, `lcs_calibrated`, `lcs_factory_only`, `flagged`, `unknown` |
| `ratification_stage` | `unratified`, `ratified`, `supplied`, `not_applicable` or null |
| `backend` | Which fetcher served the row (`RDATA`, `SOS`, `ERG_REST`, `EEA_E1A`, ...) |
| `source_network` | Deprecated mirror of `network` (removed in 1.0) |
| `ratification` | Deprecated mirror derived from the three QA columns (removed in 1.0) |
| `created_at` | When the record was fetched (UTC) |

Set `AEOLUS_LEGACY_COLUMNS=0` to drop the two mirrors. The [Data Quality](../guide/ratification.md) guide explains the three QA columns network by network.

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
