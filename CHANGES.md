# Aeolus Changelog

## [Unreleased] - 2025

### Added
- **Core types module** (`types.py`): Standardised type definitions for functional architecture
  - `SiteRecord` TypedDict: Standard schema for site metadata
  - `DataRecord` TypedDict: Standard schema for air quality measurements
  - `SourceSpec` TypedDict: Specification for data sources
  - Type aliases: `MetadataFetcher`, `DataFetcher`, `Normaliser`, `Transformer`
  - Standard column name constants for validation

- **Transform utilities module** (`transforms.py`): Composable DataFrame transformation functions
  - `pipe()`: Apply transformations in sequence
  - `compose()`: Combine transformations into reusable pipelines
  - `rename_columns()`: Rename DataFrame columns
  - `add_column()`: Add static or computed columns
  - `drop_columns()`: Remove unwanted columns
  - `convert_timestamps()`: Parse datetime columns
  - `filter_rows()`: Filter rows by predicate
  - `melt_measurands()`: Convert wide to long format
  - `drop_duplicates()`: Remove duplicate rows
  - `reset_index()`: Reset DataFrame index
  - `sort_values()`: Sort by columns
  - `fillna()`: Fill missing values
  - `select_columns()`: Select subset of columns
  - `apply_function()`: Wrap custom transformations

### Fixed
- **meteorology.py**: Added missing `timedelta` import (was causing runtime error)
- **downloader.py**: Fixed incorrect return type annotation `pd.DataFrame()` → `pd.DataFrame`
- **downloader.py**: Removed `-999` sentinel value for missing data (now uses proper NaN)
- **__init__.py**: Synchronized version number with `pyproject.toml` (now `0.1.1a`)

### Changed
- Architecture moving towards functional composition model
- Preparing for source registry and modular data source system

## [0.1.1a] - 2025-01-XX

### Features
- Download data from multiple UK regulatory networks (AURN, SAQN, WAQN, NI, AQE, Local)
- Breathe London API integration
- SQLModel-based database storage
- Meteorological data integration (Open-Meteo API)
- Standardised DataFrame output format

---

## Migration Notes

### For Users
No breaking changes in this release. The new `types.py` and `transforms.py` modules are additions that don't affect existing code.

### For Developers
The new functional architecture provides:
- **Type safety**: Use `SiteRecord` and `DataRecord` for type hints
- **Composability**: Build data pipelines with `pipe()` and `compose()`
- **Testability**: Pure functions are easier to test in isolation

Example of new functional style:
```python
from aeolus.transforms import pipe, compose, rename_columns, add_column

# Create a reusable normalisation pipeline
normalise_aurn = compose(
    rename_columns({"site": "site_code", "date": "date_time"}),
    add_column("source_network", "AURN"),
    convert_timestamps("date_time", unit="s")
)

# Apply to any DataFrame
df_clean = normalise_aurn(df_raw)
```

---

## Next Steps

See architecture planning documents for upcoming changes:
- Source registry system
- Retry logic with exponential backoff
- Parquet export for data lake
- Additional data sources (OpenAQ, Met Office DataPoint)
- Comprehensive test suite