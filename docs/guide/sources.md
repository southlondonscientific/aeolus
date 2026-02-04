# Data Sources

Aeolus supports multiple air quality data sources. This page provides an overview of each.

## UK Regulatory Networks

These networks are operated by UK government agencies and provide high-quality, ratified data.

### AURN (Automatic Urban and Rural Network)

The UK's main regulatory monitoring network with ~150 sites across England, Wales, Scotland, and Northern Ireland.

- **Coverage**: UK-wide
- **Data quality**: Ratified (high quality)
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
- **Data quality**: Ratified
- **API key**: Not required

### WAQN (Welsh Air Quality Network)

Welsh monitoring network.

- **Coverage**: Wales
- **Data quality**: Ratified
- **API key**: Not required

### NI (Northern Ireland Network)

Northern Ireland monitoring network.

- **Coverage**: Northern Ireland
- **Data quality**: Ratified
- **API key**: Not required

### AQE (Air Quality England)

Local authority monitoring sites across England.

- **Coverage**: England (local authorities)
- **Data quality**: Ratified
- **API key**: Not required

### LOCAL (Local Authority Networks)

Additional local authority monitoring networks.

- **Coverage**: England
- **Data quality**: Ratified
- **API key**: Not required

### LMAM (London Air Quality Mesh)

Greater London monitoring network.

- **Coverage**: Greater London
- **Data quality**: Ratified
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
- **Data quality**: Indicative (dual laser counters with QA/QC)
- **API key**: Required
- **Documentation**: [PurpleAir](../sources/purpleair.md)

## Networks

Networks are discrete monitoring systems with a known, manageable set of sites.

### Breathe London

A dense network of low-cost sensors across London, providing high spatial resolution data.

- **Coverage**: Greater London
- **Data quality**: Indicative (lower than reference-grade)
- **API key**: Required
- **Documentation**: [Breathe London](../sources/breathe-london.md)

### AirQo

Low-cost sensor network monitoring air quality in African cities.

- **Coverage**: Uganda, Kenya, and expanding
- **Data quality**: Indicative
- **API key**: Required
- **Documentation**: [AirQo](../sources/airqo.md)

### EPA AirNow

Real-time air quality data from the US EPA's AirNow system.

- **Coverage**: USA, Canada, Mexico
- **Data quality**: Provisional (real-time, not yet verified)
- **API key**: Required
- **History**: ~45 days (for long-term data, use EPA AQS via OpenAQ)
- **Documentation**: [EPA AirNow](../sources/airnow.md)

### Sensor.Community

Global citizen science network (formerly luftdaten.info) with 35,000+ low-cost sensors.

- **Coverage**: Global (primarily Europe)
- **Data quality**: Unvalidated (citizen science)
- **API key**: Not required
- **Documentation**: [Sensor.Community](../sources/sensor-community.md)

## Comparing Sources

| Source | Type | Coverage | Quality | Real-time | Historical |
|--------|------|----------|---------|-----------|------------|
| AURN | Network | UK | Reference | Yes | 1973+ |
| SAQN | Network | Scotland | Reference | Yes | 2000s+ |
| WAQN | Network | Wales | Reference | Yes | 2000s+ |
| NI | Network | N. Ireland | Reference | Yes | 2000s+ |
| AQE | Network | England | Reference | Yes | 2000s+ |
| LOCAL | Network | England | Reference | Yes | 2000s+ |
| LMAM | Network | London | Reference | Yes | 2000s+ |
| OpenAQ | Portal | Global | Mixed | Yes | 2015+ |
| PurpleAir | Portal | Global | Indicative | Yes | 2017+ |
| Breathe London | Network | London | Indicative | Yes | 2019+ |
| AirQo | Network | Africa | Indicative | Yes | 2020+ |
| EPA AirNow | Network | N. America | Provisional | Yes | ~45 days |
| Sensor.Community | Network | Global | Unvalidated | Yes | 2015+ |
