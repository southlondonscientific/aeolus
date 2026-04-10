# Changelog

All notable changes to Aeolus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.2] - 2026-04-10

### Added
- **LAQN data source** — London Air Quality Network (~250 sites across Greater London), backed by the ERG/Imperial College London Air API (`api.erg.ic.ac.uk`). No API key required. Replaces the defunct LMAM and LOCAL sources.
- **EEA data source** — European Environment Agency monitoring network (7,000+ stations across 40+ countries). Uses the EEA Air Quality Download API with Parquet data files. No API key required.
- **Sonitus data source** — Smart Dublin (Sonitus) air quality and noise monitoring network in Dublin, Ireland. Measures NO2, SO2, CO, NO, O3, PM1, PM2.5, PM10, TSP at 15-minute resolution. No API key required.
- **Hypothesis property tests** — Property-based tests for geo, transforms, cache, metrics, download pipeline, and LAQN source normalisation.
- **Conformance test suite** — Live API conformance tests for all data sources, validating schema compliance and data quality against real endpoints.

### Fixed
- **Frequency-aware `data_capture` in `summarise()`** — Data capture calculation now respects the actual data frequency rather than assuming hourly.

### Removed
- **LMAM and LOCAL sources** — Both pointed to dead DEFRA RData endpoints (all data URLs returning 404). London coverage is now provided by the LAQN source.

### Known Limitations
- **LAQN does not support `get_current()`** — The London Air API has no real-time endpoint equivalent to the UK-AIR SOS API used by AURN/SAQN/etc. Use `aeolus.download("LAQN", sites, last="1d")` as a workaround for recent data.
- **Regulatory sources (AURN, SAQN, etc.) label CO as ug/m3** — CO data from RData files is actually in mg/m3. The LAQN source correctly labels CO as mg/m3. A fix for the regulatory sources is planned for a future release.

## [0.4.1] - 2026-04-05

### Fixed
- **Missing package data in wheel** — `_sos_mapping.json` and bundled IBM Plex Sans fonts were excluded from the published wheel because `pyproject.toml` lacked a `[tool.setuptools.package-data]` section. This caused `get_current()` to fall back to slow live API matching, `find_sites()` metadata to lose the `measurands` column, and plots to use fallback fonts.
- **Stale deleted modules in wheel** — `database_operations.py` and `meteorology.py` (removed in v0.4.0) were leaking back into builds from a stale `build/` directory.
- **Cache filename too long for large site lists** — When downloading all sites from a network (e.g. 321 AURN sites), the cache filename exceeded the macOS 255-byte limit. The human-readable site portion is now truncated; the SHA-256 hash still ensures uniqueness.

### Added
- **`statsmodels` optional dependency** — `pip install aeolus_aq[stats]` installs `statsmodels` for deseasonalisation in `trend()`. Also included in `[all]` and `[dev]` extras.
- **Packaging test suite** — `tests/test_packaging.py` verifies that data files, fonts, and SOS backends are present in the installed package. `scripts/test_wheel.sh` builds a wheel, installs it in an isolated venv, and runs tests against it (not the source tree).

## [0.4.0] - 2026-04-02

### Added

#### User Story Notebooks
- **7 executable Jupyter notebooks** covering real-world air quality workflows, mapped to validated user personas (researcher, consultant, local authority officer, citizen scientist, health researcher, journalist, IoT developer):
  - `01_london_no2_comparison` - Roadside vs background NO2 with diurnal/weekly decomposition
  - `02_pm25_compliance_report` - Monthly PM2.5 report with WHO guidelines and DAQI bands
  - `03_sensor_vs_reference` - PurpleAir vs AURN cross-source comparison with R2/RMSE
  - `04_uk_city_ranking` - Multi-network UK city ranking across 5 regulatory networks
  - `05_exposure_assessment` - Health study exposure estimates using nearest-monitor assignment
  - `06_african_air_quality` - AirQo network analysis with WHO compliance checking
  - `07_global_sensor_comparison` - Cross-network comparison (PurpleAir, Sensor.Community, AirQo)
  - `08_trend_analysis` - Multi-year Theil-Sen trend detection with deseasonalisation

#### Local File Cache
- **`aeolus.cache`** module - Transparent Parquet-based file cache for downloaded data. Enable with `enable_cache()`, manage with `clear_cache()`, `cache_info()`. Avoids redundant API calls when re-running notebooks or analyses. Cache directory defaults to `~/.cache/aeolus/`, configurable via `AEOLUS_CACHE_DIR` env var.

#### Unified Site Discovery
- **`aeolus.find_sites()`** - Top-level function that abstracts the network/portal distinction. Supports circular search (`near=(lat, lon)` + `radius_km`), rectangular filtering (`bbox`), `measurand=` filtering (e.g. `measurand="NO2"`), and automatic source selection (free sources by default, opt-in for API-key sources via `include_all=True`). Returns metadata DataFrame with `distance_km` column when `near` is used, sorted nearest-first.
- **Per-site measurands metadata** - Metadata now includes a `measurands` column (`list[str] | None`) showing which pollutants each site measures. Populated for regulatory networks (from SOS mapping), OpenAQ, and Sensor.Community.
- **`aeolus.geo`** module - Geospatial utilities: `haversine_distance()` (great-circle distance) and `near_to_bbox()` (point+radius to bounding box).
- **`METADATA_COLUMNS`** constant and `empty_metadata_frame()` helper in `aeolus.types`.

#### Analysis Functions (`aeolus.metrics`)
- **`time_average()`** - Time-average air quality data with data capture thresholds. Supports flexible aggregation periods (daily, 8-hourly, weekly, monthly, yearly) and multiple statistics (mean, max, min, percentile). Foundation for regulatory statistics.
- **`aq_stats()`** - Annual regulatory air quality statistics: annual mean, maxima, percentiles (p95, p99), data capture, and pollutant-specific exceedance counts (NO2 hourly >200, PM10 daily >50, O3 8h rolling >120). Output suitable for LAQM Annual Status Reports.
- **`trend()`** - Non-parametric trend analysis using Theil-Sen slope with Mann-Kendall significance test. Supports deseasonalisation (STL decomposition), autocorrelation correction, and configurable confidence intervals. Returns `TrendResult` dataclass.

#### Convenience Features
- **`aeolus.summarise()`** - Quick data overview: sites, pollutants, date range, record counts, and data capture per site+pollutant combination.
- **Date range shorthand** - `aeolus.download("AURN", ["MY1"], last="30d")` as alternative to explicit `start_date`/`end_date`. Supports minutes (`90min`), hours (`6h`), days (`30d`), weeks (`2w`), months (`6m`), years (`1y`).

#### Visualisation (`aeolus.viz`)
- **`plot_time_variation()`** - Combined 2x2 temporal variation plot (diurnal, weekly, monthly, hour x weekday heatmap), equivalent to R openair's `timeVariation`.
- **`plot_trend()`** - Trend analysis plot: scatter of aggregated data with Theil-Sen line, optional CI bands (dashed), and alternating year shading.

#### Documentation
- **`docs/dev/openair_comparison.md`** - Task-by-task comparison between Aeolus and R openair, covering data import, time averaging, trend analysis, plotting, and feature coverage gaps in both directions.

### Removed
- **`aeolus.database_operations` module** — deprecated since v0.3.0. Use `pandas.to_sql()` or similar for database storage.
- **`aeolus.meteorology` module** — deprecated since v0.3.0.
- **`sqlmodel` dependency** — only used by the removed `database_operations` module.

### Changed
- **OpenAQ and PurpleAir SDKs are now optional dependencies** — `pip install aeolus_aq` installs the core library; `pip install aeolus_aq[openaq]`, `pip install aeolus_aq[purpleair]`, or `pip install aeolus_aq[all]` adds portal sources. Helpful error messages guide users to install the right extra. This enables conda-forge distribution where the SDKs are not available.
- **OpenAQ SDK upgraded to 1.0rc2** — automatic rate-limit waiting (`auto_wait=True`), full pagination (previously capped at 1000 measurements per sensor), improved connection tuning.
- **`python-dotenv` removed from runtime dependencies** — only needed by demo scripts and notebooks, not the library itself.

### Fixed
- **`aq_stats()` year filter** - Handle numpy integer types when filtering by year.
- **`plot_trend()` CI band** - CI band now fans from the data centroid rather than the y-intercept.
- **Plot rendering** - Pollutant subscripts (NO₂, PM₂.₅), year-band shading, and dashed CI lines on trend plots.
- **Empty DataFrame schema** - All sources enforce the standard 8-column schema on empty DataFrames, preventing concat failures.
- **Deprecated exports** - Removed deprecated module re-exports; narrowed exception handling across sources.

## [0.3.0rc2] - 2026-02-16

### Fixed
- **Timezone-aware timestamps across all sources** - All data sources now produce UTC-aware `date_time` and `created_at` columns, preventing `TypeError` when comparing against timezone-aware datetime inputs (e.g. `datetime.now(UTC)`). Affected sources: AURN, SAQN, WAQN, NI, AQE, LOCAL, LMAM, OpenAQ, Breathe London, AirQo, PurpleAir, Sensor.Community, AirNow.
- **Regulatory date range filter** - Defensive handling of both naive and aware `start_date`/`end_date` parameters in UK regulatory network downloads.

## [0.3.0] - Unreleased

### Added

#### New Data Sources
- **AirQo** - African cities air quality network (200+ sensors). Requires `AIRQO_API_KEY`.
- **Sensor.Community** - Global citizen science network (35,000+ sensors). No API key required.
- **EPA AirNow** - US EPA real-time data (USA, Canada, Mexico). Requires `AIRNOW_API_KEY`.
- **PurpleAir** - Global low-cost sensors (30,000+) with dual-channel QA/QC. Requires `PURPLEAIR_API_KEY`.

#### Metrics Module (`aeolus.metrics`)
- Calculate air quality indices: UK_DAQI, US_EPA, CHINA, WHO, EU_CAQI, INDIA_NAQI
- `aqi_summary()`, `aqi_timeseries()`, `aqi_check_who()` functions
- Automatic unit conversion (ppb ↔ µg/m³)

#### Visualisation Module (`aeolus.viz`)
- Publication-ready plots: time series, calendar heatmaps, diurnal patterns, boxplots, AQI cards
- Consistent colour scheme and typography

#### Other
- OpenAQ site discovery now fully implemented (search by country, city, bbox)
- [Documentation site](https://southlondonscientific.github.io/aeolus/) with full API reference and guides

### Changed
- OpenAQ migrated to official `openaq` Python SDK
- Consistent `bbox=(min_lon, min_lat, max_lon, max_lat)` format across all sources
- Portal metadata returns `site_code`/`site_name` (consistent with networks)
- `aeolus.portals.download()` parameter: `location_ids` → `sites`

### Breaking Changes

**Removed `aeolus.downloader` module** - Use the v0.2.0 API instead:
- `get_network_metadata()` → `aeolus.networks.get_metadata()`
- `download_regulatory_data()` → `aeolus.download()`
- `get_breathe_london_metadata()` → `aeolus.networks.get_metadata("BREATHE_LONDON")`

**Portal download parameter renamed** - Positional usage still works:
```python
# Keyword argument needs updating
aeolus.portals.download("OPENAQ", sites=ids, ...)  # was location_ids=
```

### Deprecated
- `aeolus.database_operations` module (removal in v0.4.0)
- `aeolus.meteorology` module (removal in v0.4.0)

## [0.2.0] - 2025-01-15

### Added
- OpenAQ data source (download only; metadata search was stub)
- Breathe London data source
- New unified API: `aeolus.download()`, `aeolus.networks`, `aeolus.portals`
- GitHub Actions workflow for automated releases

### Deprecated
- Legacy functions in `aeolus.downloader` (removed in v0.3.0)

## [0.1.0] - 2024-12-01

### Added
- Initial release
- UK regulatory networks: AURN, SAQN, WAQN, NI, AQE, LOCAL, LMAM
- Standardised data schema
