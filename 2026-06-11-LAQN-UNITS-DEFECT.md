# LAQN units defect: NOx (all history) and O₃ (since 2026-05-01) are ppb-scaled

**Found:** 2026-06-11, during Argus cross-network dedup work (paired-hour
comparison of AURN CLL2 vs LAQN BL0, the Bloomsbury twins).
**Status:** diagnosed, not yet fixed. Fix belongs here (aeolus); data
remediation belongs in Argus.

## Evidence (all queries run against Argus prod, 2026-06-11)

1. **Physics check, last 90 days:** NOx-as-NO₂ can never be below NO₂.
   Sites with mean(nox) < mean(no2): LAQN **36 of 55**; AURN 0/156,
   AQE 0/195, SAQN 0/86, LMAM 0/13, NI 0/15 (WAQN 1/30, marginal).
   LAQN's within-site nox/no2 median ratio is 0.86 ≈ the healthy
   networks' ~1.65 divided by **1.91** (the NO₂ ppb→µg/m³ factor).
   Same picture in the pure-RData era (54/67 sites) and the post-2026-06-08
   window (15/17) — not a feed-switch regression.

2. **Twin-pair ratio:** paired same-hour LAQN BL0 / AURN CLL2 NOx median
   ratio is **0.524 ≈ 1/1.9094** — the 20 °C ppb→µg/m³(as NO₂) conversion,
   to four significant figures.

3. **O₃ step on 2026-05-01:** the same paired ratio for O₃ is 1.000
   (identical values) January–April 2026, then **0.501** from May —
   exactly the O₃ ppb factor (1 ppb = 2.00 µg/m³). Network-wide
   confirmation: May/April per-site mean ratio across LAQN O₃ sites is
   0.544 median with **11 of 12 sites halved**, while 96 AURN sites (the
   seasonal control) sit at 0.966 with none halved. This step predates
   the LAQN-ERG live switch (2026-06-08) — i.e. Imperial's openair RData
   export changed around 1 May 2026.

4. **NO₂ is clean** — recent paired values are identical (ratio 1.000);
   older data differs ~7% multiplicatively, which is ratification lag
   (one chain re-scaled on ratification, the other not yet), not units.
   SO₂ diffs are noise-scale.

## Mechanism in aeolus

- `src/aeolus/sources/regulatory.py:326` blanket-labels every non-CO
  species `ug/m3`. Defra's openair exports (AURN/SAQN/NI/WAQN/AQE/LMAM)
  honour that; **Imperial's LAQN export does not** — NOx ppb-scaled for
  at least the last 13 months, O₃ ppb-scaled since ~2026-05-01.
- `src/aeolus/sources/laqn.py` (ERG live): `SPECIES_MAP`/`UNITS_MAP`
  have no NOX entry (NOx isn't fetched there), and O₃ is labelled
  `ug/m3`. Post-June-8 LAQN NOx rows in Argus therefore come from the
  RData nightly, not ERG.

## Open questions for the fix

1. Does the LAQN RData file carry a units/unit column that
   `regulatory.py` ignores? If so, honour it (and convert or label).
2. What changed at Imperial on ~2026-05-01, and is NOx-in-ppb a
   long-standing property of their export or also a change? Worth an
   email to ERG — other openair consumers are likely affected too.
3. Which temperature convention for the conversion (20 °C, factor
   1.9125 for NO₂; 2.00 for O₃ — the observed ratios match 20 °C).
4. Does the ERG JSON API serve O₃ in ppb too? (The paired 0.501 ratio
   continues into the ERG era, but those hours may be RData-sourced.)

## Remediation sketch (Argus side, after the aeolus fix)

Affected stored data: **all LAQN `nox`** and **LAQN `o3` from
2026-05-01**. Do NOT scale in place (units provenance would be
unauditable). Preferred: delete the affected (site, measurand, window)
ranges and re-backfill through the fixed adapter — same playbook as the
KX004 error-code cleanup (time-scoped, site_id literals; see argus
CLAUDE.md "TimescaleDB compression" notes). Verify afterwards with the
physics check in (1), which is now part of the data-quality watchdog's
candidate queries.

**Blast radius in Argus today:** borough verdicts and homepage rollups
use pm25/no2 only — unaffected. `/explore` charts and
`/api/readings/bulk` serve LAQN nox/o3 raw — affected until remediated.
