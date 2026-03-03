# aeolus

Top-level API for downloading and working with air quality data.

## Functions

::: aeolus.find_sites
    options:
      show_root_heading: false

::: aeolus.list_sources
    options:
      show_root_heading: false

::: aeolus.get_source_info
    options:
      show_root_heading: false

::: aeolus.download
    options:
      show_root_heading: false

::: aeolus.fetch
    options:
      show_root_heading: false

## Usage Examples

### Find Nearby Sites

```python
import aeolus

# Find AURN sites within 20 km of central London
sites = aeolus.find_sites("AURN", near=(51.5074, -0.1278), radius_km=20)
print(sites[["site_code", "site_name", "distance_km"]])
```

### Find Sites in a Bounding Box

```python
# Find sites from any free source within a bounding box
sites = aeolus.find_sites(bbox=(-0.5, 51.3, 0.3, 51.7))

# Or specify sources explicitly
sites = aeolus.find_sites(["AURN", "SAQN"], bbox=(-0.5, 51.3, 0.3, 51.7))
```

### Find Sites Then Download

```python
import aeolus
from datetime import datetime

# Discover nearby sites
sites = aeolus.find_sites("AURN", near=(51.5074, -0.1278), radius_km=10)

# Download data from the nearest sites
data = aeolus.download(
    "AURN",
    sites=sites["site_code"].tolist(),
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

### List Available Sources

```python
import aeolus

sources = aeolus.list_sources()
print(sources)
# Networks: AURN, SAQN, WAQN, NI, AQE, LOCAL, LMAM, BREATHE_LONDON, AIRQO, AIRNOW, SENSOR_COMMUNITY
# Portals: OPENAQ, PURPLEAIR
```

### Download from Single Source

```python
import aeolus
from datetime import datetime

data = aeolus.download(
    sources="AURN",
    sites=["MY1", "KC1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

### Download from Multiple Sources

```python
import aeolus
from datetime import datetime

data = aeolus.download(
    sources={
        "AURN": ["MY1"],
        "SAQN": ["ED3"]
    },
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

### Filter by Pollutant

Filter the data after downloading:

```python
import aeolus
from datetime import datetime

data = aeolus.download(
    sources="AURN",
    sites=["MY1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Filter to specific pollutants
data = data[data['measurand'].isin(['NO2', 'PM2.5'])]
```
