# EEA (European Environment Agency)

The [European Environment Agency](https://www.eea.europa.eu/) aggregates regulatory air quality data reported by EU member states and cooperating countries under the Air Quality Directive. Hourly data is available from 2013 onwards across 40+ countries and 7,000+ stations.

## Overview

- **Coverage**: 40+ European countries, 7,000+ stations
- **Data quality**: Reference (national regulatory networks, pooled by EEA)
- **Ratification**: `Verified` (verified by EEA or member state) or `Provisional` (not yet verified)
- **API key**: Not required
- **History**: 2013+ (hourly)
- **Operator**: European Environment Agency

## No API Key Required

The EEA Air Quality Download Service is fully open. No registration or API key is needed.

## Quick Start

```python
import aeolus
from datetime import datetime

# Find EEA stations within 20 km of Paris
sites = aeolus.find_sites(
    "EEA",
    near=(48.8566, 2.3522),
    radius_km=20,
)

# Download NO2 and PM2.5 for January 2024
data = aeolus.download(
    "EEA",
    sites=sites["site_code"].head(5).tolist(),
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31),
)
```

## Finding Stations

```python
# By bounding box
sites = aeolus.find_sites(
    "EEA",
    bbox=(-10, 35, 30, 60),  # (min_lon, min_lat, max_lon, max_lat) - Europe
)

# By country (via metadata filter)
sites = aeolus.networks.get_metadata("EEA")
germany = sites[sites["country"] == "DE"]
```

## Data Quality

Each row is labelled with a `ratification` value derived from the EEA `Verification` field:

| EEA field value | `ratification` |
|-----------------|----------------|
| 1 (Not yet verified) | `Provisional` |
| 2 (Verified by EEA) | `Verified` |
| 3 (Verified by member state) | `Verified` |

For recent months, expect mostly `Provisional` data; for previous calendar years, most data is `Verified`.

## Notes

- **No real-time**: `get_current()` is not supported for EEA — the download API is not near-real-time. Use national sources (AURN, etc.) for live readings.
- **Dataset variant**: Aeolus uses the E1a ("Verified") dataset for the broadest coverage of recent data.
- **Samplingpoint mapping**: EEA `Samplingpoint` identifiers follow different conventions per country. Aeolus uses the EEA's own metadata CSV to map these to EoI station codes authoritatively.

## Resources

- [EEA Air Quality Download Service](https://eeadmz1-downloads-webapp.azurewebsites.net/)
- [EEA Air Quality Statistics Viewer](https://discomap.eea.europa.eu/App/AQViewer/)
- [Air Quality Directive](https://environment.ec.europa.eu/topics/air/air-quality/eu-air-quality-standards_en)
