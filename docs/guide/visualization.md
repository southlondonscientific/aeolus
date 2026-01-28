# Visualization

Aeolus includes visualization tools for publication-ready air quality plots with sensible defaults.

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

# Get colour for a numeric value
colour = get_colour_for_value(45, pollutant="NO2", index="UK_DAQI")
```

## Saving Plots

```python
fig = viz.plot_timeseries(data)
fig.savefig('timeseries.png', dpi=300, bbox_inches='tight')
```
