# aeolus

Top-level API for downloading and working with air quality data.

## Functions

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
