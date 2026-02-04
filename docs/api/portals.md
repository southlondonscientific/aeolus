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
london_sites = aeolus.portals.find_sites(
    "OPENAQ",
    bbox=(51.28, -0.51, 51.69, 0.34)
)

# Find PurpleAir sensors in an area
purpleair_sites = aeolus.portals.find_sites(
    "PURPLEAIR",
    nwlat=51.7, nwlng=-0.5,
    selat=51.3, selng=0.3
)
```

### Download Portal Data

```python
import aeolus
from datetime import datetime

# First get location IDs from find_sites
locations = aeolus.portals.find_sites("OPENAQ", country="GB")
location_ids = locations["location_id"].tolist()[:5]

# Download using location_ids parameter
data = aeolus.portals.download(
    portal="OPENAQ",
    location_ids=location_ids,
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
