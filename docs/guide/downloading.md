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

Before downloading, you'll often want to explore available sites:

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
