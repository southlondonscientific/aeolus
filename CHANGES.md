# Aeolus Changelog

## [Unreleased] - v0.3.0

### Added

- **Air Quality Index calculations** (`aeolus.metrics` module)
  - UK DAQI (Daily Air Quality Index, 1-10 scale)
  - US EPA AQI (0-500 scale, with NowCast algorithm)
  - China AQI (0-500 scale)
  - WHO 2021 Guidelines checker (AQG and interim targets IT-1 to IT-4)
  - EU CAQI (roadside and background variants, 1-6 scale)
  - India NAQI (0-500 scale)
  
- **Summary functions**
  - `metrics.aqi_summary()`: Calculate AQI summaries with flexible aggregation (daily, weekly, monthly, yearly)
  - `metrics.aqi_timeseries()`: Calculate AQI time series with proper rolling averages
  - `metrics.aqi_check_who()`: Check compliance against WHO guidelines and interim targets
  
- **Utilities**
  - Automatic unit conversion (ppb ↔ µg/m³) with warnings
  - Pollutant name standardisation (e.g., "ozone" → "O3")
  - Coverage tracking for data quality assessment

- **80 new tests** for the metrics module (282 total tests, 68% coverage)

---

## [0.2.0] - January 2026

### New Architecture

This release introduces a significant architectural improvement that distinguishes between **networks** (discrete monitoring networks) and **portals** (global data aggregators).

- **Networks** (`aeolus.networks`): Discrete monitoring networks with known site lists
  - `get_metadata(network)`: Get all sites for a network
  - `download(network, sites, start_date, end_date)`: Download data
  - Supported: AURN, SAQN, WAQN, NI, AQE, LOCAL, LMAM, BREATHE_LONDON

- **Portals** (`aeolus.portals`): Global data aggregators requiring search
  - `find_sites(portal, **filters)`: Search for monitoring locations
  - `download(portal, sites, start_date, end_date)`: Download data
  - Supported: OpenAQ

- **Smart routing**: Top-level `aeolus.download()` automatically routes to the correct submodule

### Added

- **Breathe London integration**: Full support for London's high-density sensor network
- **OpenAQ integration**: Access to global air quality data from 100+ countries
- **Comprehensive test suite**: 202 tests, 61% coverage
- **Improved documentation**: User-focused README with clear examples

### Deprecated

The following functions are deprecated and will be removed in v0.3.0:

- `get_network_metadata()` → Use `aeolus.networks.get_metadata()`
- `download_regulatory_data()` → Use `aeolus.download()`
- `multiple_download_regulatory_data()` → Use `aeolus.download()`
- `get_breathe_london_metadata()` → Use `aeolus.networks.get_metadata("BREATHE_LONDON")`
- `download_breathe_london_data()` → Use `aeolus.download("BREATHE_LONDON", ...)`

### Fixed

- OpenAQ pagination now correctly handles all results
- Breathe London API parameter names corrected (camelCase)
- Retry decorator TypeError fixed

---

## [0.1.1a] - 2025

### Features

- Download data from UK regulatory networks (AURN, SAQN, WAQN, NI, AQE, Local)
- Breathe London API integration (basic)
- SQLModel-based database storage
- Meteorological data integration (Open-Meteo API)
- Standardised DataFrame output format
- Composable data transformations (`pipe`, `compose`, `filter_rows`, etc.)
- Source registry for extensibility
- Automatic retry logic for network resilience
