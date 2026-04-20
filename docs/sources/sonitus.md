# Sonitus (Smart Dublin)

The [Sonitus](https://data.smartdublin.ie/dataset/sonitus) network is Dublin City Council's air quality and noise monitoring network, accessed via the Smart Dublin open data portal. Aeolus exposes the air quality monitors only (noise monitors are excluded).

## Overview

- **Coverage**: Dublin, Ireland
- **Data quality**: Indicative (low-cost multi-parameter sensors) plus a small number of reference-grade national monitors co-managed with EPA Ireland
- **Resolution**: 15-minute
- **API key**: Not required (uses public credentials from the Smart Dublin data portal)
- **Pollutants**: NO2, SO2, CO, NO, O3, PM1, PM2.5, PM10, TSP

## No API Key Required

The Sonitus API uses public credentials published on the Smart Dublin data portal. These are bundled with Aeolus; no user action is required.

## Quick Start

```python
import aeolus
from datetime import datetime

# List Sonitus monitors
sites = aeolus.networks.get_metadata("SONITUS")

# Download a week of data
data = aeolus.download(
    "SONITUS",
    sites=sites["site_code"].head(3).tolist(),
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 7),
)
```

## Finding Sites

```python
# All Sonitus monitors
sites = aeolus.networks.get_metadata("SONITUS")

# Spatial filter via find_sites()
near_centre = aeolus.find_sites(
    "SONITUS",
    near=(53.3498, -6.2603),  # Dublin city centre
    radius_km=5,
)
```

## Notes

- **15-minute resolution**: Data is reported at 15-minute intervals rather than hourly.
- **Negative values**: Uncalibrated sensors occasionally produce small negative values. Aeolus passes these through as-is — filter downstream if needed for your analysis.
- **Column variability**: Available pollutants vary by monitor type (gas vs particulate).

## Resources

- [Sonitus Dataset on Smart Dublin](https://data.smartdublin.ie/dataset/sonitus)
- [Sonitus API](https://data.smartdublin.ie/sonitus-api/api/)
- [Dublin City Council Air Quality](https://www.dublincity.ie/residential/environment/air-quality-monitoring-and-noise-control)
