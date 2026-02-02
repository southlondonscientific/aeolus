# Breathe London

[Breathe London](https://www.breathelondon.org/) is a dense network of low-cost air quality sensors across Greater London, providing high spatial resolution monitoring data.

## Overview

- **Coverage**: Greater London (~100+ sensors)
- **Sensor type**: Low-cost electrochemical and optical sensors
- **Data quality**: Indicative (calibrated against reference monitors)
- **API key**: Required
- **Operator**: Vodafone/Airly

## Getting an API Key

1. Visit [Breathe London Developers](https://www.breathelondon.org/developers)
2. Request API access through their portal
3. Set the environment variable:

```bash
export BL_API_KEY=your_key_here
```

## Available Pollutants

- NO2 (nitrogen dioxide)
- PM2.5 (fine particulate matter)
- PM10 (coarse particulate matter)

## Finding Sites

```python
import aeolus

# Get all Breathe London sites
sites = aeolus.networks.get_metadata("BREATHE_LONDON")

# View site locations
print(sites[['site_code', 'site_name', 'latitude', 'longitude']])
```

## Downloading Data

```python
import aeolus
from datetime import datetime

data = aeolus.download(
    sources="BREATHE_LONDON",
    sites=["BL001", "BL002"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

## Data Quality

Breathe London sensors are **indicative** rather than reference-grade:

- Calibrated using co-location with AURN reference monitors
- Subject to sensor drift and environmental interference
- Best used for spatial patterns rather than absolute values
- Data marked as `ratification='Indicative'`

### Best Practices

1. **Use for relative comparisons** - Compare between sites rather than to absolute limits
2. **Aggregate temporally** - Daily/weekly means are more reliable than hourly
3. **Cross-reference with AURN** - Validate patterns against nearby reference monitors

## Example: London Spatial Analysis

```python
import aeolus
from datetime import datetime

# Download from multiple sensors
data = aeolus.download(
    sources="BREATHE_LONDON",
    sites=["BL001", "BL002", "BL003", "BL004"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Calculate site means
site_means = data.groupby(['site_code', 'measurand'])['value'].mean()
print(site_means.unstack())
```

## Combining with AURN

For robust London analysis, combine Breathe London with AURN reference data:

```python
data = aeolus.download(
    sources={
        "BREATHE_LONDON": ["BL001", "BL002"],
        "AURN": ["MY1", "KC1"]
    },
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Compare reference vs low-cost
data.groupby(['source_network', 'measurand'])['value'].mean()
```
