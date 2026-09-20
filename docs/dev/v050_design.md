# Aeolus v0.5.0 — design spec: the QA/schema contract + network registry

**Date:** 2026-06-09
**Status:** Design approved in brainstorming (2026-06-09); pending written-spec review before implementation planning.
**Addendum 2026-09-20 (§17):** seven items from checking this spec against the code after the correctness scrub landed
(PR #13). All are *proposals* until reviewed; §17 records the outcome of each.
**Supersedes framing in:** `sls-meta/2026-05-17-aeolus-v0.5-network-backend-architecture.md` (the full network/backend
refactor — now split: v0.5.0 takes the *contract*, v0.6.0 takes the *routing engine*).
**Grounded by:** the 2026-06-09 adversarial network-grounding workflow (64 agents, 21 cards, 2 skeptics/card +
consistency pass). Full cards + sources in the run output (`tasks/wkdfd4e4w.output`, key `result.cards`/`result.synthesis`);
workflow script under `.../workflows/scripts/aeolus-v050-network-grounding-*.js`.

---

## 1. What v0.5.0 is (and is not)

v0.5.0 is **the contract release**: it makes aeolus's wire format the canonical lingua franca for the SLS stack and
emits a real, network-aware data-quality model. It deliberately does **not** ship the full two-registry routing engine.

**In scope:**
- The **v0.4.6 correctness scrub** (`docs/dev/v046_fix_plan.md`), folded in and landed first as an internal milestone.
- The **wire-format break**: `source_network`→`network`, new `country`/`instrument_class`/`backend`, and the
  **three-column QA model** (`qa_code`/`qa_tier`/`ratification_stage`) replacing the single `ratification` string.
- A **network registry** (NetworkSpec-lite) carrying identity + the per-network QA vocabulary + structured
  ratification timing — enough to *derive* `qa_tier`, with no routing matrix.
- **Real QA-flag wiring** wherever upstream provides it (the work that makes the contract non-empty).
- The **ARGUS backend** (registered in the existing source style), gated on Argus shipping its QA migration + `/api/v1/`.
- Deprecation mirrors (`source_network`, `ratification`) and an additive `network=` kwarg.

**Out of scope → v0.6.0:** `BackendSpec` + the `(network, backend)` routing matrix; capability inspection;
cross-backend dedup; `source=` deprecation→removal; multi-backend split-and-stitch; network decomposition
(EEA/SONITUS/AirQo per-country/operator; LMAM per-council); cost-aware routing.

---

## 2. Decision ledger (locked in brainstorming 2026-06-09)

| # | Decision | Rationale |
|---|---|---|
| D1 | **Contract-first**: QA/schema + network registry + ARGUS backend now; routing engine → v0.6.0 | The QA contract only needs a *network* registry (to derive `qa_tier`); the backend routing matrix is mostly additive at the API surface, so it doesn't force a second consumer break. |
| D2 | **Fold v0.4.6 into v0.5.0** | One re-baseline event for downstream (Hermes/RHEA/Clara/Argus). Land correctness WPs first, then build the schema on correct numbers. |
| D3 | **Full QA wiring** wherever upstream exposes a flag; honest `unknown` elsewhere | Grounding proved aeolus emits *no* real QA today (hardcoded `'None'`); "promote existing mappings" was a false premise. |
| D4 | **LMAM = one platform code + `provider` per-site attribute** | Grounding refuted the per-pcode split: `aqdm` is a multi-council custodian bundle, pcode→council membership is unverified, and the "dataless pcode" partition is false (availability is per-site). |
| D5 | **`ratification_lag` is structured, not a scalar** | The single int conflated cadence vs first-ratification latency vs full-year-published across 10 networks — the #1 consistency defect. |
| D6 | **Gate ARGUS backend on Argus v1** (QA migration + `/api/v1/`) | Build clean against v1, no throwaway field-rename glue. |
| D6′ | *(proposed 2026-09-20, see §17.5)* Gate **only the ARGUS backend (§11)** on Argus v1 — not the release | The dependency is circular: Argus ingests through aeolus, so Argus's QA columns stay empty until aeolus wires real flags. |
| D7 | **Cut a 0.5.0a/rc** for internal consumers to migrate against | Catch schema-break surprises before a pinned release. |

---

## 3. Wire format (aeolus owns this)

### 3.1 DataRecord (download output)

| Column | v0.4.x | v0.5.0 | Notes |
|---|---|---|---|
| `site_code` | ✓ | ✓ | unchanged |
| `network` | — | **NEW** | renamed from `source_network` |
| `date_time` | ✓ | ✓ | unchanged (UTC-aware, left-closed) |
| `measurand` | ✓ | ✓ | unchanged |
| `value` | ✓ | ✓ | unchanged |
| `units` | ✓ | ✓ | unchanged (authoritative per-measurand, per v0.4.6 WP1 "label faithfully") |
| `qa_code` | — | **NEW** | verbatim upstream QA token; **never overwritten**; `null` where upstream is silent |
| `qa_tier` | — | **NEW** | six-value canonical enum (§4.1); derived from `qa_code` via the network's vocabulary |
| `ratification_stage` | — | **NEW** | four-value enum + `null` (§4.2) |
| `backend` | — | **NEW** | provenance: which fetcher served the row (`RDATA`/`ERG_REST`/`SOS`/`ARGUS`/`OPENAQ`/`PURPLEAIR`/`SENSOR_COMMUNITY`/`AIRNOW`/`EEA`/`SONITUS`/`AIRQO`) |
| `source_network` | ✓ | **mirror** | deprecation mirror of `network`; `DeprecationWarning`; dropped v1.0 |
| `ratification` | ✓ | **mirror** | deprecation mirror, derived from the triple (§4.3); dropped v1.0 |
| `created_at` | ✓ | ✓ | unchanged |

Additive-later (non-breaking, not in 0.5.0): `backend_version`, `detection_limit`, free-form `qa_flag`.

### 3.2 SiteRecord (metadata / `find_sites` output)

Adds `country` (ISO 3166-1 alpha-2, or `*` for global aggregators), `instrument_class` (per-site; §4.4),
`provider` (the LMAM per-site provider attribute, `null` for non-LMAM), and `backend`. Renames `source_network`→`network`
(mirror kept). `site_name`, `latitude`, `longitude`, `location_type`, `operator`, `measurands` unchanged.

---

## 4. Canonical enums (frozen — permanent public keys)

### 4.1 `qa_tier` — six values
`reference_full_qc` · `reference_provisional` · `lcs_calibrated` · `lcs_factory_only` · `flagged` · `unknown`
(definitions per the 2026-05-22 ratification doc; Argus owns the content, aeolus consumes via the shared vocabulary.)

### 4.2 `ratification_stage` — four values + null
`unratified` · `ratified` · `supplied` · `not_applicable`, **nullable**. The consistent rule (fixes the defect where the
hardcoded `'None'` was mapped five different ways across networks):

| Situation | `ratification_stage` |
|---|---|
| Regulatory network, ratification flag wired and present | `unratified` / `ratified` per the flag |
| Regulatory network, **has** a ratification concept but aeolus surfaces no per-row status (e.g. LAQN today) | **`null`** |
| Operator-supplied feed with no ratification cycle (LMAM, the "Supplied" sites in AQE/WAQN/NI) | `supplied` |
| LCS / no ratification concept | `not_applicable` |

### 4.3 Legacy `ratification` mirror (derived, dropped v1.0)
`ratified`→`Ratified`; `unratified`→`Provisional`; `qa_tier=lcs_calibrated`→`Indicative`; `lcs_factory_only`→`Validated`;
`unknown`+`not_applicable`→`Unvalidated`; `flagged`→`Invalid`; `null` status with `unknown` tier → `None`.

### 4.4 `qa_model` and `instrument_class`
`qa_model` ∈ {`regulatory_temporal_ratification`, `staged_calibration`, `point_in_time_validation`, `none`, `mixed`, `unknown`}.
`instrument_class` ∈ {`reference`, `equivalent`, `indicative`, `LCS`, `mixed`, `unknown`} (network default; per-site override allowed).

---

## 5. Network registry (NetworkSpec-lite — no routing engine)

Each network carries: `code`, `name`, `country`, `operators[]`, `regulatory: bool`, `instrument_class` (default),
`qa_model`, `qa_code_vocabulary` (`{code → {description, qa_tier, ratification_stage, source_url}}`), the structured
ratification timing (§6), `data_licence`, `homepage_url`, `notes`. **No** `BackendSpec`, capability set, or
`networks_served` — those are v0.6.0.

**Vocabulary governance:** shipped as `src/aeolus/data/qa_vocabularies/{NETWORK}.yaml`. A CI parity test enforces match
with Argus's `argus/db/seeds/qa_vocabularies/{NETWORK}.yaml` for the **7 UK networks Argus carries** (AURN, LAQN, AQE,
SAQN, WAQN, NI, BREATHE_LONDON). Argus's DB is canonical between aeolus releases; aeolus's YAML is a resynced snapshot.
**Aeolus is sole author** for LMAM and the internationals (AIRQO, PURPLEAIR, SENSOR_COMMUNITY, AIRNOW, EEA, SONITUS, OPENAQ).
(Argus's current seed uses the flat `{code: description}` form and code `BL`; the richer `{code → {tier, stage}}` structure
and the `BREATHE_LONDON` aeolus code must be reconciled into Argus's seed as part of D6.)

---

## 6. Structured ratification timing (replaces the scalar `ratification_lag_months`)

Three explicit fields on each regulatory NetworkSpec (all nullable; `null` = not applicable / not documented):
- **`ratification_cadence_months`** — how often the ratification exercise runs.
- **`first_ratification_latency_months`** — how long until a given observation first flips provisional→ratified (rolling).
- **`full_year_ratified_by`** — the annual-completeness milestone (free-text date, e.g. "~1 June of year+1").

Plus `ratification_overrides` (free-text) for per-site-type differences (e.g. AURN-affiliated sites in SAQN/WAQN ratify
quarterly while LA sites are six-monthly).

---

## 7. QA-flag wiring plan (the real per-adapter work)

| Network(s) | Wire what | Effort |
|---|---|---|
| AURN, SAQN, WAQN, NI, AQE | Replicate openair `importUKAQ(ratified=TRUE)`: join each site's `ratified_to` date and mark rows before it `ratified` (`qa_code`=`verified`/`Ratified`/`TRUE` per network), after it `unratified` (`unverified`/`Provisional`/`FALSE`). Add the `Supplied` token for LA-operated sites (WAQN model; extend to AQE, NI). | Medium — new metadata join in the regulatory pipeline |
| EEA | Map `Verification` (1/2/3) → stage; `Validity` (1..4 / -1 / -99) and `dataset` (E1a/E2a/Airbase) → tier. Already in the data. | Low–medium |
| PurpleAir | Map existing confidence/channel tokens (`Validated`, `Channel Disagreement`, `Single Channel A/B`, `Sensor Saturation`, `Invalid`, `Unvalidated`) → tier verbatim. | Low |
| AirQo | Distinguish calibrated stream (`lcs_calibrated`) from raw (`lcs_factory_only`); stop synthesising `'Indicative'` for missing status → `unknown`. | Low |
| AirNow | `qa_code='Provisional'` → `reference_provisional`/`unratified`. **Drop** the `-999`/negative→`flagged` mapping (small negatives are legitimate; EPA reports only valid data). | Low |
| LAQN, LMAM, Sensor.Community, Sonitus, OpenAQ | Honest `unknown` (no surfaced per-row flag); OpenAQ best-effort coarse tier from its monitor/sensor flag. | None (passthrough) |
| Breathe London | Map `P`→`lcs_calibrated`/`unratified`. **Do not freeze `R`** (auth-gated, never observed). Stop synthesising `'Indicative'` for missing status → `unknown`. | Low |

---

## 8. Grounded network table (the 15 v0.5.0 network codes)

Every row is backed by the cited upstream source in the workflow cards; the primary source is shown. Rows marked
**[ruling]** apply an adopted brainstorming ruling that overrides the card's first-pass (see §2 / §9).

| Code | Country | `qa_model` | `instrument_class` | QA codes → tier (verbatim upstream) | Ratification timing | Primary source |
|---|---|---|---|---|---|---|
| **AURN** | GB | regulatory_temporal_ratification | reference | `verified`→full_qc/ratified; `unverified`→provisional/unratified (openair `<species>_qc` TRUE/FALSE) | cadence 3mo; first-latency ~3mo (openair warns <6mo); full-year ~1 Jun yr+1 (ATR ~Sep) | gov.uk AURN guidance; openair importAURN |
| **LAQN** | GB | regulatory_temporal_ratification | reference | **none surfaced** → `unknown` / stage `null` **[ruling: phantom boolean dropped]** | revision window 12mo (londonair) | londonair.org.uk copyright |
| **AQE** | GB | regulatory_temporal_ratification | **mixed [ruling]** | `ratified`/`provisional`; **+`Supplied`** [ruling] | cadence ~6mo (non-AURN); full-year ~1 Jun yr+1 | airqualityengland.co.uk/about |
| **SAQN** | GB | regulatory_temporal_ratification | **mixed [ruling]** | `Ratified`/`Provisional`/`Supplied` | first-latency ~6mo (LA), ~3mo (AURN-affiliated override) | scottishairquality.scot/data/verification-ratification |
| **WAQN** | GB | regulatory_temporal_ratification | **mixed [ruling]** | `Ratified`/`Provisional`/`Supplied` (the template) | cadence 6mo (non-AURN), 3mo (AURN override); supplied sites never ratify | airquality.gov.wales/.../ratification-process |
| **NI** | GB | regulatory_temporal_ratification | **mixed [ruling]** | `Ratified`/`Provisional`; **+`Supplied`** [ruling] | first-latency ~6mo; full-year ~Sep yr+1 | airqualityni.co.uk/data/verification-and-ratification |
| **BREATHE_LONDON** | GB | staged_calibration | LCS | `P`→lcs_calibrated/unratified; **`R` not frozen** [ruling]; missing→`unknown` [ruling] | no fixed schedule (anchor-reference-dependent) | breathelondon.org/developers |
| **LMAM** | GB | mixed | mixed | **none surfaced → `unknown`/`supplied`**; `provider` is a per-site attribute **[D4]** | per-operator, not exposed | uk-air.defra.gov.uk `nondefraaqmon` |
| **AIRQO** | UG | staged_calibration | LCS (consumed stream) | `calibratedValue`→lcs_calibrated; `raw`→lcs_factory_only | n/a (near-real-time calibration) | docs.airqo.net calibration-guide |
| **PURPLEAIR** | * | point_in_time_validation | LCS | `Validated`/`Single Channel`→factory; `Channel Disagreement`/`Sensor Saturation`/`Invalid`→flagged; `Unvalidated`→unknown | n/a | community.purpleair.com confidence-score |
| **SENSOR_COMMUNITY** | * | none | LCS | none upstream → `unknown` / `not_applicable` | n/a | opendata-stuttgart meta wiki |
| **AIRNOW** | US | regulatory_temporal_ratification | reference | `Provisional`→provisional/unratified (AirNow feed never ratifies; AQS is separate) **[ruling: -999 sentinel dropped]** | certification ~1 May yr+1 (validated data in AQS) | airnow.gov/about-the-data |
| **EEA** | * | regulatory_temporal_ratification | reference | `Verification`1/2/3 → stage; `Validity`/`dataset` → tier | E1a verified by 30 Sep yr+1 (~9mo min) | dd.eionet.europa.eu vocabularies |
| **SONITUS** | IE | none | mixed | none surfaced → `unknown` / `not_applicable` | n/a | data.smartdublin.ie/dataset/sonitus |
| **OPENAQ** | * | mixed | mixed | `isMonitor=true`→reference_provisional/supplied; `false`→lcs_factory_only; measurement has no inline QA → `unknown` | n/a (per-provider) | docs.openaq.org |

**Uniform rule for the four non-AURN UK regulatory networks (AQE, SAQN, WAQN, NI):** all host centrally-ratified
reference sites *plus* LA-operated/supplied sites, so all four take `qa_model=regulatory_temporal_ratification` (their
defining axis — the heterogeneity is captured per-row, not by relabelling the model), `instrument_class=mixed`, and the
three-token vocabulary `Provisional`/`Ratified`/`Supplied`. AURN alone is pure `reference`. (This extends the approved
AQE/NI ruling to SAQN/WAQN for consistency, and keeps `qa_model` as the primary axis rather than `mixed` — see §15.)

**Notes carried into the registry:** AURN operators = four-party (Defra + Bureau Veritas CMCU + Ricardo QA/QC + NPL/ALN)
**[ruling]**. Licences corrected **[ruling]**: WAQN = Crown Copyright "personal or in-house use" (narrower than OGL);
Sensor.Community = ODbL (database) / DbCL (contents); AirQo = CC BY with a non-commercial override; AURN/NI/BL = OGL v3.0.

---

## 9. EEA, SONITUS, AirQo, OpenAQ — `is_one_network` borderline cases (kept single in 0.5.0)

The grounding flagged these as not-cleanly-one-network, but all share one harmonised framework / one consumed stream, so
the **canonical QA vocabulary is valid regardless of decomposition**. Decision: **keep a single code each in v0.5.0**, with a
"platform / harmonised-framework / aggregator" note; defer any per-country/per-operator decomposition to the v0.6.0 routing
layer. EEA (singular framework, ~38 operators) and AirQo (multi-tenant platform; consumed stream is AirQo-owned LCS) →
single code with `instrument_class=mixed` note. SONITUS (National vs Local) → single code, grade as a per-site attribute,
the authoritative EPA-IE ratified national data left as a *future separate* network. OpenAQ → §10.

---

## 10. Portals: OpenAQ & PurpleAir

The "portal" concept is **not dissolved** in v0.5.0 (that's the v0.6.0 backend reframe). `aeolus.portals` and the
`OPENAQ`/`PURPLEAIR` source codes stay, with their search-by-bbox/country access pattern unchanged; they additionally emit
the new schema and gain a registry entry.
- **PurpleAir** maps cleanly to one LCS network and is a *winner* of D3 — real channel/confidence QA wiring. The "portal"
  label becomes cosmetic.
- **OpenAQ** stays a single `OPENAQ` code (`country=*`) with a coarse best-effort `qa_tier` from its monitor/sensor flag,
  `qa_code` mostly `null`. **Documented, accepted limitations deferred to v0.6.0:** (a) no network attribution — an
  OpenAQ-mirrored AURN row stays tagged `network=OPENAQ`; (b) **no cross-source dedup** — pulling `OPENAQ` + `AURN`
  together can return the same physical sensor twice. The dedup that motivated the original refactor is explicitly not
  delivered here.

---

## 11. ARGUS backend

Registered in the existing source style (not yet a `BackendSpec`), emitting the new schema natively. **Gated on Argus
shipping its QA migration (Phase 1) + `/api/v1/`** (D6) so it's built clean against v1 with no field-rename glue. Reads
`/api/v1/sites` + `/api/v1/readings/bulk`; `AEOLUS_ARGUS_API_KEY`; rate-limit-aware retry; cache key includes the adapter
version. Closes the loop (aeolus both feeds Argus's ingestion and can read Argus's harmonised/live data) and makes the
future Hermes-on-Argus migration a one-line source change.

---

## 12. API surface & migration

- `source=` stays **primary and unchanged**. `network=` added as an **additive alias** (in contract-first, one network =
  one default route, so it's harmless and forward-compatible). `backend=` waits for v0.6.0.
- Deprecation mirrors `source_network` and `ratification` preserved with `DeprecationWarning`; dropped in v1.0.
- This is a **"silent wrong numbers / new schema — please re-baseline"** release. Every changed-output path carries a
  CHANGELOG migration note. Consumers: Hermes, RHEA, Clara, Argus.

---

## 13. v0.4.6 fold & internal sequencing

The seven correctness work packages from `docs/dev/v046_fix_plan.md` land **first**, as an internal milestone on the
v0.5.0 branch, each TDD per its plan (test-first, one commit per WP). Only then is the schema break built on top, so the
new contract is laid over correct numbers. One full-suite run + one diff-review gate before the alpha.

---

## 14. Rollout

1. Land v0.4.6 WPs (internal milestone).
2. Build the schema + registry + QA wiring + ARGUS backend (gated on Argus v1).
3. Cut **0.5.0a1/rc1** (D7) to PyPI/TestPyPI; Hermes/RHEA/Clara/Argus migrate + report.
4. Migration guide + CHANGELOG re-baseline notes + docs rewrite (network/QA framing).
5. **0.5.0** final on PyPI.

---

## 15. Residual items to settle during implementation (not blockers)

These are grounded but carry `needs_review`/`contested` verifier verdicts; resolve with a cited source as each WP is built,
do **not** silently pick:
- **AURN** first-ratification latency: 3 (card) vs 6 (openair 180-day threshold). Structured timing (§6) records both the
  3-month cadence and the practical <6-month-provisional behaviour, so the scalar ambiguity no longer forces a single wrong number.
- **AQE/SAQN/WAQN/NI** confirm the `Supplied` third state + `instrument_class=mixed` against each operator's published QA
  doc, and confirm the choice to keep `qa_model=regulatory_temporal_ratification` (vs the synthesis's suggested `mixed`).
- **WAQN/NI** confirm Ricardo-as-contractor and exact cadence (Argus seed TODOs); **WAQN licence** is confirmed narrower-than-OGL.
- **EEA** ratification scalar is a range (min ~9mo, typical ~15mo); `dataset=3` Airbase legacy may be `supplied` not `ratified`;
  `Validity=1..4`→`reference_full_qc` may over-claim — confirm against the EIONET vocabulary.
- **LMAM** per-provider QA facts (Sussex `Approved`/`Provisional`, Kent `ratified`/`provisional`, etc.) are recorded in the
  appendix for a possible v0.6 decomposition but are **not** minted as networks now; the LMAM feed emits `unknown` for all.

---

## 16. Appendix — LMAM provider reference (informational; NOT minted as networks in 0.5.0)

Recorded from grounding for a future v0.6 decomposition decision. In v0.5.0 these are `provider` attribute values on LMAM
sites, all emitting `qa_tier=unknown` (the harvest feed carries no QA flag).

| `provider` | Operator / nature | `is_one_network` (grounded) | Operator-side QA (not in feed) |
|---|---|---|---|
| `sussex` | Sussex Air Quality Partnership (ERG-operated) | yes | `Provisional`→`Approved`, annual review |
| `kent` | Kent & Medway AQ Partnership (KMAQN) | yes | `provisional`/`ratified`, 3–6mo |
| `aqdm` | **AQDM/UK-Air custodian bundle — multi-council** | **no** | per-council, none exposed |
| `nlincs` | North Lincolnshire Council | yes | supplied as-is |
| `leicester` | Leicester City Council (via AQE/Ricardo) | yes | LAQM cycle, ~6mo (inferred) |
| `hants` | Hampshire (multi-authority; legacy ~2010–2015) | **no** | per-authority, none exposed |

Dataless pcodes (`london`/`aqengland`/`essex`): **do not reserve codes** — the per-pcode "dataless" partition was
empirically refuted (availability is per-site). `london` sites route to LAQN; `aqengland` (Hertfordshire & Bedfordshire)
must **not** collide with the existing `AQE` code if ever minted.

---

## 17. Addendum 2026-09-20 — spec checked against the code

Written after the correctness scrub (§13, rollout step 1) landed as PR #13. Each item states what was found, the
proposal, and its review status. **Nothing here is decided until its status says so.**

### 17.1 How the deprecation mirrors warn  — *PROPOSED*
**Found:** §3.1/§12 say `source_network` and `ratification` are kept as mirrors "with `DeprecationWarning`", but pandas
cannot warn when a column is *read*, so the mechanism is unspecified.
**Proposal:** emit one `DeprecationWarning` per process, from the first public call that returns a data or metadata frame
(`download`, `fetch`, `find_sites`, `get_current`), with `stacklevel` pointing at the caller — so it shows in notebooks,
scripts and pytest runs, and stays hidden when aeolus is called from deep inside another library. Add an opt-out,
`AEOLUS_LEGACY_COLUMNS=0` (and `aeolus.options.legacy_columns = False`), which drops the mirrors and the warning. The
opt-out doubles as the migration test for Hermes/RHEA/Clara/Argus: run their suites with it set, and anything still
reading a mirror fails loudly. aeolus's own metrics/viz/cache/summarise code must read `network`, never the mirror.

### 17.2 The Parquet cache holds v0.4 frames  — *PROPOSED*
**Found:** `aeolus.cache` keys on source/sites/window only. After upgrading, a cached 8-column frame would be served as if
it were a v0.5.0 result. The spec versions only the ARGUS backend's cache key (§11).
**Proposal:** a schema version in the cache *path* (`~/.cache/aeolus/v2/<SOURCE>/…`), so old and new entries can never be
confused and old ones are easy to find and delete; plus a defensive check on read — a cached frame whose columns are not
the current `DATA_COLUMNS` is treated as a miss. `cache_info()` reports legacy files; `clear_cache()` removes them.

### 17.3 Rows upstream marks invalid: drop or `flagged`?  — *PROPOSED*
**Found:** EEA rows with `Validity < 1` (−1 not valid, −99 maintenance/calibration) are dropped today; §7 maps `Validity`
→ tier and §4.1 has a `flagged` tier, without saying which applies. PurpleAir already *keeps* doubtful rows behind
`include_flagged`. The scrub (WP2) dropped AirNow `-999` and NaN values on the principle that a bad number must never
reach `value`.
**Proposal — one rule for every adapter:** a row is **dropped** when upstream says the value is not a measurement
(invalid, sentinel, missing); a row is **`flagged`** when upstream publishes a usable value with a quality caveat
(PurpleAir channel disagreement, EEA below-detection-limit codes 2/3 are *valid* and are not flagged at all). So EEA
−1/−99 stay dropped, consistent with WP2.

### 17.4 AirQo: no calibrated/raw signal in the adapter  — *OPEN, needs investigation*
**Found:** §7/§8 map `calibratedValue` → `lcs_calibrated` and `raw` → `lcs_factory_only`, but the adapter reads only
`pm2_5.value` / `pm10.value`, and the measurement shape characterised on 2026-06-09 had no other field. Cannot be checked
now: `AIRQO_API_KEY` is failing authentication (conformance run, 2026-09-20).
**Proposal:** do not block the alpha on this. Ship AirQo as `qa_tier=unknown` in 0.5.0a1; once the key is regenerated,
characterise the live payload and either wire the distinction or amend §8 with a cited reason it is unavailable.

### 17.5 D6 — what is actually gated on Argus  — *PROPOSED (see D6′ in §2)*
**Found:** as of Argus `main` @ `103116f` none of the three Argus deliverables exists (Phase 1 QA migration, `/api/v1/`,
rich vocabulary seeds), and the dependency is circular — Argus's `qa_flag` is NULL for every AURN-family row *because*
aeolus emits `'None'`. Argus's Phase 1 spec also predates the 2026-06-09 grounding and carries refuted premises.
**Proposal:** gate only §11 (the ARGUS backend). Sequence: aeolus 0.5.0a1 (schema + registry + QA wiring) → Argus Phase 1,
seeds and `/api/v1/` migrate *against the alpha* (the real-world vocabulary check D7 wanted) → aeolus 0.5.0 final, with the
ARGUS backend in 0.5.0 or a 0.5.x. The CI parity test (§5) starts as aeolus-authored YAML and is switched on when Argus
has seeds to compare. Separately, Argus's write path had to stop discarding corrected values (`ON CONFLICT DO NOTHING`)
before it can absorb *any* re-baseline — implemented on Argus branch `feat/readings-upsert-history`, 2026-09-20.

### 17.6 EEA queries the wrong dataset  — *FOUND 2026-09-20, NEW WORK ITEM*
**Found (probed live, IE NO2):** the download API's `dataset` ids are **1 = up-to-date E2a** (recent data only, every row
`Verification=2`), **2 = verified E1a** (2019 and 2023 present, `Verification=1`), **3 = historical Airbase** (2012
present, `Verification=0`). The adapter's constant `DATASET_E1A = 1` is misnamed: aeolus requests only the up-to-date
feed, so **EEA downloads for earlier years return empty**. The conformance test never noticed because it only asserts
`if not data.empty`. (The `Verification` label map was also inverted — fixed in PR #13, cited to the EIONET vocabulary.)
**Proposal:** fold into §7's EEA wiring, which already keys tier on `dataset`. Select datasets by requested window —
verified archive first, up-to-date feed for what the archive does not yet cover, Airbase before 2013 — preferring the
verified row where both hold the same `(site, measurand, timestamp)`. `Verification=0` (Airbase) needs a vocabulary entry;
§15 already suspects it is `supplied` rather than `ratified`. Make the conformance test assert non-empty for a past year.
**Open:** whether this should be pulled forward of 0.5.0 — historical EEA data is unreachable in the released version.

### 17.7 AURN-family ratification is per parameter, and already downloaded  — *NOTE*
**Found:** §7 says "join each site's `ratified_to` date". The openair metadata RData that aeolus already fetches carries
`ratified_to` **per site *and* parameter** (verified live for AURN and SAQN; e.g. `ABD9` → `2026-06-30`), alongside
`start_date`/`end_date`. No new upstream source is needed, and the join key should be `(site_code, measurand)`, not
`site_code` — a site's pollutants can be ratified to different dates. Effort drops from "medium" towards "low–medium".

### 17.8 What the scrub changed that this spec should assume
- Every data path now ends in `select_columns(*DATA_COLUMNS, require_all=True)` — a single choke point. The new columns,
  the mirrors and `qa_tier` derivation can be added in **one shared finalising step** rather than in 14 adapters.
- `units` is authoritative and metrics/viz convert on use; `aq_stats` output has a `units` column.
- Retry is effective and RData hosts have a circuit-breaker; the ARGUS backend's "rate-limit-aware retry" (§11) should
  reuse that machinery, including the key-safe retry logger.
- Rename blast radius (for planning): `source_network` appears in 18 source files, 39 test files, 7 notebooks, 18 docs;
  `ratification` in 16 / 26 / 4 / 22. Mechanical but wide — one commit, with the mirrors in place so everything stays green.

### 17.9 Conversion reference conditions are a property of the network  — *PROPOSED*
**Found (2026-09-20, LAQN units defect):** aeolus converts ppb ↔ µg/m³ with `MOLAR_VOLUME = 24.45` L/mol (25 °C, the US
convention). UK and EU data are defined at **20 °C / 1013 mb** (Defra factors: NO2 1.9125, O3 1.9957, SO2 2.6609,
CO 1.1642, NO 1.2474) — aeolus's constant is 1.6 % low against them. It no longer bites UK data, because every UK route
now emits mass units (LAQN is converted in the adapter with the exact factors — the one sanctioned exception to "label
faithfully", because the ppb there is an openair interchange format, not what the network reports). It still applies
when µg/m³ data from a 20 °C network is converted *to* ppb for the US EPA index, and to OpenAQ's mixed feeds.
**Proposal:** a `reference_temperature_c` field on each NetworkSpec (20 for UK/EU, 25 for US), used by
`ensure_ugm3`/`to_index_unit` when the row's network is known, falling back to 25. No change to results for US data.

### 17.10 Units and time conventions — audit status  — *NOTE*
**Units (audited 2026-09-20):** every RData host (AURN, SAQN, WAQN, NI, AQE) and all six LMAM providers pass an internal
stoichiometry test — `(NOXasNO2 − NO2) / NO` is 1.533 in mass units, 1.000 in ppb; LAQN-ERG equals AURN exactly on a
ratified week; Sonitus NO2 matches eight EEA Irish twins at 0.97–1.00. LAQN RData was the only defect. Not checked:
non-PM fields of PurpleAir/Sensor.Community, and SOS and OpenAQ (no data returned in the sample).
**Time (NOT audited — and never scheduled):** the v0.4.6 audit's five time-handling findings (Sonitus Dublin-local parsed
as UTC; AirNow local hour as UTC; EEA never coerced; PurpleAir/Sonitus `.timestamp()` machine offset; Breathe London
`strftime("…Z")`) were not assigned to any work package. Evidence gathered since: EEA `Start` equals the German UBA
API's start times exactly and Luchtmeetnet's stamps exactly, which implies UTC+1 *if* UBA is fixed CET and Luchtmeetnet
stamps hour-ending — conventions recalled, not found in writing; Sonitus returns its first record an hour after the
requested UTC window start, suggesting local-time stamps. **This needs its own audit, by the same method as units:
twin sources with known clocks, route by route. It should precede any claim in v0.5.0 that `date_time` is UTC.**

