# Aeolus

*An opinionated toolkit for air quality data science.*

## Features

- Simple, clean API for downloading air quality data
- Support for multiple UK regulatory networks
- Automatic retry logic for resilient downloads
- Standardised data format (using Pandas)
- Composable data transformations
- Database storage support (SQLAlchemy/SQLModel)

## Quick Start

```python
import aeolus
from datetime import datetime

# List available data sources
sources = aeolus.list_sources()
print(sources)  # ['AQE', 'AURN', 'LMAM', 'LOCAL', 'NI', 'SAQD', 'SAQN', 'WAQN']

# Get site metadata
sites = aeolus.get_metadata("AURN")
print(f"Found {len(sites)} monitoring sites")

# Download air quality data
data = aeolus.download(
    sources="AURN",
    sites=["MY1"],  # Marylebone Road, London
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

print(f"Downloaded {len(data)} measurements")
print(data.head())
```

## Installation

To install Aeolus, run the following command in your terminal:

```bash
pip install aeolus-aq
```

Wheels and source distributions are available under Releases on Github.

## Data Sources

Currently, Aeolus supports downloading data from the following networks:

### UK Networks
- **AURN** (DEFRA's Automatic Urban and Rural Network)
- **SAQN** (Scottish Air Quality Network)
- **WAQN** (Wales Air Quality Network)
- **NI** (Northern Ireland Air Quality Network)
- **AQE** (Air Quality England)
- **LOCAL** (Local regulatory networks in England)
- **Breathe London** (requires API key: `BL_API_KEY`)

### Global Sources
- **OpenAQ** (Global air quality data platform - 100+ countries)
  - Requires free API key: `OPENAQ_API_KEY`
  - Get your key at: https://openaq.org/
  - Find location IDs at: https://explore.openaq.org/

Data from UK regulatory networks is sourced via the [OpenAir project](https://davidcarslaw.github.io/openair/) (using RData files provided by each regulatory network). My thanks to David Carslaw and all other contributors (see Carslaw & Ropkins, 2012 for further information).

Data from Breathe London is licensed under the Open Government Licence v3.0. For further information, see https://www.breathelondon.org.

## Setup

### API Keys

Some data sources require API keys:
- **OpenAQ**: Get free key at https://openaq.org/ (required for global data)
- **Breathe London**: Get key at https://www.breathelondon.org/developers (optional)

Set the API keys in your environment variables:
```bash
export OPENAQ_API_KEY=your_openaq_api_key
export BL_API_KEY=your_breathe_london_api_key
```

## Usage Examples

### Download from OpenAQ (Global Data)

```python
import aeolus
from datetime import datetime

# Download from any OpenAQ location worldwide
# Find location IDs at: https://explore.openaq.org/
data = aeolus.download(
    sources="OpenAQ",
    sites=["2178"],  # Example: a monitoring station
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Data is automatically standardized to match other sources
print(data.head())
```

### Download from Multiple Sources

```python
import aeolus
from datetime import datetime

# Download from multiple networks at once
data = aeolus.download(
    sources=["AURN", "SAQN"],
    sites=["MY1", "GLA4"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Data is automatically combined into one DataFrame
print(data['source_network'].unique())  # ['AURN', 'SAQN']

```

### Get Separate DataFrames per Source

```python
# Get data separated by source
data_by_source = aeolus.download(
    sources=["AURN", "SAQN"],
    sites=["MY1", "GLA4"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31),
    combine=False
)

# Returns a dictionary
for source, df in data_by_source.items():
    print(f"{source}: {len(df)} records")
```

### Filter and Transform Data

Aeolus provides composable transformation functions comparable to tidyverse:

```python
from aeolus.transforms import pipe, filter_rows, select_columns, sort_values

# Download and transform in one go
no2_data = pipe(
    aeolus.download("AURN", ["MY1"], start_date, end_date),
    filter_rows(lambda df: df["measurand"] == "NO2"),
    filter_rows(lambda df: df["value"].notna()),
    select_columns("site_code", "date_time", "value", "units"),
    sort_values("date_time")
)
```

### Work with Site Metadata

```python
# Get all sites for a network
sites = aeolus.get_metadata("AURN")

# Filter to urban background sites
urban_sites = sites[sites["location_type"] == "Urban Background"]

# Get site codes for download
site_codes = urban_sites["site_code"].tolist()

# Download data for those sites
data = aeolus.download("AURN", site_codes, start_date, end_date)
```

## Data Format

### Site Metadata

Metadata is returned as a pandas DataFrame with the following columns:

- `site_code`: Unique site identifier
- `site_name`: Human-readable site name
- `latitude`: Site latitude (decimal degrees)
- `longitude`: Site longitude (decimal degrees)
- `source_network`: Name of the source network
- `location_type`: Type of location (e.g., "Urban Background", "Roadside")
- `owner`: Organization operating the site

### Air Quality Data

Data is returned as a pandas DataFrame with the following columns:

- `site_code`: Site identifier
- `date_time`: Measurement timestamp
- `measurand`: Pollutant/parameter measured (e.g., "NO2", "PM2.5", "O3")
- `value`: Measured value
- `units`: Units of measurement (typically "ug/m3")
- `source_network`: Name of source network
- `ratification`: Ratification status
- `created_at`: When record was created

## Advanced Features

### Automatic Retry Logic

Aeolus automatically retries failed network requests with exponential backoff, making downloads resilient to temporary network issues.

### Composable Transformations

Build custom data processing pipelines:

```python
from aeolus.transforms import compose, filter_rows, add_column

# Create a reusable pipeline
my_pipeline = compose(
    filter_rows(lambda df: df["value"] > 0),
    add_column("year", lambda df: df["date_time"].dt.year),
    # ... more transformations
)

# Apply to any DataFrame
processed_data = my_pipeline(raw_data)
```

### Database Storage

Store data in a database (SQLite, PostgreSQL, etc.):

```python
from aeolus import add_sites_to_database, add_data_to_database

# Store site metadata
add_sites_to_database(sites, database_file="air_quality.db")

# Store measurement data
add_data_to_database(data, database_file="air_quality.db")
```

## Requirements

- Python >= 3.11
- pandas >= 2.3.3
- rdata >= 0.11
- requests >= 2.32.5
- sqlmodel >= 0.0.27
- tenacity >= 8.2.0

## Architecture

Aeolus uses a functional architecture with:

- **Type-safe interfaces**: TypedDicts and type aliases for consistency
- **Composable transformations**: Small, pure functions that combine into pipelines
- **Source registry**: Extensible system for adding new data sources
- **Automatic retries**: Network resilience built-in

For more details, see the [CHANGES.md](CHANGES.md) file.

## Contributing

Contributions are welcome! The codebase is designed to be extensible. To add a new data source:

1. Create a fetcher function following the `DataFetcher` type signature
2. Create a normalizer using the composable transforms
3. Register your source with the registry

See `src/aeolus/sources/regulatory.py` for examples.

## Licence

Aeolus is licensed under the GNU General Public License v3.0 or later. For further information, see https://www.gnu.org/licenses/gpl-3.0.en.html.

## Citation

If you use Aeolus in your research, please cite:

Carslaw, D. C. and K. Ropkins, (2012) openair --- an R package for air quality data analysis. Environmental Modelling & Software. Volume 27-28, 52-61.

(For the OpenAir project which provides the underlying data for regulatory networks)

## Contact

For any questions or feedback, please contact Ruaraidh Dobson at [ruaraidh.dobson@gmail.com](mailto:ruaraidh.dobson@gmail.com).

## Changelog

See [CHANGES.md](CHANGES.md) for version history and recent improvements.
