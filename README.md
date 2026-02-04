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
| **LMAM** | London air quality mesh | Greater London |

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

### AirQo (Africa)

Air quality monitoring network focused on African cities, operated by Makerere University. Provides PM2.5 and PM10 data from 200+ low-cost sensors across 16+ cities.

```python
# Get AirQo site metadata
sites = aeolus.networks.get_metadata("AIRQO")

# Filter to a specific country
uganda_sites = sites[sites["country"] == "Uganda"]

# Download data
data = aeolus.download(
    "AIRQO",
    sites=uganda_sites["site_code"].head(5).tolist(),
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

**Requires API key:** Set `AIRQO_API_KEY` in your environment. Get a free key at [analytics.airqo.net](https://analytics.airqo.net/).

### Sensor.Community (Global)

Global citizen science network (formerly luftdaten.info) with 35,000+ low-cost sensors worldwide. Provides PM2.5, PM10, temperature, humidity, and pressure data. No API key required.

```python
# Find sensors in a geographic area
from aeolus.sources.sensor_community import fetch_sensor_community_metadata

sites = fetch_sensor_community_metadata(
    area=(51.5074, -0.1278, 50)  # lat, lon, radius_km
)

# Download data using the standard interface
data = aeolus.download(
    "SENSOR_COMMUNITY",
    sites=sites["site_code"].head(5).tolist(),
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 7)
)
```

**Rate limiting:** Aeolus includes built-in rate limiting (10 requests/minute by default) to be respectful of the community-run infrastructure. You can configure this:

```python
from aeolus.sources.sensor_community import set_rate_limiting

# Adjust rate limits
set_rate_limiting(max_requests=5, period=60, min_delay=2.0)

# Disable (not recommended)
set_rate_limiting(enabled=False)
```

**Note:** Data is marked as `Unvalidated` since this is citizen science data without formal QA/QC processes.

### EPA AirNow (USA)

Real-time air quality data from the US EPA's AirNow system, covering the United States, Canada, and parts of Mexico. Provides O3, PM2.5, PM10, NO2, SO2, and CO data from thousands of monitoring stations.

```python
# Get current air quality at a location
from aeolus.sources.airnow import fetch_airnow_current

current = fetch_airnow_current(
    latitude=34.05,
    longitude=-118.24,
    distance=25  # miles
)

# Find monitoring sites in a bounding box
# bbox format: (min_lon, min_lat, max_lon, max_lat) - same as GeoJSON/shapely
sites = aeolus.networks.get_metadata(
    "AIRNOW",
    bbox=(-118.5, 33.7, -117.5, 34.3)  # LA area
)

# Download historical data (up to ~45 days)
data = aeolus.download(
    "AIRNOW",
    sites=sites["site_code"].head(3).tolist(),
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 7)
)
```

**Requires API key:** Set `AIRNOW_API_KEY` in your environment. Get a free key at [docs.airnowapi.org](https://docs.airnowapi.org/account/request/).

**Note:** AirNow provides provisional (real-time) data with approximately 45 days of history. For verified historical data going back years, use EPA AQS (via pyaqsapi or OpenAQ).

### OpenAQ

Global air quality portal aggregating measurements from 100+ countries.

```python
# Search for monitoring locations
locations = aeolus.portals.find_sites("OPENAQ", country="GB")

# Download data using site codes
site_codes = locations["site_code"].head(5).tolist()
data = aeolus.portals.download(
    "OPENAQ",
    sites=site_codes,
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

**Requires API key:** Set `OPENAQ_API_KEY` in your environment. Get a free key at [openaq.org](https://openaq.org/).

### PurpleAir (Global)

Global network of 30,000+ low-cost air quality sensors, popular with researchers and citizen scientists. PurpleAir sensors use dual laser counters for improved accuracy and measure PM1, PM2.5, PM10, temperature, humidity, and pressure.

```python
# Search for PurpleAir sensors in a bounding box (e.g., London)
# bbox format: (min_lon, min_lat, max_lon, max_lat) - same as GeoJSON/shapely
sites = aeolus.portals.find_sites(
    "PURPLEAIR",
    bbox=(-0.5, 51.3, 0.3, 51.7),
    location_type=0  # 0 = outdoor only
)

# Download data from specific sensors
data = aeolus.portals.download(
    "PURPLEAIR",
    sites=["131075", "131076"],  # Sensor indices from map.purpleair.com
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

**Requires API key:** Set `PURPLEAIR_API_KEY` in your environment. Get a free key (includes 1M API points) at [develop.purpleair.com](https://develop.purpleair.com/).

**Note:** PurpleAir sensors have dual laser counters (A and B channels). Aeolus automatically applies literature-based QA/QC and flags data quality:
- `Validated`: Both channels agree (±10 µg/m³ for low concentrations, ±10% for high)
- `Channel Disagreement`: Both channels valid but disagree beyond thresholds
- `Single Channel (A/B)`: Only one channel had valid data
- `Below Detection Limit`: Value below 0.3 µg/m³ (sensor noise floor)
- `Sensor Saturation`: Value above 1000 µg/m³

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
        "OPENAQ": ["2178"]
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

# Required for AirQo
AIRQO_API_KEY=your_key_here

# Required for PurpleAir
PURPLEAIR_API_KEY=your_key_here

# Required for EPA AirNow
AIRNOW_API_KEY=your_key_here
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
aeolus.download(sources, sites, start_date, end_date)

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

### Portals (OpenAQ, PurpleAir)

```python
# List available portals  
aeolus.portals.list_portals()

# Search for monitoring locations (filters required)
aeolus.portals.find_sites("OPENAQ", country="GB")
aeolus.portals.find_sites("OPENAQ", city="London")
# bbox format: (min_lon, min_lat, max_lon, max_lat)
aeolus.portals.find_sites("PURPLEAIR", bbox=(-0.5, 51.3, 0.3, 51.7))

# Download data
aeolus.portals.download("OPENAQ", sites, start_date, end_date)
aeolus.portals.download("PURPLEAIR", sites, start_date, end_date)
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

## Air Quality Indices

Aeolus includes a comprehensive `metrics` module for calculating air quality indices from downloaded data.

### Supported Indices

| Index | Country/Region | Scale | Description |
|-------|----------------|-------|-------------|
| **UK_DAQI** | UK | 1-10 | Daily Air Quality Index |
| **US_EPA** | USA | 0-500 | EPA AQI with NowCast |
| **CHINA** | China | 0-500 | China AQI |
| **WHO** | Global | Pass/Fail | WHO 2021 Guidelines |
| **EU_CAQI_ROADSIDE** | EU | 1-6 | European AQI (traffic) |
| **EU_CAQI_BACKGROUND** | EU | 1-6 | European AQI (background) |
| **INDIA_NAQI** | India | 0-500 | National AQI |

### Quick Example

```python
import aeolus
from aeolus import metrics
from datetime import datetime

# Download data
data = aeolus.download(
    "AURN", 
    sites=["MY1"], 
    start_date=datetime(2024, 1, 1), 
    end_date=datetime(2024, 12, 31)
)

# Calculate UK DAQI summary
summary = metrics.aqi_summary(data, index="UK_DAQI")
print(summary)

# Monthly breakdown
monthly = metrics.aqi_summary(data, index="UK_DAQI", freq="M")

# Check WHO guideline compliance
compliance = metrics.aqi_check_who(data)
print(compliance[["pollutant", "meets_guideline", "exceedance_ratio"]])
```

### Summary Options

```python
# Get overall AQI only (no per-pollutant breakdown)
simple = metrics.aqi_summary(data, index="UK_DAQI", overall_only=True)

# Wide format output (one row per period)
wide = metrics.aqi_summary(data, index="UK_DAQI", freq="M", format="wide")

# Different aggregation frequencies
daily = metrics.aqi_summary(data, index="UK_DAQI", freq="D")
weekly = metrics.aqi_summary(data, index="UK_DAQI", freq="W")
monthly = metrics.aqi_summary(data, index="UK_DAQI", freq="M")
yearly = metrics.aqi_summary(data, index="UK_DAQI", freq="Y")
```

### WHO Guidelines

The WHO module checks compliance against the 2021 Air Quality Guidelines and interim targets:

```python
from aeolus import metrics

# Check against the AQG (strictest target)
compliance = metrics.aqi_check_who(data, target="AQG")

# Check against interim targets for progressive improvement
it1 = metrics.aqi_check_who(data, target="IT-1")  # Least strict
it4 = metrics.aqi_check_who(data, target="IT-4")  # More strict
```

### Unit Conversion

The metrics module automatically converts units where needed (e.g., ppb to µg/m³) and warns you when conversions are applied.

## Acknowledgements

Aeolus wouldn't be possible without the work of many organisations and individuals. See [REFERENCES.md](REFERENCES.md) for full citations and methodology sources.

**Code Contributors**
- Dr Ruaraidh Dobson — Project creator, architecture, documentation
- Claude (Anthropic) — Code implementation, including data source integrations, AQI calculations, QA/QC methodology, and test suites

**Data Providers**
- [OpenAQ](https://openaq.org/) — Open, global air quality data portal and API
- [Breathe London](https://www.breathelondon.org/) — Imperial College London's Environmental Research Group (Open Government Licence v3.0)
- [AirQo](https://airqo.net/) — Makerere University's air quality monitoring network for African cities
- [PurpleAir](https://www.purpleair.com/) — Global network of low-cost sensors
- [Sensor.Community](https://sensor.community/) — Global citizen science sensor network (formerly luftdaten.info)
- [EPA AirNow](https://www.airnow.gov/) — US Environmental Protection Agency real-time air quality data
- UK regulatory bodies (DEFRA, SEPA, Natural Resources Wales, DAERA) — Reference-grade monitoring networks

**Standards and Methodologies**
- US EPA — Air Quality Index and NowCast algorithm
- DEFRA/COMEAP — UK Daily Air Quality Index
- WHO — 2021 Air Quality Guidelines
- CITEAIR Project — EU Common Air Quality Index
- CPCB India — National Air Quality Index
- China MEE — HJ 633-2012 AQI Standard
- PurpleAir Community — QA/QC methodology for dual-channel sensors

**Software**
- [openair](https://davidcarslaw.github.io/openair/) — David Carslaw and Karl Ropkins' R package, which provides the data files for UK regulatory networks. If you use Aeolus with UK data, please cite: Carslaw, D.C. and K. Ropkins (2012) openair — an R package for air quality data analysis. *Environmental Modelling & Software* 27-28, 52-61.
- [purpleair-api](https://github.com/carlkidcrypto/purpleair_api) — Carlos Santos' Python wrapper for the PurpleAir API

## Contributing

Contributions are welcome. The codebase is designed to be extensible — see `src/aeolus/sources/` for examples of how data sources are implemented.

## Licence

GNU General Public License v3.0 or later. See [LICENCE](LICENCE) for details.

## Contact

Ruaraidh Dobson — [ruaraidh.dobson@gmail.com](mailto:ruaraidh.dobson@gmail.com)

Issues and feature requests: [GitHub Issues](https://github.com/southlondonscientific/aeolus/issues)
