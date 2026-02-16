# Changelog

All notable changes to Aeolus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

#### Visualization Module (`aeolus.viz`)
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
- Standardized data schema
