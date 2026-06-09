# Aeolus vs R openair: Task-by-Task Comparison

This document maps common air quality analysis tasks between the R [openair](https://bookdown.org/david_carslaw/openair/) package and Aeolus. Where the libraries differ in scope or approach, the differences are noted plainly.

**openair** is an established R package (first released 2008) for air quality data analysis and visualisation, widely used in UK regulatory work. **Aeolus** is a Python library focused on downloading and standardising air quality data from multiple sources, with analysis and plotting functions added in v0.4.0.

The two libraries serve different primary purposes. openair assumes you already have data (typically from a single UK network) and focuses on statistical analysis and plotting. Aeolus focuses on getting data from many sources into a common format, with analysis built on top.

## Data Import

### Importing UK regulatory data

**openair:**
```r
library(openair)
data <- importUKAQ(site = "my1", year = 2024)
# or can specify the source with soruce = "aurn", source = "saqn", etc.
```

**Aeolus:**
```python
import aeolus
from datetime import datetime

data = aeolus.download("AURN", ["MY1"],
    datetime(2024, 1, 1), datetime(2024, 12, 31))

# Also: "SAQN", "WAQN", "NI", "AQE", "LAQN"
```

**Differences:** Both openair and Aeolus use a single function (`importUKAQ()` and `download()`, respectively) with the source as a parameter. As it is limited to the UK, openair automatically attempts to detect the monitoring network to which a site belongs, making `source` optional. Aeolus additionally handles non-UK sources (OpenAQ, PurpleAir, AirQo, Sensor.Community, AirNow, Breathe London). By default openair returns wide-format data (one column per pollutant); Aeolus returns long format (one row per measurement).

### Importing multiple sources

**openair:**
```r
data <- importUKAQ(
    site = c("my1", "gla4"), 
    year = 2024, 
    source = c("aurn", "saqn")
)
```

**Aeolus:**
```python
data = aeolus.download(
    {"AURN": ["MY1"], "SAQN": ["GLA4"]},
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31),
)
```

### Finding sites near a location

**openair:**
```r
# All English sites within 10 km of central London
importMeta(
    source = c("aurn", "aqe", "lmam"),
    lat = 51.5074, 
    lng = -0.1278, 
    max_dist = 10
)
```

**Aeolus:**
```python
# All free-source sites within 10 km of central London
sites = aeolus.find_sites(near=(51.5074, -0.1278), radius_km=10)

# Returns site_code, site_name, lat/lon, distance_km — sorted nearest-first
```

### Data summary

**openair:** Users typically use base R `summary()` or inspect the data frame directly.

**Aeolus:**
```python
aeolus.summarise(data)
# Returns: site_code, source_network, measurand, start, end, records, valid, data_capture
```

## Time Averaging

**openair:**
```r
# Average to daily
daily <- timeAverage(data, avg.time = "day", data.thresh = 75)

# Average to monthly
monthly <- timeAverage(data, avg.time = "month")
```

**Aeolus:**
```python
from aeolus.metrics import time_average

daily = time_average(data, freq="D", data_thresh=0.75)
monthly = time_average(data, freq="ME")
```

**Differences:** openair's `timeAverage` operates on wide-format data and uses string identifiers like `"day"`, `"month"`. Aeolus uses pandas offset aliases (`"D"`, `"ME"`, `"8h"`, etc.), which are more flexible but require familiarity with pandas conventions. Both support data capture thresholds.

## Annual Statistics

**openair:** 
```r
stats = aqStats(data)
# Returns annual mean hourly, max hourly, min hourly, median hourly, p95, p99,
# max daily mean, max 8h rolling mean, max 24h rolling mean, and certain
# UK-specific statistics
```

**Aeolus:**
```python
from aeolus.metrics import aq_stats

stats = aq_stats(data)
# Returns per site/year/pollutant: annual mean, max hourly, max daily mean,
# max 8h rolling mean, p95, p99, data capture, exceedance counts
# (NO2 hours >200, PM10 days >50, O3 days >120)
```

## Trend Analysis

**openair:**
```r
TheilSen(data, pollutant = "no2", deseason = TRUE, avg.time = "month")
# Produces plot with trend line and statistics
```

**Aeolus:**
```python
from aeolus.metrics import trend
from aeolus.viz import plot_trend

result = trend(data, pollutant="NO2", deseason=True, avg_time="month")
# result.slope, result.p_value, result.ci_lower, result.ci_upper, etc.

fig = plot_trend(data, trend_result=result)
```

**Differences:** openair's `TheilSen` combines analysis and plotting in one call. Aeolus separates them: `trend()` returns a `TrendResult` dataclass with the statistics, and `plot_trend()` handles visualisation. Both use Theil-Sen slope with Mann-Kendall significance and optional STL deseasonalisation.

## Temporal Variation Plots

### Time variation (combined panel)

**openair:**
```r
timeVariation(data, pollutant = "no2")
# Produces 4-panel plot: diurnal, day-of-week, monthly, hour×weekday heatmap
```

**Aeolus:**
```python
from aeolus.viz import plot_time_variation

fig = plot_time_variation(data, pollutant="NO2")
# Same 4-panel layout: diurnal, weekly, monthly, heatmap
```

### Individual temporal plots

**openair:**
```r
fig = variationPlot(data, "no2", x = "hour")
fig = variationPlot(data, "no2", x = "weekday")
fig = variationPlot(data, "no2", x = "month")
```

**Aeolus:**
```python
from aeolus.viz import plot_diurnal, plot_weekly, plot_monthly

fig = plot_diurnal(data, pollutants=["NO2"])
fig = plot_weekly(data, pollutants=["NO2"])
fig = plot_monthly(data, pollutants=["NO2"])
```

## Time Series Plotting

**openair:**
```r
timePlot(data, pollutant = c("no2", "pm25"))
```

**Aeolus:**
```python
from aeolus.viz import plot_timeseries

fig = plot_timeseries(data, pollutants=["NO2", "PM2.5"])
```

## Calendar Heatmap

**openair:**
```r
calendarPlot(data, pollutant = "no2", year = 2024)
```

**Aeolus:**
```python
from aeolus.viz import plot_calendar

fig = plot_calendar(data, measurand="NO2", year=2024)
```

## Air Quality Index

**openair:** No AQI calculation functions; pre-calculated UK DAQI available through `importUKAQ()`.

**Aeolus:**
```python
from aeolus.metrics import aqi_summary, aqi_check_who, list_indices

# Calculate UK DAQI
summary = aqi_summary(data, index="UK_DAQI", freq="D")

# Also: US_EPA, CHINA, EU_CAQI_ROADSIDE, EU_CAQI_BACKGROUND, INDIA_NAQI

# Check WHO guideline compliance
compliance = aqi_check_who(data, target="AQG")
```

## Near-Real-Time Data

**openair:** No built-in function.

**Aeolus:**
```python
latest = aeolus.get_current("AURN", sites=["MY1", "KC1"])
# Routes to the UK-AIR SOS API for near-real-time readings
```

## What openair Has That Aeolus Does Not

These are openair functions without an Aeolus equivalent as of v0.4.0:

| openair function | Description |
|------------------|-------------|
| `polarPlot()` | Bivariate polar plot (concentration by wind speed and direction) |
| `polarAnnulus()` | Polar annulus plot (wind direction × time of day/year) |
| `polarFreq()` | Wind frequency polar plot |
| `windRose()` | Wind rose diagram |
| `percentileRose()` | Percentile wind rose |
| `trajPlot()`, `trajCluster()` | Back-trajectory plotting and clustering (HYSPLIT) |
| `scatterPlot()` | Enhanced scatter plot with smoothing and conditioning |
| `corPlot()` | Correlation matrix plot |
| `linearRelation()` | Linear regression with conditioning |
| `selectByDate()` | Flexible date subsetting |
| `splitByDate()` | Split data at specific dates |
| `smoothTrend()` | GAM-based smooth trend |
| `conditionalEval()`, `conditionalQuantile()` | Model evaluation tools |

Most of these (especially the polar/wind plots and trajectory analysis) require wind speed and direction data, which is outside Aeolus's current scope. The plotting functions that don't require meteorological data (scatter, correlation) are straightforward to do with matplotlib/seaborn directly.

## What Aeolus Has That openair Does Not

| Aeolus feature | Description |
|----------------|-------------|
| Multi-source download | Single API for 11+ data sources across UK, US, Africa, global |
| `find_sites()` | Spatial site discovery with circular/bbox search |
| `get_current()` | Near-real-time data via SOS API |
| AQI calculation | 7 international indices (UK DAQI, US EPA, China, EU CAQI, India, WHO) |
| WHO compliance checking | Guideline and interim target compliance assessment |
| Local file caching | Automatic Parquet-based download caching |
| Progress indicators | Optional tqdm progress for bulk downloads |
| `summarise()` | Quick data overview with completeness metrics |
| Date shorthand | `last="30d"` convenience for date ranges |

## Data Format Differences

| Aspect | openair | Aeolus |
|--------|---------|--------|
| Data shape | Wide (one column per pollutant) | Long (one row per measurement) |
| Column names | Lower case (`date`, `no2`, `pm25`) | Descriptive (`date_time`, `measurand`, `value`) |
| Timestamps | POSIXct, local time or UTC | Always UTC-aware `datetime64[ns, UTC]` |
| Units | Implicit (assumed µg/m³) | Explicit `units` column |
| Site identity | `site` column | `site_code` + `source_network` columns |
| Missing data | NA in pollutant columns | Missing rows or `value=NaN` |

The long format used by Aeolus is more verbose but handles multi-source, multi-pollutant data without column name conflicts. Converting between formats is straightforward with pandas `pivot`/`melt`.
