# Data Sources

Aeolus supports multiple air quality data sources. This page provides an overview of each.

## UK Regulatory Networks

These networks are operated by UK government agencies and provide high-quality, ratified data.

### AURN (Automatic Urban and Rural Network)

The UK's main regulatory monitoring network with ~150 sites across England, Wales, Scotland, and Northern Ireland.

- **Coverage**: UK-wide
- **Data quality**: `qa_tier = reference_full_qc` once ratified, `reference_provisional` before (per site, pollutant and date)
- **API key**: Not required
- **Pollutants**: NO2, O3, PM2.5, PM10, SO2, CO

```python
import aeolus
from datetime import datetime

data = aeolus.download(
    sources="AURN",
    sites=["MY1", "KC1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

### SAQN (Scottish Air Quality Network)

Additional monitoring sites in Scotland, complementing AURN coverage.

- **Coverage**: Scotland
- **Data quality**: `qa_tier = reference_full_qc` once ratified, `reference_provisional` before (`qa_code` = `Ratified`/`Provisional`)
- **API key**: Not required

### WAQN (Welsh Air Quality Network)

Welsh monitoring network.

- **Coverage**: Wales
- **Data quality**: `qa_tier = reference_full_qc` once ratified, `reference_provisional` before (`qa_code` = `Ratified`/`Provisional`)
- **API key**: Not required

### NI (Northern Ireland Network)

Northern Ireland monitoring network.

- **Coverage**: Northern Ireland
- **Data quality**: `qa_tier = reference_full_qc` once ratified, `reference_provisional` before (`qa_code` = `Ratified`/`Provisional`)
- **API key**: Not required

### AQE (Air Quality England)

Local authority monitoring sites across England.

- **Coverage**: England (local authorities)
- **Data quality**: `qa_tier = reference_full_qc` once ratified, `reference_provisional` before (`qa_code` = `Ratified`/`Provisional`)
- **API key**: Not required

### LAQN (London Air Quality Network)

London's main regulatory monitoring network, managed by ERG at Imperial College London. ~250 sites across all London boroughs.

- **Coverage**: Greater London
- **Data quality**: no per-row flag in the londonair files — `qa_code` null, `qa_tier = unknown`
- **API key**: Not required

### LMAM (Locally-Managed Automatic Monitoring)

DEFRA's umbrella feed for automatic stations operated by local authorities and regional networks outside the national strategy (AURN, SAQN, WAQN, NI, AQE). 196 active sites across six provider networks: Sussex, Kent, AQ Data Manager, North Lincolnshire, Leicester, Hampshire.

- **Coverage**: UK (non-AURN/AQE local authority networks)
- **Data quality**: no per-row flag in the DEFRA feed — `qa_code` null, `qa_tier = unknown`, `ratification_stage = supplied`
- **API key**: Not required

## Global Portals

Portals aggregate data from multiple sources worldwide. Due to their scale (hundreds of thousands of sites), you search for sites first, then download.

### OpenAQ

A global open data platform aggregating air quality data from government agencies, research institutions, and other sources worldwide.

- **Coverage**: 100+ countries
- **Data quality**: Varies by source
- **API key**: Required
- **Documentation**: [OpenAQ](../sources/openaq.md)

### PurpleAir

Global network of 30,000+ low-cost air quality sensors, popular with researchers and citizen scientists.

- **Coverage**: Global (primarily USA, Europe, Australia)
- **Data quality**: `qa_tier = lcs_factory_only` (channel-agreement label in `qa_code`; disagreeing or saturated channels are `flagged`)
- **API key**: Required
- **Documentation**: [PurpleAir](../sources/purpleair.md)

## Networks

Networks are discrete monitoring systems with a known, manageable set of sites.

### Breathe London

A dense network of low-cost sensors across London, providing high spatial resolution data.

- **Coverage**: Greater London
- **Data quality**: `qa_tier = lcs_calibrated` where the API reports status `P`, else `unknown`
- **API key**: Required
- **Documentation**: [Breathe London](../sources/breathe-london.md)

### AirQo

Low-cost sensor network monitoring air quality in African cities.

- **Coverage**: Uganda, Kenya, and expanding
- **Data quality**: calibrated low-cost sensors; `qa_tier = unknown` until AirQo's calibrated/raw flag is wired
- **API key**: Required
- **Documentation**: [AirQo](../sources/airqo.md)

### EPA AirNow

Real-time air quality data from the US EPA's AirNow system.

- **Coverage**: USA, Canada, Mexico
- **Data quality**: `qa_code = Provisional`, `qa_tier = reference_provisional` (real-time, never ratified in AirNow)
- **API key**: Required
- **History**: ~45 days (for long-term data, use EPA AQS via OpenAQ)
- **Documentation**: [EPA AirNow](../sources/airnow.md)

### Sensor.Community

Global citizen science network (formerly luftdaten.info) with 35,000+ low-cost sensors.

- **Coverage**: Global (primarily Europe)
- **Data quality**: no per-row flag — `qa_code` null, `qa_tier = unknown` (citizen science)
- **API key**: Not required
- **Documentation**: [Sensor.Community](../sources/sensor-community.md)

### EEA (European Environment Agency)

Pan-European monitoring data from national reference networks, aggregated by the European Environment Agency. 7,000+ stations across 40+ countries.

- **Coverage**: Europe (EU/EEA member states)
- **Data quality**: `qa_tier = reference_full_qc` (verified archive) or `reference_provisional` (up-to-date feed); Airbase rows (2002–2012) are `unknown`
- **API key**: Not required

### Sonitus (Smart Dublin)

Air quality and noise monitoring network in Dublin, Ireland. Measures NO2, SO2, CO, NO, O3, PM1, PM2.5, PM10, and TSP at 15-minute resolution.

- **Coverage**: Dublin, Ireland
- **Data quality**: no per-row flag — `qa_code` null, `qa_tier = unknown` (low-cost multi-parameter, plus a few EPA reference monitors)
- **API key**: Not required

## Comparing Sources

| Source | Type | Coverage | `qa_tier` | Real-time | Historical |
|--------|------|----------|-----------|-----------|------------|
| AURN | Network | UK | reference_full_qc / reference_provisional | Yes | 1973+ |
| SAQN | Network | Scotland | reference_full_qc / reference_provisional | Yes | 2000s+ |
| WAQN | Network | Wales | reference_full_qc / reference_provisional | Yes | 2000s+ |
| NI | Network | N. Ireland | reference_full_qc / reference_provisional | Yes | 2000s+ |
| AQE | Network | England | reference_full_qc / reference_provisional | Yes | 2000s+ |
| LAQN | Network | London | unknown (no flag published) | Yes | 1990s+ |
| LMAM | Network | UK (council/regional) | unknown (no flag published) | Yes | 2000s+ |
| EEA | Network | Europe | reference_full_qc / reference_provisional (Airbase unknown) | No | 2002+ (Airbase to 2012, verified archive from 2013) |
| OpenAQ | Portal | Global | unknown (provider mix) | Yes | 2015+ |
| PurpleAir | Portal | Global | lcs_factory_only / flagged (met rows unknown) | Yes | 2017+ |
| Breathe London | Network | London | lcs_calibrated | Yes | 2019+ |
| AirQo | Network | Africa | unknown (until wired) | Yes | 2020+ |
| EPA AirNow | Network | N. America | reference_provisional | Yes | ~45 days |
| Sensor.Community | Network | Global | unknown (no flag published) | Yes | 2015+ |
| Sonitus | Network | Dublin, Ireland | unknown (no flag published) | Yes | 2020+ |
