# EEA (European Environment Agency)

The [European Environment Agency](https://www.eea.europa.eu/) aggregates regulatory air quality data reported by EU member states and cooperating countries under the Air Quality Directive. Hourly data is available from 2013 onwards across 40+ countries and 7,000+ stations.

!!! warning "Experimental"
    EEA support is **experimental** (`aeolus.get_source_info("EEA")["status"]`), and Aeolus warns once per session when you use it. Known gaps:

    - **Clocks are verified for a few countries only.** The EEA says its hourly timestamps are in fixed UTC+1, and Aeolus converts from that. Measured true for the up-to-date feed in DE, NL, IE, ES and PL and for the verified archive in DE, NL, PL and IT. Two measured exceptions are handled: Italy's up-to-date feed is on local clock time (treated as Europe/Rome; the hour that does not exist each spring and the ambiguous one each autumn are dropped), and Ireland's verified archive is on plain UTC. Every other country, and the Airbase archive, is *assumed* to follow the EEA's statement.
    - **Overlapping datasets differ.** Where the archive and the feed both hold a day, Aeolus serves the archive; the feed's values for the same hours can differ by rounding or later corrections.

## Overview

- **Coverage**: 40+ European countries, 7,000+ stations
- **Data quality**: Reference (national regulatory networks, pooled by EEA)
- **Ratification**: `Verified` (full QA/QC by the data provider) or `Provisional` (preliminary or not verified)
- **API key**: Not required
- **History**: hourly data from 2013 (verified archive), recent months (up-to-date feed) and 2002–2012 (Airbase)
- **Operator**: European Environment Agency

## No API Key Required

The EEA Air Quality Download Service is fully open. No registration or API key is needed.

## Quick Start

```python
import aeolus
from datetime import datetime

# Find EEA stations within 20 km of Paris
sites = aeolus.find_sites(
    "EEA",
    near=(48.8566, 2.3522),
    radius_km=20,
)

# Download NO2 and PM2.5 for January 2024
data = aeolus.download(
    "EEA",
    sites=sites["site_code"].head(5).tolist(),
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31),
)
```

## Finding Stations

```python
# By bounding box
sites = aeolus.find_sites(
    "EEA",
    bbox=(-10, 35, 30, 60),  # (min_lon, min_lat, max_lon, max_lat) - Europe
)

# By country (via metadata filter)
sites = aeolus.networks.get_metadata("EEA")
germany = sites[sites["country"] == "DE"]
```

## Data Quality

Each row is labelled with a `ratification` value derived from the EEA `Verification` field:

| EEA field value | `ratification` |
|-----------------|----------------|
| 1 (Verified) | `Verified` |
| 2 (Preliminary verified) | `Provisional` |
| 3 (Not verified) | `Provisional` |

Codes follow the [EIONET observation-verification vocabulary](https://dd.eionet.europa.eu/vocabulary/aq/observationverification). Versions before 0.5.0 had this mapping inverted.

!!! warning "Historical coverage"
    Aeolus currently queries only the EEA *up-to-date* feed, which holds recent data (all `Provisional`). Requests for earlier years return an empty frame; the verified archive is not yet wired in.

## Notes

- **No real-time**: `get_current()` is not supported for EEA — the download API is not near-real-time. Use national sources (AURN, etc.) for live readings.
- **Dataset variant**: Aeolus uses the E1a ("Verified") dataset for the broadest coverage of recent data.
- **Samplingpoint mapping**: EEA `Samplingpoint` identifiers follow different conventions per country. Aeolus uses the EEA's own metadata CSV to map these to EoI station codes authoritatively.

## Resources

- [EEA Air Quality Download Service](https://eeadmz1-downloads-webapp.azurewebsites.net/)
- [EEA Air Quality Statistics Viewer](https://discomap.eea.europa.eu/App/AQViewer/)
- [Air Quality Directive](https://environment.ec.europa.eu/topics/air/air-quality/eu-air-quality-standards_en)

## Data quality

`qa_code` is the EIONET `Verification` code, verbatim: `"1"` verified → `qa_tier = reference_full_qc`, `ratification_stage = ratified`; `"2"` preliminary verified and `"3"` not verified → `reference_provisional`, `unratified`; `"0"` (Airbase, 2002–2012, status not recorded) → `unknown`. The legacy `ratification` mirror shows `Ratified` or `Provisional`. Rows with `Validity < 1` (invalid, or under maintenance) are dropped rather than flagged.

`backend` says which EEA dataset served each row: `EEA_E1A` (verified archive, reported annually after national QA/QC), `EEA_E2A` (up-to-date feed) or `EEA_AIRBASE`. Aeolus asks for the archive and the feed on every download that reaches past 2012 (and Airbase only for the years up to 2012, which is all it holds) and serves each site-pollutant-day, on the archive's own clock, from the highest-priority dataset that holds it. A dataset whose request fails is reported as a warning and the others still serve.
