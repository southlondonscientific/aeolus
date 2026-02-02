# Aeolus Roadmap

This document tracks planned features and improvements for aeolus. Items are organised by theme and roughly prioritised within each section.

## Data Sources

### Networks (discrete monitoring sites)

| Source | Description | Status | Python SDK | Notes |
|--------|-------------|--------|------------|-------|
| PurpleAir | Global low-cost sensor network (~30k+ sensors) | **Done** | [`purpleair-api`](https://pypi.org/project/purpleair-api/) - actively maintained (v1.3.1, Oct 2025) | API requires registration, uses point-based billing. Free tier: 1M points on signup. |
| Sensor.Community | European citizen science network (formerly Luftdaten) | Considering | [`luftdaten`](https://pypi.org/project/luftdaten/) - **inactive** (no releases in 12+ months) | Open data, no API key required. May need to implement from scratch. |
| US EPA AirNow | Official US real-time monitoring (2,500+ stations) | Considering | [`pyairnow`](https://pypi.org/project/pyairnow/) - async client | Free API key required. Real-time and forecast data. |
| US EPA AQS | Official US historical regulatory data | Considering | [`pyaqsapi`](https://github.com/USEPA/pyaqsapi) - **official EPA package** | Historical data only (not real-time). Returns pandas DataFrames. |

### Portals (global aggregators)

| Source | Description | Status | Python SDK | Notes |
|--------|-------------|--------|------------|-------|
| European Environment Agency | EU regulatory data | Considering | None (R package [`euroaq`](https://openair-project.github.io/euroaq/) exists) | Would need to implement API client from scratch. |

## Air Quality Indices

| Index | Region | Status | Notes |
|-------|--------|--------|-------|
| UK DAQI | UK | Done | |
| US EPA AQI | USA | Done | Includes NowCast |
| China AQI | China | Done | |
| EU CAQI | Europe | Done | Roadside and background variants |
| India NAQI | India | Done | |
| WHO Guidelines | Global | Done | Compliance checking |
| Canada AQHI | Canada | Considering | Health-based index (different methodology) |
| Hong Kong AQHI | Hong Kong | Considering | Health-based index |
| Singapore PSI | Singapore | Considering | |

## Data Quality

| Feature | Status | Notes |
|---------|--------|-------|
| QA/QC flag standardisation | Planned (v0.3.0) | The current `ratification` column contains network-specific values (e.g. "Validated", "Channel Disagreement" for PurpleAir; "Ratified", "Unvalidated" for Breathe London). Need to define a unified schema with: (1) a standard set of flag values across all sources, (2) clear semantics for each flag, (3) optional source-specific detail in a separate column. See REFERENCES.md for methodology sources. |
| Automated outlier detection | Considering | Statistical methods for identifying suspect data |
| Data completeness metrics | Considering | Report coverage/gaps in downloaded data |

## Infrastructure

| Feature | Status | Notes |
|---------|--------|-------|
| Local caching | Considering | Cache downloaded data to reduce API calls |
| Parquet export | Considering | Efficient storage format for large datasets |
| Site discovery by location | Considering | "Find sites within X km" across all sources |

## Visualisation

| Feature | Status | Notes |
|---------|--------|-------|
| Pollution roses | Considering | Requires wind data integration |
| Calendar heatmaps | Considering | |
| Diurnal/weekly patterns | Considering | |
| Exceedance charts | Considering | Days/hours exceeding thresholds |

## Future Directions

These are larger scope items that may be better suited as separate packages or a future major version:

- **Health impact modelling** - Exposure assessment, health impact functions, population-weighted exposures
- **Forecast integration** - Air quality forecasts from various sources
- **Emissions data** - Integration with emissions inventories

---

## Version Planning

### v0.3.0 (next)
- PurpleAir data source with dual-channel QA/QC support
- QA/QC flag standardisation across sources

### v0.2.0 (current)
- Migrated to OpenAQ official Python SDK
- Added AirQo source
- Added Breathe London source
- GitHub Actions release workflow

### v0.1.0
- Initial release with UK regulatory networks
- Core metrics and transforms
