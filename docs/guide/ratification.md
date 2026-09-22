# Data Quality

Every row Aeolus returns carries three data-quality columns, derived from what the upstream network actually published:

| Column | What it holds |
|---|---|
| `qa_code` | The upstream's own quality token, **verbatim** — `verified`, `Ratified`, `"2"`, `Channel Disagreement`, `P`, … — or null where the upstream said nothing for that row. Aeolus never invents one. |
| `qa_tier` | A cross-network comparability tier derived from `qa_code` through the network's vocabulary: `reference_full_qc`, `reference_provisional`, `lcs_calibrated`, `lcs_factory_only`, `flagged` or `unknown`. |
| `ratification_stage` | Where the row is in a regulatory ratification cycle: `unratified`, `ratified`, `supplied`, `not_applicable`, or null where the network has a ratification concept but no per-row status is available. |

Two more columns say where the row came from: `network` (who produced it) and `backend` (which of Aeolus's fetchers served it — `RDATA`, `SOS`, `ERG_REST`, …).

The pre-0.5.0 `ratification` column is still present as a **deprecated mirror** derived from the three columns above (`Ratified`, `Provisional`, `Indicative`, `Validated`, `Invalid`, `Unvalidated`, `None`). It is removed in 1.0; set `AEOLUS_LEGACY_COLUMNS=0` to drop it now and check your code no longer reads it. Filter on `qa_code` or `qa_tier` instead.

## What each network publishes

| Network | `qa_code` | `qa_tier` |
|---|---|---|
| AURN | `verified` / `unverified` — from the site's per-pollutant `ratified_to` date in the openair metadata | `reference_full_qc` / `reference_provisional` |
| SAQN, WAQN, NI, AQE | `Ratified` / `Provisional`, the same way | `reference_full_qc` / `reference_provisional` |
| AURN-SOS and the other near-real-time sources | always the network's unratified token | `reference_provisional` |
| EEA | the EIONET `Verification` code: `"1"` verified, `"2"` preliminary verified, `"3"` not verified | `reference_full_qc` for `"1"`, else `reference_provisional` |
| PurpleAir | the channel-agreement label: `Validated`, `Single Channel (A)`/`(B)`, `Channel Disagreement`, `Sensor Saturation`, `Invalid`, `Unvalidated` | `lcs_factory_only` (validated, single channel), `flagged` (disagreement, saturation, invalid), `unknown` |
| Breathe London | `RatificationStatus` (`P`), null where absent | `lcs_calibrated`, else `unknown` |
| AirNow | `Provisional` — the AirNow feed is never ratified; certified data is in EPA's AQS | `reference_provisional` |
| LAQN, LMAM, Sensor.Community, Sonitus, OpenAQ, AirQo | null — these feeds publish no per-row flag | `unknown` |

The vocabularies live in `src/aeolus/data/qa_vocabularies/<NETWORK>.yaml` and are shared with Argus.

## Filtering by quality

```python
import aeolus
from datetime import datetime

data = aeolus.download("AURN", ["MY1"], datetime(2023, 1, 1), datetime(2023, 12, 31))

# Only ratified rows
ratified = data[data["ratification_stage"] == "ratified"]

# Anything that has passed full QA/QC, whatever the network
reference = data[data["qa_tier"] == "reference_full_qc"]

# Drop rows the upstream flagged (PurpleAir channel disagreement etc.)
clean = data[data["qa_tier"] != "flagged"]

# How much of a download is ratified?
print(data.groupby(["network", "ratification_stage"], dropna=False).size())
```

For PurpleAir, `aeolus.download("PURPLEAIR", ..., include_flagged=False)` keeps only rows whose `qa_code` is `Validated`.

## Recommendations

- For regulatory reporting, use `ratification_stage == "ratified"`; provisional data can change on ratification.
- Compare networks on `qa_tier`, not on the raw `qa_code` — the codes are each network's own words.
- A null `qa_code` means the upstream said nothing; it is not a bad reading. Check the network's documentation page for what that implies.
- Recent AURN-family data is provisional for roughly three to six months; the metadata's `ratified_to` date is what Aeolus uses to tell.
