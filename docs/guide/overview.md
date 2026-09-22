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
site_code | network | date_time                 | measurand | value | units | qa_code | qa_tier | ratification_stage | backend | source_network | ratification | created_at
----------|---------|---------------------------|-----------|-------|-------|---------|---------|--------------------|---------|----------------|--------------|---------------------------
MY1       | AURN    | 2024-01-01 00:00:00+00:00 | NO2       | 45.2  | ug/m3 | null    | unknown | null               | RDATA   | AURN           | None         | 2026-02-16 12:00:00+00:00
```

- `network` is who produced the data; `backend` is which of Aeolus's fetchers served it (`AURN` via `RDATA` or `SOS`).
- `qa_code` is the upstream's own quality token, verbatim. `qa_tier` (`reference_full_qc`, `reference_provisional`, `lcs_calibrated`, `lcs_factory_only`, `flagged`, `unknown`) and `ratification_stage` (`unratified`, `ratified`, `supplied`, `not_applicable`, or null) are derived from it through the network's vocabulary, so they mean the same thing across networks.
- `source_network` and `ratification` are deprecated mirrors of the columns above, kept until 1.0. Set `AEOLUS_LEGACY_COLUMNS=0` to drop them and confirm your code no longer reads them.

This makes it easy to combine and compare data from different sources.

## Metadata Schema

Site metadata (from `find_sites()`) uses a consistent format:

```
site_code | site_name          | latitude | longitude | network | country | instrument_class | provider | backend | measurands | source_network
----------|--------------------|---------:|----------:|---------|---------|------------------|----------|---------|------------|---------------
MY1       | London Marylebone  | 51.5225  | -0.1546   | AURN    | GB      | reference        | null     | RDATA   | [NO2, ...] | AURN
```

`provider` is the operating council for LMAM sites and null elsewhere; `instrument_class` is the network's default until per-site values are wired.

When using `near`, an additional `distance_km` column is included, sorted nearest-first.

## Time Conventions

Every `date_time` is timezone-aware **UTC** and marks the **start** of its averaging interval: a timestamp of `13:00` is the mean over `13:00`–`14:00` (left-closed: `[13:00, 14:00)`).

This is openair's "date beginning" convention. The UK-AIR web portal shows the same data "date ending", so values there appear an hour later. Where an upstream uses a different clock or labels the end of the interval (the EEA publishes in UTC+1, Sonitus stamps the end of each 15-minute bin, OpenAQ gives both ends), Aeolus converts, so the same hour from two sources carries the same timestamp.

!!! note "Earlier versions of this page"
    Before 0.5.0 this page said `13:00` meant `12:00`–`13:00`. The UK sources never worked that way; the page was wrong, not the data.
