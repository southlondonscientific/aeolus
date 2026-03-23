# Downloading Data

This guide covers the various ways to download data with Aeolus.

## Basic Download

The simplest download specifies a source, sites, and date range:

```python
import aeolus
from datetime import datetime

data = aeolus.download(
    sources="AURN",
    sites=["MY1", "KC1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

## Finding Sites

Before downloading, you'll often want to explore available sites. The `find_sites()` function works across all sources:

```python
# Find sites near a location (sorted by distance)
sites = aeolus.find_sites("AURN", near=(51.5074, -0.1278), radius_km=20)
print(sites[["site_code", "site_name", "distance_km"]])

# Find sites in a bounding box
sites = aeolus.find_sites("AURN", bbox=(-0.5, 51.3, 0.3, 51.7))

# Find sites from all free sources
sites = aeolus.find_sites(near=(51.5, -0.1), radius_km=10)

# Include API-key sources too (warns on failures)
sites = aeolus.find_sites(near=(51.5, -0.1), radius_km=10, include_all=True)
```

You can also access network-specific metadata directly:

```python
# Get all sites for a network
sites = aeolus.networks.get_metadata("AURN")

# Filter by location, pollutant, etc.
london_sites = sites[sites['site_name'].str.contains('London')]
```

## Multiple Sources

Download from multiple sources simultaneously:

```python
data = aeolus.download(
    sources={
        "AURN": ["MY1", "KC1"],
        "SAQN": ["ED3", "GLA4"]
    },
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

The resulting DataFrame contains data from all sources, distinguished by the `source_network` column.

## Filtering Pollutants

To download specific pollutants only, filter the data after downloading:

```python
# Download all data
data = aeolus.download(
    sources="AURN",
    sites=["MY1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Filter to NO2 and PM2.5
data = data[data['measurand'].isin(['NO2', 'PM2.5'])]
```

## Working with the Data

The returned DataFrame is a standard pandas DataFrame:

```python
# Basic statistics
print(data.groupby('measurand')['value'].describe())

# Filter to specific pollutant
no2_data = data[data['measurand'] == 'NO2']

# Pivot for time series analysis
pivot = data.pivot_table(
    index='date_time',
    columns=['site_code', 'measurand'],
    values='value'
)
```

## Handling Missing Data

Air quality data often has gaps. Aeolus returns only the data that exists - it doesn't fill missing values:

```python
# Check data completeness
data.groupby(['site_code', 'measurand']).size()

# Check coverage via AQI summary (includes coverage column)
from aeolus import metrics
summary = metrics.aqi_summary(data, index="UK_DAQI", freq="D")
print(summary[['site_code', 'period', 'pollutant', 'coverage']])
```

## Local File Caching

Enable caching to avoid redundant API calls when re-running notebooks or analyses. Cached data is stored as Parquet files:

```python
from aeolus.cache import enable_cache, clear_cache, cache_info

# Enable caching (all subsequent downloads are cached)
enable_cache()

# First call hits the API
data = aeolus.download("AURN", ["MY1"], start, end)

# Second call is instant (served from cache)
data = aeolus.download("AURN", ["MY1"], start, end)

# Check cache status
info = cache_info()
print(f"Cached: {info['total_files']} files, {info['total_size_mb']:.1f} MB")

# Clear cache for a specific source
clear_cache("AURN")

# Clear entire cache
clear_cache()
```

The cache directory defaults to `~/.cache/aeolus/` and can be overridden:

```python
# Via function argument
enable_cache(cache_dir="/path/to/cache")

# Or via environment variable
# export AEOLUS_CACHE_DIR=/path/to/cache
```

## Large Downloads

For large date ranges, data is downloaded in chunks automatically. Progress is shown in the console.

```python
# This will download in monthly chunks
data = aeolus.download(
    sources="AURN",
    sites=["MY1"],
    start_date=datetime(2020, 1, 1),
    end_date=datetime(2024, 12, 31)
)
```
