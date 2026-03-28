# Conda-forge Distribution: Optional Dependencies Design

**Date:** 2026-03-28
**Status:** Draft
**Goal:** Make `aeolus_aq` distributable on conda-forge by making `openaq` and `purpleair-api` optional dependencies.

## Context

Aeolus has 12 runtime dependencies. 10 are available on conda-forge; 2 are not:

- **`openaq`** — Python SDK for OpenAQ. No conda-forge feedstock. Also pinned to a pre-release (`>=1.0.0rc2`), which conda-forge disallows.
- **`purpleair-api`** — Python SDK for PurpleAir. No conda-forge feedstock.

Both are "portal" sources that require API keys. Making them optional unblocks the conda-forge submission without reducing functionality for pip users (who can still install the extras).

## Approach: Lazy Import with Graceful Skip

Sources that depend on missing SDKs simply don't register. The library loads and works for all other sources. Users who need OpenAQ or PurpleAir install the extras via pip.

### Design Principles

1. **`import aeolus` always works** — no `ImportError` regardless of which optional SDKs are installed.
2. **Missing sources are invisible** — they don't appear in `list_sources()` or `find_sites()`. No broken stubs.
3. **Clear error at point of use** — if a user explicitly requests `download("OPENAQ", ...)` and the source isn't registered, the existing `api.py` error handling already covers this (source not found).
4. **pip users are unaffected** — `pip install aeolus_aq[all]` gives the same experience as today.

## Changes

### 1. `pyproject.toml` — restructure dependencies

Move `openaq` and `purpleair-api` from core `dependencies` to optional extras:

```toml
dependencies = [
    "pandas>=2.3.3",
    "rdata>=0.11",
    "requests>=2.32.5",
    "tenacity>=8.2.0",
    "matplotlib>=3.7.0",
    "python-dotenv>=1.2.1",
    "numpy>=1.24.0",
    "scipy>=1.10.0",
    "pyarrow>=14.0.0",
]

[project.optional-dependencies]
openaq = ["openaq>=1.0.0rc2"]
purpleair = ["purpleair-api>=1.3.1"]
all = [
    "openaq>=1.0.0rc2",
    "purpleair-api>=1.3.1",
]
progress = ["tqdm>=4.60"]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.11.1",
    "responses>=0.23.0",
    "freezegun>=1.2.2",
    "tqdm>=4.60",
    "openaq>=1.0.0rc2",
    "purpleair-api>=1.3.1",
]
```

The `dev` extra includes both optional SDKs so the full test suite runs in CI.

### 2. `src/aeolus/sources/openaq.py` — lazy SDK imports

Move the two top-level SDK imports inside the functions that use them:

- `from openaq import OpenAQ` → move into `_get_client()`
- `from openaq.shared.exceptions import OpenAQError` → move into `fetch_openaq_data()` (used in `except` clauses)

The `register_source()` call at module level stays — it only runs if the module is successfully imported.

### 3. `src/aeolus/sources/purpleair.py` — lazy SDK imports

Move the top-level import:

- `from purpleair_api.PurpleAirAPIError import PurpleAirAPIError` → move into `fetch_purpleair_metadata()` and `fetch_purpleair_data()` (the two functions that catch it)

The `PurpleAirReadAPI` import in `_get_purpleair_client()` is already lazy — no change needed there.

### 4. `src/aeolus/sources/__init__.py` — guard imports

Wrap the two source imports in `try/except ImportError`:

```python
from . import (
    airnow,
    airqo,
    breathe_london,
    regulatory,
    sensor_community,
    sos,
)

try:
    from . import openaq
except ImportError:
    pass

try:
    from . import purpleair
except ImportError:
    pass
```

When the SDK is missing, the module-level `from openaq import OpenAQ` (now inside functions, but the module itself still does `from ..registry import register_source` etc.) — actually, with the SDK imports moved inside functions, the module will import fine. The `ImportError` guard is a safety net for any transitive import issues.

### 5. Tests — skip when SDK missing

Add `pytest.importorskip()` at the top of:

- `tests/test_openaq.py` — `pytest.importorskip("openaq")`
- `tests/test_purpleair.py` — `pytest.importorskip("purpleair_api")`

This ensures the test suite passes in conda-forge's build environment where these SDKs aren't available.

### 6. Conda-forge recipe — `recipe.yaml`

Create a conda-forge feedstock with recipe (using the newer `recipe.yaml` format). Key points:

- Source: PyPI sdist (standard for conda-forge Python packages)
- Build: `noarch: python` (pure Python package)
- Dependencies: only the 9 core deps (all confirmed on conda-forge)
- Test: `import aeolus` + run pytest with `-m "not integration"` and skipping openaq/purpleair tests
- License: GPL-3.0-or-later

The recipe itself will live in a separate `aeolus_aq-feedstock` repo managed by conda-forge. We'll prepare a draft locally for the submission PR.

## What This Does NOT Change

- **All existing pip installs work identically** — `pip install aeolus_aq` still pulls in all deps (users who want the old behaviour use `pip install aeolus_aq[all]`). Actually, this is a behaviour change: bare `pip install aeolus_aq` will no longer include OpenAQ/PurpleAir. This is acceptable because both require API keys anyway, and the `[all]` extra restores the previous behaviour.
- **The public API is unchanged** — `aeolus.download()`, `aeolus.list_sources()`, `aeolus.find_sites()` all work the same.
- **No new abstractions** — this follows the existing lazy-import pattern already used in `purpleair.py`.
- **CI/CD is unaffected** — the `dev` extra includes both SDKs, so GitHub Actions tests everything.

## Future Work

When `openaq` and `purpleair-api` get conda-forge feedstocks, they can be added as optional dependencies in the conda recipe (using `run_constrained` or as extras). No code changes needed — just a recipe update.
