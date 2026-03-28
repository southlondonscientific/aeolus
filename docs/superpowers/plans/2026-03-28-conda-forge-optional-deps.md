# Conda-forge Optional Dependencies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `openaq` and `purpleair-api` optional dependencies so `aeolus_aq` can be packaged for conda-forge.

**Architecture:** Move SDK imports from module-level to inside functions. Guard source registration in `sources/__init__.py` with `try/except ImportError`. Restructure `pyproject.toml` extras. Add `pytest.importorskip` to test files.

**Tech Stack:** Python packaging (`pyproject.toml` extras), pytest (`importorskip`), conda-forge (`recipe.yaml`)

**Spec:** `docs/superpowers/specs/2026-03-28-conda-forge-optional-deps-design.md`

---

### Task 1: Make OpenAQ SDK imports lazy

**Files:**
- Modify: `src/aeolus/sources/openaq.py:32-33` (top-level imports)
- Modify: `src/aeolus/sources/openaq.py:66` (`_get_client` function)
- Modify: `src/aeolus/sources/openaq.py:229-232` (`fetch_openaq_data` try/except)
- Modify: `src/aeolus/sources/openaq.py:294` (second try/except in same function)

- [ ] **Step 1: Remove top-level SDK imports**

In `src/aeolus/sources/openaq.py`, remove lines 32-33:

```python
from openaq import OpenAQ
from openaq.shared.exceptions import OpenAQError
```

- [ ] **Step 2: Add lazy import in `_get_client()`**

In `_get_client()`, add the import at the top of the function body (before the `global _client` line):

```python
def _get_client() -> "OpenAQ":
    """
    Get an OpenAQ client instance (reuses existing client).

    Supports both OPENAQ_API_KEY (Aeolus convention) and OPENAQ-API-KEY (SDK convention).

    Returns:
        OpenAQ: Configured client instance

    Raises:
        ValueError: If no API key is found
    """
    from openaq import OpenAQ

    global _client

    # Reuse existing client if available
    if _client is not None:
        return _client

    # Support both env var conventions
    api_key = os.getenv("OPENAQ_API_KEY") or os.getenv("OPENAQ-API-KEY")

    if not api_key:
        raise ValueError(
            "OpenAQ API key required. Set OPENAQ_API_KEY environment variable. "
            "Get a free key at: https://openaq.org/"
        )

    _client = OpenAQ(api_key=api_key, auto_wait=True)
    return _client
```

- [ ] **Step 3: Add lazy import in `fetch_openaq_data()` for exception handling**

In `fetch_openaq_data()`, add the import at the top of the function body (after the docstring):

```python
def fetch_openaq_data(
    sites: list[str], start_date: datetime, end_date: datetime
) -> pd.DataFrame:
    """..."""
    from openaq.shared.exceptions import OpenAQError

    client = _get_client()
    all_measurements = []
    # ... rest unchanged
```

- [ ] **Step 4: Run OpenAQ tests to verify nothing broke**

Run: `source .venv/bin/activate && pytest tests/test_openaq.py -v`
Expected: All tests PASS (the SDK is installed in dev venv)

- [ ] **Step 5: Commit**

```bash
git add src/aeolus/sources/openaq.py
git commit -m "refactor: make openaq SDK imports lazy for optional dependency support"
```

---

### Task 2: Make PurpleAir SDK imports lazy

**Files:**
- Modify: `src/aeolus/sources/purpleair.py:45` (top-level import)
- Modify: `src/aeolus/sources/purpleair.py:135-215` (`fetch_purpleair_metadata`)
- Modify: `src/aeolus/sources/purpleair.py:291-438` (`fetch_purpleair_data`)

- [ ] **Step 1: Remove top-level SDK import**

In `src/aeolus/sources/purpleair.py`, remove line 45:

```python
from purpleair_api.PurpleAirAPIError import PurpleAirAPIError
```

- [ ] **Step 2: Add lazy import in `fetch_purpleair_metadata()`**

Add the import at the top of the function body (after the docstring):

```python
@retry_on_network_error
def fetch_purpleair_metadata(**filters) -> pd.DataFrame:
    """..."""
    from purpleair_api.PurpleAirAPIError import PurpleAirAPIError

    try:
        client = _get_purpleair_client()
    # ... rest unchanged
```

- [ ] **Step 3: Add lazy import in `fetch_purpleair_data()`**

Add the import at the top of the function body (after the docstring):

```python
@retry_on_network_error
def fetch_purpleair_data(
    sites: list[str],
    start_date: datetime,
    end_date: datetime,
    raw: bool = False,
    include_flagged: bool = True,
) -> pd.DataFrame:
    """..."""
    from purpleair_api.PurpleAirAPIError import PurpleAirAPIError

    try:
        client = _get_purpleair_client()
    # ... rest unchanged
```

- [ ] **Step 4: Run PurpleAir tests to verify nothing broke**

Run: `source .venv/bin/activate && pytest tests/test_purpleair.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/aeolus/sources/purpleair.py
git commit -m "refactor: make purpleair-api SDK imports lazy for optional dependency support"
```

---

### Task 3: Guard source imports in `sources/__init__.py`

**Files:**
- Modify: `src/aeolus/sources/__init__.py:29-38`

- [ ] **Step 1: Replace the import block**

Replace the current import block with guarded imports for openaq and purpleair:

```python
# Import source modules to trigger their registration
# As we add more sources, import them here
from . import (
    airnow,  # noqa: F401
    airqo,  # noqa: F401
    breathe_london,  # noqa: F401
    regulatory,  # noqa: F401
    sensor_community,  # noqa: F401
    sos,  # noqa: F401
)

# Optional sources — SDK may not be installed (e.g. conda-forge)
try:
    from . import openaq  # noqa: F401
except ImportError:
    pass

try:
    from . import purpleair  # noqa: F401
except ImportError:
    pass
```

Update `__all__` to keep both names (they're still valid when installed):

```python
__all__ = [
    "airnow",
    "airqo",
    "breathe_london",
    "openaq",
    "purpleair",
    "regulatory",
    "sensor_community",
    "sos",
]
```

- [ ] **Step 2: Run full test suite to verify nothing broke**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/aeolus/sources/__init__.py
git commit -m "refactor: guard openaq and purpleair imports for optional dependency support"
```

---

### Task 4: Add `pytest.importorskip` to test files

**Files:**
- Modify: `tests/test_openaq.py:10` (add importorskip before SDK import)
- Modify: `tests/test_purpleair.py:13` (add importorskip before SDK import)

- [ ] **Step 1: Add importorskip to `tests/test_openaq.py`**

Add `pytest.importorskip` before the `from openaq...` import at the top of the file. Replace line 11 (`from openaq.shared.exceptions import OpenAQError`):

```python
import pytest

openaq_mod = pytest.importorskip("openaq", reason="openaq SDK not installed")
from openaq.shared.exceptions import OpenAQError
```

- [ ] **Step 2: Add importorskip to `tests/test_purpleair.py`**

Add `pytest.importorskip` before the `from purpleair_api...` import at the top of the file. Replace line 13 (`from purpleair_api.PurpleAirAPIError import PurpleAirAPIError`):

```python
import pytest

pytest.importorskip("purpleair_api", reason="purpleair-api SDK not installed")
from purpleair_api.PurpleAirAPIError import PurpleAirAPIError
```

- [ ] **Step 3: Run full test suite to verify nothing broke**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS (SDKs are installed in dev venv)

- [ ] **Step 4: Commit**

```bash
git add tests/test_openaq.py tests/test_purpleair.py
git commit -m "test: skip openaq and purpleair tests when SDKs not installed"
```

---

### Task 5: Restructure `pyproject.toml` dependencies

**Files:**
- Modify: `pyproject.toml:10-23` (dependencies and optional-dependencies)

- [ ] **Step 1: Move SDK deps to optional extras**

Remove `openaq` and `purpleair-api` from `dependencies` and add new extras:

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
progress = [
    "tqdm>=4.60",
]
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
docs = [
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.5.0",
    "mkdocstrings[python]>=0.24.0",
]
```

- [ ] **Step 2: Reinstall in dev mode to verify**

Run: `source .venv/bin/activate && pip install -e ".[dev]"`
Expected: All deps install successfully

- [ ] **Step 3: Run full test suite**

Run: `pytest -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat: make openaq and purpleair-api optional dependencies

Moves both SDKs to optional extras to unblock conda-forge packaging.
Install with: pip install aeolus_aq[all] for full functionality."
```

---

### Task 6: Test graceful degradation without SDKs

This task verifies the whole change works end-to-end by temporarily uninstalling the optional SDKs.

- [ ] **Step 1: Uninstall optional SDKs**

Run: `source .venv/bin/activate && pip uninstall openaq purpleair-api -y`

- [ ] **Step 2: Verify `import aeolus` works**

Run: `python -c "import aeolus; print(aeolus.list_sources())"`
Expected: Prints a list of sources WITHOUT `OPENAQ` and `PURPLEAIR`. Should include AURN, SAQN, etc.

- [ ] **Step 3: Verify helpful error for missing source**

Run: `python -c "import aeolus; aeolus.download('OPENAQ', ['123'], last='7d')"`
Expected: `ValueError: Unknown source: OPENAQ` with list of available sources.

- [ ] **Step 4: Verify tests skip correctly**

Run: `pytest tests/test_openaq.py tests/test_purpleair.py -v`
Expected: All tests SKIPPED with reason "openaq SDK not installed" / "purpleair-api SDK not installed"

- [ ] **Step 5: Verify remaining tests pass**

Run: `pytest --ignore=tests/test_openaq.py --ignore=tests/test_purpleair.py -v`
Expected: All tests PASS

- [ ] **Step 6: Reinstall optional SDKs**

Run: `pip install -e ".[dev]"`

- [ ] **Step 7: Verify full test suite passes again**

Run: `pytest -v`
Expected: All tests PASS (including openaq and purpleair)

---

### Task 7: Create conda-forge recipe draft

**Files:**
- Create: `conda-forge/recipe.yaml`

- [ ] **Step 1: Create the recipe directory**

Run: `mkdir -p conda-forge`

- [ ] **Step 2: Write the recipe**

Create `conda-forge/recipe.yaml`:

```yaml
schema_version: 1

context:
  name: aeolus_aq
  version: "0.4.0"

package:
  name: ${{ name }}
  version: ${{ version }}

source:
  url: https://pypi.org/packages/source/a/${{ name }}/${{ name }}-${{ version }}.tar.gz
  # sha256 will be filled in after PyPI upload

build:
  noarch: python
  script: python -m pip install . --no-deps --no-build-isolation -vv

requirements:
  host:
    - python >=3.11
    - pip
  run:
    - python >=3.11
    - pandas >=2.3.3
    - rdata >=0.11
    - requests >=2.32.5
    - tenacity >=8.2.0
    - matplotlib-base >=3.7.0
    - python-dotenv >=1.2.1
    - numpy >=1.24.0
    - scipy >=1.10.0
    - pyarrow >=14.0.0

tests:
  - python:
      imports:
        - aeolus
      pip_check: true
  - script: pytest tests/ -v -m "not integration and not live" --ignore=tests/test_openaq.py --ignore=tests/test_purpleair.py
    requirements:
      run:
        - pytest

about:
  home: https://github.com/southlondonscientific/aeolus
  summary: Download and standardise air quality data from UK and international monitoring networks
  license: GPL-3.0-or-later
  license_file: LICENSE

extra:
  recipe-maintainers:
    - ruaraidhdobson
```

Note: `matplotlib-base` is the conda-forge equivalent of `matplotlib` (avoids pulling in the full GUI backend).

- [ ] **Step 3: Commit**

```bash
git add conda-forge/recipe.yaml
git commit -m "feat: add conda-forge recipe draft for feedstock submission"
```

---

### Task 8: Update CLAUDE.md and documentation

**Files:**
- Modify: `CLAUDE.md` (update dependency table and install instructions)

- [ ] **Step 1: Update the dependency table in CLAUDE.md**

In the Networks table, no changes needed. In the Portals table, add a note about optional install:

Add a new section after the Portals table:

```markdown
### Optional SDK Dependencies

OpenAQ and PurpleAir require optional SDK packages not available on conda-forge:

| Extra | Install command | Provides |
|-------|----------------|----------|
| `openaq` | `pip install aeolus_aq[openaq]` | OpenAQ portal access |
| `purpleair` | `pip install aeolus_aq[purpleair]` | PurpleAir portal access |
| `all` | `pip install aeolus_aq[all]` | All optional sources |

For conda users: `conda install aeolus_aq` then `pip install openaq purpleair-api` for portal sources.
```

- [ ] **Step 2: Update the Common Commands section**

Add conda install to the commands section:

```bash
# Install from conda-forge
conda install -c conda-forge aeolus_aq

# Install with all optional sources (pip only)
pip install aeolus_aq[all]
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document optional dependencies and conda install"
```
