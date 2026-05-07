# Changelog

All notable changes to Aeolus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.4] - 2026-05-07

### Fixed (silent wrong numbers — please re-baseline)

- **`aqi_summary` unit conversion** — US EPA O3/CO require ppm and SO2/NO2 require ppb (40 CFR App. G); China and India NAQI CO breakpoints are mg/m³. The Aeolus standard schema is µg/m³, but the public `aqi_summary` path was handing µg/m³ values straight to each index's `calculate(...)` without converting. Real readings produced AQI values that were off by orders of magnitude — typically near 0 for US EPA O3 and "Excellent" for China CO. Now converts via a new `metrics.base.to_index_unit()` helper that consults each index's `UNITS` mapping. **Migration**: any code asserting on specific AQI values for these pollutants from earlier 0.4.x will see different (now correct) results — re-baseline expected outputs.
- **`aqi_summary` rolling window** — The docstring claimed it "handles the required averaging periods for each index" but the implementation took a flat mean across the whole period. PM2.5 spikes during a 24h window were diluted by clean air; O3 8h peaks weren't captured. Now applies each pollutant's required window (PM 24h, O3 8h, NO2 1h, etc.) with the same 75% min-periods rule as `aqi_timeseries`, and reports the worst rolling-window AQI within the period.
- **`aqi_summary(index="WHO")`** — WHO is a guideline-compliance check, not an AQI; the `who` module exposes `check_guideline()`, not `calculate()`. Calls used to swallow the `AttributeError` and return `AQIResult(value=None)` for every row. Now raises a clear `ValueError` pointing at `aqi_check_who()`.
- **`aqi_summary` coverage denominator** — Used the dataset-wide span instead of the per-(site, pollutant) span, mis-attributing coverage in mixed-pollutant inputs and occasionally exceeding 1.0. Now per-group, capped at 1.0.
- **US EPA O3 8h/1h routing** — A reading of e.g. 0.140 ppm 8-hour was routed to the 1-hour table (which gives ~AQI 131) instead of the 8-hour table (which gives ~AQI 225). The 8-hour table now covers AQI 0-300 (up to 0.200 ppm) per 40 CFR App. G; the 1-hour table is reserved for AQI > 300. Explicitly passing `averaging_period="1h"` still honours the override.
- **China O3 8-hour above 800 µg/m³** — HJ 633-2012 says "for AQI > 300, use the 1-hour table"; the 8-hour breakpoint list ended at 800 µg/m³ (AQI 300), so values above it returned `None` and were silently capped at AQI 500. Extended the 8-hour table to cover AQI 301-500.
- **China and India NAQI breakpoint gaps** — Both specs assume inputs are reported at a fixed precision (CO 1 decimal, India NAQI Pb 2 decimals, others integer). Without rounding, a 2.05 mg/m³ China CO reading fell in no breakpoint band and capped at AQI 500. Inputs are now rounded to the spec's precision before lookup; the original concentration is preserved on the result.
- **`aq_stats` sub-hourly inputs** — 15-minute data produced `data_capture` ≈ 4.0 (35,040 obs / 8,760 expected hours), trivially passing any threshold and double-counting NO2 exceedance hours. Sub-hourly inputs are now resampled to hourly means before the per-year statistics are computed, and `data_capture` is clipped at 1.0.
- **Breathe London `ListSensors` filtering** — The endpoint silently rejects every documented query parameter (`borough`, `sponsor`, `species`, `latitude`/`longitude`/`radius`) with HTTP 400, but the error was swallowed and `fetch_breathe_london_metadata()` returned an empty frame for every filtered call. The adapter now fetches the full sensor list once and applies all filters client-side. The `species` filter is a no-op with a warning since `ListSensors` does not expose per-site measurands.
- **Metadata fetcher empty schemas (AirNow, AirQo, PurpleAir)** — All three returned `empty_data_frame()` (8-col data schema) on error/empty paths instead of `empty_metadata_frame()` (6-col metadata schema). Concatenation against valid metadata silently produced mixed-column frames.
- **Cache bypass via submodules** — `aeolus.networks.download()` and `aeolus.portals.download()` skipped the local Parquet cache entirely; only the top-level `aeolus.download()` cached. Both submodules now route through a new `aeolus.cache.fetch_with_cache()` helper, so direct submodule calls cache the same way.

### Added

- **`bbox_aware`, `sos_backend`, `default_measurands` fields on `SourceSpec`** — Replaces the hardcoded `_BBOX_AWARE_NETWORKS` and `_SOS_BACKENDS` sets in `api.py`. New bbox-aware networks and SOS-backed networks now declare their capabilities at registration time. `default_measurands` declares a fallback list for sources whose metadata feeds don't expose per-site measurands (BREATHE_LONDON: `["NO2", "PM2.5"]`; AIRQO: `["PM2.5", "PM10"]`); `find_sites(measurand=…)` consults it so these sources stop being silently dropped while regulatory networks keep their "old/decommissioned site" semantics.
- **`last="30d"` shorthand on submodule downloads** — `aeolus.networks.download(...)` and `aeolus.portals.download(...)` now accept `last=` the same way the top-level `aeolus.download` does. Date-range parsing extracted to a new shared `aeolus._dates` module.
- **`metrics.base.to_index_unit(values_ugm3, pollutant, target_unit)`** — Convert µg/m³ to the unit each index's breakpoints expect (ppm, ppb, mg/m³, or µg/m³). Drives the unit conversion fix above.
- **`china.UNITS`, `china.get_unit()`, `india_naqi.UNITS`, `india_naqi.get_unit()`** — Public per-index unit mappings, mirroring the existing US EPA exports.
- **Authoritative AQI spec corpus tests** — ~50 parametrised cases drawn directly from each agency's published breakpoint table (US EPA 40 CFR App. G, DEFRA DAQI, China HJ 633-2012, India CPCB) plus end-to-end `aqi_summary` regressions. Locks in numerical correctness so future unit-conversion or routing regressions can't slip through silent.
- **Shared "Unknown source" error message** — `registry.unknown_source_message()` is now used by every public entry point, so submodule errors carry the same available-sources list and optional-SDK install hint that the top-level surfaces.

### Changed (potentially breaking for downstream callers)

- **`find_sites(measurand=…)` now returns more sites for BREATHE_LONDON and AIRQO** — Previously these were silently dropped because their metadata feeds don't expose per-site measurands. They now match against the source's declared `default_measurands`. Code that depended on the strict "exclude unknown" behaviour can read the underlying source's `measurands` column directly.
- **`aqi_summary` numerical AQI values change for non-µg/m³ pollutants** — Per the unit-conversion fix above. UK DAQI and EU CAQI are µg/m³ across all pollutants and are unaffected.

### Notes

- `_BBOX_AWARE_NETWORKS` and `_SOS_BACKENDS` (private symbols on `aeolus.api`) were removed in favour of the new `SourceSpec` fields. No public-API breakage.

## [0.4.3] - 2026-04-19

### Fixed
- **LAQN same-day queries** — LAQN API rejects `StartDate=X/EndDate=X` with HTTP 400. The adapter now pads `end` by one day when start and end fall on the same calendar day, so current-data and same-day historical queries work.
- **LAQN missing `location_type`** — `find_sites("LAQN")` now surfaces `@SiteType` (Roadside, Urban Background, Kerbside, Suburban, Industrial, Rural) as the standard `location_type` column, matching AURN and other regulatory sources.
- **`source_network` inconsistency across six sources** — AIRQO, AIRNOW, BREATHE_LONDON, OPENAQ, PURPLEAIR, and SENSOR_COMMUNITY adapters emitted display names (e.g. `"Breathe London"`) instead of their registry keys (`"BREATHE_LONDON"`). `get_current()` and `download()` lookups by the metadata value silently failed. All sources now emit `source_network` matching their registry key.

### Added
- **Cross-source consistency tests** (`tests/test_source_consistency.py`) — static checks that every source adapter emits `source_network` matching its registry key, that registry keys are uppercase, and that every spec has the required fields. New sources get these checks for free.

## [0.4.2] - 2026-04-10

### Added
- **LAQN data source** — London Air Quality Network (~250 sites across Greater London), backed by the ERG/Imperial College London Air API (`api.erg.ic.ac.uk`). No API key required. Replaces the defunct LMAM and LOCAL sources.
- **EEA data source** — European Environment Agency monitoring network (7,000+ stations across 40+ countries). Uses the EEA Air Quality Download API with Parquet data files. No API key required.
- **Sonitus data source** — Smart Dublin (Sonitus) air quality and noise monitoring network in Dublin, Ireland. Measures NO2, SO2, CO, NO, O3, PM1, PM2.5, PM10, TSP at 15-minute resolution. No API key required.
- **Hypothesis property tests** — Property-based tests for geo, transforms, cache, metrics, download pipeline, and LAQN source normalisation.
- **Conformance test suite** — Live API conformance tests for all data sources, validating schema compliance and data quality against real endpoints.

### Fixed
- **Frequency-aware `data_capture` in `summarise()`** — Data capture calculation now respects the actual data frequency rather than assuming hourly.
- **`data_capture` capped at 1.0 in `summarise()`** — When timestamps were sub-minute apart, the inferred frequency could underestimate expected records, producing `data_capture` > 1.0.
- **CO units corrected to mg/m3** — All sources (regulatory and LAQN) now correctly label CO as mg/m3. Previously, regulatory sources labelled CO as ug/m3 despite the values being in mg/m3.

### Removed
- **LMAM and LOCAL sources** — Both pointed to dead DEFRA RData endpoints (all data URLs returning 404). London coverage is now provided by the LAQN source.

### Known Limitations
- **LAQN does not support `get_current()`** — The London Air API has no real-time endpoint equivalent to the UK-AIR SOS API used by AURN/SAQN/etc. Use `aeolus.download("LAQN", sites, last="1d")` as a workaround for recent data.

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
- **8 executable Jupyter notebooks** covering real-world air quality workflows, mapped to validated user personas (researcher, consultant, local authority officer, citizen scientist, health researcher, journalist, IoT developer):
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
