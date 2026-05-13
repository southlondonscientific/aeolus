# Aeolus - Claude Code Context

Air quality data downloading and standardisation library for UK and international monitoring networks.

**Current Version:** 0.4.5.2

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
notebooks/                   # 8 user story Jupyter notebooks (v0.4.0)
src/aeolus/
├── __init__.py          # Public API (download, list_sources, etc.)
├── api.py               # Main download() function implementation
├── registry.py          # Source registration system
├── transforms.py        # Data normalisation utilities
├── sources/             # Data source implementations
│   ├── regulatory.py    # UK regulatory networks (AURN, SAQN, WAQN, NI, AQE)
│   ├── laqn.py          # London Air Quality Network (ERG/Imperial)
│   ├── openaq.py        # OpenAQ global portal
│   ├── breathe_london.py # Breathe London network
│   ├── airqo.py         # AirQo African network
│   ├── purpleair.py     # PurpleAir global portal
│   ├── sensor_community.py # Sensor.Community citizen science
│   ├── airnow.py        # EPA AirNow US network
│   ├── eea.py           # EEA European monitoring network
│   ├── sonitus.py       # Smart Dublin (Sonitus) network
│   ├── sos.py           # UK-AIR SOS near-real-time API (AURN-SOS, SAQN-SOS, etc.)
│   └── _sos_mapping.json # Static SOS station mapping (auto-generated)
├── cache.py             # Local Parquet-based download caching
├── geo.py               # Geospatial utilities (haversine, bbox)
├── progress.py          # Optional tqdm progress bars (fallback to logging)
├── metrics/             # Air quality metrics calculations
└── viz/                 # Visualisation utilities
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
| LAQN | No | London Air Quality Network (~250 sites) |
| BREATHE_LONDON | Yes (`BL_API_KEY`) | London low-cost sensors |
| AIRQO | Yes (`AIRQO_API_KEY`) | African cities (200+ sensors) |
| AIRNOW | Yes (`AIRNOW_API_KEY`) | USA, Canada, Mexico |
| SENSOR_COMMUNITY | No | Global citizen science (35,000+) |
| EEA | No | Europe (40+ countries, 7,000+ stations) |
| SONITUS | No | Dublin, Ireland |

### Portals (search required)

| Source | API Key | Coverage |
|--------|---------|----------|
| OPENAQ | Yes (`OPENAQ_API_KEY`) | Global (100+ countries) |
| PURPLEAIR | Yes (`PURPLEAIR_API_KEY`) | Global low-cost sensors (30,000+) |

### Optional SDK Dependencies

OpenAQ and PurpleAir require optional SDK packages not available on conda-forge:

| Extra | Install command | Provides |
|-------|----------------|----------|
| `openaq` | `pip install aeolus_aq[openaq]` | OpenAQ portal access |
| `purpleair` | `pip install aeolus_aq[purpleair]` | PurpleAir portal access |
| `stats` | `pip install aeolus_aq[stats]` | `statsmodels` for deseasonalisation in `trend()` |
| `progress` | `pip install aeolus_aq[progress]` | `tqdm` progress bars for bulk downloads |
| `all` | `pip install aeolus_aq[all]` | OpenAQ + PurpleAir + statsmodels |

For conda users: `conda install -c conda-forge aeolus_aq` then `pip install openaq purpleair-api` for portal sources.

## Standard Data Schema

All sources normalise data to this 8-column schema:
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
# Install from conda-forge
conda install -c conda-forge aeolus_aq

# Install with all optional sources (pip only)
pip install aeolus_aq[all]

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
3. Create a normaliser using `compose()` from transforms
4. Register with `register_source()` from registry
5. Import in `src/aeolus/sources/__init__.py`
6. Add tests in `tests/test_newsource.py`

**Using the library:**
```python
import aeolus
from datetime import datetime

# List available sources
aeolus.list_sources()

# Find sites near a location (adds distance_km column, sorted nearest-first)
sites = aeolus.find_sites("AURN", near=(51.5074, -0.1278), radius_km=20)

# Find sites in a bounding box
sites = aeolus.find_sites(["AURN", "SAQN"], bbox=(-0.5, 51.3, 0.3, 51.7))

# Find sites from all free sources (no API key needed)
sites = aeolus.find_sites()

# Get current (near-real-time) readings via SOS API
latest = aeolus.get_current("AURN", sites=["MY1", "KC1"])

# List all sources including SOS backends
aeolus.list_sources(include_all=True)

# Download data
data = aeolus.download(
    sources="AURN",
    sites=["MY1", "KC1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Date range shorthand
data = aeolus.download("AURN", ["MY1"], last="30d")

# Quick data overview
aeolus.summarise(data)
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

- `tests/test_sos.py` - SOS near-real-time API tests
- `tests/test_find_sites.py` - find_sites() unified site discovery
- `tests/test_cache.py` - Local file cache
- `tests/test_progress.py` - Progress indicator wrapper tests
- `tests/test_geo.py` - Geospatial utilities

Mock API responses are defined as pytest fixtures within each test file.

## Release History

### v0.4.0 (current, March 2026)
- **User story notebooks**: 8 executable Jupyter notebooks in `notebooks/` covering real-world workflows.
- **Local file caching**: `aeolus.cache` module for Parquet-based download caching.
- **OpenAQ SDK 1.0rc2**: Auto rate-limit waiting, full pagination, improved connection tuning.
- **Removed deprecated modules**: `database_operations.py`, `meteorology.py`, and `sqlmodel` dependency.
- **Version jump**: Skipped v0.3.0 final; v0.4.0 supersedes v0.3.0rc2.
- See `CHANGELOG.md` for full details.

### v0.3.0rc2 (February 2026)
- **Timezone fixes**: All 7 data sources now produce UTC-aware `date_time` and `created_at` columns.
- **Schema consistency**: Strict 8-column data schema. Empty DataFrames carry standard columns.
- **Release process**: Tag `v*` on main triggers GitHub Actions (`release.yml`).

## Roadmap

### v0.4.0 (current)
~~**User story notebooks**~~ (done) - 8 executable Jupyter notebooks in `notebooks/`, mapped to 9 validated user personas. Spec: `docs/dev/user_stories_v040.md`.

**Analysis functions** (high priority):
- ~~`time_average()` — time averaging with data capture thresholds~~ (done)
- ~~`aq_stats()` — annual regulatory statistics, exceedance counts, data capture~~ (done)
- ~~`trend()` — Theil-Sen non-parametric trend with CI, p-value, deseasonalisation~~ (done)
- ~~`time_variation()` plot — combined 4-panel temporal decomposition~~ (done, as `plot_time_variation()`)

**Data access features** (high priority):
- ~~`find_sites(near=(lat, lon), radius_km=N)` convenience function~~ (done)
- ~~`get_current()` near-real-time data via UK-AIR SOS API~~ (done)
- ~~Progress indicators for multi-site downloads~~ (done, optional `tqdm`)
- ~~Local file caching for historical data~~ (done, Parquet-based `aeolus.cache`)

**Convenience features** (medium priority):
- ~~`summarise()` — quick data overview with sites, pollutants, date range, data capture~~ (done)
- ~~Date range shorthand (`last="30d"`) for `download()` and `fetch()`~~ (done)

**User personas** (documented in `docs/dev/user_stories_v040.md`):
- Primary: Academic researcher, health/epidemiology researcher, environmental consultant
- Secondary: Local authority officer, citizen scientist, educator/student
- Strategic: AI/LLM agent, data journalist, smart city developer

### Planning Documents
- `docs/dev/user_stories_v040.md` - User story notebooks tech spec and persona research
- `docs/dev/potential_data_sources.md` - Evaluated data sources for future integration (EEA, Open-Meteo, WAQI, etc.)
- `docs/dev/openair_comparison.md` - Task-by-task comparison with R openair

## Notes

- Python 3.11+ required
- Uses `pandas` for data handling
- Time bins are left-closed: timestamp 13:00 represents [12:00, 13:00)
- Low-cost sensor data marked as `ratification='Unvalidated'`
- PurpleAir data has additional QA flags (`Validated`, `Single Channel`, etc.)
- All timestamps are UTC-aware (enforced since v0.3.0rc2)
- Data schema is strict 8 columns; `site_name` is in metadata only, not data output
- Empty DataFrames always carry the standard schema columns (never bare `pd.DataFrame()`)
- SOS sources (AURN-SOS, etc.) are registered with `primary=False` — hidden from `list_sources()` and `find_sites()` by default, pass `include_all=True` to see them
- `get_current()` auto-routes AURN→AURN-SOS for near-real-time readings
- SOS station mapping is shipped as `_sos_mapping.json`; refresh with `from aeolus.sources.sos import rebuild_sos_mapping; rebuild_sos_mapping()`
- Progress bars require `pip install tqdm` (or `pip install aeolus[progress]`); without it, falls back to logging

## Cross-product session log

A running log of development across all SLS products lives at `../SLS-PRODUCT-DEV.md`. At the end of any session that materially changes this project's state (commits, deploys, design decisions, new dependencies), append an entry to that file's Session Log section (newest first) and update the Status Snapshot row for this product. The template and conventions are in the log's "How to update" section — keep entries terse (~250 words) with Achieved / Decisions / Next / Open subsections. Skip for trivial sessions (single-line fixes, pure exploration, no commits).
