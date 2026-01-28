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
# ['AURN', 'SAQN', 'WAQN', 'NI', 'BREATHE_LONDON', 'AIRQO']
```

## Supported Networks

| Network | Description | API Key |
|---------|-------------|---------|
| AURN | UK Automatic Urban and Rural Network | No |
| SAQN | Scottish Air Quality Network | No |
| WAQN | Welsh Air Quality Network | No |
| NI | Northern Ireland Network | No |
| BREATHE_LONDON | London low-cost sensors | Yes |
| AIRQO | African cities network | Yes |
