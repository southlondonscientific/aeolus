# Aeolus - Claude Code Context

Air quality data downloading and standardization library for UK and international monitoring networks.

**Current Version:** 0.3.0

## Quick Start

```bash
# Activate virtual environment
source .venv/bin/activate

# Run tests
pytest

# Run a specific test file
pytest tests/test_airqo.py -v
```

## Environment Setup

**Always activate the virtual environment before working:**
```bash
source .venv/bin/activate
```

**Environment variables** are in `.env` (copy from `.env.example`):
- `OPENAQ_API_KEY` - Required for OpenAQ data
- `BL_API_KEY` - Required for Breathe London data
- `AIRQO_API_KEY` - Required for AirQo data
- `PURPLEAIR_API_KEY` - Required for PurpleAir data
- `AIRNOW_API_KEY` - Required for EPA AirNow data
- AURN, SAQN, and Sensor.Community do not require API keys

## Project Structure

```
src/aeolus/
├── __init__.py          # Public API (download, list_sources, etc.)
├── api.py               # Main download() function implementation
├── registry.py          # Source registration system
├── transforms.py        # Data normalization utilities
├── sources/             # Data source implementations
│   ├── regulatory.py    # UK regulatory networks (AURN, SAQN, WAQN, NI, AQE, LOCAL, LMAM)
│   ├── openaq.py        # OpenAQ global portal
│   ├── breathe_london.py # Breathe London network
│   ├── airqo.py         # AirQo African network
│   ├── purpleair.py     # PurpleAir global portal
│   ├── sensor_community.py # Sensor.Community citizen science
│   └── airnow.py        # EPA AirNow US network
├── metrics/             # Air quality metrics calculations
└── viz/                 # Visualization utilities
```

## Data Sources

### Networks (known site lists)

| Source | API Key | Coverage |
|--------|---------|----------|
| AURN | No | UK national network |
| SAQN | No | Scotland |
| WAQN | No | Wales |
| NI | No | Northern Ireland |
| AQE | No | Air Quality England |
| LOCAL | No | Local authority networks |
| LMAM | No | London air quality mesh |
| BREATHE_LONDON | Yes (`BL_API_KEY`) | London low-cost sensors |
| AIRQO | Yes (`AIRQO_API_KEY`) | African cities (200+ sensors) |
| AIRNOW | Yes (`AIRNOW_API_KEY`) | USA, Canada, Mexico |
| SENSOR_COMMUNITY | No | Global citizen science (35,000+) |

### Portals (search required)

| Source | API Key | Coverage |
|--------|---------|----------|
| OPENAQ | Yes (`OPENAQ_API_KEY`) | Global (100+ countries) |
| PURPLEAIR | Yes (`PURPLEAIR_API_KEY`) | Global low-cost sensors (30,000+) |

## Standard Data Schema

All sources normalize to this schema:
- `site_code` - Unique site identifier
- `site_name` - Human-readable name (in metadata)
- `date_time` - Timestamp (left-closed intervals)
- `measurand` - Pollutant (PM2.5, NO2, O3, etc.)
- `value` - Measurement value
- `units` - Units (typically ug/m3)
- `source_network` - Data source name
- `ratification` - Data quality flag
- `created_at` - When record was fetched

**Metadata schema** (from `get_metadata()` / `find_sites()`):
- `site_code` - Unique site identifier (use for download)
- `site_name` - Human-readable name
- `latitude`, `longitude` - Location coordinates
- `source_network` - Data source name

**Bounding box format** (consistent across all sources):
- `bbox=(min_lon, min_lat, max_lon, max_lat)` - GeoJSON/shapely convention

## Common Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run all tests
pytest

# Run tests with coverage
pytest --cov=aeolus --cov-report=html

# Run specific test markers
pytest -m "not slow"        # Skip slow tests
pytest -m "not integration" # Skip API-dependent tests

# Run demos
python demo.py              # Main demo
python demo_airqo.py        # AirQo demo
python demo_openaq.py       # OpenAQ demo
```

## Code Patterns

**Adding a new data source:**
1. Create `src/aeolus/sources/newsource.py`
2. Implement `fetch_*_metadata()` and `fetch_*_data()` functions
3. Create a normalizer using `compose()` from transforms
4. Register with `register_source()` from registry
5. Import in `src/aeolus/sources/__init__.py`
6. Add tests in `tests/test_newsource.py`

**Using the library:**
```python
import aeolus
from datetime import datetime

# List available sources
aeolus.list_sources()

# Download data
data = aeolus.download(
    sources="AURN",
    sites=["MY1", "KC1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

## Testing

Tests use `pytest` with `responses` for mocking HTTP calls. Test files mirror source structure:
- `tests/test_regulatory.py` - AURN/SAQN tests
- `tests/test_openaq.py` - OpenAQ tests
- `tests/test_airqo.py` - AirQo tests
- `tests/test_breathe_london.py` - Breathe London tests
- `tests/test_purpleair.py` - PurpleAir tests
- `tests/test_sensor_community.py` - Sensor.Community tests
- `tests/test_airnow.py` - EPA AirNow tests

Mock API responses are defined as pytest fixtures within each test file.

## Notes

- Python 3.11+ required
- Uses `pandas` for data handling
- Time bins are left-closed: timestamp 13:00 represents [12:00, 13:00)
- Low-cost sensor data marked as `ratification='Unvalidated'`
- PurpleAir data has additional QA flags (`Validated`, `Single Channel`, etc.)
