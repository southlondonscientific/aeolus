# Metrics & Analysis

Aeolus includes built-in functions for calculating Air Quality Indices (AQI) from multiple international standards.

## Supported AQI Systems

| Index | Country | Scale | Pollutants |
|-------|---------|-------|------------|
| UK_DAQI | UK | 1-10 | O3, NO2, SO2, PM2.5, PM10 |
| US_EPA | USA | 0-500 | O3, PM2.5, PM10, CO, SO2, NO2 |
| CHINA | China | 0-500 | PM2.5, PM10, SO2, NO2, O3, CO |
| EU_CAQI | EU | 1-6 | NO2, PM2.5, PM10, O3, CO |
| INDIA_NAQI | India | 0-500 | PM2.5, PM10, SO2, NO2, O3, CO, NH3 |
| WHO | Global | - | Guidelines compliance checker |

## AQI Summary

Calculate AQI statistics over a time period:

```python
import aeolus
from aeolus import metrics
from datetime import datetime

# Download data
data = aeolus.download(
    sources="AURN",
    sites=["MY1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31)
)

# Overall summary for the entire period
summary = metrics.aqi_summary(data, index="UK_DAQI")

# Monthly breakdown
monthly = metrics.aqi_summary(data, index="UK_DAQI", freq="M")

# Just the overall AQI (not per-pollutant)
simple = metrics.aqi_summary(data, index="UK_DAQI", overall_only=True)
```

### Output Formats

**Long format** (default) - one row per site/period/pollutant:

```
site_code | period  | pollutant | mean | aqi_value | aqi_category
MY1       | 2024-01 | NO2       | 45.2 | 3         | Low
MY1       | 2024-01 | PM2.5     | 12.1 | 2         | Low
```

**Wide format** - one row per site/period:

```python
wide = metrics.aqi_summary(data, index="UK_DAQI", freq="M", format="wide")
```

## AQI Time Series

Get AQI values for each timestamp with appropriate rolling averages:

```python
# Calculate hourly AQI with rolling averages
ts = metrics.aqi_timeseries(data, index="UK_DAQI")

# The function applies the correct rolling window for each pollutant
# (e.g., 8-hour for O3, 24-hour for PM2.5)
```

Plot the results:

```python
import matplotlib.pyplot as plt

pivot = ts.pivot(index="date_time", columns="pollutant", values="aqi_value")
pivot.plot(figsize=(12, 4))
plt.ylabel("AQI Value")
plt.title("UK DAQI by Pollutant")
plt.show()
```

## WHO Guidelines

Check compliance with WHO Air Quality Guidelines:

```python
# Check against the strictest guideline (AQG)
compliance = metrics.aqi_check_who(data)

print(compliance[["pollutant", "mean_concentration", "guideline_value", "meets_guideline"]])
```

WHO provides interim targets for regions working towards the guidelines:

```python
# Check against Interim Target 1 (least strict)
compliance_it1 = metrics.aqi_check_who(data, target="IT-1")

# Available targets: "AQG", "IT-1", "IT-2", "IT-3", "IT-4"
```

## Listing Available Indices

```python
# See all available indices
indices = metrics.list_indices()
print(indices)

# Get details about an index
info = metrics.get_index_info("UK_DAQI")
print(f"Name: {info['name']}")
print(f"Scale: {info['scale']}")
print(f"Pollutants: {info['pollutants']}")
```

## Example: Annual AQI Report

```python
import aeolus
from aeolus import metrics
from datetime import datetime

# Download a full year
data = aeolus.download(
    sources="AURN",
    sites=["MY1", "KC1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31)
)

# Monthly AQI summary
monthly = metrics.aqi_summary(
    data,
    index="UK_DAQI",
    freq="M",
    overall_only=True
)

print(monthly)

# WHO compliance check
who_check = metrics.aqi_check_who(data)
print("\nWHO Guideline Compliance:")
print(who_check[["site_code", "pollutant", "meets_guideline", "exceedance_ratio"]])
```
