# LMAM (Locally-Managed Automatic Monitoring)

[LMAM](https://uk-air.defra.gov.uk/networks/network-info?view=nondefraaqmon) is DEFRA's umbrella feed for automatic air quality stations operated by UK local authorities and regional networks outside the national strategy (AURN, SAQN, WAQN, NI, AQE). It provides regulatory-grade hourly data from 196 active sites across six provider networks.

## Overview

- **Coverage**: UK (council and regional networks outside AURN/AQE)
- **Sensor type**: Reference and reference-equivalent instruments
- **Data quality**: Ratified (where provider supplies it; otherwise indicative)
- **API key**: Not required
- **Operator**: Various local authorities (DEFRA aggregates)

## Provider Networks

| Provider code | Network | Approx. sites |
|---------------|---------|---------------|
| `sussex` | Sussex Air Quality Network | 53 |
| `kent` | Kent and Medway Air Quality | 44 |
| `aqdm` | UK Air Quality (Defra-managed) | 59 |
| `nlincs` | Air Quality in North Lincolnshire | 28 |
| `leicester` | Leicester Council AQ Network | 7 |
| `hants` | Hampshire Air Quality Network | 6 |

The DEFRA metadata feed also lists `london`, `aqengland`, and `essex` provider codes, but their per-site data files don't currently exist on the server. Aeolus filters them out at metadata time so `find_sites("LMAM")` only returns sites whose data endpoints are reachable. For London coverage use the dedicated [LAQN](uk-networks.md#laqn-london-air-quality-network) source instead.

## Available Pollutants

NO, NO2, NOXasNO2, O3, SO2, CO, PM10, PM2.5 — the subset varies by site. The `measurands` column in the metadata frame lists each site's reported parameters.

## Finding Sites

```python
import aeolus

# All active LMAM sites
sites = aeolus.find_sites("LMAM")

# Restrict to one provider (use the `pcode` column from metadata)
kent_sites = sites[sites["pcode"] == "kent"]

# Or use spatial filters as usual
sx = aeolus.find_sites("LMAM", bbox=(-0.5, 50.5, 1.0, 51.2))
```

## Downloading Data

```python
import aeolus
from datetime import datetime

data = aeolus.download(
    "LMAM",
    sites=["BN1", "CR9"],   # use the site_code column from find_sites
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31),
)
```

## API Details

- **Metadata**: `https://uk-air.defra.gov.uk/openair/LMAM/R_data/LMAM_metadata.RData` (single RData file)
- **Per-site data**: `https://uk-air.defra.gov.uk/openair/LMAM/R_data/{pcode}/{SITE}_{YEAR}.RData`

The `{pcode}/` subfolder is the discriminator between provider networks — `find_sites("LMAM")` populates a `site_code → pcode` mapping from the metadata feed and the data fetcher uses it transparently. You don't normally need to deal with `pcode` yourself unless filtering by provider.

## Notes

- The R `openair` package's `source="local"` and `source="lmam"` are aliases for the same DEFRA feed.
- Sites overlap with other UK sources at certain locations (e.g. a few AURN-affiliated sites also appear in LMAM via the `aqdm` provider). When a site is available in both, prefer the source with the ratification status you need.
