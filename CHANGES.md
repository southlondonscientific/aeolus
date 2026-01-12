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

- **Source registry module** (`registry.py`): Simple dictionary-based source management
  - `register_source()`: Register a data source
  - `get_source()`: Retrieve a registered source
  - `list_sources()`: List all available sources
  - `source_exists()`: Check if source is registered
  - `get_source_info()`: Get source metadata
  - Case-insensitive source name handling

- **Regulatory sources module** (`sources/regulatory.py`): UK regulatory networks in functional style
  - Factory functions: `make_metadata_fetcher()`, `make_data_fetcher()`
  - Composable normalisation pipelines using transforms
  - Registered networks: AURN, SAQN, SAQD, NI, WAQN, AQE, LOCAL, LMAM
  - Shared configuration (URLs, measurands)
  - Low-level `fetch_rdata()` function with error handling and retry logic
  - Tested with real data (MY1 site, 3046 sites metadata, 26,677 data records)

- **Decorators module** (`decorators.py`): Function decorators for cross-cutting concerns
  - `with_retry()`: Exponential backoff retry logic for network operations
  - `with_timeout()`: Ensure HTTP requests have timeouts
  - `with_logging()`: Add structured logging to functions
  - `ignore_exceptions()`: Gracefully handle non-critical failures
  - Pre-configured decorators: `retry_on_network_error`, `retry_aggressive`, `retry_gentle`
  - Uses `tenacity` library for robust retry logic
  - Automatically retries on connection errors, timeouts, and 5xx server errors
  - Does not retry on 4xx client errors (bad requests)

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

## Next Steps (Remaining from Original Plan)

Completed so far:
- ✅ Step 1: Fixed bugs
- ✅ Step 2: Created types.py
- ✅ Step 3: Created transforms.py
- ✅ Step 4: Created registry.py
- ✅ Step 5: Refactored AURN & regulatory networks
- ✅ Step 6: Added retry decorator with exponential backoff

Still to do:
- Step 7: Write first tests (1-2 hours)
- Step 8: Update __init__.py exports (30 mins)

Future enhancements:
- Parquet export for data lake
- Additional data sources (OpenAQ, Met Office DataPoint)
- Breathe London refactor to match new architecture
- TimescaleDB integration for production
- Comprehensive test suite