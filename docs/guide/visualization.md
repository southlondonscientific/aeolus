# Visualization

Aeolus includes visualization tools for publication-ready air quality plots with sensible defaults.

!!! tip "See it in action"
    - [Notebook 01](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/01_london_no2_comparison.ipynb) uses `plot_diurnal()`, `plot_weekly()`, and `plot_time_variation()` for temporal decomposition
    - [Notebook 02](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/02_pm25_compliance_report.ipynb) uses `plot_timeseries()` with guideline overlay and `plot_calendar()` heatmap
    - [Notebook 03](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/03_sensor_vs_reference.ipynb) uses `plot_timeseries()` for multi-source overlay

## Built-in Plots

The `aeolus.viz` module provides ready-made visualizations.

### Time Series

```python
from aeolus import viz

# Basic time series plot
fig = viz.plot_timeseries(data)

# With AQI bands in background (e.g., "UK_DAQI", "US_EPA")
fig = viz.plot_timeseries(data, show_bands="UK_DAQI")

# With a guideline value
fig = viz.plot_timeseries(data, guideline=40, guideline_label="WHO Annual")
```

### AQI Cards

Display large AQI values with colour-coded backgrounds:

```python
# Single AQI card
fig = viz.plot_aqi_card(value=3, category="Low")

# With custom title
fig = viz.plot_aqi_card(value=3, category="Low", title="Current AQI")

# Before/after comparison
fig = viz.plot_aqi_comparison(
    before_value=7,
    before_category="Moderate",
    after_value=3,
    after_category="Low"
)
```

### Diurnal Patterns

Show how pollution varies by hour of day:

```python
# Average diurnal pattern with confidence interval
fig = viz.plot_diurnal(data)

# Without confidence interval
fig = viz.plot_diurnal(data, show_ci=False)

# Show range instead of CI
fig = viz.plot_diurnal(data, show_range=True)
```

### Weekly Patterns

Show day-of-week variations:

```python
fig = viz.plot_weekly(data)
```

### Monthly/Seasonal Patterns

```python
fig = viz.plot_monthly(data)
```

### Calendar Heatmaps

Visualize data as a calendar (requires specifying a pollutant):

```python
fig = viz.plot_calendar(data, pollutant="NO2", year=2024)
```

### Time Variation (2x2 Panel)

The classic temporal decomposition plot, equivalent to R openair's `timeVariation`. Shows four facets: diurnal (hourly mean with CI), weekly (day-of-week bars), monthly (bars), and hour x weekday heatmap:

```python
# Standard 2x2 temporal variation
fig = viz.plot_time_variation(data, pollutant="NO2")

# Without confidence interval on diurnal panel
fig = viz.plot_time_variation(data, pollutant="PM2.5", show_ci=False)

# Custom title
fig = viz.plot_time_variation(data, pollutant="O3", title="Ozone Temporal Patterns")
```

### Trend Plot

Visualise trend analysis results: scatter of aggregated data with Theil-Sen regression line, optional CI bands, and year shading:

```python
from aeolus import metrics

# First run trend analysis
result = metrics.trend(data, pollutant="NO2")

# Then plot it
fig = viz.plot_trend(data, result)

# Without CI bands or year shading
fig = viz.plot_trend(data, result, show_ci=False, show_year_bands=False)
```

### Distribution Plots

Compare distributions across sites or time periods:

```python
# Boxplots by site
fig = viz.plot_distribution(data, pollutant="NO2", group_by="site")

# By month
fig = viz.plot_distribution(data, pollutant="NO2", group_by="month")

# Violin plots
fig = viz.plot_distribution(data, pollutant="NO2", group_by="site", style="violin")

# Available group_by options: 'site', 'month', 'weekday', 'hour', 'year'
```

## Using matplotlib Directly

All Aeolus data is in pandas DataFrames, so you can use any plotting library:

```python
import matplotlib.pyplot as plt

# Filter to one pollutant
no2 = data[data['measurand'] == 'NO2']

# Pivot for plotting
pivot = no2.pivot_table(
    index='date_time',
    columns='site_code',
    values='value'
)

# Plot
pivot.plot(figsize=(12, 4))
plt.ylabel('NO2 (µg/m³)')
plt.title('NO2 Concentrations')
plt.show()
```

## Aeolus Style

Apply the Aeolus visual style to your own matplotlib plots:

```python
from aeolus import viz

# Apply consistent styling
viz.apply_aeolus_style()

# Now your matplotlib plots will use the Aeolus palette
```

## Colour Palettes

Access the colour palettes directly:

```python
from aeolus.viz import (
    AEOLUS_6_BAND,        # Core 6-colour AQI palette
    UK_DAQI_COLOURS,      # Official UK DAQI colours
    US_EPA_COLOURS,       # Official US EPA colours
    get_colour_for_category,
    get_colour_for_value,
)

# Get colour for a category
colour = get_colour_for_category("Low", index="UK_DAQI")

# Get colour for an AQI value (1-10 for UK_DAQI)
colour = get_colour_for_value(3, index="UK_DAQI")
```

## Saving Plots

```python
fig = viz.plot_timeseries(data)
fig.savefig('timeseries.png', dpi=300, bbox_inches='tight')
```
