# Aeolus v0.4.6 — correctness scrub: sequenced fix plan

Source backlog: `docs/dev/bug_audit_v046.md` (two audits — the original 68-finding pass and the
2026-05-30 coverage + test-quality pass; ~130 distinct findings combined). The 3 Criticals already
shipped in v0.4.5.2.

## Scope & cut-line

- **v0.4.6 ships: all Important findings + every Medium/Low that is cheap and rides along with its
  cluster.** Remaining Medium/Low (resilience tail, micro-optimisations) → rolling backlog, not a blocker.
- **Test-quality fixes are NOT a separate phase.** Each work package fixes its product bugs *and* the
  tests that should have caught them, in the same commit — the test is what guards the fix against
  regression. (38 test-quality gaps total; the highest-value ones would have caught bugs we already shipped.)
- This is a "silent wrong numbers — please re-baseline" release: every WP that changes emitted values
  carries a CHANGELOG migration note. Consumers: Hermes, Argus, RHEA.

## Process

1. Branch `fix/v046-correctness-scrub` off `main`.
2. One commit per work package, TDD: write/repair the test first (it should fail on current code),
   then the fix. Targeted test sweeps per WP during iteration; full suite once at the end.
3. After all WPs: one diff-review pass over `git diff main..HEAD` (read the diff, not the tree),
   then ship v0.4.6.

## Up-front decision (reshapes WP1) — DECIDED

**Units philosophy: (B) label faithfully + convert downstream.** (Decided 2026-05-30.)

Sources emit correct *per-measurand* units exactly as the network reports them (AirNow stays ppb/ppm;
fix the mislabellers — SOS/Sonitus hardcoding `ug/m3` for CO → `mg/m3`; canonicalise notation). The
`units` column is authoritative. Metrics/viz must honour it: convert via the existing `ensure_ugm3`
(scalar) / `ensure_ugm3_array` to whatever unit they need *before* applying thresholds, means, or axis
labels — never assume `ug/m3`. No ppb→µg/m³ conversion is imposed at the adapter (that would bake in
molecular-weight + T/P assumptions and lose source-native truth).

Rationale: closest to aeolus's existing schema contract ("units — typically ug/m3", i.e. already
variable), preserves what each network actually measured, and keeps conversion visible at the point of
use. Cost accepted: every metrics/viz aggregation must respect the units column (WP1 + WP3 + WP6 cover this).

---

## Work packages (in order)

### WP1 — Units & unit-labelling  *(cross-cutting; do first)*  ✅ DONE
Split into two commits. The metrics/viz "honour the units column" half moved to **WP3** (metrics) and
**WP6** (viz) so those functions are touched once, with their other fixes.
- **WP1a (`97401ee`) — source labelling.** Sonitus per-measurand units (CO→`mg/m3`); SOS uses the
  `ts_info['uom']` it already derives instead of flat `ug/m3`; EEA canonicalises all unit notations
  (`µ`/`μ`→`u`, `.m-3`→`/m3`) not just `ug.m-3`. Tests: replaced the `test_sonitus` lock-in assertion;
  added SOS uom + EEA notation regression tests.
- **WP1b (`2ba10b0`) — conversion primitive.** `ensure_ugm3_array` now warns on unknown units and on
  ppb/ppm with no molecular weight (parity with scalar `ensure_ugm3`), instead of silently assuming µg/m³.
**Re-baseline:** CO units change for SOS/Sonitus (and any consumer concatenating CO across sources).
**Deferred here:** `ratification='None'` on SOS is unchanged — it matches `regulatory.py` and is a
separate ratification-vocabulary question, not units.

### WP2 — Missing-data sentinels & NaN handling  *(crashes + silent skew)*  ✅ DONE
Three commits. Scoped in parallel by 5 read-only scout agents (all findings confirmed real).
- **WP2a (`3addeb6`) — sources drop bad values.** AirNow `-999` sentinel + non-numeric-`Value` guard
  (no longer aborts the site fetch); SOS JSON-null guard (no longer crashes the timeseries);
  regulatory/sonitus/EEA NaN-value drops via `filter_rows`; sensor_community NaT-timestamp skip.
- **WP2b (`97aea60`) — AQI NaN→unknown.** All 5 index `calculate()`s guard NaN (was: EU/China/India
  reported the WORST band; US/UK crashed) and return value/category/color None.
- **WP2c (`fce7fcd`) — get_current.** Drops NaN-value rows before idxmax, returns the latest *valid*
  reading; an all-NaN group yields no row.
**Re-baseline:** AirNow/SOS means/exceedances change (sentinels removed); AQI on a missing reading is
now unknown rather than the worst category.

### WP3 — Metrics correctness: units-honouring + duplicate-timestamp + calendar-period
**Findings:** *(units-honouring, moved from WP1)* `aq_stats` exceedance thresholds assume `ug/m3`
without checking the units column (ppb NO2 mis-tested); `time_average` stamps `units.iloc[0]` on a
mixed-unit group and averages across scales — both must convert via `ensure_ugm3_array` / group on
`(measurand, units)`. *(duplicate-timestamp)* duplicate `(site,date_time,measurand)` inflates
`time_average` data-capture to 100% and double-counts in `resample().mean()`; same corrupts rolling AQI
in `aqi_summary`/`aqi_timeseries`. *(calendar)* coverage denominator hard-codes 720/2160/8760h
(Feb→0.93, leap years wrong); right-closed period bins violate left-closed; p95/p99 `.quantile()` lacks
explicit `interpolation=`; rolling AQI leaks across period boundaries; `aqi_timeseries` missing `.copy()`.
**Fix:** convert each group to µg/m³ (or group on `(measurand, units)`) before thresholds/means; dedup on
the key at the top of each metrics entry; derive `expected_hours` from the actual `pd.Period` span; fix
bin closure to left-closed; explicit `interpolation='linear'`; `.copy()`. Touch each metrics function once.
**Tests folded:** `test_download_robustness` tautological capture bounds; `test_stats` capture-range
can't catch >1.0; `test_metrics_properties` array-vs-scalar never reaches below-band/gap path.
**Re-baseline:** data-capture and period-AQI values shift. **Severity: Important.**

### WP4 — Schema consistency & find_sites robustness  *(crashes + silent concat misalignment)*
**Findings:** regulatory normaliser omits `select_columns` (wrong column order); `select_columns`
silently emits <8 cols when an upstream step failed; LMAM `measurands` is a comma-string not a list
(breaks `measurand=` filter — drops all LMAM); `find_sites(measurand=...)` KeyErrors when a source omits
`measurands`; AirQo grids fallback has no lat/lon → `find_sites` KeyError.
**Fix:** append `select_columns(*DATA_COLUMNS)` to regulatory; make `select_columns` `reindex` to the
full schema on the data path (or assert); LMAM `measurands`→sorted list; guard `find_sites` for a
missing `measurands` column; AirQo always emit lat/lon (NaN) + terminate normaliser with `select_columns`.
**Tests folded:** `test_regulatory` empty-schema `.empty`-only; `test_find_sites` fixtures always carry
`measurands`; `test_sensor_community` subset-only column checks.
**Severity: Important.**

### WP5 — Caching correctness
**Findings:** `last=` downloads never hit cache (`datetime.now()` µs → unique key every call →
unbounded Parquet growth, "instant re-run" promise broken); partial-success fetches cached as
authoritative (latches transient per-site failures); `_cache_key` tz-sensitive (naive vs UTC hash
differently); `cache_info` crashes on concurrent file removal.
**Fix:** quantise end-of-range (floor to hour) before keying / round `last=`-derived timestamps;
don't cache partial-success (or cache per-site); normalise tz in the key; guard `f.stat()` in `cache_info`.
**Tests folded:** `test_cache` multi-site key + sorted-order independence; `disabled_by_default` default.
**Severity: Important (the `last=` growth bug).**

### WP6 — viz robustness
**Findings:** `plot_diurnal/weekly/monthly/_plot_diurnal_panel/distribution` crash on incomplete time
axes; `plot_diurnal/calendar` silently pool multiple sites; `downsample(method="mean")` ZeroDivision on
short spans; `decimate` step floors to 1 (cap not honoured); `prepare_timeseries` averages mixed units;
`get_official_colours` WHO raises instead of degrading; UK_DAQI official colours dict-key collision.
**Fix:** reindex panels to full axes; single-site guard (error on multi-site); `freq_seconds=max(1,…)`
and `step=ceil(...)`; pivot on `(measurand, units)`; WHO colour entry; fix the colour-dict collision.
**Tests folded:** the big one — many plot tests assert only `isinstance(fig, Figure)`; assert on drawn
data (`ax.lines[0].get_ydata()` peaks/dips); the `downsample` NaN early-return test gap.
**Severity: Important/Medium (crashes on real sparse data).**

### WP7 — Latching caches & resilience tail
**Findings:** EEA `_get_spo_mapping` CSV-fallback latches `{}`; SOS `_get_network_mapping` latches `{}`
(both NEW beyond v0.4.5); `near_to_bbox` unclamped latitudes near poles → HTTP 400 → silent zero sites;
`list_networks()` leaks hidden `*-SOS` backends (ignores `primary=False`); Breathe London spatial filter
KeyError on missing lat/lon; AirQo `filter_invalid_rows` drops genuine 0 µg/m³; AirNow daily-chunk
`T00` boundary double-count + drops sub-day time; sensor_community re-downloads after type learned.
**Fix:** stay `None` on error (mirror v0.4.5 cache pattern); clamp lat to [-90,90]; `primary` filter on
`list_networks`; guard BL columns; AirQo `>= 0`; AirNow non-overlapping chunks + dedup + honour `%H`;
sensor_community move learned types out of `unknown_sites`.
**Severity: mixed Important/Medium.**

---

## Deferred to rolling backlog (post-v0.4.6)
Remaining Low-severity test-quality polish that doesn't guard a shipped fix; micro-perf items
(sensor_community re-download is in WP7 only because it's cheap). The `release.yml` Node-20 action bump
(before 2026-06-16) tracked separately.

## Rough sizing
WP1–WP4 are the correctness core (~1–2 days each with tests). WP5–WP7 lighter. One full-suite + one
diff-review at the end. Realistic: a focused multi-day scrub, shippable as a single v0.4.6.
