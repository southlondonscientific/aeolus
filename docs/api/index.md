# API Reference

This section provides detailed documentation for all Aeolus functions and classes.

## Module Overview

| Module | Description |
|--------|-------------|
| [`aeolus`](aeolus.md) | Top-level API (download, list_sources, etc.) |
| [`aeolus.networks`](networks.md) | Network-specific functions |
| [`aeolus.portals`](portals.md) | Portal-specific functions (OpenAQ) |
| [`aeolus.metrics`](metrics.md) | Air quality index calculations |

## Quick Reference

### Core Functions

```python
import aeolus

# List available data sources
aeolus.list_sources()

# Get information about a source
aeolus.get_source_info("AURN")

# Download data (main entry point)
aeolus.download(sources, sites, start_date, end_date)
```

### Network Functions

```python
# Get site metadata for a network
aeolus.networks.get_metadata("AURN")

# Download from a specific network
aeolus.networks.download("AURN", sites, start, end)
```

### Portal Functions

```python
# Find sites on a portal
aeolus.portals.find_sites("OpenAQ", country="GB")

# Download from a portal
aeolus.portals.download("OpenAQ", location_ids, start, end)
```

### Metrics Functions

```python
from aeolus import metrics

# Calculate AQI summary
metrics.aqi_summary(data, index="UK_DAQI")

# Get AQI time series
metrics.aqi_timeseries(data, index="UK_DAQI")

# Check WHO guideline compliance
metrics.aqi_check_who(data)

# List available indices
metrics.list_indices()
```
