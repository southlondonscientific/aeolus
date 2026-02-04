# aeolus.networks

Functions for working with discrete monitoring networks (AURN, SAQN, Breathe London, etc.).

## Functions

::: aeolus.networks.get_metadata
    options:
      show_root_heading: false

::: aeolus.networks.download
    options:
      show_root_heading: false

::: aeolus.networks.list_networks
    options:
      show_root_heading: false

## Usage Examples

### Get Network Metadata

```python
import aeolus

# Get all AURN sites
sites = aeolus.networks.get_metadata("AURN")

# View columns
print(sites.columns)
# Index(['site_code', 'site_name', 'latitude', 'longitude', 'site_type', ...])

# Filter to London sites
london = sites[sites['site_name'].str.contains('London')]
```

### Download Network Data

```python
import aeolus
from datetime import datetime

data = aeolus.networks.download(
    network="AURN",
    sites=["MY1", "KC1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

### List Available Networks

```python
networks = aeolus.networks.list_networks()
print(networks)
# ['AURN', 'SAQN', 'WAQN', 'NI', 'AQE', 'LOCAL', 'LMAM', 
#  'BREATHE_LONDON', 'AIRQO', 'AIRNOW', 'SENSOR_COMMUNITY']
```

## Supported Networks

### UK Regulatory Networks (no API key required)

| Network | Description |
|---------|-------------|
| AURN | UK Automatic Urban and Rural Network |
| SAQN | Scottish Air Quality Network |
| WAQN | Welsh Air Quality Network |
| NI | Northern Ireland Network |
| AQE | Air Quality England |
| LOCAL | Local authority networks |
| LMAM | London air quality mesh |

### Other Networks

| Network | Description | API Key |
|---------|-------------|---------|
| BREATHE_LONDON | London low-cost sensors | Yes (`BL_API_KEY`) |
| AIRQO | African cities network | Yes (`AIRQO_API_KEY`) |
| AIRNOW | US EPA real-time data | Yes (`AIRNOW_API_KEY`) |
| SENSOR_COMMUNITY | Global citizen science | No |
