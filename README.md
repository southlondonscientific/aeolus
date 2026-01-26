# Aeolus

*An opinionated Python toolkit for air quality data analysis.*

Aeolus provides a simple, unified, opinionated workflow for downloading and working with air quality data from multiple sources.

Aeolus distinguishes between two types of data source:

- **Networks** are discrete monitoring networks with a known set of sites (e.g. the UK's AURN/SAQN or Breathe London). You can list all sites and download data directly.
- **Portals** are global data aggregators (e.g. OpenAQ). With hundreds of thousands of sites worldwide, you search first, then download.

## Installation

```bash
pip install aeolus-aq
```

Requires Python 3.11 or later.

## Quick Start

```python
import aeolus
from datetime import datetime

# Download data from the UK's national network
data = aeolus.download(
    "AURN",
    sites=["MY1", "KC1"],  # Marylebone Road, North Kensington
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 3, 31)
)

print(data.head())
```

```
   site_code           date_time measurand  value  units source_network
0       MY1 2024-01-01 00:00:00       NO2   42.3  ug/m3           AURN
1       MY1 2024-01-01 00:00:00     PM2.5   18.7  ug/m3           AURN
2       MY1 2024-01-01 00:00:00      PM10   24.1  ug/m3           AURN
...
```

## Data Sources

### UK Regulatory Networks

These networks provide quality-assured data from reference-grade monitors operated by UK government bodies:

| Network | Description | Coverage |
|---------|-------------|----------|
| **AURN** | Automatic Urban and Rural Network | England, Wales, Scotland, N. Ireland |
| **SAQN** | Scottish Air Quality Network | Scotland |
| **WAQN** | Welsh Air Quality Network | Wales |
| **NI** | Northern Ireland Network | Northern Ireland |
| **AQE** | Air Quality England | England (local authorities) |
| **LOCAL** | Local authority networks | England |

```python
# Get metadata for all AURN sites
sites = aeolus.networks.get_metadata("AURN")

# Download from multiple UK networks
data = aeolus.download(
    {
        "AURN": ["MY1", "KC1"],
        "SAQN": ["GLA4", "ED3"]
    },
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

### Breathe London

High-density sensor network across London, operated by Imperial College London's Environmental Research Group.

```python
# Get Breathe London site metadata
sites = aeolus.networks.get_metadata("BREATHE_LONDON")

# Download data
data = aeolus.download(
    "BREATHE_LONDON",
    sites=["BL0001", "BL0002"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

**Requires API key:** Set `BL_API_KEY` in your environment. Get a free key at [breathelondon.org/developers](https://www.breathelondon.org/developers).

### OpenAQ

Global air quality portal aggregating measurements from 100+ countries.

```python
# Search for monitoring locations
locations = aeolus.portals.find_sites(
    "OpenAQ",
    country="GB",
    parameter="pm25"
)

# Download data using location IDs
data = aeolus.download(
    "OpenAQ",
    sites=locations["location_id"].head(5).tolist(),
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

**Requires API key:** Set `OPENAQ_API_KEY` in your environment. Get a free key at [openaq.org](https://openaq.org/).

## Working with the Data

### Standardised Format

All data sources return pandas DataFrames with a consistent schema:

| Column | Description |
|--------|-------------|
| `site_code` | Unique site identifier |
| `date_time` | Measurement timestamp |
| `measurand` | Pollutant (NO2, PM2.5, PM10, O3, etc.) |
| `value` | Measured concentration |
| `units` | Units (typically µg/m³) |
| `source_network` | Data source |

### Data Transformations

Aeolus includes composable transformation functions for data processing:

```python
from aeolus.transforms import pipe, filter_rows, select_columns

# Filter to NO2 measurements above 40 µg/m³
exceedances = pipe(
    data,
    filter_rows(lambda df: df["measurand"] == "NO2"),
    filter_rows(lambda df: df["value"] > 40),
    select_columns("site_code", "date_time", "value")
)
```

### Combining Sources

Download from multiple sources in a single call:

```python
data = aeolus.download(
    {
        "AURN": ["MY1"],
        "BREATHE_LONDON": ["BL0001"],
        "OpenAQ": ["2178"]
    },
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# All data in one DataFrame with source_network column
data.groupby("source_network").size()
```

## Configuration

### Environment Variables

Create a `.env` file or set these in your environment:

```bash
# Required for OpenAQ
OPENAQ_API_KEY=your_key_here

# Required for Breathe London
BL_API_KEY=your_key_here
```

### Using with dotenv

```python
from dotenv import load_dotenv
load_dotenv()

import aeolus
# API keys are now available
```

## API Reference

### Top-Level Functions

```python
# Download data (smart routing to appropriate source)
aeolus.download(source, sites, start_date, end_date)

# List all available sources
aeolus.list_sources()

# Get information about a source
aeolus.get_source_info("AURN")
```

### Networks (UK regulatory, Breathe London)

```python
# List available networks
aeolus.networks.list_networks()

# Get site metadata
aeolus.networks.get_metadata("AURN")

# Download data
aeolus.networks.download("AURN", ["MY1"], start_date, end_date)
```

### Portals (OpenAQ)

```python
# List available portals  
aeolus.portals.list_portals()

# Search for monitoring locations (filters required)
aeolus.portals.find_sites("OpenAQ", country="GB")
aeolus.portals.find_sites("OpenAQ", coordinates=(51.5, -0.1), radius=10000)

# Download data
aeolus.portals.download("OpenAQ", location_ids, start_date, end_date)
```

## Examples

### Annual Statistics for a Site

```python
import aeolus
import pandas as pd
from datetime import datetime

# Download a full year of data
data = aeolus.download(
    "AURN",
    sites=["MY1"],
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31)
)

# Calculate annual means by pollutant
annual_means = (
    data
    .groupby("measurand")["value"]
    .mean()
    .round(1)
)
print(annual_means)
```

### Compare Sites Across Networks

```python
# Download from multiple networks
data = aeolus.download(
    {
        "AURN": ["MY1", "KC1"],
        "SAQN": ["GLA4"]
    },
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 6, 30)
)

# Monthly NO2 by site
monthly = (
    data[data["measurand"] == "NO2"]
    .set_index("date_time")
    .groupby(["site_code", pd.Grouper(freq="M")])["value"]
    .mean()
    .unstack(level=0)
)
```

### Export to CSV

```python
data = aeolus.download("AURN", ["MY1"], start_date, end_date)
data.to_csv("marylebone_road_2024.csv", index=False)
```

## Acknowledgements

Aeolus wouldn't be possible without the work of many organisations and individuals:

**Data Providers**
- [OpenAQ](https://openaq.org/) — For building an open, global air quality data portal and API
- [Breathe London](https://www.breathelondon.org/) — Imperial College London's Environmental Research Group, for high-density monitoring data across London (Open Government Licence v3.0)
- UK regulatory bodies (DEFRA, SEPA, Natural Resources Wales, DAERA) — For maintaining reference-grade monitoring networks

**Software**
- [openair](https://davidcarslaw.github.io/openair/) — David Carslaw and Karl Ropkins' R package, which provides the data files for UK regulatory networks. If you use Aeolus with UK data, please cite: Carslaw, D.C. and K. Ropkins (2012) openair — an R package for air quality data analysis. *Environmental Modelling & Software* 27-28, 52-61.

## Contributing

Contributions are welcome. The codebase is designed to be extensible — see `src/aeolus/sources/` for examples of how data sources are implemented.

## Licence

GNU General Public License v3.0 or later. See [LICENCE](LICENCE) for details.

## Contact

Ruaraidh Dobson — [ruaraidh.dobson@gmail.com](mailto:ruaraidh.dobson@gmail.com)

Issues and feature requests: [GitHub Issues](https://github.com/southlondonscientific/aeolus/issues)
