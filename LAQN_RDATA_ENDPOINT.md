# LAQN: add RData endpoint as a faster alternative to the ERG REST API

**Status:** proposed enhancement to `aeolus/sources/laqn.py`
**Discovered:** 2026-05-07 during Pan v0.4.x grid-resolution validation work

## Problem

The current LAQN fetcher (`aeolus/src/aeolus/sources/laqn.py`) hits the
ERG REST API at `https://api.erg.ic.ac.uk/AirQuality/`. Per-site
download for a full year of hourly data takes **60–160 seconds per
site**. Fetching all 256 LAQN sites for a single year is ~4–5 hours
sequential.

For comparison, the parallel networks (AURN/SAQN/WAQN/AQE) use the
**openair RData feed** convention and fetch in well under 1 second per
site. Pan's v0.4.x validation work needed all-LAQN annual means; the
current API path made that infeasible without subsampling.

## The fix

LAQN publishes the same per-site annual RData files that the
defra/SEPA/NRW openair feeds do, at:

```
https://www.londonair.org.uk/r_data/<SITECODE>_<YEAR>.RData
```

Verified live (2026-05-07): HTTP/2 200, `application/R`,
~200–400 KB/site. Examples:

- `https://www.londonair.org.uk/r_data/MY1_2024.RData` → 379 443 bytes
- `https://www.londonair.org.uk/r_data/BG1_2024.RData` → 186 717 bytes
- `https://www.londonair.org.uk/r_data/CT3_2024.RData` → exists

The format is identical to the AURN feed — same RData column schema
(`date`, `no2`, `pm10`, etc.), same encoding. The existing
`aeolus.sources.regulatory.fetch_rdata()` helper parses it cleanly with
no modifications.

## Suggested implementation

Add LAQN to the `regulatory.py` source family rather than keeping it
isolated in `laqn.py`. Concretely:

1. Add to the `_NETWORK_METADATA_URLS` dict in `regulatory.py` — though
   note LAQN's site metadata is currently fetched via the ERG API
   (richer site-type info than the openair metadata RData provides);
   the metadata path can stay on the ERG API while the data path moves
   to RData.
2. Add a `_NETWORK_DATA_URL_BASES` entry mapping `"laqn"` to
   `https://www.londonair.org.uk/r_data` (matching the per-site URL
   pattern used by AURN/SAQN/WAQN/AQE).
3. Update `aeolus.networks.download("LAQN", sites=..., start_date=..., end_date=...)`
   to use the RData feed by default, with the ERG REST API kept as a
   fallback for any site not present in the RData feed (some recent
   LAQN sites take a few weeks to appear in openair archives).
4. Preserve the current ERG-based metadata path (returns `location_type`
   = "Kerbside" / "Roadside" / "Urban Background" / "Suburban" /
   "Industrial" / etc.) — this is richer than the openair metadata.

## Performance expectations

After the swap:
- 256 LAQN sites for a single year: ~1–5 minutes total (vs ~4–5 hours).
- Parallelisable with `ThreadPoolExecutor(max_workers=4)` like the
  other regulatory feeds.

## Notes

- **Year coverage:** LAQN openair archives go back to ~2010 with full
  hourly coverage from ~2008 for some sites. Verify URL availability
  for older years; some early-2000s sites may only exist in the ERG
  API.
- **Hourly-vs-daily granularity:** the openair RData feed is hourly,
  matching the ERG API's hourly default — no granularity downgrade.
- **Measurand coverage:** RData feed includes NO2, PM10, PM2.5, NOX,
  O3, SO2, CO where the site measures them. Same as ERG API.
- **CRITICAL — units differ from AURN:** the LAQN openair RData reports
  **gases in ppb** (parts per billion by volume), unlike AURN's openair
  RData which reports **gases in µg/m³**. This was empirically verified
  2026-05-07 against MY1 Marylebone Road 2024 data: the RData shows NO2
  annual mean ~17 (only sensible as ppb; ×1.913 = 32.5 µg/m³, which
  matches reality). PM is in µg/m³ in both feeds. The aeolus
  integration MUST apply the ppb → µg/m³ conversion at parse time so
  downstream consumers see the same units across networks. Standard
  conversion factors at 20°C / 101.3 kPa:
  - NO2: ppb × 1.913 = µg/m³
  - NO:  ppb × 1.247 = µg/m³ (NOX is conventionally reported as
    NO2-equivalent µg/m³, so ppb × 1.913 there too)
  - O3:  ppb × 2.000 = µg/m³
  - SO2: ppb × 2.661 = µg/m³
  - CO:  ppb × 1.165 = µg/m³ (or × 0.001165 if RData stores ppm)
  Without the conversion, a downstream LUR (Pan v0.4.x) sees obs values
  ~half of true µg/m³ and reports MAE 16+ at LAQN sites that should be
  3–5; this is the single highest-impact item in the integration.
- **Licence:** LAQN data is published by the Environmental Research
  Group at Imperial College London under the standard openair / KCL
  attribution requirements — same redistribution terms as AURN
  (acknowledge ERG/Imperial as the data provider in any published
  output).

## Where this came up

Pan validation script `scripts/validate_at_laqn.py` (in the pan repo)
currently bypasses aeolus and hits the LAQN RData feed directly via
`aeolus.sources.regulatory.fetch_rdata`. Once aeolus has native LAQN
RData support, that script should switch to
`aeolus.networks.download("LAQN", ...)` and drop the inline RData
fetcher.

The Pan grid-resolution validation work (FINDINGS §11+) and any
subsequent Pan retrains using LAQN as a holdout are direct beneficiaries.

## References

- openair R package's `importKCL()` — uses the same URL pattern.
- `aeolus/src/aeolus/sources/regulatory.py` — existing AURN/SAQN/WAQN
  RData implementation to mirror.
- LAQN data portal: https://www.londonair.org.uk/
- ERG REST API (kept as metadata path): https://api.erg.ic.ac.uk/AirQuality/
