# v0.5.0 Plan 4: Docs, Notebooks, Migration Guide and the `0.5.0a1` Alpha — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every user-facing document, notebook and example describe the v0.5.0 contract (13-column schema, `network`/`qa_code`/`qa_tier`/`ratification_stage`/`backend`, UTC interval-start time convention, faithful units), give consumers a migration guide, and cut `0.5.0a1` to PyPI for Hermes, RHEA, Clara and Argus to migrate against.

**Architecture:** Documentation is treated as code: a small offline test (`tests/test_docs_vocabulary.py`) fails on pre-0.5.0 vocabulary anywhere in the user-facing docs and notebooks, so the rewrite is red-first and cannot silently regress. The eight notebooks are edited to the new column names, then **executed live** with `jupyter nbconvert --execute` (the outputs committed are what a user would see; feedback rule: notebooks must be validated with live API access). The alpha is a version bump + CHANGELOG heading + tag; the existing `release.yml` publishes to PyPI after the offline suite passes.

**Tech Stack:** mkdocs-material + mkdocstrings (`uv run --extra docs mkdocs build --strict`), `nbconvert`/`ipykernel` (not in the venv — run with `uv run --with nbconvert --with ipykernel --with matplotlib --with geopandas`), setuptools build via `uv build`, GitHub Actions `release.yml` (tag `v*` → tests → PyPI trusted publishing).

**Spec:** `docs/dev/v050_design.md` §3 (wire format), §4 (enums), §12 (API surface & migration), §14 (rollout steps 3–4), §17.1 (mirrors), §17.10 (units/time audit). Roadmap row: `docs/superpowers/plans/2026-09-21-v050-contract-core.md` (row 4 of the plan table). Plans 1–3 are merged (PRs #15, #16, #17).

## Global Constraints

- British English throughout (normalise, summarise, visualisation).
- Public data schema is exactly `aeolus.schema.DATA_COLUMNS` (13 columns, in this order): `site_code, network, date_time, measurand, value, units, qa_code, qa_tier, ratification_stage, backend, source_network, ratification, created_at`. Metadata schema is `aeolus.schema.METADATA_COLUMNS` (11): `site_code, site_name, latitude, longitude, network, country, instrument_class, provider, backend, measurands, source_network`.
- `qa_tier` values (frozen, spec §4): `reference_full_qc`, `reference_provisional`, `lcs_calibrated`, `lcs_factory_only`, `flagged`, `unknown`. `ratification_stage` values: `unratified`, `ratified`, `supplied`, `not_applicable`, or null.
- `source_network` and `ratification` are deprecated mirrors, removed in 1.0; `AEOLUS_LEGACY_COLUMNS=0` (or `aeolus.options.legacy_columns = False`) drops them. Docs may mention them only as deprecated mirrors.
- The legacy `ratification` mirror is derived by `aeolus.qa.legacy_ratification`: stage `ratified` → `Ratified`, `unratified` → `Provisional`, tier `lcs_calibrated` → `Indicative`, `lcs_factory_only` → `Validated`, `flagged` → `Invalid`, tier `unknown` with a stage → `Unvalidated`, otherwise `None`. Docs must not present these labels as what a network "marks" data as; they describe `qa_code`/`qa_tier` instead.
- `date_time` is tz-aware UTC and marks the START of the averaging interval (13:00 = [13:00, 14:00)). Units are as the network reports them; the one conversion is LAQN RData gases (ppb → µg/m³ at 20 °C, documented in `docs/sources/uk-networks.md`).
- Version strings live in TWO places and must agree: `pyproject.toml` `version = "..."` and `src/aeolus/__init__.py` `__version__ = "..."`. `CLAUDE.md` "Current Version" is the third, informational.
- Never print API keys. `.env` at the repo root holds them; CI has none. `AIRQO_API_KEY` is expired (user-owned item) — do not chase it; report honestly.
- Offline suite command (the only pytest command executors run unless a step says "live"): `uv run pytest tests/ -m "not live and not integration and not conformance" --no-cov -p no:cacheprovider -q` (~3 min).
- Docs build check: `uv run --extra docs mkdocs build --strict -q` (passes on `main` today; must still pass after every docs task).
- One commit per task, message body ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Branch: `feat/v050-docs-alpha` off `main` (`e88ee4e` or later).
- Publishing to PyPI (pushing the `v0.5.0a1` tag) is outward-facing and irreversible: **Task 9 stops and asks the user before pushing the tag.**

## What is stale today (survey, 2026-09-23)

| File | Stale content |
|---|---|
| `README.md:54` | example output shows the old `source_network` column and 8 columns; `:168` "marked as `Unvalidated`" |
| `docs/getting-started/quickstart.md:25-37` | 8-column table with `source_network`, `ratification` |
| `docs/getting-started/configuration.md` | lists only API keys; no `AEOLUS_LEGACY_COLUMNS`, `AEOLUS_CACHE_DIR`, `AEOLUS_CACHE_VOLATILE_TTL_S`, `AEOLUS_METADATA_TTL_S`, `AEOLUS_RDATA_BREAKER_FAILURES` |
| `docs/guide/overview.md:82-98` | already 13-column (Plan 1) — verify only |
| `docs/guide/downloading.md:75,93` | `summarise` columns and "distinguished by the `source_network` column" |
| `docs/guide/sources.md:96-175` | per-source "Data quality: Indicative/Unvalidated" bullets and table column |
| `docs/sources/airqo.md:9,63`, `breathe-london.md:9,62,104`, `sensor-community.md:9,140`, `sonitus.md:8`, `openaq.md:108`, `airnow.md:107`, `eea.md:62-64`, `purpleair.md:133`, `lmam.md:71` | `ratification='…'` statements, `source_network` groupbys, old EEA `ratification` table |
| `docs/dev/openair_comparison.md:71,264` | `source_network` in the site-identity row (it is in nav as "Coming from R/openair?") |
| `docs/api/index.md`, `mkdocs.yml` nav | no page for `aeolus.schema`, `aeolus.qa`, `aeolus.network_registry`, `aeolus.units`, `aeolus.cache` |
| `notebooks/02,03,04,05,06,07` | code cells use `source_network` / `ratification` (list in Task 6); notebook 02's kernelspec is `aeolus`, the others `python3`; all executed outputs predate v0.5.0 |
| `CLAUDE.md:283` | "Low-cost sensor data marked as `ratification='Unvalidated'`" |
| `CHANGELOG.md:8` | `## [Unreleased] — targeting v0.5.0` |
| `.github/workflows/release.yml` | GitHub Release is never marked pre-release |

---

### Task 1: Docs vocabulary guard (red first)

**Files:**
- Create: `tests/test_docs_vocabulary.py`

**Interfaces:**
- Produces: a pytest module every later docs/notebook task must keep green. No runtime code.

- [ ] **Step 1: Write the test**

```python
"""The user-facing docs and notebooks describe the v0.5.0 contract, not the 0.4 one.

Fails on pre-0.5.0 vocabulary so a docs rewrite cannot silently regress.
Developer notes (docs/dev, docs/superpowers), the CHANGELOG and the migration
guide are exempt: they legitimately talk about the old names.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

USER_DOCS = [
    ROOT / "README.md",
    ROOT / "CLAUDE.md",
    ROOT / "notebooks" / "README.md",
    *sorted((ROOT / "docs" / "getting-started").glob("*.md")),
    *sorted((ROOT / "docs" / "guide").glob("*.md")),
    *sorted((ROOT / "docs" / "sources").glob("*.md")),
    *sorted((ROOT / "docs" / "api").glob("*.md")),
    ROOT / "docs" / "index.md",
    ROOT / "docs" / "dev" / "openair_comparison.md",  # in the site nav
]
EXEMPT = {ROOT / "docs" / "guide" / "migrating-to-0.5.md"}
NOTEBOOKS = sorted((ROOT / "notebooks").glob("*.ipynb"))

# Phrases that only made sense before v0.5.0.
FORBIDDEN = [
    re.compile(r"8-column|eight columns|\b8 columns"),
    re.compile(r"ratification\s*=\s*['\"]"),           # ratification='Indicative' etc.
    re.compile(r"marked as `?(Unvalidated|Indicative|Provisional)`?"),
    re.compile(r"\*\*Data quality\*\*:\s*(Indicative|Unvalidated)"),
]
# `source_network` / `ratification` may appear only where the line says they are legacy mirrors.
LEGACY = re.compile(r"\bsource_network\b|\bratification\b(?!_stage)")
LEGACY_CONTEXT = re.compile(r"deprecated|mirror|legacy|1\.0|Migrat|migrat|AEOLUS_LEGACY_COLUMNS|ratification_stage")


def _offending_lines(text: str):
    for n, line in enumerate(text.splitlines(), 1):
        for pat in FORBIDDEN:
            if pat.search(line):
                yield n, line.strip()
        if LEGACY.search(line) and not LEGACY_CONTEXT.search(line):
            yield n, line.strip()


@pytest.mark.parametrize("path", [p for p in USER_DOCS if p.exists() and p not in EXEMPT], ids=lambda p: str(p.relative_to(ROOT)))
def test_user_docs_use_v050_vocabulary(path):
    bad = list(_offending_lines(path.read_text()))
    assert not bad, f"{path.relative_to(ROOT)} still uses pre-0.5.0 vocabulary:\n" + "\n".join(f"  {n}: {l}" for n, l in bad)


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_code_uses_v050_columns(path):
    nb = json.loads(path.read_text())
    bad = []
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue
        for line in "".join(cell["source"]).splitlines():
            if "source_network" in line or re.search(r"[\"']ratification[\"']", line):
                bad.append(f"cell {i}: {line.strip()}")
    assert not bad, f"{path.name} reads legacy columns:\n" + "\n".join(bad)


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_kernel_is_python3(path):
    nb = json.loads(path.read_text())
    assert nb["metadata"]["kernelspec"]["name"] == "python3", "kernelspec must be the portable 'python3'"


def test_version_strings_agree():
    import tomllib

    import aeolus

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert aeolus.__version__ == pyproject["project"]["version"]
    assert f"**Current Version:** {aeolus.__version__}" in (ROOT / "CLAUDE.md").read_text()
```

- [ ] **Step 2: Run it and confirm it is red for the right files**

Run: `uv run pytest tests/test_docs_vocabulary.py -q -p no:cacheprovider --no-cov 2>&1 | grep -E "^FAILED|passed|failed"`
Expected: FAIL for `README.md`, `CLAUDE.md`, `quickstart.md`, `downloading.md`, `sources.md`, most of `docs/sources/*.md`, `openair_comparison.md`; notebooks 02–07 (columns) and 02 (kernel); `test_version_strings_agree` PASSES (0.4.5.4 everywhere today). `overview.md` and `ratification.md` should already pass — if they fail, fix the regex, not the doc, unless the line is genuinely stale.

- [ ] **Step 3: Commit the red test alone**

```bash
git checkout -b feat/v050-docs-alpha main
git add tests/test_docs_vocabulary.py
git commit -m "test(docs): guard the user docs and notebooks against pre-0.5.0 vocabulary"
```

---

### Task 2: README, quick start, configuration, downloading guide

**Files:**
- Modify: `README.md:44-60` (example output), `README.md:168`, `README.md` schema table (~262-275, add a link to the migration guide)
- Modify: `docs/getting-started/quickstart.md:25-37`
- Modify: `docs/getting-started/configuration.md` (add an "Aeolus settings" section after the API keys)
- Modify: `docs/guide/downloading.md:75,93`
- Modify: `CLAUDE.md:283`
- Test: `tests/test_docs_vocabulary.py`

**Interfaces:**
- Consumes: `aeolus.schema.DATA_COLUMNS`, `aeolus.options.legacy_columns`, env vars `AEOLUS_LEGACY_COLUMNS`, `AEOLUS_CACHE_DIR`, `AEOLUS_CACHE_VOLATILE_TTL_S`, `AEOLUS_METADATA_TTL_S`, `AEOLUS_RDATA_BREAKER_FAILURES` (verify each name with `grep -rn "AEOLUS_" src/aeolus/*.py src/aeolus/sources/*.py` before documenting; document only those that exist, with the code's default).
- Produces: the README schema table is the canonical short description; the migration guide (Task 5) links to it.

- [ ] **Step 1: Produce a real example output for the README**

Run (live, AURN needs no key):
```bash
uv run python -c "
import aeolus, pandas as pd
from datetime import datetime
pd.set_option('display.width', 200)
d = aeolus.download('AURN', sites=['MY1'], start_date=datetime(2024,1,1), end_date=datetime(2024,1,1,3))
print(d[['site_code','network','date_time','measurand','value','units','qa_code','qa_tier','ratification_stage','backend']].head(4).to_string())
"
```
Paste the printed table into `README.md` in place of lines 53–58, adding one line under it: `(plus the deprecated mirrors source_network and ratification, and created_at — 13 columns in all; see the schema table below)`.

- [ ] **Step 2: Rewrite README line 168 and the schema table**

Replace `**Note:** Data is marked as `Unvalidated` since this is citizen science data without formal QA/QC processes.` with:
`**Note:** Sensor.Community publishes no per-row quality flag, so `qa_code` is null and `qa_tier` is `unknown` (`ratification_stage = not_applicable`).`

In the schema table keep the 13 rows already there; append a row for `created_at` if missing, and after the table add:
`Migrating from 0.4? See [Migrating to 0.5](docs/guide/migrating-to-0.5.md).`

- [ ] **Step 3: Rewrite the quick start table (`docs/getting-started/quickstart.md:25-37`)**

```markdown
## Understanding the Output

Every download returns the same 13 columns (`aeolus.schema.DATA_COLUMNS`):

| Column | Description |
|--------|-------------|
| `site_code` | Unique identifier for the monitoring site |
| `network` | Which network produced the data (`AURN`, `LAQN`, `EEA`, ...) |
| `date_time` | Start of the averaging interval, tz-aware UTC (`13:00` covers 13:00–14:00) |
| `measurand` | Pollutant name (PM2.5, NO2, O3, ...) |
| `value` | Measured concentration |
| `units` | As the network reports them (`ug/m3`; `mg/m3` for CO; `ppb` for AirNow gases) |
| `qa_code` | The network's own quality token, verbatim (null where it publishes none) |
| `qa_tier` | Cross-network quality tier: `reference_full_qc`, `reference_provisional`, `lcs_calibrated`, `lcs_factory_only`, `flagged`, `unknown` |
| `ratification_stage` | `unratified`, `ratified`, `supplied`, `not_applicable` or null |
| `backend` | Which fetcher served the row (`RDATA`, `SOS`, `ERG_REST`, `EEA_E1A`, ...) |
| `source_network` | Deprecated mirror of `network` (removed in 1.0) |
| `ratification` | Deprecated mirror derived from the three QA columns (removed in 1.0) |
| `created_at` | When the record was fetched (UTC) |

Set `AEOLUS_LEGACY_COLUMNS=0` to drop the two mirrors. The [Data Quality](../guide/ratification.md) guide explains the three QA columns network by network.
```

- [ ] **Step 4: Add the settings section to `configuration.md`**

After the API-key sections, add (fill each default from the code — `grep -n "AEOLUS_" src/aeolus/options.py src/aeolus/cache.py src/aeolus/sources/regulatory.py`):

```markdown
## Aeolus settings

All optional. Read once at import (or first use) from the environment.

| Variable | Default | Effect |
|---|---|---|
| `AEOLUS_LEGACY_COLUMNS` | `1` | `0` drops the deprecated `source_network` and `ratification` mirrors — use it to prove your code has migrated to 0.5 |
| `AEOLUS_CACHE_DIR` | `~/.cache/aeolus` | Where downloads are cached (a versioned sub-directory per cache format) |
| `AEOLUS_CACHE_VOLATILE_TTL_S` | (code default) | How long a download whose window touches "now" is served from cache |
| `AEOLUS_METADATA_TTL_S` | `86400` | How long AURN-family site metadata (the `ratified_to` join) is memoised |
| `AEOLUS_RDATA_BREAKER_FAILURES` | `3` | Consecutive failures before an openair RData host is skipped for the rest of the process |

The same switches exist in code on `aeolus.options` (for example `aeolus.options.legacy_columns = False`).
```
Delete any row whose variable does not exist in the code.

- [ ] **Step 5: Fix `downloading.md` and `CLAUDE.md`**

`downloading.md:75`: `# Shows: site_code, network, measurand, start, end, records, valid, data_capture`.
`downloading.md:93`: `The resulting DataFrame contains data from all sources, distinguished by the `network` column (and `backend`, which says which fetcher served each row).`
`CLAUDE.md:283`: replace with `- Networks that publish no per-row flag (LAQN, LMAM, Sensor.Community, Sonitus, OpenAQ) have null `qa_code` and `qa_tier = unknown`; low-cost networks carry `ratification_stage = not_applicable``.

- [ ] **Step 6: Run the guard for these files and the docs build**

Run: `uv run pytest tests/test_docs_vocabulary.py -q -p no:cacheprovider --no-cov -k "README or CLAUDE or quickstart or configuration or downloading" 2>&1 | tail -3`
Expected: all PASS.
Run: `uv run --extra docs mkdocs build --strict -q && echo OK`
Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add README.md CLAUDE.md docs/getting-started docs/guide/downloading.md
git commit -m "docs: README, quick start, configuration and downloading guide describe the 0.5 schema"
```

---

### Task 3: Sources guide and per-source pages speak `qa_code`/`qa_tier`

**Files:**
- Modify: `docs/guide/sources.md:90-176`
- Modify: `docs/sources/airqo.md`, `breathe-london.md`, `sensor-community.md`, `sonitus.md`, `openaq.md`, `airnow.md`, `eea.md`, `purpleair.md`, `lmam.md` (the lines listed in the survey table; each page gets one consistent "Data quality" section)
- Modify: `docs/dev/openair_comparison.md:71,264`
- Test: `tests/test_docs_vocabulary.py`

**Interfaces:**
- Consumes: the registry facts below (from `aeolus.network_registry.list_network_specs()`, 2026-09-23). Verify with `uv run python -c "from aeolus.network_registry import get_network_spec as g; print(g('PURPLEAIR').qa_code_vocabulary)"` before writing.

| Network | `instrument_class` | `qa_code` values → `qa_tier` | default `ratification_stage` |
|---|---|---|---|
| AURN | reference | `verified` → reference_full_qc / ratified; `unverified` → reference_provisional / unratified | per row |
| SAQN, WAQN, NI, AQE | mixed | `Ratified` → reference_full_qc; `Provisional` → reference_provisional; `Supplied` (in the vocabulary, never emitted yet) | per row |
| LAQN | reference | none published → null, `unknown` | null |
| LMAM | mixed | none published → null, `unknown` | `supplied` |
| EEA | reference | `"1"` verified → reference_full_qc / ratified; `"2"`, `"3"` → reference_provisional / unratified; `"0"` (Airbase) → unknown / null | per row |
| AIRNOW | reference | `Provisional` → reference_provisional / unratified | unratified |
| BREATHE_LONDON | LCS | `P` → lcs_calibrated / unratified; null where the API gives no status → unknown | not_applicable |
| PURPLEAIR | LCS | `Validated`, `Single Channel (A)`/`(B)`, `Below Detection Limit` → lcs_factory_only; `Channel Disagreement`, `Sensor Saturation`, `Invalid` → flagged; `Unvalidated` → unknown | not_applicable |
| AIRQO | LCS | `calibrated` → lcs_calibrated; `raw` → lcs_factory_only (not wired until the key is renewed → null, unknown) | not_applicable |
| SENSOR_COMMUNITY | LCS | none → null, `unknown` | not_applicable |
| SONITUS | mixed | none → null, `unknown` | not_applicable |
| OPENAQ | mixed | none → null, `unknown` | null |

- [ ] **Step 1: Rewrite the "Data quality" bullets in `docs/guide/sources.md`**

For each source block (lines ~96–154) replace `- **Data quality**: Indicative (...)` / `Unvalidated (...)` with a `qa_tier` statement, e.g. PurpleAir: `- **Data quality**: `qa_tier = lcs_factory_only` (channel-agreement label in `qa_code`; disagreeing channels are `flagged`)`; Breathe London: `- **Data quality**: `qa_tier = lcs_calibrated` where the API reports status `P`, else `unknown``; AirQo, Sensor.Community, Sonitus: `- **Data quality**: no per-row flag published — `qa_code` null, `qa_tier = unknown``.

In the comparison table (~lines 165–176) rename the column `Data Quality` → `qa_tier` and fill from the table above (`reference_full_qc / reference_provisional` for the regulatory networks, `unknown` for LAQN/LMAM/Sensor.Community/Sonitus/OpenAQ, `lcs_factory_only` PurpleAir, `lcs_calibrated` Breathe London, `unknown` AirQo until wired).

- [ ] **Step 2: Give every `docs/sources/*.md` page one "Data quality" section**

Template (adapt the two facts per page from the table; keep any existing correct `qa_code` paragraph from Plan 2 — `uk-networks.md`, `airnow.md`, `breathe-london.md:109`, `eea.md:89`, `purpleair.md:145` already have one; merge, do not duplicate):

```markdown
## Data quality

`qa_code` is <the network's own token, or "null: the network publishes no per-row flag">.
`qa_tier` is <value(s)> and `ratification_stage` is <value(s)>.
<One sentence on what that means in practice, e.g. "Treat the data as indicative; it has been calibrated against reference monitors but is not ratified.">
See the [Data Quality guide](../guide/ratification.md) for filtering by tier.
```

Specific line fixes:
- `airqo.md:9,63`, `breathe-london.md:9,62`, `sensor-community.md:9,140`, `sonitus.md:8`: replace the `Indicative`/`Unvalidated` header bullet with the `qa_tier` value and delete the `ratification='…'` sentence.
- `breathe-london.md:104`: `data.groupby(['network', 'measurand'])['value'].mean()`.
- `openaq.md:108`: `Check the `network` and `backend` columns to understand provenance (OpenAQ rows carry `network = "OPENAQ"`; the originating provider is not exposed per row in 0.5).`
- `airnow.md:107`: `AirNow rows carry `qa_code = "Provisional"` (`qa_tier = reference_provisional`, `ratification_stage = unratified`) because:` and keep the reasons.
- `eea.md:62-70`: replace the `ratification` table with the `Verification` → `qa_code`/`qa_tier` table from the row above (the existing line 89 paragraph can move up into it).
- `purpleair.md:133`: `print(data['qa_code'].value_counts())`.
- `lmam.md:71`: reword so `source_network` becomes `network`.
- `docs/dev/openair_comparison.md:71`: `network` in the `summarise` column list; `:264`: `| Site identity | `site` column | `site_code` + `network` columns |`.

- [ ] **Step 3: Run the guard and the docs build**

Run: `uv run pytest tests/test_docs_vocabulary.py -q -p no:cacheprovider --no-cov -k "sources or openair" 2>&1 | tail -3` → all PASS.
Run: `uv run --extra docs mkdocs build --strict -q && echo OK` → `OK`.

- [ ] **Step 4: Commit**

```bash
git add docs/guide/sources.md docs/sources docs/dev/openair_comparison.md
git commit -m "docs: sources guide and per-source pages describe qa_code and qa_tier"
```

---

### Task 4: API reference pages for the contract modules

**Files:**
- Create: `docs/api/schema.md`
- Modify: `docs/api/index.md` (module table), `mkdocs.yml` (nav under "API Reference")
- Test: `uv run --extra docs mkdocs build --strict`

**Interfaces:**
- Consumes: public names in `aeolus.schema` (`DATA_COLUMNS`, `METADATA_COLUMNS`, `finalise_data_frame`, `finalise_metadata_frame`, `public_data_columns`, `empty_public_frame`), `aeolus.qa` (`QaTier`, `RatificationStage`, `derive_qa`, `legacy_ratification` — check the enum names with `grep -n "^class\|^def" src/aeolus/qa.py`), `aeolus.network_registry` (`NetworkSpec`, `get_network_spec`, `list_network_specs`, `route_for`, `spec_for_source`), `aeolus.units` (`canonical_unit`, `canonical_units`), `aeolus.cache` (`cache_info`, `clear_cache` — check names with `grep -n "^def " src/aeolus/cache.py`).

- [ ] **Step 1: Write `docs/api/schema.md`**

```markdown
# aeolus.schema, aeolus.qa, aeolus.network_registry

The v0.5.0 contract: the public column set, the QA enums, and the registry that maps each network's own quality tokens onto them.

## Schema

::: aeolus.schema
    options:
      members: [DATA_COLUMNS, METADATA_COLUMNS, public_data_columns, finalise_data_frame, finalise_metadata_frame]
      show_root_heading: false

## QA enums and derivation

::: aeolus.qa
    options:
      show_root_heading: false

## Network registry

Each network's identity, QA vocabulary, ratification timing and licence live in `src/aeolus/data/qa_vocabularies/<CODE>.yaml` and are read through this module.

::: aeolus.network_registry
    options:
      members: [NetworkSpec, get_network_spec, list_network_specs, route_for, spec_for_source]
      show_root_heading: false

## Units and cache

::: aeolus.units
    options:
      show_root_heading: false

::: aeolus.cache
    options:
      show_root_heading: false
```
If `mkdocs build --strict` rejects a `members:` name, remove that name (do not invent one).

- [ ] **Step 2: Wire the nav and the index table**

`mkdocs.yml` nav, under `API Reference`, after `aeolus.metrics: api/metrics.md`: `      - aeolus.schema / qa / registry: api/schema.md`.
`docs/api/index.md` module table, add: `| [`aeolus.schema`, `aeolus.qa`, `aeolus.network_registry`](schema.md) | The 0.5 contract: public columns, QA tiers, per-network vocabularies |`.

- [ ] **Step 3: Build strictly**

Run: `uv run --extra docs mkdocs build --strict -q && echo OK` → `OK` (mkdocstrings warnings about missing docstrings are errors under `--strict`; add a one-line docstring to the offending public function in `src/` rather than loosening the build).

- [ ] **Step 4: Commit**

```bash
git add docs/api/schema.md docs/api/index.md mkdocs.yml src/aeolus
git commit -m "docs(api): reference pages for schema, qa, network_registry, units and cache"
```

---

### Task 5: Migration guide

**Files:**
- Create: `docs/guide/migrating-to-0.5.md`
- Modify: `mkdocs.yml` nav (User Guide, after "Data Quality (Ratification)": `      - Migrating to 0.5: guide/migrating-to-0.5.md`), `docs/index.md` (one link line near the top), `docs/guide/ratification.md` (one link line)
- Test: `tests/test_docs_vocabulary.py` (this file is exempt; the build is the check)

**Interfaces:**
- Consumes: `CHANGELOG.md` `[Unreleased]` sections (lines 8–88 today) — every "please re-baseline" bullet must appear in the guide's re-baseline table; `docs/dev/v046_fix_plan.md` "Re-baseline" lines 53, 66, 85, 103.
- Produces: the page consumers (Hermes, RHEA, Clara, Argus) are pointed at in Task 9.

- [ ] **Step 1: Write the guide**

```markdown
# Migrating to 0.5

0.5.0 is a **"new schema, corrected numbers — please re-baseline"** release. Nothing you fetched with 0.4 should be assumed equal to what 0.5 returns. This page lists what changed, how to find each change in your code, and how to prove you have migrated.

## Ten-minute checklist

1. Install `aeolus_aq>=0.5.0a1` (PyYAML is a new runtime dependency; conda users need `pyyaml` too).
2. Run your code with `AEOLUS_LEGACY_COLUMNS=0`. Anything that reads `source_network` or `ratification` breaks here — fix it with the column map below.
3. Rename: `source_network` → `network`. If you also need to know *which fetcher* produced a row, read `backend`.
4. Replace every test on `ratification` with a test on `qa_tier` or `ratification_stage` (table below). Keep `qa_code` if you want the network's own word.
5. Re-fetch anything you store: values changed for LAQN gases, SOS/Sonitus CO, AirNow/SOS sentinels, EEA past years, monthly/quarterly/annual `time_average` labels, and the `ratification` mirror for wired networks.
6. Clear or ignore caches written by 0.4: 0.5 uses `~/.cache/aeolus/v4/` and never serves older entries.

## Column map

| 0.4 | 0.5 | Notes |
|---|---|---|
| `source_network` | `network` | mirror kept until 1.0, `DeprecationWarning` once per process |
| `ratification` | `qa_code` + `qa_tier` + `ratification_stage` | mirror kept until 1.0, now *derived* from the three columns |
| — | `backend` | `RDATA`, `SOS`, `ERG_REST`, `EEA_E1A`/`EEA_E2A`/`EEA_AIRBASE`, ... |
| (metadata) `source_network` | `network` | plus new `country`, `instrument_class`, `provider`, `backend`, `measurands` |

## The `ratification` mirror changed meaning

The mirror is now computed from `qa_tier` and `ratification_stage`:
`ratified` → `Ratified`; `unratified` → `Provisional`; tier `lcs_calibrated` → `Indicative`; `lcs_factory_only` → `Validated`; `flagged` → `Invalid`; tier `unknown` with a stage → `Unvalidated`; otherwise `None`.

Concretely, per network:

| Network | 0.4 `ratification` | 0.5 `ratification` (mirror) | Read instead |
|---|---|---|---|
| AURN, SAQN, WAQN, NI, AQE | always `None` | `Ratified` / `Provisional` per site, pollutant and date (`ratified_to` from the openair metadata) | `ratification_stage` |
| AURN-SOS etc. / `get_current()` | `None` | `Provisional` | `ratification_stage` |
| EEA | `Verified`/`Preliminary`/`Not verified` (and inverted before 0.4.6) | `Ratified` / `Provisional`; Airbase rows `None` | `qa_code` (`"1"`, `"2"`, `"3"`, `"0"`) |
| PurpleAir | channel labels | `Validated` / `Invalid` | `qa_code` (the label) |
| Breathe London | `Indicative` synthesised when absent | `Indicative` (`P`) or `Unvalidated` (no status) | `qa_code` |
| AirNow | `Provisional` | `Provisional` | `ratification_stage` |
| LAQN, LMAM, Sensor.Community, Sonitus, OpenAQ, AirQo | various | `Unvalidated` or `None` | `qa_tier` (`unknown`) |

## Values that changed (re-baseline)

| Path | What changed | Since |
|---|---|---|
| `LAQN` (RData route) gases NO2, NOx, NO, O3, SO2, CO | were ppb/ppm labelled `ug/m3`/`mg/m3`; now converted with Defra's 20 °C factors (×1.9125 NO2/NOx, ×1.9957 O3, ×2.6609 SO2, ×1.1642 CO, ×1.2474 NO). MY1 annual NO2 2023: 21.8 → 41.7 | 0.5.0 |
| SOS sources and Sonitus CO | unit relabelled `ug/m3` → `mg/m3`, values unchanged | 0.5.0 |
| SOS unit strings | `ug/m-3` → `ug/m3` | 0.5.0 |
| AirNow, SOS | `-999`/sentinel rows dropped instead of stored | 0.5.0 |
| EEA, any year before the up-to-date feed | previously **empty**; now served from the verified archive (E1a) or Airbase, with `backend` saying which | 0.5.0 |
| EEA timestamps | converted from the EEA's UTC+1 (Ireland's archive: UTC; Italy's feed: local) — one-hour shift vs 0.4 | 0.5.0 |
| Sonitus timestamps | were bin end; now bin start (−15 min / −1 h) | 0.5.0 |
| `time_average(freq="ME"/"QE"/"YE"/"W")` | rows labelled at period start (were end) | 0.5.0 |
| data capture, period AQI | shift with the above | 0.5.0 |

## Behaviour changes that are not value changes

- `download()`, `fetch()`, `find_sites()`, `get_current()` accept `network=` as an alias for the first argument.
- `summarise()` and `time_average()` report `network` and accept 0.4 frames.
- `get_source_info()` reports `status` (`stable` | `experimental`) and `status_note`; **EEA is experimental** and raises one `AeolusExperimentalWarning` per process.
- Each AURN-family download fetches that network's metadata once per process (memoised `AEOLUS_METADATA_TTL_S`, default a day) for the ratification join.
- Retries now actually retry; a dead openair host is skipped after `AEOLUS_RDATA_BREAKER_FAILURES` failures.

## Proving you have migrated

```bash
AEOLUS_LEGACY_COLUMNS=0 pytest        # your suite, with the mirrors off
python -W error::DeprecationWarning -c "import aeolus; ..."   # or turn the one-time warning into an error
```

## Consumers

Hermes, RHEA, Clara and Argus: pin `aeolus_aq==0.5.0a1`, run with the mirrors off, and re-pull stored readings for the paths in the re-baseline table. Argus's write path (guarded upsert + `readings_history`) is designed for exactly this re-pull; see `argus/docs/2026-09-20-write-path-upsert-handoff.md`.
```
Check every factual line against `CHANGELOG.md` before committing; where they disagree, the CHANGELOG (written when the change landed) wins and the guide is corrected. Check the cache version with `grep _CACHE_VERSION src/aeolus/cache.py` (the CHANGELOG line 76 still says `v3`; if the code says `v4`, fix the CHANGELOG line too).

- [ ] **Step 2: Wire the nav and links; build strictly**

`mkdocs.yml`: add the nav entry. `docs/index.md`: after the first paragraph add `Upgrading from 0.4? Read [Migrating to 0.5](guide/migrating-to-0.5.md) first.` `docs/guide/ratification.md`: at the end add `Coming from the 0.4 `ratification` column? See [Migrating to 0.5](migrating-to-0.5.md).`
Run: `uv run --extra docs mkdocs build --strict -q && echo OK` → `OK`.
Run: `uv run pytest tests/test_docs_vocabulary.py -q -p no:cacheprovider --no-cov 2>&1 | tail -2` → docs tests PASS (notebook tests still red).

- [ ] **Step 3: Commit**

```bash
git add docs/guide/migrating-to-0.5.md docs/index.md docs/guide/ratification.md mkdocs.yml CHANGELOG.md
git commit -m "docs: migration guide for 0.5 (column map, mirror semantics, re-baseline table)"
```

---

### Task 6: Notebooks — edit to the 0.5 columns

**Files:**
- Modify: `notebooks/02_pm25_compliance_report.ipynb` (cells 3, 4, 6 + kernelspec), `03_sensor_vs_reference.ipynb` (cells 9, 10, 12, 19), `04_uk_city_ranking.ipynb` (cells 3, 4, 6, 9), `05_exposure_assessment.ipynb` (cell 6), `06_african_air_quality.ipynb` (cell 11), `07_global_sensor_comparison.ipynb` (cells 7, 10, 12, 13, 15, 16, 18, 20)
- Modify: `notebooks/README.md`
- Test: `tests/test_docs_vocabulary.py` (`test_notebook_code_uses_v050_columns`, `test_notebook_kernel_is_python3`)

**Interfaces:**
- Consumes: the new columns; `find_sites()` metadata now has `network`.
- Produces: notebooks that Task 7 executes unchanged.

- [ ] **Step 1: Apply the edits with a script (do not hand-edit JSON)**

```python
# scratch: notebooks_edit.py — run with: uv run --no-project python notebooks_edit.py
import json, re, pathlib
ROOT = pathlib.Path("notebooks")
SUBS = [
    (r'"source_network"', '"network"'),
    (r"'source_network'", "'network'"),
    # ratification → the QA columns (03 cell 10, 06 cell 11, 07 cells 12 and 20)
    (r'combined\.groupby\(\["network", "ratification"\]\)\.size\(\)', 'combined.groupby(["network", "qa_tier"]).size()'),
    (r'# Check ratification flags — shows data quality metadata', '# Check the QA tier — PurpleAir rows are lcs_factory_only, AURN rows reference_*'),
    (r'# Check ratification — AirQo data is unvalidated low-cost sensor data', '# Check the QA tier — AirQo publishes calibrated and raw streams; until the key is renewed the tier is unknown'),
    (r'pm25\["ratification"\]\.value_counts\(\)', 'pm25["qa_tier"].value_counts()'),
    (r'flags = net_data\["ratification"\]\.value_counts\(\)', 'flags = net_data["qa_tier"].value_counts()'),
    (r'"QA Flags": ", "\.join\(net_data\["ratification"\]\.unique\(\)\)', '"QA tiers": ", ".join(sorted(net_data["qa_tier"].unique()))'),
]
for path in sorted(ROOT.glob("*.ipynb")):
    nb = json.loads(path.read_text())
    nb["metadata"]["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    for cell in nb["cells"]:
        src = "".join(cell["source"])
        new = src
        for pat, rep in SUBS:
            new = re.sub(pat, rep, new)
        if new != src:
            cell["source"] = new.splitlines(keepends=True)
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
```
Then: `grep -n "ratification\|source_network" notebooks/*.ipynb | grep -v '"ratification_stage\|outputs' | head` — any remaining hit is a markdown cell to reword by hand (say "quality tier" instead of "ratification flag").

- [ ] **Step 2: Update `notebooks/README.md`**

Under "Design Principles" add: `- **0.5 schema** - every download carries `network`, `backend`, `qa_code`, `qa_tier` and `ratification_stage`; the notebooks use those, never the deprecated `source_network`/`ratification` mirrors.` In the table, mark 06 and 07 with `(requires a current AirQo token; outputs last executed <date from Task 7>)` only if Task 7 cannot run them.

- [ ] **Step 3: Run the notebook guard tests**

Run: `uv run pytest tests/test_docs_vocabulary.py -q -p no:cacheprovider --no-cov -k notebook 2>&1 | tail -2` → all PASS.

- [ ] **Step 4: Commit**

```bash
git add notebooks
git commit -m "docs(notebooks): use network, qa_code and qa_tier; portable python3 kernel"
```

---

### Task 7: Notebooks — execute live and commit the outputs

**Files:**
- Modify (outputs only): `notebooks/0[1-8]_*.ipynb`
- Modify: `notebooks/README.md` (execution date line)

**Interfaces:**
- Consumes: `.env` at the repo root (`PURPLEAIR_API_KEY`, `BL_API_KEY`, `AIRQO_API_KEY` — the last is expired).
- Produces: committed outputs a reader can trust.

- [ ] **Step 1: Confirm which keys are present (never print values)**

Run: `uv run python -c "from dotenv import load_dotenv; import os; load_dotenv('.env'); print({k: bool(os.getenv(k)) for k in ['PURPLEAIR_API_KEY','BL_API_KEY','AIRQO_API_KEY','OPENAQ_API_KEY','AIRNOW_API_KEY']})"`

- [ ] **Step 2: Execute the key-free notebooks first (01, 02, 04, 08), one at a time**

```bash
for nb in 01_london_no2_comparison 02_pm25_compliance_report 04_uk_city_ranking 08_trend_analysis; do
  uv run --with nbconvert --with ipykernel --with matplotlib --with geopandas \
    jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=900 notebooks/$nb.ipynb \
    || echo "FAILED: $nb"
done
```
Expected: each finishes in under 5 minutes (README promise) with no `FAILED:` line. If a notebook fails, read the traceback in the notebook (`uv run --no-project python -c "import json;nb=json.load(open('notebooks/<nb>.ipynb'));print([o for c in nb['cells'] for o in c.get('outputs',[]) if o.get('output_type')=='error'])"`), fix the notebook code (not the library, unless it is a genuine library defect — then stop and report), and re-run that notebook.

- [ ] **Step 3: Execute the keyed notebooks (03, 05 need PurpleAir / BL; 06, 07 need AirQo)**

Same command for `03_sensor_vs_reference`, `05_exposure_assessment`, then `06_african_air_quality`, `07_global_sensor_comparison`. Expected: 03 and 05 pass. **06 and 07 will fail at AirQo authentication while the key is expired.** In that case: `git checkout notebooks/06_african_air_quality.ipynb notebooks/07_global_sensor_comparison.ipynb` is WRONG (it would revert Task 6's edits) — instead leave their outputs as executed-with-failure? No: keep Task 6's edited source with the *previous* outputs cleared: `uv run --with nbconvert jupyter nbconvert --clear-output --inplace notebooks/06_african_air_quality.ipynb notebooks/07_global_sensor_comparison.ipynb`, and record in `notebooks/README.md` table: `06`, `07`: "outputs cleared 2026-09-2x pending a renewed AirQo token". Say so in the PR description and the session log. Do not fabricate outputs.

- [ ] **Step 4: Sanity-check the outputs**

Run: `uv run --no-project python - <<'EOF'
import json, glob
for f in sorted(glob.glob("notebooks/*.ipynb")):
    nb = json.load(open(f)); errs = [o for c in nb["cells"] for o in c.get("outputs", []) if o.get("output_type") == "error"]
    execd = any(c.get("outputs") for c in nb["cells"] if c["cell_type"] == "code")
    print(f.split("/")[-1], "executed" if execd else "NO OUTPUTS", "| errors:", len(errs))
EOF`
Expected: 01–05, 08 executed with 0 errors; 06, 07 either executed (key renewed) or NO OUTPUTS.
Also spot-check one output shows the new columns: `grep -c '"qa_tier"' notebooks/03_sensor_vs_reference.ipynb` → ≥ 1.

- [ ] **Step 5: Add the execution date to `notebooks/README.md`** — one line under the table: `Outputs last executed live on 2026-09-2x with aeolus 0.5.0a1 (dev).`

- [ ] **Step 6: Run the full offline suite (the notebook guard is part of it) and commit**

Run: `uv run pytest tests/ -m "not live and not integration and not conformance" --no-cov -p no:cacheprovider -q 2>&1 | tail -1` → all passed.
```bash
git add notebooks
git commit -m "docs(notebooks): re-executed live against the 0.5 schema"
```

---

### Task 8: Version `0.5.0a1`, CHANGELOG heading, pre-release flag

**Files:**
- Modify: `pyproject.toml:8` (`version = "0.5.0a1"`), `src/aeolus/__init__.py:71` (`__version__ = "0.5.0a1"`), `CLAUDE.md:5` (`**Current Version:** 0.5.0a1`)
- Modify: `CHANGELOG.md:8` → `## [0.5.0a1] - 2026-09-2x (alpha for internal consumers)` and add a fresh `## [Unreleased]` line above it; keep the sub-sections as they are
- Modify: `.github/workflows/release.yml` — in the "Create GitHub Release" step add `          prerelease: ${{ contains(github.ref_name, 'a') || contains(github.ref_name, 'b') || contains(github.ref_name, 'rc') }}` under `with:`
- Test: `tests/test_docs_vocabulary.py::test_version_strings_agree`, `uv build` + wheel smoke test

- [ ] **Step 1: Make the version test red, then green**

Change `pyproject.toml` only, run `uv run pytest tests/test_docs_vocabulary.py -k version -q -p no:cacheprovider --no-cov` → FAIL. Change `__init__.py` and `CLAUDE.md` → PASS.

- [ ] **Step 2: CHANGELOG and release workflow edits** (as listed above). Add to the CHANGELOG under the new heading, first line: `First alpha of the 0.5 contract for Hermes, RHEA, Clara and Argus to migrate against. Not for general use. Migration guide: docs/guide/migrating-to-0.5.md.`

- [ ] **Step 3: Build and smoke-test the wheel in an isolated interpreter**

```bash
rm -rf dist && uv build -q
unzip -l dist/aeolus_aq-0.5.0a1-py3-none-any.whl | grep -c "qa_vocabularies/.*\.yaml"   # expect 15
uv run --isolated --no-project --python 3.13 --with dist/aeolus_aq-0.5.0a1-py3-none-any.whl python -c "
import aeolus, warnings
from aeolus.network_registry import list_network_specs
print(aeolus.__version__, len(list_network_specs()), 'networks')
from aeolus.schema import DATA_COLUMNS; assert len(DATA_COLUMNS) == 13
"
```
Expected: `15`, then `0.5.0a1 15 networks`.

- [ ] **Step 4: Full offline suite, docs build, commit**

Run: `uv run pytest tests/ -m "not live and not integration and not conformance" --no-cov -p no:cacheprovider -q 2>&1 | tail -1` → all passed.
Run: `uv run --extra docs mkdocs build --strict -q && echo OK` → `OK`.
```bash
git add pyproject.toml src/aeolus/__init__.py CLAUDE.md CHANGELOG.md .github/workflows/release.yml
git commit -m "chore(release): 0.5.0a1 — alpha of the 0.5 contract for internal consumers"
```

---

### Task 9: PR, two-round review, merge, tag (with confirmation), consumer handoff

**Files:**
- Create: `../argus/docs/2026-09-2x-aeolus-0.5.0a1-handoff.md` (Argus is the consumer with stored data to re-baseline)
- Modify: `../sls-meta/SLS-PRODUCT-DEV.md` (session log + Aeolus snapshot row)

- [ ] **Step 1: Live conformance before the PR** (feedback rule: it catches what offline and CI miss)

Run: `uv run pytest tests/test_conformance.py -m conformance --no-cov -q -p no:cacheprovider 2>&1 | tail -3` (~10 min). Expected: all pass except the two AirQo-key failures. Any other failure blocks the PR.

- [ ] **Step 2: Open the PR**

```bash
git push -u origin feat/v050-docs-alpha
gh pr create --title "v0.5.0 Plan 4: docs, notebooks, migration guide, 0.5.0a1" --body "$(cat <<'EOF'
Plan: docs/superpowers/plans/2026-09-23-v050-docs-notebooks-alpha.md

- tests/test_docs_vocabulary.py guards the user docs and notebooks against pre-0.5.0 vocabulary
- README, quick start, configuration, downloading, sources guide and every source page describe the 13-column schema and qa_code/qa_tier
- API reference pages for schema/qa/network_registry/units/cache
- Migration guide docs/guide/migrating-to-0.5.md
- Notebooks edited to the new columns and re-executed live (<list which>; 06/07 <status>)
- Version 0.5.0a1; release workflow marks alphas as pre-releases

Offline: <n> passed. Live conformance: <n> passed, AirQo-key failures only. mkdocs --strict OK.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Review round one** — dispatch a high-effort code review of the PR diff (`gh pr diff <n>`) with the instruction to read the *diff*, check every doc statement against the code (`src/aeolus/...`) and the CHANGELOG, and execute the offline pytest command only. Address every finding test-first where a test can express it (the vocabulary guard is the usual place); commit `docs: review fixes`.

- [ ] **Step 4: Review round two** — a second reviewer verifies each round-one finding is resolved and probes the fix commit for regressions (the process that caught real defects on #16 and #17). Approve or fix again.

- [ ] **Step 5: Merge** — `gh pr merge <n> --merge --delete-branch`; `git checkout main && git pull`. The docs workflow deploys the site from `main`.

- [ ] **Step 6: STOP — ask the user before publishing**

Pushing the tag runs `release.yml`, which publishes `0.5.0a1` to PyPI (irreversible: that version number can never be reused). Ask: "Ready to tag `v0.5.0a1` and publish the alpha to PyPI?" Proceed only on a yes. Then:
```bash
git tag -a v0.5.0a1 -m "0.5.0a1: alpha of the 0.5 contract for internal consumers" && git push origin v0.5.0a1
gh run watch --exit-status $(gh run list --workflow=release.yml --limit 1 --json databaseId -q '.[0].databaseId')
uv run --isolated --no-project --python 3.13 --with "aeolus_aq==0.5.0a1" python -c "import aeolus; print(aeolus.__version__)"
```
Expected: the release run passes; the last command prints `0.5.0a1` from PyPI (allow a minute for the index).

- [ ] **Step 7: Consumer handoff and logs**

Write `../argus/docs/2026-09-2x-aeolus-0.5.0a1-handoff.md` (≤ 40 lines): pin `aeolus_aq==0.5.0a1`; run the worker with `AEOLUS_LEGACY_COLUMNS=0` in dev; the re-baseline table from the migration guide restricted to Argus's seven UK networks (LAQN gases ×1.91–2.66; SOS CO units; AURN-family `ratification` mirror now `Ratified`/`Provisional` — Argus's `qa_flag` will stop being NULL; `time_average` period labels); the units gate must assert, not convert (per `2026-09-20-laqn-units-aeolus-reply.md`); link to the migration guide. Then update `../sls-meta/SLS-PRODUCT-DEV.md` (session entry + snapshot row: Plan 4 merged, `0.5.0a1` on PyPI or awaiting the user's go, next = Plan 5 gated on Argus v1) and commit/push both repos.

---

## Self-review

**Spec coverage.** §12 (API surface & migration) → Tasks 2, 5; §14 step 3 (cut the alpha) → Tasks 8–9; §14 step 4 (migration guide, CHANGELOG re-baseline notes, docs rewrite) → Tasks 2–5, 8; §3/§4 (wire format, enums, as documented) → Tasks 2–4; §17.1 mirrors → Tasks 2, 5; §17.10 units/time → Task 5 re-baseline table and Task 2 quick start; roadmap "re-execute the 8 notebooks live" → Tasks 6–7. **Not here (deliberately):** Plan 5 ARGUS backend; conda-forge (alphas are not picked up by the feedstock bot; the final 0.5.0 will be); a `notebooks` extra in `pyproject.toml` (YAGNI — `uv run --with` suffices for maintainers, and the notebooks README already tells users to `pip install jupyter matplotlib`).

**Placeholder scan.** Dates written `2026-09-2x` are to be replaced with the actual date at execution; PR-body `<…>` slots are to be filled from the run. No other placeholders.

**Type consistency.** Column names match `aeolus.schema.DATA_COLUMNS`; tier/stage values match `aeolus.qa`; env var names in Task 2 are verified against the code at execution (step 4 says to drop any that do not exist); the vocabulary guard's exempt file name (`migrating-to-0.5.md`) matches Task 5's file name and the nav entry.
