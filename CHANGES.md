# Aeolus Changelog

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
