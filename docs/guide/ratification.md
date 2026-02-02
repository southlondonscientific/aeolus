# Data Quality (Ratification)

All data returned by Aeolus includes a `ratification` column that indicates the quality or validation status of each measurement. This page explains what each value means and how different data sources handle quality assurance.

## Overview

The `ratification` column provides a consistent way to understand data quality across all sources, even though each source has different QA/QC processes:

| Value | Meaning | Sources |
|-------|---------|---------|
| `Ratified` | Officially validated by network operator | UK regulatory networks |
| `Provisional` | Awaiting official validation | UK regulatory networks, EPA AirNow |
| `Validated` | Passed automated QA/QC checks | PurpleAir |
| `Indicative` | Calibrated low-cost sensor data | AirQo |
| `Unvalidated` | No formal QA/QC applied | OpenAQ, Breathe London, Sensor.Community, PurpleAir (non-PM) |
| `Invalid` | Failed QA/QC checks | PurpleAir |

## Source-Specific Details

### UK Regulatory Networks (AURN, SAQN, WAQN, NI, AQE)

Reference-grade monitors with formal ratification by government bodies.

| Value | Meaning |
|-------|---------|
| `Ratified` | Data has been reviewed and officially approved |
| `Provisional` | Recent data awaiting formal review (typically ratified within weeks/months) |
| `None` | Status not available |

**Note:** Ratified data from UK networks is considered the gold standard for air quality measurements.

### OpenAQ

Global aggregator of data from many sources with varying quality.

| Value | Meaning |
|-------|---------|
| `Unvalidated` | All data (OpenAQ aggregates from multiple sources with different QA processes) |

**Note:** OpenAQ data quality depends on the original source. Reference-grade government monitors will be more reliable than low-cost sensors.

### Breathe London

London sensor network operated by Imperial College London.

| Value | Meaning |
|-------|---------|
| `Ratified` | Data validated by ERG |
| `Provisional` | Awaiting validation |
| `Unvalidated` | Status unknown or not provided |

**Note:** Breathe London uses a mix of reference-grade and indicative monitors.

### EPA AirNow

US EPA real-time air quality monitoring network.

| Value | Meaning |
|-------|---------|
| `Provisional` | All data (real-time, preliminary, subject to change) |

**Note:** AirNow data is preliminary and updated hourly. For verified historical US data, use the EPA AQS (Air Quality System) which contains ratified data after a 6+ month delay.

### AirQo

African air quality network using calibrated low-cost sensors.

| Value | Meaning |
|-------|---------|
| `Indicative` | All data (machine learning calibrated against reference monitors) |

**Note:** AirQo sensors are calibrated using machine learning models trained on co-located reference monitors. Data is suitable for understanding patterns and trends but may have higher uncertainty than reference-grade measurements.

### PurpleAir

Global network of dual-channel laser particle counters.

| Value | Meaning |
|-------|---------|
| `Validated` | Both channels agree within thresholds |
| `Channel Disagreement` | Both channels valid but disagree beyond thresholds |
| `Single Channel (A)` | Only channel A had valid data |
| `Single Channel (B)` | Only channel B had valid data |
| `Below Detection Limit` | Value below 0.3 µg/m³ (sensor noise floor) |
| `Sensor Saturation` | Value above 1000 µg/m³ (sensor range exceeded) |
| `Invalid` | Both channels invalid |
| `Unvalidated` | Non-PM measurements (temperature, humidity) |

**QA/QC Thresholds (PM measurements):**

| Concentration | Agreement Required |
|--------------|-------------------|
| < 0.3 µg/m³ | Flagged as below detection limit |
| 0.3–100 µg/m³ | Channels must agree within ±10 µg/m³ |
| 100–1000 µg/m³ | Channels must agree within ±10% |
| > 1000 µg/m³ | Flagged as sensor saturation |

**Note:** PurpleAir's dual-channel design allows automated QA/QC. The `include_flagged=False` parameter can be used to retrieve only validated data.

### Sensor.Community

Global citizen science network.

| Value | Meaning |
|-------|---------|
| `Unvalidated` | All data (citizen-installed sensors with no formal QA/QC) |

**Note:** Sensor.Community data is valuable for understanding spatial patterns but has no formal quality control. Sensor placement, maintenance, and calibration vary widely.

## Filtering by Quality

### Get only validated data

```python
# Filter to ratified/validated data only
clean_data = data[data['ratification'].isin(['Ratified', 'Validated'])]
```

### PurpleAir: exclude flagged data

```python
from aeolus.sources.purpleair import fetch_purpleair_data

# Only retrieve measurements that passed QA/QC
data = fetch_purpleair_data(
    sites=["131075"],
    start_date=start,
    end_date=end,
    include_flagged=False
)
```

### Check quality distribution

```python
# See breakdown of quality flags
print(data['ratification'].value_counts())
```

## Recommendations

| Use Case | Recommended Sources | Minimum Quality |
|----------|--------------------|-----------------| 
| Regulatory compliance | UK networks | `Ratified` |
| Health studies | UK networks, reference-grade OpenAQ | `Ratified` or `Provisional` |
| Spatial analysis | Any source | Any (understand limitations) |
| Trend analysis | Consistent source over time | `Provisional` or better |
| Real-time alerts | PurpleAir, Sensor.Community | `Validated` or `Unvalidated` with caution |

## Further Reading

- [REFERENCES.md](https://github.com/southlondonscientific/aeolus/blob/main/REFERENCES.md) - QA/QC methodology sources
- [PurpleAir QA/QC](../sources/purpleair.md#qaqc-methodology) - Detailed PurpleAir thresholds
