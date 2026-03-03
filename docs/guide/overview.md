# Overview

Aeolus is organised around two types of data sources:

## Networks vs Portals

**Networks** are discrete monitoring networks operated by specific organisations:

- AURN (UK government regulatory network)
- SAQN (Scottish network)
- Breathe London (London low-cost sensors)
- AirQo (African cities)

**Portals** are aggregation platforms that collect data from multiple sources:

- OpenAQ (global data from 100+ countries)
- PurpleAir (global low-cost sensors)

## The Unified API

The typical workflow is: **find sites → download data → analyse → plot**.

### Finding Sites

Use `find_sites()` to discover monitoring sites without needing to know whether a source is a network or portal:

```python
import aeolus

# Find AURN sites near central London
sites = aeolus.find_sites("AURN", near=(51.5074, -0.1278), radius_km=20)
print(sites[["site_code", "site_name", "distance_km"]])

# Find sites from all free sources (no API key needed)
sites = aeolus.find_sites(near=(51.5, -0.1), radius_km=10)

# Find sites in a bounding box
sites = aeolus.find_sites(["AURN", "SAQN"], bbox=(-0.5, 51.3, 0.3, 51.7))
```

### Downloading Data

Use `download()` with the site codes from `find_sites()`:

```python
from datetime import datetime

start = datetime(2024, 1, 1)
end = datetime(2024, 1, 31)

# Single source
data = aeolus.download("AURN", ["MY1"], start, end)

# Multiple sources
data = aeolus.download(
    {"AURN": ["MY1"], "OpenAQ": ["2178"]},
    start_date=start,
    end_date=end
)
```

### Analyse and Plot

```python
from aeolus import metrics, viz

# Annual regulatory statistics
stats = metrics.aq_stats(data, year=2024)

# Trend analysis
result = metrics.trend(data, pollutant="NO2")

# Temporal variation plot (openair-style 2x2)
fig = viz.plot_time_variation(data, pollutant="NO2")
```

## Data Standardisation

All sources return data in a consistent format:

```
site_code | date_time           | measurand | value | units | source_network | ratification | created_at
----------|---------------------|-----------|-------|-------|----------------|--------------|--------------------
MY1       | 2024-01-01 00:00:00 | NO2       | 45.2  | ug/m3 | AURN           | None         | 2026-02-16 12:00:00
```

This makes it easy to combine and compare data from different sources.

## Metadata Schema

Site metadata (from `find_sites()`) uses a consistent format:

```
site_code | site_name          | latitude | longitude | source_network
----------|--------------------|---------:|----------:|--------------
MY1       | London Marylebone  | 51.5225  | -0.1546   | AURN
```

When using `near`, an additional `distance_km` column is included, sorted nearest-first.

## Time Conventions

Aeolus uses **left-closed intervals** for timestamps. A timestamp of `13:00` represents the period from `12:00` to `13:00`.

This matches the convention used by most regulatory networks.
