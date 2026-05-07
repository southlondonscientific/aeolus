# Metrics & Analysis

Aeolus includes analysis functions for regulatory statistics, trend detection, and air quality index calculation.

!!! tip "See it in action"
    - [Notebook 01](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/01_london_no2_comparison.ipynb) uses `time_average()` and `aq_stats()` for roadside vs background analysis
    - [Notebook 02](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/02_pm25_compliance_report.ipynb) uses `aqi_summary()`, `aqi_check_who()`, and `aq_stats()` for a compliance report
    - [Notebook 08](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/08_trend_analysis.ipynb) uses `trend()` and `plot_trend()` for multi-year Theil-Sen analysis with deseasonalisation

## Time Averaging

Use `time_average()` to resample data to a coarser time resolution with data capture thresholds. Periods with insufficient valid observations are set to NaN:

```python
from aeolus import metrics

# Daily averages (at least 75% data capture required)
daily = metrics.time_average(data, freq="D", data_thresh=0.75)

# Monthly averages
monthly = metrics.time_average(data, freq="ME")

# Daily maximum
daily_max = metrics.time_average(data, freq="D", statistic="max")

# 95th percentile, no threshold
p95 = metrics.time_average(data, freq="D", statistic="percentile", percentile=95, data_thresh=0)

# Only specific pollutants
no2_daily = metrics.time_average(data, freq="D", pollutants=["NO2"])
```

The output includes a `data_capture` column showing the fraction of valid observations in each period.

## Annual Statistics

Use `aq_stats()` to calculate regulatory statistics suitable for LAQM Annual Status Reports:

```python
# All years and pollutants
stats = metrics.aq_stats(data)

# Specific year
stats = metrics.aq_stats(data, year=2024)

# Specific pollutant
stats = metrics.aq_stats(data, pollutant="NO2")
```

Output columns:

| Column | Description |
|--------|-------------|
| `annual_mean` | Annual mean concentration |
| `max_hourly` | Maximum hourly value |
| `max_daily_mean` | Maximum daily mean |
| `max_8h_rolling_mean` | Maximum 8-hour rolling mean |
| `p95`, `p99` | 95th and 99th percentiles |
| `data_capture` | Fraction of valid hours |
| `exceedance_hours_200` | Hours > 200 µg/m³ (NO2) |
| `exceedance_days_50` | Days with daily mean > 50 µg/m³ (PM10) |
| `exceedance_days_120` | Days where max 8h rolling mean > 120 µg/m³ (O3) |

## Trend Analysis

Use `trend()` for non-parametric trend detection using Theil-Sen slope and Mann-Kendall significance test:

```python
# Monthly trend with deseasonalisation
result = metrics.trend(data, pollutant="NO2")

print(f"Slope: {result.slope:.2f} µg/m³/year")
print(f"Change: {result.slope_pct:.1f}%/year")
print(f"p-value: {result.p_value:.4f}")
print(f"95% CI: [{result.ci_lower:.2f}, {result.ci_upper:.2f}]")

# Seasonal aggregation
result = metrics.trend(data, pollutant="PM2.5", avg_time="season")

# Annual aggregation (no deseasonalisation)
result = metrics.trend(data, pollutant="O3", avg_time="year")

# Multi-site data returns a list
results = metrics.trend(multi_site_data, pollutant="NO2")
for r in results:
    print(f"{r.site_code}: {r.slope:.2f} ({r.p_value:.3f})")
```

Visualise the result with `plot_trend()`:

```python
from aeolus import viz

fig = viz.plot_trend(data, result)
```

## Supported AQI Systems

| Index | Country | Scale | Pollutants |
|-------|---------|-------|------------|
| UK_DAQI | UK | 1-10 | O3, NO2, SO2, PM2.5, PM10 |
| US_EPA | USA | 0-500 | O3, PM2.5, PM10, CO, SO2, NO2 |
| CHINA | China | 0-500 | PM2.5, PM10, SO2, NO2, O3, CO |
| EU_CAQI_ROADSIDE | EU | 1-6 | NO2, PM2.5, PM10 |
| EU_CAQI_BACKGROUND | EU | 1-6 | NO2, O3, PM2.5, PM10, SO2 |
| INDIA_NAQI | India | 0-500 | PM2.5, PM10, SO2, NO2, O3, CO, NH3, Pb |
| WHO | Global | - | Guidelines compliance checker |

## AQI Summary

Calculate AQI statistics over a time period.

For each `(site, period, pollutant)`, `aqi_summary` applies the index's
required rolling-average window (e.g. PM 24h, O3 8h, NO2 1h) and reports
the **worst-case AQI** within the period — matching how regulators
publish daily/period AQI values. Concentration summary statistics
(mean, median, percentiles) are computed over the raw hourly readings.

Aeolus data is always µg/m³; `aqi_summary` converts to each index's
native unit (US EPA O3/CO use ppm; SO2/NO2 use ppb; China and India
NAQI CO use mg/m³) before invoking the index's `calculate(...)`.

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
print(f"Scale: {info['scale_min']}-{info['scale_max']}")
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
