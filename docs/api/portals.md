# aeolus.portals

Functions for working with global data portals (OpenAQ, PurpleAir).

## Functions

::: aeolus.portals.find_sites
    options:
      show_root_heading: false

::: aeolus.portals.download
    options:
      show_root_heading: false

::: aeolus.portals.list_portals
    options:
      show_root_heading: false

## Usage Examples

### Find Sites

```python
import aeolus

# Find OpenAQ sites in a country
uk_sites = aeolus.portals.find_sites("OPENAQ", country="GB")

# Find sites within a bounding box
# bbox format: (min_lon, min_lat, max_lon, max_lat) - same as GeoJSON/shapely
london_sites = aeolus.portals.find_sites(
    "OPENAQ",
    bbox=(-0.51, 51.28, 0.34, 51.69)
)

# Find PurpleAir sensors in an area (using standard bbox format)
purpleair_sites = aeolus.portals.find_sites(
    "PURPLEAIR",
    bbox=(-0.5, 51.3, 0.3, 51.7)
)
```

### Download Portal Data

```python
import aeolus
from datetime import datetime

# First get site codes from find_sites
locations = aeolus.portals.find_sites("OPENAQ", country="GB")
site_codes = locations["site_code"].tolist()[:5]

# Download using sites parameter (consistent with networks API)
data = aeolus.portals.download(
    portal="OPENAQ",
    sites=site_codes,
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

### List Available Portals

```python
portals = aeolus.portals.list_portals()
print(portals)
# ['OPENAQ', 'PURPLEAIR']
```

## Supported Portals

| Portal | Description | API Key |
|--------|-------------|---------|
| OPENAQ | Global air quality data platform | Yes (`OPENAQ_API_KEY`) |
| PURPLEAIR | Global low-cost sensor network (30,000+) | Yes (`PURPLEAIR_API_KEY`) |
