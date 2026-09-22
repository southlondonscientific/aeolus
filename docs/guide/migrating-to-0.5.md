# Migrating to 0.5

0.5.0 is a **"new schema, corrected numbers — please re-baseline"** release. Nothing you fetched with 0.4 should be assumed equal to what 0.5 returns. This page lists what changed, how to find each change in your code, and how to prove you have migrated.

## Ten-minute checklist

1. Install the alpha: `pip install --pre "aeolus_aq==0.5.0a1"` (pip only — alphas are not published to conda-forge; PyYAML is a new runtime dependency and comes with the wheel).
2. Run your code with `AEOLUS_LEGACY_COLUMNS=0`. Anything that reads `source_network` or `ratification` breaks here — fix it with the column map below.
3. Rename: `source_network` → `network`. If you also need to know *which fetcher* produced a row, read `backend`.
4. Replace every test on `ratification` with a test on `qa_tier` or `ratification_stage` (table below). Keep `qa_code` if you want the network's own word.
5. Re-fetch anything you store: values changed for LAQN gases, SOS/Sonitus CO, AirNow/SOS sentinels, EEA past years, OpenAQ and Sonitus timestamps, monthly/quarterly/annual `time_average` labels, and the `ratification` mirror for wired networks.
6. Clear or ignore caches written by 0.4: 0.5 uses `~/.cache/aeolus/v4/` and never serves older entries.

## Column map

| 0.4 | 0.5 | Notes |
|---|---|---|
| `source_network` | `network` | mirror kept until 1.0, `DeprecationWarning` once per process |
| `ratification` | `qa_code` + `qa_tier` + `ratification_stage` | mirror kept until 1.0, now *derived* from the three columns |
| — | `backend` | `RDATA`, `SOS`, `ERG_REST`, `EEA_E1A`/`EEA_E2A`/`EEA_AIRBASE`, ... |
| (metadata) `source_network` | `network` | plus new `country`, `instrument_class`, `provider`, `backend`, `measurands` |

Every `download()` (top-level, `aeolus.networks`, `aeolus.portals`) returns the public 13-column frame. For metadata, only the top-level `aeolus.find_sites()` returns the public schema; `aeolus.networks.get_metadata()` and `aeolus.portals.find_sites()` still return the raw adapter frames with `source_network`.

## The `ratification` mirror changed meaning

For wired networks the mirror is now computed from `qa_tier` and `ratification_stage`, and the **stage wins**: tier `lcs_calibrated` → `Indicative`, `lcs_factory_only` → `Validated`, `flagged` → `Invalid`, tier `unknown` with a stage → `Unvalidated`; then stage `ratified` → `Ratified` and `unratified` → `Provisional` overwrite the tier label. Rows with no stage and no tier label are the *string* `"None"` (as in 0.4), not a null. Networks that publish no flag keep the label their adapter always set.

Concretely, per network:

| Network | 0.4 `ratification` | 0.5 `ratification` (mirror) | Read instead |
|---|---|---|---|
| AURN, SAQN, WAQN, NI, AQE | always `None` | `Ratified` / `Provisional` per site, pollutant and date (`ratified_to` from the openair metadata) | `ratification_stage` |
| AURN-SOS etc. / `get_current()` | `None` | `Provisional` | `ratification_stage` |
| EEA | `Verified` / `Provisional`, **inverted** (1 → Provisional) | `Ratified` (code 1) / `Provisional` (2, 3); Airbase rows (code 0) `None` | `qa_code` (`"1"`, `"2"`, `"3"`, `"0"`) |
| PurpleAir | channel labels verbatim | `Validated` (Validated, Single Channel A/B, Below Detection Limit) / `Invalid` (Channel Disagreement, Sensor Saturation, Invalid) / `Unvalidated` | `qa_code` (the label) |
| Breathe London | `Indicative` synthesised when the API gave no status | `Provisional` (status `P`: calibrated but unratified) or `Unvalidated` (no status) | `qa_code` |
| AirNow | `Provisional` | `Provisional` | `ratification_stage` |
| AirQo | `Indicative` | `Indicative` (unchanged; not yet wired) | `qa_tier` (`unknown`) |
| Sensor.Community, Sonitus, OpenAQ | `Unvalidated` | `Unvalidated` (unchanged) | `qa_tier` (`unknown`) |
| LAQN, LMAM | `None` | `None` (unchanged) | `qa_tier` (`unknown`); LMAM `ratification_stage = supplied` |

## Values that changed (re-baseline)

| Path | What changed | Since |
|---|---|---|
| `LAQN` (RData route) gases NO2, NOx, NO, O3, SO2, CO | were ppb/ppm labelled `ug/m3`/`mg/m3`; now converted with Defra's 20 °C factors (×1.9125 NO2/NOx, ×1.9957 O3, ×2.6609 SO2, ×1.1642 CO, ×1.2474 NO). MY1 annual NO2 2023: 21.8 → 41.6 | 0.5.0 |
| `LAQN-ERG` | returned whole days; now trimmed to the requested hours | 0.5.0 |
| SOS sources and Sonitus CO | unit relabelled `ug/m3` → `mg/m3`, values unchanged | 0.5.0 |
| SOS unit strings | `ug/m-3` → `ug/m3` | 0.5.0 |
| AirNow, SOS, regulatory, Sonitus, EEA | `-999`/sentinel and NaN rows dropped instead of stored | 0.5.0 |
| AirNow | the final day of a window was mostly skipped; now fetched | 0.5.0 |
| `get_current("AIRNOW")` | timestamps were off by the site's UTC offset | 0.5.0 |
| AirQo | genuine 0 µg/m³ readings are kept (were dropped) | 0.5.0 |
| EEA, any year before the up-to-date feed | previously **empty**; now served from the verified archive (E1a) or Airbase, with `backend` saying which | 0.5.0 |
| EEA `ratification` | was inverted (code 1 → `Provisional`); now code 1 → `Ratified`, 2/3 → `Provisional` | 0.5.0 |
| EEA timestamps | converted from the EEA's UTC+1 (Ireland's archive: UTC; Italy's feed: local) — one-hour shift vs 0.4 | 0.5.0 |
| OpenAQ timestamps | were the END of the hour; now the start (−1 h) | 0.5.0 |
| Sonitus timestamps | were the end of each 15-minute bin; now the start (−15 min); first summer hour no longer lost | 0.5.0 |
| Request windows (PurpleAir, Sonitus, Breathe London, EEA) | were read on the machine's local clock; now UTC | 0.5.0 |
| `time_average(freq="ME"/"QE"/"YE"/"W")` | rows labelled at period start (were end) and capture uses the right denominator | 0.5.0 |
| `aq_stats()` | converts ppb/ppm to µg/m³ before thresholds and reports a `units` column (annual means were ppb labelled µg/m³) | 0.5.0 |
| `time_average()`, `trend()`, temporal plots | mixed-unit groups converted before pooling (were averaged across scales) | 0.5.0 |
| Duplicate `(site, measurand, date_time)` rows | collapsed before statistics (inflated capture and averages) | 0.5.0 |
| AQI of a missing reading | unknown, not the worst band (or a crash) | 0.5.0 |
| `aqi_summary()` coverage | real period span and one cadence per site/pollutant | 0.5.0 |
| data capture, period AQI | shift with the above | 0.5.0 |

Still open: the interval convention of the UK-AIR SOS near-real-time feed (`get_current()`) is unverified while Defra's endpoint is down; it may label hours one out of step with downloads. Compare before you join the two.

## Behaviour changes that are not value changes

- `find_sites()` and `networks.get_metadata()` list only AURN-family sites that are still measuring something, one row per site (0.4 listed every site ever run, once per parameter — the nearest AURN site to central London was one closed in 1978). Site `start_date`/`end_date` are now aggregated across the site's series and the per-parameter `ratified_to` is gone from the site list (read `qa_code` on the data instead). Pass `include_closed=True` for historical work.
- `download()`, `fetch()`, `find_sites()`, `get_current()` accept `network=` as an alias for the first argument.
- `summarise()` and `time_average()` report `network` and accept 0.4 frames.
- `get_source_info()` reports `status` (`stable` | `experimental`) and `status_note`; **EEA is experimental** and raises one `AeolusExperimentalWarning` per process.
- Each AURN-family download fetches that network's metadata once per process (memoised `AEOLUS_METADATA_TTL_S`, default a day) for the ratification join.
- Retries now actually retry; after `AEOLUS_RDATA_BREAKER_FAILURES` consecutive failures an openair host fails fast for `AEOLUS_RDATA_BREAKER_COOLDOWN_S` (60 s) before it is probed again.

## Proving you have migrated

```bash
AEOLUS_LEGACY_COLUMNS=0 pytest        # your suite, with the mirrors off
python -W error::DeprecationWarning -c "import aeolus; ..."   # or turn the one-time warning into an error
```

## Consumers

Hermes, RHEA, Clara and Argus: pin `aeolus_aq==0.5.0a1`, run with the mirrors off, and re-pull stored readings for the paths in the re-baseline table. Argus's write path (guarded upsert + `readings_history`) is designed for exactly this re-pull; see `argus/docs/2026-09-20-write-path-upsert-handoff.md`.
