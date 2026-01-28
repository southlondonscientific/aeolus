# aeolus.portals

Functions for working with global data portals (OpenAQ, etc.).

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

# Find sites in a country
uk_sites = aeolus.portals.find_sites("OpenAQ", country="GB")

# Find sites within a bounding box (min_lat, min_lon, max_lat, max_lon)
london_sites = aeolus.portals.find_sites(
    "OpenAQ",
    bbox=(51.28, -0.51, 51.69, 0.34)
)

# Find sites by city
city_sites = aeolus.portals.find_sites("OpenAQ", city="London")
```

### Download Portal Data

```python
import aeolus
from datetime import datetime

# First get location IDs from find_sites
locations = aeolus.portals.find_sites("OpenAQ", country="GB")
location_ids = locations["location_id"].tolist()[:5]

# Download using location_ids parameter
data = aeolus.portals.download(
    portal="OpenAQ",
    location_ids=location_ids,
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

### List Available Portals

```python
portals = aeolus.portals.list_portals()
print(portals)
# ['OpenAQ']
```

## Supported Portals

| Portal | Description | API Key |
|--------|-------------|---------|
| OpenAQ | Global air quality data platform | Yes |
