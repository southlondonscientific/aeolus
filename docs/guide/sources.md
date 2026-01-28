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

## Global Platforms

### OpenAQ

A global open data platform aggregating air quality data from government agencies, research institutions, and other sources worldwide.

- **Coverage**: 100+ countries
- **Data quality**: Varies by source
- **API key**: Required
- **Documentation**: [OpenAQ](../sources/openaq.md)

## Low-Cost Sensor Networks

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

## Comparing Sources

| Source | Coverage | Quality | Real-time | Historical |
|--------|----------|---------|-----------|------------|
| AURN | UK | Reference | Yes | 1973+ |
| SAQN | Scotland | Reference | Yes | 2000s+ |
| OpenAQ | Global | Mixed | Yes | 2015+ |
| Breathe London | London | Indicative | Yes | 2019+ |
| AirQo | Africa | Indicative | Yes | 2020+ |
