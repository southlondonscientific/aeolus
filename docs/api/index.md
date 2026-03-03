# API Reference

This section provides detailed documentation for all Aeolus functions and classes.

## Module Overview

| Module | Description |
|--------|-------------|
| [`aeolus`](aeolus.md) | Top-level API (find_sites, download, list_sources) |
| [`aeolus.networks`](networks.md) | Network-specific functions |
| [`aeolus.portals`](portals.md) | Portal-specific functions (OpenAQ, PurpleAir) |
| [`aeolus.metrics`](metrics.md) | Air quality indices and analysis functions |

## Quick Reference

### Core Functions

```python
import aeolus

# Find nearby monitoring sites
aeolus.find_sites("AURN", near=(51.5, -0.1), radius_km=20)

# Find sites in a bounding box
aeolus.find_sites(bbox=(-0.5, 51.3, 0.3, 51.7))

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
aeolus.portals.find_sites("OPENAQ", country="GB")

# Download from a portal
aeolus.portals.download("OPENAQ", sites, start, end)
```

### Analysis Functions

```python
from aeolus import metrics

# Time-average with data capture thresholds
daily = metrics.time_average(data, freq="D", data_thresh=0.75)

# Annual regulatory statistics (LAQM-ready)
stats = metrics.aq_stats(data, year=2024)

# Non-parametric trend analysis (Theil-Sen + Mann-Kendall)
result = metrics.trend(data, pollutant="NO2")
```

### AQI Functions

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

### Visualization Functions

```python
from aeolus import viz, metrics

# Time variation (openair-style 2x2 plot)
fig = viz.plot_time_variation(data, pollutant="NO2")

# Trend plot
result = metrics.trend(data, pollutant="NO2")
fig = viz.plot_trend(data, result)
```
