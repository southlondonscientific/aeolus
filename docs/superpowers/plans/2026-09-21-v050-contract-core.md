# v0.5.0 Contract Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every frame aeolus returns carry the v0.5.0 wire format — `network`, `backend`, `country`, `instrument_class`, and the three-column QA model — derived from a network registry, with the old `source_network` / `ratification` columns kept as deprecation mirrors.

**Architecture:** Adapters keep emitting today's eight columns. A single *finalising step* (`aeolus.schema.finalise_data_frame`) runs where every download converges — `networks.download`, `portals.download`, `get_current` — and turns an adapter frame into the public schema using a **network registry** loaded from YAML (`aeolus.network_registry`) and pure **QA derivation** functions (`aeolus.qa`). No adapter is rewritten in this plan; until an adapter is wired (Plan 2) its rows get `qa_code = null`, `qa_tier = "unknown"`, and its existing `ratification` string is preserved in the mirror, so consumers see no regression.

**Tech Stack:** Python 3.11+, pandas ≥ 2.3.3, PyYAML (new runtime dependency), pytest, `responses`, uv.

**Spec:** `docs/dev/v050_design.md` — §3 (wire format), §4 (enums), §5 (registry), §6 (ratification timing), §8 (the 15 networks), §12 (API surface), §17 (addendum: 17.1 mirrors, 17.2 cache, 17.8 convergence points). Executors read both.

## Where this sits — the v0.5.0 roadmap

This is **Plan 1 of 5**. Each later plan is written when reached, against what this one produced.

| Plan | Scope | Depends on |
|---|---|---|
| **1. Contract core** (this document) | registry, QA derivation, finalising step, mirrors, `network=`, cache v3 | — |
| 2. QA wiring | real `qa_code` per adapter: AURN-family `ratified_to` join on `(site, measurand)`; EEA `Verification`; PurpleAir tokens; Breathe London; AirNow; AirQo (needs a working key) | 1 |
| 3. EEA datasets | query E1a → E2a → Airbase by window, prefer verified rows; Italy caveat; conformance test asserts a past year is non-empty (spec §17.6) | 1, 2 |
| 4. Docs, notebooks, migration guide, `0.5.0a1` | rewrite the schema docs; re-execute the 8 notebooks live; migration guide; cut the alpha for Hermes/RHEA/Clara/Argus | 1–3 |
| 5. ARGUS backend | gated on Argus `/api/v1/` + its QA migration (spec §11, D6′) | 1, and Argus |

Also outstanding, outside these plans: the SOS interval-convention check (spec §17.10) and `reference_temperature_c` (§17.9 — fold into Plan 2).

## Global Constraints

- British English in identifiers and prose: `normalise`, `summarise`, `finalise`.
- Run everything with `uv run`. Offline tests: `uv run pytest <files> -m "not live and not integration and not conformance" --no-cov -p no:cacheprovider`. **Before merging, also run live conformance** (`uv run pytest tests/test_conformance.py -m conformance --no-cov -q -p no:cacheprovider`, ~10 min) — it has caught regressions the offline suite and CI both passed. Two AirQo failures are expected while `AIRQO_API_KEY` is expired.
- `date_time` is tz-aware UTC and marks the START of its interval. Never call `.timestamp()` or `strftime("…Z")` on a user datetime without `aeolus._dates.to_utc()`.
- `units` is authoritative; nothing in this plan touches values or units.
- Enum values are **permanent public keys** (spec §4, "frozen"). Copy them verbatim from this plan; do not rename, re-case or "tidy" them.
- `qa_code` is verbatim upstream and is **never overwritten**; `null` where upstream is silent.
- Anything stored in `DataFrame.attrs` must be JSON-serialisable (pandas writes `attrs` into Parquet).
- Empty frames always carry the full schema — never a bare `pd.DataFrame()`.
- One commit per task. End each commit message with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Work on a branch `feat/v050-contract-core` off `main` (after PR #14 has merged).

## File structure

| File | Responsibility |
|---|---|
| `src/aeolus/qa.py` (create) | The frozen enums, and two pure functions: derive `(qa_tier, ratification_stage)` from `qa_code`; derive the legacy `ratification` string from the triple. No I/O, no pandas-free surprises. |
| `src/aeolus/data/qa_vocabularies/<CODE>.yaml` (create ×15) | One file per network: identity, QA vocabulary, structured ratification timing, licence. Data only. |
| `src/aeolus/network_registry.py` (create) | `NetworkSpec` dataclass; loads and validates the YAML; `get_network_spec()`; `SOURCE_ROUTES` — which `(network, backend)` each registered *source* serves. |
| `src/aeolus/schema.py` (create) | The public column lists; `finalise_data_frame()` / `finalise_metadata_frame()`; the legacy-mirror option and its one-time `DeprecationWarning`. The only module that knows both the adapter schema and the public one. |
| `src/aeolus/types.py` (modify) | `ADAPTER_DATA_COLUMNS` (today's eight) for adapters; `DATA_COLUMNS` becomes the public list; `empty_data_frame()` follows it. |
| `src/aeolus/networks/api.py`, `portals/api.py`, `api.py` (modify) | Call the finalising step at the three convergence points; `network=` alias; read `network`, not `source_network`. |
| `src/aeolus/cache.py` (modify) | `_CACHE_VERSION = "v3"`; a cached frame whose columns are not the current schema is a miss. |
| `src/aeolus/metrics/stats.py`, `transforms.py` (modify) | Internal readers use `network`. |
| `tests/test_qa.py`, `tests/test_network_registry.py`, `tests/test_schema.py` (create) | One test file per new module. |

---

### Task 1: QA enums and derivation (`aeolus.qa`)

**Files:**
- Create: `src/aeolus/qa.py`
- Test: `tests/test_qa.py`

**Interfaces:**
- Produces: `QA_TIERS: tuple[str, ...]`, `RATIFICATION_STAGES: tuple[str, ...]`, `QA_MODELS`, `INSTRUMENT_CLASSES`; `derive_qa(qa_codes: pd.Series, vocabulary: dict[str, dict], default_stage: str | None) -> tuple[pd.Series, pd.Series]`; `legacy_ratification(qa_tier: pd.Series, stage: pd.Series) -> pd.Series`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_qa.py
"""QA enums are frozen public keys; derivation is pure and total."""

import pandas as pd
import pytest

from aeolus.qa import (
    INSTRUMENT_CLASSES, QA_MODELS, QA_TIERS, RATIFICATION_STAGES, derive_qa, legacy_ratification,
)


def test_enums_are_exactly_the_frozen_values():
    assert QA_TIERS == (
        "reference_full_qc", "reference_provisional", "lcs_calibrated",
        "lcs_factory_only", "flagged", "unknown",
    )
    assert RATIFICATION_STAGES == ("unratified", "ratified", "supplied", "not_applicable")
    assert QA_MODELS == (
        "regulatory_temporal_ratification", "staged_calibration",
        "point_in_time_validation", "none", "mixed", "unknown",
    )
    assert INSTRUMENT_CLASSES == ("reference", "equivalent", "indicative", "LCS", "mixed", "unknown")


VOCAB = {
    "verified": {"qa_tier": "reference_full_qc", "ratification_stage": "ratified"},
    "unverified": {"qa_tier": "reference_provisional", "ratification_stage": "unratified"},
}


def test_known_codes_map_through_the_vocabulary():
    tier, stage = derive_qa(pd.Series(["verified", "unverified"]), VOCAB, default_stage=None)
    assert tier.tolist() == ["reference_full_qc", "reference_provisional"]
    assert stage.tolist() == ["ratified", "unratified"]


def test_missing_code_is_unknown_with_the_network_default_stage():
    tier, stage = derive_qa(pd.Series([None, float("nan")]), VOCAB, default_stage="supplied")
    assert tier.tolist() == ["unknown", "unknown"]
    assert stage.tolist() == ["supplied", "supplied"]


def test_code_not_in_vocabulary_is_unknown_and_stage_null():
    tier, stage = derive_qa(pd.Series(["mystery"]), VOCAB, default_stage=None)
    assert tier.tolist() == ["unknown"]
    assert stage.isna().all()


@pytest.mark.parametrize(
    "tier, stage, expected",
    [
        ("reference_full_qc", "ratified", "Ratified"),
        ("reference_provisional", "unratified", "Provisional"),
        ("lcs_calibrated", "not_applicable", "Indicative"),
        ("lcs_factory_only", "not_applicable", "Validated"),
        ("flagged", "not_applicable", "Invalid"),
        ("unknown", "not_applicable", "Unvalidated"),
        ("unknown", None, "None"),
    ],
)
def test_legacy_ratification_mirror(tier, stage, expected):
    out = legacy_ratification(pd.Series([tier]), pd.Series([stage], dtype=object))
    assert out.tolist() == [expected]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_qa.py --no-cov -p no:cacheprovider -q`
Expected: collection error, `ModuleNotFoundError: No module named 'aeolus.qa'`

- [ ] **Step 3: Implement**

```python
# src/aeolus/qa.py
"""
The v0.5.0 data-quality model: frozen enums and pure derivation functions.

The enum values are permanent public keys (renaming one is a major breaking
change), shared with Argus. ``qa_code`` is whatever the upstream wrote;
``qa_tier`` and ``ratification_stage`` are derived from it through the
network's vocabulary (see ``aeolus.network_registry``).
"""

import pandas as pd

QA_TIERS = (
    "reference_full_qc", "reference_provisional", "lcs_calibrated",
    "lcs_factory_only", "flagged", "unknown",
)
RATIFICATION_STAGES = ("unratified", "ratified", "supplied", "not_applicable")
QA_MODELS = (
    "regulatory_temporal_ratification", "staged_calibration",
    "point_in_time_validation", "none", "mixed", "unknown",
)
INSTRUMENT_CLASSES = ("reference", "equivalent", "indicative", "LCS", "mixed", "unknown")


def derive_qa(
    qa_codes: pd.Series, vocabulary: dict[str, dict], default_stage: str | None
) -> tuple[pd.Series, pd.Series]:
    """Return ``(qa_tier, ratification_stage)`` for a series of upstream codes.

    A missing code means the upstream said nothing: tier ``unknown`` and the
    network's *default_stage*. A code the vocabulary does not list is also
    ``unknown``, with a null stage — an unrecognised token must not be
    silently promoted to the network default.
    """
    codes = qa_codes.astype(object)
    missing = codes.isna()
    tier_map = {code: entry["qa_tier"] for code, entry in vocabulary.items()}
    stage_map = {code: entry.get("ratification_stage") for code, entry in vocabulary.items()}

    tier = codes.map(tier_map).where(~missing, "unknown").fillna("unknown")
    stage = codes.map(stage_map).astype(object)
    stage = stage.where(~missing, default_stage)
    return tier.astype(object), stage.where(stage.notna(), None)


_LEGACY_BY_TIER = {
    "lcs_calibrated": "Indicative",
    "lcs_factory_only": "Validated",
    "flagged": "Invalid",
}


def legacy_ratification(qa_tier: pd.Series, stage: pd.Series) -> pd.Series:
    """The pre-0.5.0 ``ratification`` string, derived from the new columns (spec §4.3)."""
    out = pd.Series("None", index=qa_tier.index, dtype=object)
    out = out.where(~(qa_tier == "unknown") | stage.isna(), "Unvalidated")
    for tier, label in _LEGACY_BY_TIER.items():
        out = out.where(qa_tier != tier, label)
    out = out.where(stage != "ratified", "Ratified")
    out = out.where(stage != "unratified", "Provisional")
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_qa.py --no-cov -p no:cacheprovider -q`
Expected: all pass. (If `("lcs_calibrated", "not_applicable")` fails, check the order of the `where` calls: the stage rules come last only for `ratified`/`unratified`, which LCS rows never carry.)

- [ ] **Step 5: Commit**

```bash
git add src/aeolus/qa.py tests/test_qa.py
git commit -m "feat(qa): frozen QA enums and pure derivation functions"
```

---

### Task 2: Network vocabulary files

**Files:**
- Create: `src/aeolus/data/__init__.py` (empty), `src/aeolus/data/qa_vocabularies/<CODE>.yaml` × 15
- Modify: `pyproject.toml` (dependency + package data)

**Interfaces:**
- Produces: 15 YAML files with exactly the keys shown below. Task 3 loads and validates them.

- [ ] **Step 1: Add PyYAML and ship the data files**

In `pyproject.toml`, add `"pyyaml>=6.0",` to `dependencies`, and extend the package-data list:

```toml
[tool.setuptools.package-data]
aeolus = [
    "sources/_sos_mapping.json",
    "viz/fonts/*.ttf",
    "viz/fonts/OFL.txt",
    "data/qa_vocabularies/*.yaml",
]
```

Run: `uv lock && uv sync --extra dev`

- [ ] **Step 2: Write `AURN.yaml` — the template every file follows**

```yaml
# src/aeolus/data/qa_vocabularies/AURN.yaml
code: AURN
name: Automatic Urban and Rural Network
country: GB
regulatory: true
operators: [Defra, Bureau Veritas (CMCU), Ricardo (QA/QC), NPL (ALN)]
instrument_class: reference
qa_model: regulatory_temporal_ratification
default_ratification_stage: null     # has a ratification concept; per-row status not yet surfaced
qa_code_vocabulary:
  verified:
    description: Ratified by the QA/QC unit
    qa_tier: reference_full_qc
    ratification_stage: ratified
    source_url: https://uk-air.defra.gov.uk/networks/network-info?view=aurn
  unverified:
    description: Provisional, not yet ratified
    qa_tier: reference_provisional
    ratification_stage: unratified
    source_url: https://uk-air.defra.gov.uk/networks/network-info?view=aurn
ratification_cadence_months: 3
first_ratification_latency_months: 3
full_year_ratified_by: "~1 June of year+1"
ratification_overrides: "openair treats data younger than ~6 months as provisional"
data_licence: OGL-UK-3.0
homepage_url: https://uk-air.defra.gov.uk/networks/network-info?view=aurn
notes: ""
```

- [ ] **Step 3: Write the other fourteen files, same keys, these values**

`qa_code_vocabulary` entries are written `code → tier / stage`. Use `description` = the code in plain words, and `source_url` = the file's `homepage_url`. `null` means YAML `null`. Timing fields not listed are `null`; `ratification_overrides` and `notes` not listed are `""`.

| code | name | country | regulatory | instrument_class | qa_model | default_ratification_stage | qa_code_vocabulary | timing | data_licence | homepage_url |
|---|---|---|---|---|---|---|---|---|---|---|
| LAQN | London Air Quality Network | GB | true | reference | regulatory_temporal_ratification | null | *(empty map `{}`)* | `ratification_overrides: "revision window ~12 months"` | OGL-UK-3.0 | https://www.londonair.org.uk |
| AQE | Air Quality England | GB | true | mixed | regulatory_temporal_ratification | null | `Ratified` → reference_full_qc / ratified; `Provisional` → reference_provisional / unratified; `Supplied` → unknown / supplied | cadence 6; full-year "~1 June of year+1" | OGL-UK-3.0 | https://www.airqualityengland.co.uk |
| SAQN | Scottish Air Quality Network | GB | true | mixed | regulatory_temporal_ratification | null | same three tokens as AQE | first-latency 6; overrides "AURN-affiliated sites ~3 months" | OGL-UK-3.0 | https://www.scottishairquality.scot |
| WAQN | Welsh Air Quality Network | GB | true | mixed | regulatory_temporal_ratification | null | same three tokens as AQE | cadence 6; overrides "AURN-affiliated sites 3 months; supplied sites never ratify" | Crown Copyright (personal or in-house use) | https://airquality.gov.wales |
| NI | Northern Ireland Air | GB | true | mixed | regulatory_temporal_ratification | null | same three tokens as AQE | first-latency 6; full-year "~September of year+1" | OGL-UK-3.0 | https://www.airqualityni.co.uk |
| LMAM | Locally Managed Automatic Monitoring | GB | true | mixed | mixed | supplied | `{}` | — | OGL-UK-3.0 | https://uk-air.defra.gov.uk/networks/network-info?view=nondefraaqmon |
| BREATHE_LONDON | Breathe London | GB | false | LCS | staged_calibration | not_applicable | `P` → lcs_calibrated / unratified | — | OGL-UK-3.0 | https://www.breathelondon.org |
| AIRQO | AirQo | UG | false | LCS | staged_calibration | not_applicable | `calibrated` → lcs_calibrated / not_applicable; `raw` → lcs_factory_only / not_applicable | — | CC-BY-4.0 (non-commercial override) | https://airqo.net |
| PURPLEAIR | PurpleAir | "*" | false | LCS | point_in_time_validation | not_applicable | `Validated` → lcs_factory_only; `Single Channel (A)` → lcs_factory_only; `Single Channel (B)` → lcs_factory_only; `Channel Disagreement` → flagged; `Sensor Saturation` → flagged; `Invalid` → flagged; `Unvalidated` → unknown (all stage not_applicable) | — | PurpleAir API terms | https://www2.purpleair.com |
| SENSOR_COMMUNITY | Sensor.Community | "*" | false | LCS | none | not_applicable | `{}` | — | ODbL-1.0 (database), DbCL-1.0 (contents) | https://sensor.community |
| AIRNOW | EPA AirNow | US | true | reference | regulatory_temporal_ratification | unratified | `Provisional` → reference_provisional / unratified | full-year "~1 May of year+1 (in AQS, not AirNow)" | US public domain | https://www.airnow.gov |
| EEA | European Environment Agency | "*" | true | reference | regulatory_temporal_ratification | null | `"1"` → reference_full_qc / ratified; `"2"` → reference_provisional / unratified; `"3"` → reference_provisional / unratified | full-year "E1a by 30 September of year+1" | EEA standard re-use policy (CC-BY-4.0) | https://www.eea.europa.eu |
| SONITUS | Sonitus (Dublin City Council) | IE | false | mixed | none | not_applicable | `{}` | — | CC-BY-4.0 | https://data.smartdublin.ie/dataset/sonitus |
| OPENAQ | OpenAQ | "*" | false | mixed | mixed | null | `{}` | — | per-provider (see OpenAQ) | https://openaq.org |

Quote `"*"`, and quote the EEA codes (`"1"`, `"2"`, `"3"`) — they are strings, because `qa_code` is verbatim text.

- [ ] **Step 4: Check every file parses**

Run: `uv run python -c "import yaml, glob; [yaml.safe_load(open(f)) for f in glob.glob('src/aeolus/data/qa_vocabularies/*.yaml')]; print(len(glob.glob('src/aeolus/data/qa_vocabularies/*.yaml')))"`
Expected: `15`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/aeolus/data
git commit -m "feat(registry): QA vocabulary files for the 15 v0.5.0 networks"
```

---

### Task 3: Network registry (`aeolus.network_registry`)

**Files:**
- Create: `src/aeolus/network_registry.py`
- Test: `tests/test_network_registry.py`

**Interfaces:**
- Consumes: `aeolus.qa.QA_TIERS`, `RATIFICATION_STAGES`, `QA_MODELS`, `INSTRUMENT_CLASSES`; the YAML files from Task 2.
- Produces: `NetworkSpec` (frozen dataclass with the YAML keys as attributes); `get_network_spec(code: str) -> NetworkSpec`; `list_network_specs() -> list[NetworkSpec]`; `SOURCE_ROUTES: dict[str, tuple[str, str]]` mapping a registered source name to `(network_code, backend)`; `route_for(source: str) -> tuple[str, str]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_network_registry.py
import pytest

import aeolus
import aeolus.sources  # noqa: F401  (registers the sources)
from aeolus.network_registry import SOURCE_ROUTES, get_network_spec, list_network_specs, route_for
from aeolus.qa import INSTRUMENT_CLASSES, QA_MODELS, QA_TIERS, RATIFICATION_STAGES

CODES = {
    "AURN", "LAQN", "AQE", "SAQN", "WAQN", "NI", "BREATHE_LONDON", "LMAM", "AIRQO",
    "PURPLEAIR", "SENSOR_COMMUNITY", "AIRNOW", "EEA", "SONITUS", "OPENAQ",
}


def test_the_fifteen_networks_load():
    assert {spec.code for spec in list_network_specs()} == CODES


@pytest.mark.parametrize("code", sorted(CODES))
def test_every_value_is_a_frozen_enum_member(code):
    spec = get_network_spec(code)
    assert spec.qa_model in QA_MODELS
    assert spec.instrument_class in INSTRUMENT_CLASSES
    assert spec.default_ratification_stage in (*RATIFICATION_STAGES, None)
    for entry in spec.qa_code_vocabulary.values():
        assert entry["qa_tier"] in QA_TIERS
        assert entry.get("ratification_stage") in (*RATIFICATION_STAGES, None)
    assert all(isinstance(k, str) for k in spec.qa_code_vocabulary)


def test_lookup_is_case_insensitive_and_unknown_codes_say_so():
    assert get_network_spec("aurn").code == "AURN"
    with pytest.raises(KeyError, match="NOPE"):
        get_network_spec("NOPE")


def test_every_registered_source_has_a_route_to_a_known_network():
    for source in aeolus.list_sources(include_all=True):
        network, backend = route_for(source)
        assert network in CODES, source
        assert backend


@pytest.mark.parametrize(
    "source, expected",
    [
        ("AURN", ("AURN", "RDATA")), ("AURN-SOS", ("AURN", "SOS")), ("LAQN-ERG", ("LAQN", "ERG_REST")),
        ("SAQD", ("SAQN", "RDATA")), ("BREATHE_LONDON", ("BREATHE_LONDON", "BREATHE_LONDON")),
        ("OPENAQ", ("OPENAQ", "OPENAQ")),
    ],
)
def test_routes(source, expected):
    assert route_for(source) == expected
    assert SOURCE_ROUTES[source] == expected
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_network_registry.py --no-cov -p no:cacheprovider -q`
Expected: `ModuleNotFoundError: No module named 'aeolus.network_registry'`

- [ ] **Step 3: Implement**

```python
# src/aeolus/network_registry.py
"""
Network registry: who each network is and how to read its QA codes.

A *network* is who produced the data (AURN, LAQN, ...). A *source* is a way
aeolus fetches it (``AURN`` via RData, ``AURN-SOS`` via the SOS API). Several
sources can serve one network; ``SOURCE_ROUTES`` records which. The routing
*engine* (choosing a backend) is v0.6.0 — this is only the lookup table.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources

import yaml

from .qa import INSTRUMENT_CLASSES, QA_MODELS, QA_TIERS, RATIFICATION_STAGES


@dataclass(frozen=True)
class NetworkSpec:
    code: str
    name: str
    country: str
    regulatory: bool
    instrument_class: str
    qa_model: str
    default_ratification_stage: str | None
    qa_code_vocabulary: dict = field(default_factory=dict)
    operators: tuple = ()
    ratification_cadence_months: int | None = None
    first_ratification_latency_months: int | None = None
    full_year_ratified_by: str | None = None
    ratification_overrides: str = ""
    data_licence: str = ""
    homepage_url: str = ""
    notes: str = ""


def _validate(spec: NetworkSpec) -> None:
    if spec.qa_model not in QA_MODELS:
        raise ValueError(f"{spec.code}: qa_model {spec.qa_model!r} is not one of {QA_MODELS}")
    if spec.instrument_class not in INSTRUMENT_CLASSES:
        raise ValueError(f"{spec.code}: instrument_class {spec.instrument_class!r}")
    if spec.default_ratification_stage not in (*RATIFICATION_STAGES, None):
        raise ValueError(f"{spec.code}: default_ratification_stage {spec.default_ratification_stage!r}")
    for code, entry in spec.qa_code_vocabulary.items():
        if not isinstance(code, str):
            raise ValueError(f"{spec.code}: qa code {code!r} must be a string (quote it in the YAML)")
        if entry["qa_tier"] not in QA_TIERS:
            raise ValueError(f"{spec.code}: {code!r} has qa_tier {entry['qa_tier']!r}")
        if entry.get("ratification_stage") not in (*RATIFICATION_STAGES, None):
            raise ValueError(f"{spec.code}: {code!r} has stage {entry.get('ratification_stage')!r}")


@lru_cache(maxsize=1)
def _load() -> dict[str, NetworkSpec]:
    specs = {}
    folder = resources.files("aeolus") / "data" / "qa_vocabularies"
    for path in sorted(folder.iterdir(), key=lambda p: p.name):
        if not path.name.endswith(".yaml"):
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        raw["operators"] = tuple(raw.get("operators") or ())
        raw["qa_code_vocabulary"] = raw.get("qa_code_vocabulary") or {}
        spec = NetworkSpec(**raw)
        _validate(spec)
        specs[spec.code] = spec
    return specs


def list_network_specs() -> list[NetworkSpec]:
    return list(_load().values())


def get_network_spec(code: str) -> NetworkSpec:
    try:
        return _load()[code.upper()]
    except KeyError:
        raise KeyError(f"Unknown network {code.upper()!r}. Known: {sorted(_load())}") from None


# source name -> (network code, backend). Every registered source must appear.
SOURCE_ROUTES: dict[str, tuple[str, str]] = {
    **{n: (n, "RDATA") for n in ("AURN", "SAQN", "WAQN", "NI", "AQE", "LMAM", "LAQN")},
    "SAQD": ("SAQN", "RDATA"),
    **{f"{n}-SOS": (n, "SOS") for n in ("AURN", "SAQN", "WAQN", "NI", "AQE")},
    "LAQN-ERG": ("LAQN", "ERG_REST"),
    **{n: (n, n) for n in (
        "BREATHE_LONDON", "AIRQO", "AIRNOW", "EEA", "SONITUS",
        "SENSOR_COMMUNITY", "OPENAQ", "PURPLEAIR",
    )},
}


def route_for(source: str) -> tuple[str, str]:
    try:
        return SOURCE_ROUTES[source.upper()]
    except KeyError:
        raise KeyError(
            f"Source {source.upper()!r} has no entry in network_registry.SOURCE_ROUTES"
        ) from None
```

Note for the reviewer: spec §3.1 lists the `backend` values but omits one for Breathe London. This plan adds `BREATHE_LONDON`, following the pattern of every other single-backend network. Record it in the spec (§3.1) in this commit.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_network_registry.py --no-cov -p no:cacheprovider -q`
Expected: all pass. A `TypeError: __init__() got an unexpected keyword argument` means a YAML file has a key the dataclass lacks — fix the YAML, not the dataclass.

- [ ] **Step 5: Commit**

```bash
git add src/aeolus/network_registry.py tests/test_network_registry.py docs/dev/v050_design.md
git commit -m "feat(registry): NetworkSpec, YAML loader and source routes"
```

---

### Task 4: The public schema and the finalising step (`aeolus.schema`)

**Files:**
- Create: `src/aeolus/schema.py`
- Modify: `src/aeolus/types.py`
- Test: `tests/test_schema.py`

**Interfaces:**
- Consumes: `route_for`, `get_network_spec` (Task 3); `derive_qa`, `legacy_ratification` (Task 1).
- Produces: `types.ADAPTER_DATA_COLUMNS` (the eight columns adapters emit); `schema.DATA_COLUMNS` (public, ordered); `schema.LEGACY_DATA_COLUMNS = ("source_network", "ratification")`; `schema.finalise_data_frame(df: pd.DataFrame, source: str) -> pd.DataFrame`; `schema.empty_public_frame() -> pd.DataFrame`.

Transitional rule, stated once: an adapter that has **not** been wired emits no `qa_code` column. Its rows get `qa_code = None`, tier `unknown`, the network's default stage — and the legacy `ratification` mirror **keeps the adapter's own string**, so nothing a consumer reads today changes. An adapter that *does* emit `qa_code` (Plan 2) gets a mirror derived from the triple.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_schema.py
import pandas as pd
import pytest

import aeolus.sources  # noqa: F401
from aeolus.schema import DATA_COLUMNS, empty_public_frame, finalise_data_frame


def adapter_frame(network="AURN", ratification="None", **extra):
    base = {
        "site_code": ["MY1"], "date_time": [pd.Timestamp("2024-01-01", tz="UTC")], "measurand": ["NO2"],
        "value": [41.6], "units": ["ug/m3"], "source_network": [network],
        "ratification": [ratification], "created_at": [pd.Timestamp("2024-06-01", tz="UTC")],
    }
    return pd.DataFrame({**base, **{k: [v] for k, v in extra.items()}})


def test_public_columns_and_order():
    assert DATA_COLUMNS == [
        "site_code", "network", "date_time", "measurand", "value", "units",
        "qa_code", "qa_tier", "ratification_stage", "backend",
        "source_network", "ratification", "created_at",
    ]
    assert list(finalise_data_frame(adapter_frame(), "AURN").columns) == DATA_COLUMNS
    assert list(empty_public_frame().columns) == DATA_COLUMNS


def test_network_and_backend_come_from_the_source_route_not_the_adapter():
    out = finalise_data_frame(adapter_frame(network="whatever"), "AURN-SOS")
    assert out.loc[0, "network"] == "AURN" and out.loc[0, "backend"] == "SOS"
    assert out.loc[0, "source_network"] == "AURN"  # the mirror equals `network`


def test_unwired_adapter_is_unknown_and_keeps_its_ratification_string():
    out = finalise_data_frame(adapter_frame("PURPLEAIR", ratification="Channel Disagreement"), "PURPLEAIR")
    assert out.loc[0, "qa_code"] is None
    assert out.loc[0, "qa_tier"] == "unknown"
    assert out.loc[0, "ratification_stage"] == "not_applicable"   # PurpleAir's network default
    assert out.loc[0, "ratification"] == "Channel Disagreement"   # unchanged for consumers


def test_wired_adapter_derives_tier_stage_and_mirror():
    out = finalise_data_frame(adapter_frame("AURN", qa_code="verified"), "AURN")
    assert out.loc[0, "qa_code"] == "verified"
    assert out.loc[0, "qa_tier"] == "reference_full_qc"
    assert out.loc[0, "ratification_stage"] == "ratified"
    assert out.loc[0, "ratification"] == "Ratified"


def test_values_units_and_times_are_untouched():
    before = adapter_frame()
    out = finalise_data_frame(before.copy(), "AURN")
    for col in ("site_code", "date_time", "measurand", "value", "units", "created_at"):
        pd.testing.assert_series_equal(out[col], before[col])


def test_empty_adapter_frame_gives_empty_public_frame():
    out = finalise_data_frame(adapter_frame().iloc[0:0], "AURN")
    assert out.empty and list(out.columns) == DATA_COLUMNS


def test_finalising_twice_is_harmless():
    once = finalise_data_frame(adapter_frame("AURN", qa_code="verified"), "AURN")
    pd.testing.assert_frame_equal(finalise_data_frame(once.copy(), "AURN"), once)


def test_requested_range_attr_survives():
    frame = adapter_frame()
    frame.attrs["aeolus_requested_range"] = ["2024-01-01T00:00:00+00:00", "2024-01-02T00:00:00+00:00"]
    assert finalise_data_frame(frame, "AURN").attrs == frame.attrs
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_schema.py --no-cov -p no:cacheprovider -q`
Expected: `ModuleNotFoundError: No module named 'aeolus.schema'`

- [ ] **Step 3: Rename the adapter column list in `types.py`**

In `src/aeolus/types.py`, rename the existing `DATA_COLUMNS = [...]` list to `ADAPTER_DATA_COLUMNS` and keep `DATA_COLUMNS` as an alias for now (Task 5 repoints it):

```python
# What an ADAPTER emits. The public schema (aeolus.schema.DATA_COLUMNS) is
# built from this by aeolus.schema.finalise_data_frame.
ADAPTER_DATA_COLUMNS = [
    "site_code", "date_time", "measurand", "value", "units",
    "source_network", "ratification", "created_at",
]
DATA_COLUMNS = ADAPTER_DATA_COLUMNS  # repointed to the public schema in Task 5
```

- [ ] **Step 4: Implement `schema.py`**

```python
# src/aeolus/schema.py
"""
The public wire format, and the one step that produces it.

Adapters emit ``types.ADAPTER_DATA_COLUMNS``. ``finalise_data_frame`` runs where
every download converges and adds the network identity and the QA model. It is
the only code that knows both schemas — do not add these columns in adapters.
"""

import pandas as pd

from .network_registry import get_network_spec, route_for
from .qa import derive_qa, legacy_ratification

DATA_COLUMNS = [
    "site_code", "network", "date_time", "measurand", "value", "units",
    "qa_code", "qa_tier", "ratification_stage", "backend",
    "source_network", "ratification", "created_at",
]
LEGACY_DATA_COLUMNS = ("source_network", "ratification")  # mirrors, dropped in v1.0


def empty_public_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=DATA_COLUMNS)


def finalise_data_frame(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Turn an adapter frame for *source* into the public schema. Idempotent."""
    attrs = dict(df.attrs)
    if df.empty:
        out = empty_public_frame()
        out.attrs = attrs
        return out

    network, backend = route_for(source)
    spec = get_network_spec(network)
    out = df.copy()
    out["network"] = network
    out["backend"] = backend
    out["source_network"] = network

    wired = "qa_code" in out.columns
    codes = out["qa_code"] if wired else pd.Series(None, index=out.index, dtype=object)
    out["qa_code"] = codes.astype(object).where(codes.notna(), None)
    out["qa_tier"], out["ratification_stage"] = derive_qa(
        out["qa_code"], spec.qa_code_vocabulary, spec.default_ratification_stage
    )
    if wired or "ratification" not in out.columns:
        out["ratification"] = legacy_ratification(out["qa_tier"], out["ratification_stage"])

    out = out[DATA_COLUMNS]
    out.attrs = attrs
    return out
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_schema.py tests/test_qa.py tests/test_network_registry.py --no-cov -p no:cacheprovider -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/aeolus/schema.py src/aeolus/types.py tests/test_schema.py
git commit -m "feat(schema): public wire format and the finalising step"
```

---

### Task 5: Switch the library over — convergence points, adapters, cache v3

This is the breaking commit. It is large on purpose: the suite must go from green (old schema) to green (new schema) in one step.

**Files:**
- Modify: `src/aeolus/networks/api.py:150-156`, `src/aeolus/portals/api.py:175-181`, `src/aeolus/api.py` (`get_current`, the two `pd.DataFrame(columns=_STANDARD_COLUMNS)` sites), `src/aeolus/types.py`, `src/aeolus/cache.py`
- Modify: the four adapters that import `DATA_COLUMNS` — `sources/regulatory.py`, `sources/laqn.py`, `sources/eea.py`, `sources/sonitus.py`
- Modify tests: every adapter-level assertion on `DATA_COLUMNS`
- Test: `tests/test_schema.py` (extend)

**Interfaces:**
- Consumes: `schema.finalise_data_frame`, `schema.DATA_COLUMNS`, `schema.empty_public_frame`.
- Produces: `aeolus.download`, `aeolus.fetch`, `aeolus.networks.download`, `aeolus.portals.download`, `aeolus.get_current` all return the public schema. `types.DATA_COLUMNS` **is** `schema.DATA_COLUMNS`; `types.empty_data_frame()` still returns the *adapter* schema (adapters call it).

- [ ] **Step 1: Write the failing end-to-end tests** (append to `tests/test_schema.py`)

```python
from datetime import datetime
from unittest.mock import patch

import aeolus
from aeolus.registry import get_source


def _fake_fetcher(sites, start, end):
    return adapter_frame("AURN")


def test_download_returns_the_public_schema():
    with patch.dict(get_source("AURN"), {"fetch_data": _fake_fetcher}):
        out = aeolus.download("AURN", ["MY1"], datetime(2024, 1, 1), datetime(2024, 1, 2))
    assert list(out.columns) == DATA_COLUMNS
    assert out.loc[0, "network"] == "AURN" and out.loc[0, "backend"] == "RDATA"


def test_the_cache_holds_public_frames(tmp_path):
    from aeolus import cache

    cache.enable_cache(cache_dir=tmp_path)
    try:
        with patch.dict(get_source("AURN"), {"fetch_data": _fake_fetcher}):
            aeolus.download("AURN", ["MY1"], datetime(2024, 1, 1), datetime(2024, 1, 2))
        (path,) = tmp_path.rglob("*.parquet")
        assert "v3" in path.parts
        assert list(pd.read_parquet(path).columns) == DATA_COLUMNS
    finally:
        cache.disable_cache()


def test_a_cached_frame_with_the_wrong_columns_is_a_miss(tmp_path):
    from aeolus import cache

    cache.enable_cache(cache_dir=tmp_path)
    try:
        start, end = datetime(2024, 1, 1), datetime(2024, 1, 2)
        stale = adapter_frame("AURN")                      # eight old columns
        cache.put("AURN", "MY1", start, end, stale)
        assert cache.get("AURN", "MY1", start, end) is None
    finally:
        cache.disable_cache()
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_schema.py --no-cov -p no:cacheprovider -q -k "public_schema or cache_holds or wrong_columns"`
Expected: 3 failures (old column list; `v2` in the path; stale frame served).

- [ ] **Step 3: Finalise at the two download convergence points**

In `src/aeolus/networks/api.py`, replace the final `return _cache.fetch_with_cache(...)` with:

```python
    from .. import cache as _cache
    from ..schema import finalise_data_frame

    # Finalise BEFORE caching, so the cache only ever holds public frames.
    def fetch_public(sites_, start_, end_):
        return finalise_data_frame(fetcher(sites_, start_, end_), network)

    return _cache.fetch_with_cache(
        network, sites, start_date, end_date, fetch_public, last=last
    )
```

Make the identical change in `src/aeolus/portals/api.py` (the variable there is `portal`, not `network`).

- [ ] **Step 4: Finalise in `get_current`, and fix the empty frames in `api.py`**

In `src/aeolus/api.py`, import `from .schema import DATA_COLUMNS as _STANDARD_COLUMNS, finalise_data_frame` (replacing the `types` import of `_STANDARD_COLUMNS`). In `get_current`, wrap both return paths:

```python
    if fetch_latest is not None:
        return finalise_data_frame(fetch_latest(sites), resolved_source)
```

and the fallback's final frame likewise — `resolved_source` is the name `get_current` already resolved (e.g. `"AURN-SOS"`), so `backend` reflects what actually served the row.

- [ ] **Step 5: Repoint `types.DATA_COLUMNS`, keep adapters on the adapter list**

In `src/aeolus/types.py`, replace the alias line from Task 4 with a lazy re-export, and leave `empty_data_frame()` on the adapter list:

```python
def __getattr__(name):  # `from aeolus.types import DATA_COLUMNS` = the public schema
    if name == "DATA_COLUMNS":
        from .schema import DATA_COLUMNS
        return DATA_COLUMNS
    raise AttributeError(name)


def empty_data_frame() -> pd.DataFrame:
    """Empty frame in the ADAPTER schema — what a fetcher returns for no data."""
    return pd.DataFrame(columns=ADAPTER_DATA_COLUMNS)
```

In the four adapters, change `DATA_COLUMNS` to `ADAPTER_DATA_COLUMNS` in both the import and the `select_columns(*…, require_all=True)` call. Find them with:

Run: `grep -n "DATA_COLUMNS" src/aeolus/sources/*.py`
Expected: hits in `regulatory.py`, `laqn.py`, `eea.py`, `sonitus.py` only; after the edit every hit reads `ADAPTER_DATA_COLUMNS`.

- [ ] **Step 6: Cache v3 and the column check**

In `src/aeolus/cache.py`: set `_CACHE_VERSION = "v3"` and extend its comment with `v3 = the 0.5.0 public schema`. In `get()`, straight after the `pd.read_parquet` try-block:

```python
    from .schema import DATA_COLUMNS

    if list(data.columns) != DATA_COLUMNS:
        logger.debug("Cache entry has a different schema, refetching: %s/%s", source, site)
        return None
```

- [ ] **Step 7: Move adapter-level test assertions to the adapter list**

Tests that call a *fetcher or normaliser directly* must compare with `ADAPTER_DATA_COLUMNS`; tests that call `aeolus.download` compare with the public list.

Run: `grep -rln "DATA_COLUMNS" tests/ | sort`
For each file: if it imports `DATA_COLUMNS` and asserts on the output of `fetch_*`, `normalise_*`, `make_data_fetcher(...)` or `select_columns`, change the import and the assertion to `ADAPTER_DATA_COLUMNS`. `tests/conformance_helpers.py` and `tests/test_source_consistency.py` assert on `aeolus.download` output — leave them on `DATA_COLUMNS`, and in `conformance_helpers.py` add after the column check:

```python
    from aeolus.qa import QA_TIERS, RATIFICATION_STAGES

    assert set(data["qa_tier"].unique()) <= set(QA_TIERS)
    assert set(data["ratification_stage"].dropna().unique()) <= set(RATIFICATION_STAGES)
    assert (data["network"] == data["source_network"]).all()
```

- [ ] **Step 8: Run the whole offline suite**

Run: `uv run pytest -m "not live and not integration and not conformance" --no-cov -q -p no:cacheprovider`
Expected: all pass. Typical leftovers: a test building an 8-column frame and passing it to `cache.put` then `cache.get` (now a miss — give it a public frame via `finalise_data_frame`), and tests asserting an empty `download()` result has 8 columns.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(schema)!: downloads return the v0.5.0 wire format; cache v3

BREAKING: aeolus.download/fetch/get_current return 13 columns. source_network
and ratification remain as mirrors."
```

---

### Task 6: Legacy-mirror option and the one-time deprecation warning

**Files:**
- Create: `src/aeolus/options.py`
- Modify: `src/aeolus/schema.py`, `src/aeolus/__init__.py`, `tests/conftest.py`
- Test: `tests/test_schema.py` (extend)

**Interfaces:**
- Produces: `aeolus.options.legacy_columns: bool` (default `True`; env `AEOLUS_LEGACY_COLUMNS=0` sets it `False` at import); with it `False`, `finalise_data_frame` omits the two mirrors and emits no warning. With it `True`, the first finalised non-empty frame per process raises one `DeprecationWarning`.

- [ ] **Step 1: Write the failing tests**

```python
import warnings

import aeolus.options
from aeolus import schema


def test_mirrors_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(aeolus.options, "legacy_columns", False)
    out = finalise_data_frame(adapter_frame(), "AURN")
    assert "source_network" not in out.columns and "ratification" not in out.columns
    assert list(out.columns) == [c for c in DATA_COLUMNS if c not in schema.LEGACY_DATA_COLUMNS]


def test_deprecation_warning_is_raised_once_per_process(monkeypatch):
    monkeypatch.setattr(schema, "_warned_legacy", False)
    with pytest.warns(DeprecationWarning, match="source_network.*ratification.*AEOLUS_LEGACY_COLUMNS"):
        finalise_data_frame(adapter_frame(), "AURN")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        finalise_data_frame(adapter_frame(), "AURN")


def test_no_warning_when_mirrors_are_off(monkeypatch):
    monkeypatch.setattr(schema, "_warned_legacy", False)
    monkeypatch.setattr(aeolus.options, "legacy_columns", False)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        finalise_data_frame(adapter_frame(), "AURN")
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_schema.py --no-cov -p no:cacheprovider -q -k "mirrors or deprecation or no_warning"`
Expected: `ModuleNotFoundError: No module named 'aeolus.options'`

- [ ] **Step 3: Implement**

```python
# src/aeolus/options.py
"""Process-wide switches. Set as attributes: ``aeolus.options.legacy_columns = False``."""

import os

# Keep the pre-0.5.0 mirror columns (`source_network`, `ratification`) on every
# frame. Turn off to prove a consumer has migrated: anything still reading a
# mirror then fails loudly. Removed, with the mirrors, in v1.0.
legacy_columns: bool = os.environ.get("AEOLUS_LEGACY_COLUMNS", "1").strip() not in ("0", "false", "False")
```

In `src/aeolus/schema.py`, add `import warnings`, `from . import options`, a module flag `_warned_legacy = False`, and replace the tail of `finalise_data_frame` (from `out = out[DATA_COLUMNS]`) with:

```python
    global _warned_legacy
    if options.legacy_columns:
        columns = DATA_COLUMNS
        if not _warned_legacy:
            _warned_legacy = True
            warnings.warn(
                "The `source_network` and `ratification` columns are deprecated mirrors of "
                "`network` and of `qa_code`/`qa_tier`/`ratification_stage`; they will be removed "
                "in aeolus 1.0. Set AEOLUS_LEGACY_COLUMNS=0 (or aeolus.options.legacy_columns = "
                "False) to drop them now and check your code has migrated.",
                DeprecationWarning,
                stacklevel=4,
            )
    else:
        columns = [c for c in DATA_COLUMNS if c not in LEGACY_DATA_COLUMNS]
    out = out[columns]
    out.attrs = attrs
    return out
```

`empty_public_frame()` must honour the option too: build its column list the same way. In `src/aeolus/__init__.py` add `from . import options` and `"options"` to `__all__`. In `tests/conftest.py` add an autouse fixture so the one-time warning never makes test order matter:

```python
@pytest.fixture(autouse=True)
def _legacy_warning_already_given(monkeypatch):
    """The once-per-process DeprecationWarning is tested explicitly; elsewhere it is noise."""
    from aeolus import schema

    monkeypatch.setattr(schema, "_warned_legacy", True)
```

The cache's column check (Task 5, Step 6) must compare against the *active* column list: replace `DATA_COLUMNS` there with `list(empty_public_frame().columns)`.

- [ ] **Step 4: Run to verify**

Run: `uv run pytest tests/test_schema.py tests/test_cache.py tests/test_cache_correctness.py --no-cov -p no:cacheprovider -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(schema): legacy-mirror switch and one-time DeprecationWarning"
```

---

### Task 7: Metadata schema and the `network=` alias

**Files:**
- Modify: `src/aeolus/schema.py`, `src/aeolus/api.py` (`find_sites`, `download`, `fetch`, `get_current`)
- Test: `tests/test_schema.py` (extend), `tests/test_find_sites.py` (extend)

**Interfaces:**
- Produces: `schema.METADATA_COLUMNS = ["site_code", "site_name", "latitude", "longitude", "network", "country", "instrument_class", "provider", "backend", "measurands", "source_network"]`; `schema.finalise_metadata_frame(df, source) -> pd.DataFrame` (extra adapter columns such as `location_type` are kept, after the core ones); `download(..., network=...)`, `find_sites(network=...)`, `get_current(network=...)` accept `network=` as an alias of the first positional `sources`/`source` argument.

- [ ] **Step 1: Write the failing tests**

```python
def metadata_frame(**extra):
    base = {"site_code": ["MY1"], "site_name": ["Marylebone Road"], "latitude": [51.52],
            "longitude": [-0.15], "source_network": ["AURN"], "measurands": [["NO2"]]}
    return pd.DataFrame({**base, **{k: [v] for k, v in extra.items()}})


def test_metadata_gains_identity_columns():
    from aeolus.schema import METADATA_COLUMNS, finalise_metadata_frame

    out = finalise_metadata_frame(metadata_frame(location_type="Kerbside"), "AURN")
    assert list(out.columns) == METADATA_COLUMNS + ["location_type"]
    row = out.iloc[0]
    assert (row["network"], row["country"], row["instrument_class"], row["backend"]) == ("AURN", "GB", "reference", "RDATA")
    assert row["provider"] is None and row["source_network"] == "AURN"


def test_lmam_provider_comes_from_pcode():
    from aeolus.schema import finalise_metadata_frame

    out = finalise_metadata_frame(metadata_frame(pcode="sussex"), "LMAM")
    assert out.loc[0, "provider"] == "sussex"


def test_network_keyword_is_an_alias_for_the_source():
    with patch.dict(get_source("AURN"), {"fetch_data": _fake_fetcher}):
        a = aeolus.download("AURN", ["MY1"], datetime(2024, 1, 1), datetime(2024, 1, 2))
        b = aeolus.download(network="AURN", sites=["MY1"], start_date=datetime(2024, 1, 1), end_date=datetime(2024, 1, 2))
    pd.testing.assert_frame_equal(a.drop(columns="created_at"), b.drop(columns="created_at"))


def test_network_and_sources_together_is_an_error():
    with pytest.raises(TypeError, match="network.*sources"):
        aeolus.download("AURN", ["MY1"], datetime(2024, 1, 1), datetime(2024, 1, 2), network="AURN")
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_schema.py --no-cov -p no:cacheprovider -q -k "metadata or provider or keyword or together"`
Expected: `ImportError: cannot import name 'METADATA_COLUMNS'`, and `TypeError: download() got an unexpected keyword argument 'network'`.

- [ ] **Step 3: Implement `finalise_metadata_frame`** (append to `src/aeolus/schema.py`)

```python
METADATA_COLUMNS = [
    "site_code", "site_name", "latitude", "longitude", "network", "country",
    "instrument_class", "provider", "backend", "measurands", "source_network",
]


def finalise_metadata_frame(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Add network identity to an adapter's site metadata. Extra columns are kept."""
    network, backend = route_for(source)
    spec = get_network_spec(network)
    out = df.copy()
    for column in ("site_name", "latitude", "longitude", "measurands"):
        if column not in out.columns:
            out[column] = None
    out["network"] = network
    out["source_network"] = network
    out["country"] = spec.country
    out["backend"] = backend
    if "instrument_class" not in out.columns:
        out["instrument_class"] = spec.instrument_class
    # LMAM's provider is its pcode subfolder (spec D4); null for every other network
    out["provider"] = out["pcode"] if network == "LMAM" and "pcode" in out.columns else None
    core = [c for c in METADATA_COLUMNS if options.legacy_columns or c != "source_network"]
    extras = [c for c in out.columns if c not in METADATA_COLUMNS]
    return out[core + extras]
```

- [ ] **Step 4: Call it in `find_sites`, and add the alias**

In `src/aeolus/api.py`, inside `find_sites`'s per-source loop, finalise each source's frame before it is appended (`df = finalise_metadata_frame(df, name)`), import `METADATA_COLUMNS as _METADATA_COLUMNS` from `.schema` instead of `.types`, and change the measurand-filter code and the default-measurands lookup to read `combined["network"]`. Then give `download`, `fetch`, `find_sites` and `get_current` a trailing keyword-only `network=None` and start each with:

```python
    if network is not None:
        if sources is not None:     # `source` in find_sites / get_current
            raise TypeError("pass either `network=` or `sources`, not both")
        sources = network
```

`download`'s first parameter therefore becomes `sources: str | dict[str, list[str]] | None = None`; keep its existing "sources is required" error for the case where both are `None`.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest -m "not live and not integration and not conformance" --no-cov -q -p no:cacheprovider`
Expected: all pass. `tests/test_find_sites.py` assertions of the form `list(result.columns) == METADATA_COLUMNS` now need the `schema` list — update the import.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(schema): metadata identity columns and the network= alias"
```

---

### Task 8: Internal readers, docs of record, and the changelog

**Files:**
- Modify: `src/aeolus/api.py` (`summarise`), `src/aeolus/metrics/stats.py` (`time_average`), `src/aeolus/transforms.py`, `CLAUDE.md`, `README.md` (schema table), `docs/guide/overview.md` (schema section), `CHANGELOG.md`
- Test: `tests/test_api.py`, `tests/test_stats.py` (extend)

**Interfaces:**
- Produces: `summarise()` groups on and returns `network`; `time_average()` output has `network` (and, while mirrors are on, `source_network`). Both still accept a pre-0.5.0 frame that has only `source_network`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api.py
def test_summarise_reports_network_and_accepts_old_frames():
    import aeolus

    idx = pd.date_range("2023-01-01", periods=24, freq="h", tz="UTC")
    new = pd.DataFrame({"site_code": "MY1", "network": "AURN", "date_time": idx, "measurand": "NO2", "value": 1.0})
    old = new.rename(columns={"network": "source_network"})
    assert aeolus.summarise(new)["network"].tolist() == ["AURN"]
    assert aeolus.summarise(old)["network"].tolist() == ["AURN"]
```

```python
# tests/test_stats.py
def test_time_average_carries_network():
    df = _make_hourly_data(start="2023-01-01", end="2023-01-01 23:00", value=10.0)
    df = df.rename(columns={"source_network": "network"})
    assert time_average(df, freq="D")["network"].tolist() == ["TEST"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_api.py tests/test_stats.py --no-cov -p no:cacheprovider -q -k "reports_network or carries_network"`
Expected: `KeyError: 'source_network'` and `KeyError: 'network'`.

- [ ] **Step 3: Implement**

Add one helper to `src/aeolus/schema.py` and use it in both readers:

```python
def with_network_column(df: pd.DataFrame) -> pd.DataFrame:
    """Accept a pre-0.5.0 frame: if it has `source_network` but no `network`, add one."""
    if "network" not in df.columns and "source_network" in df.columns:
        return df.assign(network=df["source_network"])
    return df
```

In `summarise`: `df = with_network_column(data.copy())`, group on `["site_code", "network", "measurand"]`, emit `"network": network` in each row and in the empty-result column list. In `time_average`: call `with_network_column` on the input, take `network_val = group["network"].iloc[0] if "network" in group.columns else ""`, and emit it as `network` (rename `_TIME_AVERAGE_COLUMNS`' `source_network` entry to `network`). In `transforms.py`, change any default `"source_network"` argument or docstring example to `"network"`.

- [ ] **Step 4: Documentation of record**

Replace the 8-column schema list in `CLAUDE.md` ("Standard Data Schema"), in `README.md` and in `docs/guide/overview.md` with the 13 columns of `schema.DATA_COLUMNS`, one line each, marking `source_network` and `ratification` "deprecated mirror, removed in 1.0". In `CHANGELOG.md` under `[Unreleased]` add a `### Changed (breaking)` section: the new columns and what each means; the mirrors and `AEOLUS_LEGACY_COLUMNS=0`; `network=`; cache `v3`; PyYAML as a new dependency; and the sentence "Until each adapter is wired (next release step), `qa_code` is null and `qa_tier` is `unknown` for every network; the `ratification` mirror is unchanged."

- [ ] **Step 5: Full verification**

Run: `uv run pytest -m "not live and not integration and not conformance" --no-cov -q -p no:cacheprovider`
Expected: all pass.
Run: `mv .env .env.hidden; uv run --isolated --extra dev --python 3.13 pytest -m "not live and not integration and not conformance" --no-cov -q -p no:cacheprovider; mv .env.hidden .env`
Expected: all pass (this is what CI sees: no keys, no local-only packages — it catches an undeclared PyYAML).
Run: `uv run pytest tests/test_conformance.py -m conformance --no-cov -q -p no:cacheprovider`
Expected: 36 passed, 2 failed (AirQo authentication) — identical to `main`.
Run: `AEOLUS_LEGACY_COLUMNS=0 uv run pytest tests/test_schema.py tests/test_api.py --no-cov -q -p no:cacheprovider`
Expected: failures ONLY in tests that read a mirror column on purpose; none inside `src/aeolus`.

- [ ] **Step 6: Commit and open the PR**

```bash
git add -A
git commit -m "feat(schema): internal readers use network; schema docs and changelog"
git push -u origin feat/v050-contract-core
gh pr create --base main --title "v0.5.0 contract core: network registry, QA model, public schema"
```

---

## Self-review

- **Spec coverage.** §3.1 → Tasks 4–5; §3.2 → Task 7; §4.1–4.4 → Task 1; §4.3 mirror → Tasks 1, 4; §5 and §6 → Tasks 2–3; §8 → Task 2; §12 (`network=`, mirrors) → Tasks 6–7; §17.1 → Task 6; §17.2 → Task 5; §17.8 → Task 5. **Deliberately not here:** §7 QA wiring (Plan 2), §17.6 EEA datasets (Plan 3), §17.9 reference temperature (Plan 2), §11 ARGUS (Plan 5), the Argus parity CI test (switches on when Argus has seeds — Plan 5).
- **Spec gaps this plan resolves:** no `backend` value for Breathe London (added `BREATHE_LONDON`); PyYAML not yet a dependency (added); `SAQD` source unmentioned (routes to network `SAQN`).
- **Known limits:** `network=` is an alias only — it does not choose between `AURN` and `AURN-SOS` (that is the v0.6.0 routing engine). `instrument_class` is the network default on every site; per-site overrides arrive with Plan 2.
