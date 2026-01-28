# aeolus.metrics

Air Quality Index calculations and metrics.

## Functions

::: aeolus.metrics.aqi_summary
    options:
      show_root_heading: false

::: aeolus.metrics.aqi_timeseries
    options:
      show_root_heading: false

::: aeolus.metrics.aqi_check_who
    options:
      show_root_heading: false

::: aeolus.metrics.list_indices
    options:
      show_root_heading: false

::: aeolus.metrics.get_index_info
    options:
      show_root_heading: false

## Supported Indices

| Index | Country | Scale | Description |
|-------|---------|-------|-------------|
| UK_DAQI | UK | 1-10 | UK Daily Air Quality Index |
| US_EPA | USA | 0-500 | US EPA Air Quality Index (with NowCast) |
| CHINA | China | 0-500 | China Air Quality Index |
| EU_CAQI_ROADSIDE | EU | 1-6 | European AQI for traffic stations |
| EU_CAQI_BACKGROUND | EU | 1-6 | European AQI for background stations |
| INDIA_NAQI | India | 0-500 | India National Air Quality Index |
| WHO | Global | - | WHO Air Quality Guidelines checker |

## Usage Examples

### AQI Summary

```python
import aeolus
from aeolus import metrics
from datetime import datetime

# Download data
data = aeolus.download(
    sources="AURN",
    sites=["MY1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Calculate UK DAQI summary
summary = metrics.aqi_summary(data, index="UK_DAQI")

# Monthly breakdown
monthly = metrics.aqi_summary(data, index="UK_DAQI", freq="M")

# Just overall AQI values
simple = metrics.aqi_summary(data, index="UK_DAQI", overall_only=True)
```

### AQI Time Series

```python
# Get hourly AQI values with rolling averages
ts = metrics.aqi_timeseries(data, index="UK_DAQI")

# Plot
ts.pivot(index="date_time", columns="pollutant", values="aqi_value").plot()
```

### WHO Guideline Compliance

```python
# Check against WHO Air Quality Guidelines
compliance = metrics.aqi_check_who(data)
print(compliance[["pollutant", "meets_guideline", "exceedance_ratio"]])

# Check against less strict interim targets
compliance_it1 = metrics.aqi_check_who(data, target="IT-1")
```

### List Available Indices

```python
# See all available indices
indices = metrics.list_indices()
print(indices)
# ['UK_DAQI', 'US_EPA', 'CHINA', 'WHO', 'EU_CAQI_ROADSIDE', ...]

# Get details about a specific index
info = metrics.get_index_info("UK_DAQI")
print(info["pollutants"])  # ['O3', 'NO2', 'SO2', 'PM2.5', 'PM10']
```
