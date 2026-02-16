# Aeolus - Claude Code Context

Air quality data downloading and standardization library for UK and international monitoring networks.

**Current Version:** 0.3.0rc2

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

All sources normalize data to this 8-column schema:
- `site_code` - Unique site identifier
- `date_time` - Timestamp (UTC-aware, left-closed intervals)
- `measurand` - Pollutant (PM2.5, NO2, O3, etc.)
- `value` - Measurement value
- `units` - Units (typically ug/m3)
- `source_network` - Data source name
- `ratification` - Data quality flag
- `created_at` - When record was fetched (UTC-aware)

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

## Release History

### v0.3.0rc2 (current, February 2026)
- **Timezone fixes**: All 7 data sources now produce UTC-aware `date_time` and `created_at` columns. Previously, naive timestamps caused `TypeError` when compared against tz-aware inputs.
- **Schema consistency**: Data output is now a strict 8-column schema (see above). `site_name` was removed from data output (it remains in metadata). Categorical dtypes removed from regulatory sources (caused issues when concatenating across sources). Empty DataFrames now carry the standard schema columns.
- **Release process**: Tag `v*` on main triggers GitHub Actions (`release.yml`) which builds a wheel via `uv build` and creates a GitHub Release. Docs deploy automatically on push to main via `docs.yml` (mkdocs).

### v0.3.0 (unreleased, targets full release after rc testing)
- See `CHANGELOG.md` for full v0.3.0 feature list (AirQo, Sensor.Community, PurpleAir, AirNow, metrics module, viz module).

## Roadmap

### v0.4.0 (planned)
**User story notebooks** - 7 executable Jupyter notebooks exercising real-world workflows, mapped to 9 validated user personas. Full specification in `docs/dev/user_stories_v040.md`.

Key notebooks:
1. London roadside vs background NO2 (no API key needed)
2. Monthly PM2.5 compliance report (no API key needed)
3. Low-cost sensor vs reference monitor (PurpleAir key)
4. UK city air quality ranking (no API key needed)
5. Exposure assessment for health study (Breathe London key)
6. African air quality with AirQo (AirQo key)
7. Global sensor network comparison (PurpleAir + AirQo keys)

**Quality of life features** anticipated:
- `find_sites(near=(lat, lon), radius_km=N)` convenience function
- Progress indicators for multi-site downloads
- Local file caching for historical data

**User personas** (documented in `docs/dev/user_stories_v040.md`):
- Primary: Academic researcher, health/epidemiology researcher, environmental consultant
- Secondary: Local authority officer, citizen scientist, educator/student
- Strategic: AI/LLM agent, data journalist, smart city developer

### Planning Documents
- `docs/dev/user_stories_v040.md` - User story notebooks tech spec and persona research
- `docs/dev/potential_data_sources.md` - Evaluated data sources for future integration (EEA, Open-Meteo, WAQI, etc.)

## Notes

- Python 3.11+ required
- Uses `pandas` for data handling
- Time bins are left-closed: timestamp 13:00 represents [12:00, 13:00)
- Low-cost sensor data marked as `ratification='Unvalidated'`
- PurpleAir data has additional QA flags (`Validated`, `Single Channel`, etc.)
- All timestamps are UTC-aware (enforced since v0.3.0rc2)
- Data schema is strict 8 columns; `site_name` is in metadata only, not data output
- Empty DataFrames always carry the standard schema columns (never bare `pd.DataFrame()`)
