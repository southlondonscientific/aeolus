# Connector pattern

Every data source in `src/aeolus/sources/` follows the same shape. This is not
enforced by inheritance or metaclass magic — it's a convention, guarded by the
static tests in `tests/test_source_pattern.py` and the consistency tests in
`tests/test_source_consistency.py`.

Keep new sources to this pattern. Deviations stand out in review, make the
codebase easier to navigate, and let downstream tools (like the MCP server
and the aeolus CLI) rely on consistent behaviour.

## File layout

```python
"""
Module docstring — one paragraph on what the source is, plus:
- API URL
- Authentication requirements (API key / free)
- Rate limits (if any)
- Known quirks
"""

# imports: stdlib, then third-party, then aeolus

# ============================================================================
# CONSTANTS
# ============================================================================

API_BASE = "..."
MEASURAND_MAP = {...}


# ============================================================================
# HTTP CLIENT
# ============================================================================

@retry_on_network_error
def _get_json(path: str) -> dict | None:
    ...


# ============================================================================
# METADATA
# ============================================================================

def normalise_X_metadata() -> Normaliser:
    return compose(...)


def fetch_X_metadata(**filters) -> pd.DataFrame:
    ...


# ============================================================================
# DATA
# ============================================================================

def fetch_X_data(sites: list[str], start_date: datetime, end_date: datetime) -> pd.DataFrame:
    ...


# ============================================================================
# SOURCE REGISTRATION
# ============================================================================

register_source("X", {
    "type": "network",          # or "portal"
    "name": "Human-readable name",
    "fetch_metadata": fetch_X_metadata,
    "fetch_data": fetch_X_data,
    "normalise": ...,
    "requires_api_key": False,
})
```

## Contract

### Required

- **`@retry_on_network_error`** on every function that makes a `requests.*` call.
  SDK-wrapped sources (OpenAQ, PurpleAir) don't need it if the SDK handles retries.

- **`empty_data_frame()`** from `aeolus.types` for empty data results, and
  **`empty_metadata_frame()`** for empty metadata. Never construct a bare
  `pd.DataFrame(columns=[...])` for an empty-schema DataFrame — the helpers
  exist so that schema additions stay centralised.

- **`AeolusDataWarning`** on any data-fetch path that silently returns no data.
  Use `warnings.warn(msg, AeolusDataWarning, stacklevel=2)`. `logger.warning`
  is not a substitute — it's too quiet and users miss it.

- **`compose()`** from `aeolus.transforms` for normalisers where possible.
  Imperative normalisers are allowed but should be a last resort.

- **`source_network`** column value must equal the registry key. Registry keys
  are uppercase (`LAQN`, `BREATHE_LONDON`). The `name` field in the spec is
  the human-readable display name (`"Breathe London"`).

- **`units`** must come from the canonical vocabulary in `tests/test_source_consistency.py`.

- **`ratification`** must come from the canonical vocabulary in `tests/test_source_consistency.py`.

- **Canonical pollutant spellings**: `PM2.5` not `PM25`, `NO2` not `no2`, etc.
  See `CANONICAL_POLLUTANTS` in `tests/test_source_consistency.py`.

### Signatures

- **`fetch_X_metadata(**filters) -> pd.DataFrame`**
  Always accept `**filters` even if the source ignores them — unifies the
  calling convention across sources. Optional spatial filters (`near`,
  `bbox`, `country`) are source-specific.

- **`fetch_X_data(sites: list[str], start_date: datetime, end_date: datetime) -> pd.DataFrame`**
  Sites is a list of site codes (never a single string). Dates are always
  `datetime` (naive or tz-aware both accepted; sources normalise to UTC).
  Returns a DataFrame with the 8-column `DATA_COLUMNS` schema.

### Registry spec

Every spec must include:

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | Human-readable display name |
| `fetch_metadata` | `MetadataFetcher` | `(**filters) -> DataFrame` |
| `fetch_data` | `DataFetcher` | `(sites, start, end) -> DataFrame` |
| `normalise` | `Normaliser` | `DataFrame -> DataFrame` |
| `requires_api_key` | `bool` | Must be a `bool`, not a truthy string |

Optional:

| Field | Type | Notes |
|-------|------|-------|
| `type` | `"network"` or `"portal"` | Default `"network"` |
| `primary` | `bool` | Default `True`. `False` = hidden from `list_sources()` (used for SOS backends) |
| `fetch_latest` | `DataFetcher` | For near-real-time data (SOS backends) |

## When to deviate

Sometimes a source genuinely doesn't fit. OpenAQ uses the official SDK
(no `requests`); EEA needs a parquet download round-trip before the standard
pipeline applies. These deviations are fine — but they should be the exception,
explicitly documented in the module docstring, and not propagated to other
sources.

If you find yourself deviating repeatedly, the pattern itself may need to
evolve. Update this doc and the tests, don't paper over it.

## Tests that enforce the pattern

- `tests/test_source_consistency.py` — vocabulary, registry-key, and field-type checks
- `tests/test_source_pattern.py` — structural pattern checks (retry decorators, empty-frame helpers, AeolusDataWarning usage)
