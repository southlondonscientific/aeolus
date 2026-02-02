# PurpleAir

[PurpleAir](https://www.purpleair.com/) operates a global network of 30,000+ low-cost air quality sensors, popular with researchers and citizen scientists.

## Overview

- **Coverage**: Global (30,000+ sensors)
- **Sensors**: Dual-channel laser particle counters
- **Data quality**: QA/QC via channel agreement
- **API key**: Required (free tier available)
- **Operator**: PurpleAir Inc.

## Getting an API Key

1. Visit [PurpleAir Developer Portal](https://develop.purpleair.com/)
2. Create an account and register your application
3. You'll receive 1,000,000 API points for free
4. Set the environment variable:

```bash
export PURPLEAIR_API_KEY=your_key_here
```

## Available Measurements

- PM1.0, PM2.5, PM10 (particulate matter)
- Temperature
- Humidity
- Pressure

## Finding Sensors

```python
import aeolus

# Get outdoor sensors in a bounding box (London example)
sites = aeolus.portals.find_sites(
    "PURPLEAIR",
    nwlat=51.7, nwlng=-0.5,
    selat=51.3, selng=0.3,
    location_type=0  # 0 = outdoor, 1 = indoor
)

# View available sensors
print(sites[['site_code', 'site_name', 'latitude', 'longitude']])
```

## Downloading Data

```python
import aeolus
from datetime import datetime

# Download from specific sensors (use sensor indices from map.purpleair.com)
data = aeolus.download(
    sources="PURPLEAIR",
    sites=["131075", "131076"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

## QA/QC Methodology

PurpleAir sensors have two laser particle counters (Channel A and Channel B) for redundancy. Aeolus applies literature-based QA/QC thresholds:

### Concentration-Dependent Thresholds

| Concentration | Threshold Type | Agreement Required |
|--------------|----------------|-------------------|
| < 0.3 µg/m³ | Detection limit | Flagged as noise |
| 0.3-100 µg/m³ | Absolute | ±10 µg/m³ |
| 100-1000 µg/m³ | Relative | ±10% |
| > 1000 µg/m³ | Saturation | Flagged as saturated |

### Ratification Flags

- `Validated`: Both channels agree within thresholds
- `Channel Disagreement`: Both valid but disagree beyond thresholds
- `Single Channel (A)` / `Single Channel (B)`: Only one channel valid
- `Below Detection Limit`: Value below sensor noise floor
- `Sensor Saturation`: Value above sensor range

### Raw Data Access

For custom QA/QC or analysis, you can access raw channel data:

```python
from aeolus.sources.purpleair import fetch_purpleair_data

# Get raw wide-format data with both channels
raw_data = fetch_purpleair_data(
    sites=["131075"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 7),
    raw=True  # Returns pm2.5_atm_a, pm2.5_atm_b, etc.
)

# Get only validated data (exclude flagged measurements)
clean_data = fetch_purpleair_data(
    sites=["131075"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 7),
    include_flagged=False
)
```

## Example: London Air Quality

```python
import aeolus
from datetime import datetime

# Find sensors in London
sites = aeolus.portals.find_sites(
    "PURPLEAIR",
    nwlat=51.7, nwlng=-0.5,
    selat=51.3, selng=0.3,
    location_type=0
)

# Download a week of data
sensor_ids = sites['site_code'].head(5).tolist()
data = aeolus.download(
    sources="PURPLEAIR",
    sites=sensor_ids,
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 7)
)

# Check QA/QC flag distribution
print(data['ratification'].value_counts())
```

## Resources

- [PurpleAir Map](https://map.purpleair.com/) - Find sensor indices
- [PurpleAir API Documentation](https://api.purpleair.com/)
- [Developer Portal](https://develop.purpleair.com/)
- [Community Forum](https://community.purpleair.com/) - QA/QC methodology discussions
