# Aeolus Data Volume Estimate

*Estimated 2026-04-09. Methodology and caveats below.*

## Headline

Aeolus provides access to approximately **28 billion station-hours** of air quality monitoring data from **~145,000 monitoring locations** across **100+ countries**.

Excluding global portal overlap: **~6.4 billion station-hours** from dedicated networks with no double-counting.

## Methodology

**Station-hours** is defined as: `sites × measurands_per_site × years_of_history × 8766 hours/year`. This metric normalises across reporting frequencies — one station-hour represents one hour of monitoring at one site for one measurand, whether the source reports every minute or every hour.

Site counts were obtained from live metadata queries via `aeolus.find_sites()` on 2026-04-09. Average measurands per site were estimated from the `measurands` column where available, or from known network characteristics. Historical depth is based on the earliest available data year per network, as documented by the network operators.

## Source-by-source breakdown

| Source | Sites | Avg measurands | History (years) | Station-hours (M) | Type |
|--------|------:|---------------:|----------------:|-------------------:|------|
| AURN | 321 | 5.2 | 25 | 366 | UK reference |
| SAQN | 152 | 4.0 | 20 | 107 | UK reference |
| WAQN | 70 | 4.0 | 15 | 37 | UK reference |
| NI | 30 | 4.0 | 15 | 16 | UK reference |
| AQE | 454 | 3.0 | 15 | 179 | UK reference |
| LAQN | 250 | 4.0 | 10 | 87 | London (ERG/Imperial) |
| EEA | 7,020 | 3.0 | 10 | 1,846 | European reference |
| Sonitus | 40 | 5.0 | 5 | 9 | Irish municipal |
| Sensor.Community | ~35,000 | 2.0 | 5 | 3,068 | Global citizen science |
| Breathe London | 294 | 3.0 | 5 | 39 | London low-cost |
| AirQo | 510 | 3.0 | 4 | 54 | African cities |
| AirNow | 2,400 | 3.0 | 10 | 631 | US/Canada/Mexico |
| OpenAQ | ~70,000 | 3.0 | 10 | 18,409 | Global portal |
| PurpleAir | ~30,000 | 2.0 | 6 | 3,156 | Global low-cost |
| **Total** | **~145,000** | | | **~28,000** | |

## Caveats

1. **Portal overlap.** OpenAQ aggregates data from many sub-networks, including AURN, EEA, AirNow, and others. PurpleAir sensors may also appear in OpenAQ. The ~28 billion figure includes this overlap. The non-portal total (~6.4 billion station-hours) avoids double-counting but excludes portal-only sources.

2. **Historical sites.** Site counts include historical/closed sites (e.g. AURN's 321 includes sites operating since 1998, many now closed). This is correct for estimating total accessible data volume but overstates the *current* network size.

3. **Data availability vs. data capture.** Not all station-hours have valid readings. Instrument downtime, calibration periods, and data quality flags reduce actual data capture to typically 85-95% for reference networks and 60-80% for low-cost sensors.

4. **Measurand estimates.** Average measurands per site are approximate. Reference stations may measure 6-8 pollutants; low-cost sensors typically measure 2-3 (PM2.5, PM10, sometimes temperature/humidity).

5. **History depth varies.** The "years" column represents the maximum history available from the earliest sites. Many sites have shorter records. The estimate assumes all sites have the full history, which overstates volume by perhaps 30-50% for networks with significant site turnover.

6. **Portal site counts are approximate.** OpenAQ and PurpleAir site counts are based on published statistics and may fluctuate. Sensor.Community's count is based on their published figure of 35,000+ active sensors.

## Recommended citation figures

- **Conservative (non-overlapping, dedicated networks only):** ~6 billion station-hours from ~45,000 locations
- **Inclusive (all sources, acknowledging overlap):** ~28 billion station-hours from ~145,000 locations across 100+ countries
- **UK-specific:** ~760 million station-hours from ~1,200 UK monitoring sites spanning up to 25 years
