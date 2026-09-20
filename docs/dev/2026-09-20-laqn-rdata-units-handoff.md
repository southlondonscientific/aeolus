# Handoff: LAQN RData gases are ppb, labelled `ug/m3`

**Date:** 2026-09-20
**From:** an Argus session (the readings write-path work you handed over this morning). **For:** the Aeolus v0.4.6 scrub.
**Status:** brief only — nothing in Aeolus has been changed. This file is untracked and uncommitted.

## Outcome (Aeolus session, same day) — confirmed, fixed by CONVERTING in the adapter

Checked against the raw files rather than taken on trust; the central claim holds and is broader than shown here
(three twin pairs, six years 2005–2026). **Decision (user): convert, do not relabel.** `LAQN` now emits µg/m³ (CO mg/m³)
using Defra's exact 20 °C factors (`LAQN_VOLUME_TO_MASS` in `sources/regulatory.py`); through the public API,
MY1 2023 annual means equal the AURN file to two decimals (NO2 41.62 = 41.62). So **Argus's units gate only needs to
assert, not convert** — and it must not multiply again. Corrections to this note and the June one: the June note's
"O3 changed on 1 May 2026 / NO2 clean" was aeolus 0.4.5 switching LAQN from the ERG API to RData, not a change at
Imperial; the NOx < NO2 physics check cannot detect this defect inside one file; AURN twins are an exact oracle only for
*ratified* years (provisional-year ratios wander 1.9–2.3); pre-~2015 files are rounded (residual ~0.5 µg/m³). The open
items below are closed: the file has no `no` column; `pm10_raw` is not read (aeolus reads `pm10`); LMAM is clean (all six
providers pass a stoichiometry test); CO is ppm and converts at 1.1642. Units audit of the other routes: §17.10 of
`v050_design.md`.

## The defect

`sources/regulatory.py` (~line 420) stamps units on every RData network with one blanket rule:

```python
lambda m: "mg/m3" if m == "CO" else "ug/m3"
```

That is right for the Defra-family openair files (AURN, SAQN, WAQN, NI, AQE, LMAM). It is **wrong for LAQN**.
The `londonair.org.uk/r_data/` files store gases in **volume units**; openair converts them on import and Aeolus,
reading the raw file, does not. From openair's `R/importImperial.R` (formerly `importKCL`), default `units = "mass"`:

```r
## change units to mass units, use values in ugm3Conversion table
if (units == "mass") {
  thedata$nox <- thedata$nox * 1.91
  thedata$no2 <- thedata$no2 * 1.91
  thedata$o3  <- thedata$o3  * 2.00
  thedata$so2 <- thedata$so2 * 2.66
  thedata$co  <- thedata$co  * 1.16
  thedata$pm10_raw <- thedata$pm10_raw * 1.30
```

So `aeolus.download("LAQN", …)` returns NOx / NO2 / O3 / SO2 in ppb and CO in ppm, all labelled `ug/m3` / `mg/m3`.
`LAQN-ERG` (the API route) returns true µg/m³. Same network, same label, values ~2× apart. Exactly the "silent wrong
numbers" class the scrub is about; it is not in `bug_audit_v046.md` or `v046_fix_plan.md` as of today.

### This was specified, then dropped

`aeolus/LAQN_RDATA_ENDPOINT.md` (written by a Pan session, 7 May 2026 — the note that proposed this source) says:
*"CRITICAL — units differ from AURN: the LAQN openair RData reports gases in ppb… The aeolus integration MUST
apply the ppb → µg/m³ conversion at parse time"*, with factors. Commit `d2a0535` added the source the same day
without it. Two consequences for the fix: (1) that note asked for **conversion at parse time**, which cuts against
the scrub's "no conversion at the adapter" principle — decide deliberately, and tell Argus which; (2) the missing
piece was a test, not knowledge — pin `LAQN` to its AURN twin (MY1, KC1) in the conformance suite.

## Evidence (aeolus 0.4.5.4, Marylebone Road MY1, 15 Sep 2026, values as returned)

| hour (UTC) | measurand | `LAQN` (RData) | `AURN` (RData) | `LAQN-ERG` |
|---|---|---|---|---|
| 10:00 | O3 | 15.22 | 30.73 | 30.4 |
| 14:00 | O3 | 28.42 | 60.47 | 56.7 |
| 18:00 | O3 | 35.59 | 70.05 | 71.0 |
| 10:00 | NO2 | 35.27 | 41.88 | 67.5 |
| 11:00 | NO2 | 36.75 | 43.41 | 70.3 |

- Median `LAQN-ERG / LAQN` over ~200 common hours each: **NO2 1.912, O3 1.996** — the 20 °C ppb→µg/m³ factors
  (1.9125, 1.9957). Across BX1 / MY1 / LB4, 273 of 274 common site-hours differ, all by these factors
  (SO2 ≈ 2.66, noisier because ERG rounds to 0.1).
- O3 is the clean three-way check: AURN-RData and ERG agree; LAQN-RData is half of both.
- **Do not read the NO2 AURN column as a units check.** AURN and ERG disagree for MY1 NO2 by a *calibration* relation,
  not a factor (AURN ≈ 0.73 × ERG − 8, stable over the day) — two data managers' provisional scaling of one
  analyser. Separate, real, and not an Aeolus bug; noted so nobody chases it as one.

### Added later the same day — it holds in old, ratified files, and the factors are exact

RData only, same analyser in both networks (the `AURN` file is Defra's µg/m³):

| site-year | NO2 `AURN`/`LAQN` | O3 | SO2 | residual after `LAQN` × factor |
|---|---|---|---|---|
| MY1 2023 (ratified) | 1.9125 | 1.9957 | 2.6609 | median 0.00, p95 0.00 µg/m³ |
| KC1 2019 (ratified) | 1.9125 | 1.9957 | 2.6609 | median 0.00, p95 0.00 |
| MY1 2012 | 1.9167 | 2.0000 | 2.7368 | median ~0.5 |

MY1 2023 annual mean NO2: 21.8 as Aeolus returns it, 41.7 converted, **41.7 in the AURN file**. The londonair files
are Defra's values divided by the *precise* 20 °C factors — so if you ever do convert, use 1.9125 / 1.9957 / 2.6609
(CO 1.1642, NO 1.2474), not openair's rounded 1.91 / 2.00 / 2.66. And the AURN twins (MY1, KC1, …) are a ready-made
exact conformance oracle for `LAQN`.

Also seen: MY1 2012 PM10 is ~24 % higher in the LAQN file than the AURN file (38.1 vs 30.8) — not units; looks like
TEOM correction (`pm10_raw` × 1.3 in openair vs AURN's reference-equivalent). Worth knowing which PM10 column the
adapter reads.

## Fix direction (yours to decide)

Your plan's principle is "emit units exactly as the network reports them; never assume `ug/m3`; no conversion imposed
at the adapter". Under that, the fix is a per-network units map: LAQN RData gases → `ppb`, CO → `ppm`, PM stays
`ug/m3`. Points to check while there:

- `pm10_raw` (TEOM ×1.3 in openair) — does Aeolus emit that column for LAQN, and under what measurand name?
- NOx: openair uses 1.91 (as NO2). Your WP notes say NOx/NO in ppb cannot be converted downstream for want of a
  molecular weight — labelling LAQN NOx as ppb will route it into that path.
- LAQN `NO` — not in openair's conversion list; confirm whether the file carries it and in what units.
- A conformance test that pins `LAQN` vs `LAQN-ERG` agreement for one site-week would have caught this.

**Re-baseline line for the fix plan:** LAQN RData gas values change meaning (relabelled ppb/ppm). Consumers that
stored them as µg/m³ hold values understated by 1.91× (NOx, NO2), 2.00× (O3), 2.66× (SO2), 1.16× (CO).

## Blast radius in Argus (measured today, read-only)

Argus backfills via the plain-name RData sources by design, and a nightly cron
(`argus/deploy/run-sos-outage-recovery.sh`, running since 14 May) re-sends a 6-day RData window that includes LAQN.

| LAQN gas rows in Argus (archive spans **2024-01 → now only**) | RData route — unrounded values, ppb-scale | ERG route — 1-dp values, µg/m³ |
|---|---|---|
| 2024-01 … 2025-03 (tier-1 RData backfill of 11 May 2026) | 1,443,408 (NO2 mean 12.9) | 90,488 — also RData: mean 11.6, just ≤1 dp by chance |
| 2025-04 (the join month) | 78,510 | 19,134 |
| 2025-05 … 2026-05-08 (earlier ERG-route year, RData interleaved) | 505,084 (NO2 mean 10.8) | 706,038 (NO2 mean 20.0) |
| since 2026-05-09 | 195,850 (9.1) | 159,075 (15.6) |

**Row-level discriminator:** the ERG API rounds to 1 dp, RData does not — `value <> round(value, 1)` marks an RData
row. (An earlier draft of this note split rows by `fetched_at` lag ≥ 30 h. That was wrong: ERG's day-granular API
delivers rows up to ~48 h late, so "late" ≠ RData. RHI 13 Sep 00:00–03:00 was the counter-example.)

Roughly **2.3 M of 3.2 M LAQN gas rows (~72 %) are ppb-scale values served as µg/m³.** Twin check on full years, so no
time-of-day confound: LAQN MY1+KC1 2024 NO2 = 12.0 as stored vs 25.5 for the same analysers under AURN.
NOx and CO are RData-only at the sites sampled (the ERG route returned NO2 / O3 / SO2), so those measurands are
ppb/ppm-scale throughout.

How it shows in served series — and why nobody saw it:
- **A period step in late April 2025**, where the RData backfill meets the ERG year. It fell in spring: the real
  March→May fall in NO2 almost exactly cancels the ×1.91 step, so served monthly means read 17.1 → 16.0 → 17.6.
- **Hour-level steps since then** in 27 of the 56 LAQN sites active for NO2 (29 are clean, none is mostly RData):
  wherever the ERG poller missed an hour, the nightly RData job filled it at half scale. Example, BT4 Brent–Ikea,
  10 Sep 2026: 15:00 = 31.7 (ERG) → 16:00 = 18.96 (RData; 36.3 converted) → … 20:00 = 11.09 (21.2).

Downstream: borough summaries and WHO ratios, the trend card, Hermes (Argus-first), RHEA via
`/api/readings/bulk`, and Argus's Pan baseline calibration artifact (annual means from the readings DB).

This is also why **the Argus prod deploy of the upsert is on hold**: under `DO NOTHING` the poller's ERG value
wins wherever it arrives first; under the upsert the nightly job would overwrite days 2–6 of LAQN gases at half scale every
night. The Argus-side repair is planned in `argus/docs/2026-09-20-laqn-units-repair-plan.md`: **re-download all LAQN
via RData** (decided — ERG does not serve historic data well) once your fix lands, through the new upsert, verified
against the AURN twins. It assumes you *relabel* (ppb/ppm) and Argus converts at ingest with the exact factors;
if you convert in the adapter instead, say so — Argus's units gate then only needs to assert.

## Verified vs not

Verified: the openair source above (fetched from `openair-project/openair` master today); the ratios, on
aeolus 0.4.5.4 against live upstreams; stored Argus values for MY1 match ERG for live-window rows; row counts by
write route. **Not** verified: PM columns in LAQN RData (assumed fine — mass by nature — but unchecked, and
`pm10_raw` specifically is not); LAQN `NO`; whether any *other* plain-name network has a similar quirk (the Defra
family shares one file convention, LAQN is the odd one out, LMAM unchecked); CO (ppm?) against a twin. The ppb
convention is now verified for 2012, 2019 and 2023 (table above) but not earlier.
