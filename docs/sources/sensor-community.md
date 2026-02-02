# Sensor.Community

[Sensor.Community](https://sensor.community/) (formerly luftdaten.info) is a global citizen science project for air quality monitoring with 35,000+ sensors worldwide.

## Overview

- **Coverage**: Global (35,000+ sensors)
- **Sensors**: SDS011, PMS series, BME280, and others
- **Data quality**: Unvalidated (citizen science)
- **API key**: Not required
- **Operator**: Community-run (originated in Stuttgart, Germany)

## No API Key Required

Sensor.Community data is completely open. No registration or API key needed.

## Available Measurements

Depending on sensor type:

- **PM sensors** (SDS011, PMS series): PM2.5, PM10
- **Environmental sensors** (BME280, DHT22): Temperature, Humidity, Pressure

## Quick Start

```python
import aeolus
from datetime import datetime

# Get available sensors in the UK
metadata = aeolus.networks.get_metadata(
    "SENSOR_COMMUNITY",
    sensor_type="SDS011",
    country="GB"
)

# Pick some sensors
sites = metadata["site_code"].head(5).tolist()

# Download data - same interface as all other sources
data = aeolus.download(
    "SENSOR_COMMUNITY",
    sites,
    datetime(2024, 1, 1),
    datetime(2024, 1, 7)
)
```

## Finding Sensors

```python
import aeolus

# Get sensors by country
uk_sensors = aeolus.networks.get_metadata(
    "SENSOR_COMMUNITY",
    sensor_type="SDS011",
    country="GB"
)

# Get sensors in a geographic area (50km radius around London)
london_sensors = aeolus.networks.get_metadata(
    "SENSOR_COMMUNITY",
    area=(51.5074, -0.1278, 50),  # lat, lon, radius_km
    sensor_type="SDS011"
)

# Get sensors in a bounding box
sensors = aeolus.networks.get_metadata(
    "SENSOR_COMMUNITY",
    box=(51.3, -0.5, 51.7, 0.3),  # lat1, lon1, lat2, lon2
    sensor_type="SDS011"
)
```

## Downloading Data

### Historical Data

Use the standard `aeolus.download()` interface:

```python
import aeolus
from datetime import datetime

# Get metadata first
metadata = aeolus.networks.get_metadata(
    "SENSOR_COMMUNITY",
    sensor_type="SDS011",
    country="GB"
)

# Pick sensors and download
sites = metadata["site_code"].head(3).tolist()
data = aeolus.download(
    "SENSOR_COMMUNITY",
    sites,
    datetime(2024, 1, 1),
    datetime(2024, 1, 7)
)
```

Historical data is available from the daily archive (from 2015 onwards).

### Real-Time Data

For real-time monitoring, use the dedicated function:

```python
from aeolus.sources.sensor_community import fetch_sensor_community_realtime

# Get current data from UK PM sensors
data = fetch_sensor_community_realtime(
    sensor_type="SDS011",
    country="GB",
    averaging="5min"  # Options: "5min", "1h", "24h"
)
```

## Rate Limiting

Aeolus includes built-in rate limiting to be respectful of the community-run infrastructure:

- **Default**: 10 requests per minute, 1 second minimum between requests
- **Configurable**: Adjust as needed

```python
from aeolus.sources.sensor_community import set_rate_limiting

# More conservative rate limiting
set_rate_limiting(max_requests=5, period=60, min_delay=2.0)

# Disable rate limiting (not recommended)
set_rate_limiting(enabled=False)
```

## Data Quality

Data is marked as `ratification='Unvalidated'` because:

- Sensors are installed and maintained by citizens
- No formal calibration or QA/QC process
- Sensor placement varies widely
- Best used for understanding spatial patterns and trends

## Supported Sensor Types

### PM Sensors
| Type | Measurements |
|------|--------------|
| SDS011 | PM2.5, PM10 |
| SDS021 | PM2.5, PM10 |
| PMS1003/3003/5003/6003/7003 | PM1, PM2.5, PM10 |
| HPM | PM2.5, PM10 |
| SPS30 | PM1, PM2.5, PM4, PM10 |

### Environmental Sensors
| Type | Measurements |
|------|--------------|
| BME280 | Temperature, Humidity, Pressure |
| BMP280 | Temperature, Pressure |
| DHT22 | Temperature, Humidity |
| SHT31 | Temperature, Humidity |

## Example: UK Air Quality Snapshot

```python
from aeolus.sources.sensor_community import (
    fetch_sensor_community_realtime,
    set_rate_limiting
)

# Use conservative rate limiting
set_rate_limiting(max_requests=10, period=60, min_delay=1.0)

# Get current UK data
data = fetch_sensor_community_realtime(
    sensor_type="SDS011",
    country="GB"
)

# Basic statistics
pm25 = data[data['measurand'] == 'PM2.5']['value']
print(f"UK PM2.5 - Mean: {pm25.mean():.1f}, Max: {pm25.max():.1f} µg/m³")
print(f"Active sensors: {data['site_code'].nunique()}")
```

## Resources

- [Sensor.Community Website](https://sensor.community/)
- [Live Map](https://maps.sensor.community/)
- [Data Archive](https://archive.sensor.community/) - Historical CSV files
- [API Documentation](https://github.com/opendata-stuttgart/meta/wiki/EN-APIs)
- [Forum](https://forum.sensor.community/)
