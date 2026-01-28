# Potential Air Quality Data Sources for Aeolus

*Research conducted: January 2025*

This document evaluates potential air quality data networks and portals for integration into the aeolus library. All sources listed offer free API access (with varying limits).

## Currently Implemented

| Source | Coverage | Status |
|--------|----------|--------|
| UK Regulatory (DEFRA/AURN) | UK | ✅ Implemented |
| OpenAQ | Global (~160 countries) | ✅ Implemented |
| Breathe London | London | ✅ Implemented |

---

## Recommended Additions

### Tier 1: High Priority (Global/Regional Coverage, Excellent Free Tiers)

#### 1. Open-Meteo Air Quality API
**Recommendation: STRONGLY RECOMMENDED**

- **Coverage**: Global (based on CAMS European 11km and CAMS global 40km forecasts)
- **Pollutants**: PM10, PM2.5, CO, NO2, SO2, O3, Aerosol Optical Depth, Dust, UV Index, Pollen
- **Free Tier**: 10,000 calls/day for non-commercial use
- **Auth**: No API key required for free tier
- **Unique Value**: Forecast data (not just real-time), pollen data, model-based coverage everywhere
- **Documentation**: https://open-meteo.com/en/docs/air-quality-api

**Why include**: Provides forecast data (unique among free APIs), no auth needed, excellent for filling gaps where no monitors exist. Model-based data complements station-based sources like OpenAQ.

```
Pros:
+ No API key required
+ Forecast data available
+ Global coverage via models
+ Includes pollen data
+ Very generous free tier

Cons:
- Model data, not ground-truth measurements
- Resolution limited (11-40km)
- Non-commercial only for free tier
```

---

#### 2. EPA AirNow API (US)
**Recommendation: STRONGLY RECOMMENDED**

- **Coverage**: United States (nationwide)
- **Pollutants**: PM2.5, PM10, O3, NO2, SO2, CO
- **Free Tier**: 500 requests/hour per endpoint type (free government service)
- **Auth**: Free API key required
- **Data Types**: Real-time, forecasts, historical
- **Documentation**: https://docs.airnowapi.org/

**Why include**: Official EPA data, high quality regulatory measurements, excellent for US-based users and research.

```
Pros:
+ Official government data (high quality)
+ Free and reliable
+ Includes forecasts
+ Good documentation

Cons:
- US only
- Rate limits per endpoint type
```

---

#### 3. World Air Quality Index (AQICN/WAQI)
**Recommendation: STRONGLY RECOMMENDED**

- **Coverage**: Global (100+ countries, 11,000+ stations)
- **Pollutants**: PM2.5, PM10, NO2, CO, SO2, O3
- **Free Tier**: 1,000 requests/second (very generous)
- **Auth**: Free API key required
- **Restrictions**: Non-commercial, attribution required, no redistribution
- **Documentation**: https://aqicn.org/api/

**Why include**: Massive global coverage aggregating many networks, provides standardised AQI alongside raw data.

```
Pros:
+ Massive global coverage
+ Aggregates many networks
+ Very high rate limits
+ Real-time data

Cons:
- Non-commercial restriction
- Must attribute
- Cannot cache/redistribute data
- Some data quality variation
```

---

#### 4. European Environment Agency (EEA)
**Recommendation: STRONGLY RECOMMENDED**

- **Coverage**: EU + EEA member states (40+ countries)
- **Pollutants**: All major pollutants + heavy metals
- **Free Tier**: Free and open (public data)
- **Auth**: None required
- **Data Format**: Parquet files, SQL API
- **Documentation**: https://www.eea.europa.eu/en/datahub/datahubitem-view/778ef9f5-6293-4846-badd-56a29c70880d

**Why include**: Official European regulatory data, excellent for research and compliance work, historical data back to 1970s.

```
Pros:
+ Official regulatory data
+ Completely free and open
+ Excellent historical archive
+ Well-documented

Cons:
- Complex data model
- Download-focused (not real-time API)
- Parquet format requires processing
```

---

### Tier 2: Good Options (Regional Focus or Limited Free Tiers)

#### 5. AirQo (Africa)
**Recommendation: RECOMMENDED**

- **Coverage**: 16+ African cities (200+ monitors)
- **Pollutants**: PM2.5, PM10, O3, NO2, SO2, CO
- **Free Tier**: Unrestricted access for public use
- **Auth**: API key required
- **Documentation**: https://docs.airqo.net/airqo-rest-api-documentation

**Why include**: Fills a major gap - Africa is underserved by other APIs. Important for global environmental justice research.

```
Pros:
+ Fills major coverage gap
+ Free tier unrestricted
+ Growing network
+ Open source platform

Cons:
- Limited to African cities
- Younger network (less historical data)
```

---

#### 6. IQAir AirVisual API
**Recommendation: RECOMMENDED (with caveats)**

- **Coverage**: Global (based on monitors + forecasts)
- **Pollutants**: PM2.5, PM10, O3, NO2, CO, SO2
- **Free Tier**: Community tier (limited calls)
- **Auth**: Free API key required
- **Extras**: Weather data included
- **Documentation**: https://api-docs.iqair.com/

**Why include**: Good global coverage, includes weather data, widely used consumer API.

```
Pros:
+ Global coverage
+ Includes weather data
+ Well-documented

Cons:
- Limited free tier
- Rate limits not clearly documented
- Some data from models
```

---

#### 7. OpenWeatherMap Air Pollution API
**Recommendation: RECOMMENDED**

- **Coverage**: Global (coordinate-based)
- **Pollutants**: CO, NO, NO2, O3, SO2, NH3, PM2.5, PM10
- **Free Tier**: Up to 1,000,000 calls/month
- **Auth**: Free API key required
- **Extras**: 4-day forecast, historical back to Nov 2020
- **Documentation**: https://openweathermap.org/api/air-pollution

**Why include**: Very generous free tier, familiar API for weather developers, includes ammonia (NH3).

```
Pros:
+ Extremely generous free tier
+ Familiar API for weather devs
+ Forecast included
+ Includes NH3

Cons:
- Model-based data
- Historical only from 2020
- Resolution unclear
```

---

#### 8. Sensor.Community (Luftdaten)
**Recommendation: CONSIDER**

- **Coverage**: Global citizen science network (~35,000 stations)
- **Pollutants**: PM2.5, PM10 (primarily)
- **Free Tier**: Free and open
- **Auth**: None required
- **Documentation**: https://sensor.community/en/

**Why include**: Massive citizen science network, completely open data, useful for hyperlocal studies.

```
Pros:
+ Huge number of sensors
+ Completely free and open
+ No API key needed
+ Hyperlocal coverage

Cons:
- Low-cost sensors (quality varies)
- Limited pollutants (mainly PM)
- Informal API
- Data quality not validated
```

---

#### 9. PurpleAir API
**Recommendation: CONSIDER (with caveats)**

- **Coverage**: Global (primarily US, consumer network)
- **Pollutants**: PM1, PM2.5, PM10, temperature, humidity
- **Free Tier**: 1 million points on signup (points-based)
- **Auth**: API key required
- **Data**: Real-time + historical since 2016
- **Documentation**: https://api.purpleair.com/

**Why include**: Large consumer sensor network, popular in US, good historical data.

```
Pros:
+ Large sensor network
+ Historical data since 2016
+ Real-time updates

Cons:
- Points-based system
- Free points may run out
- Consumer-grade sensors
- PM only
```

---

### Tier 3: Specialised / Limited Applicability

#### 10. EPA AQS API (US Historical)
**Recommendation: NICHE USE**

- **Coverage**: United States
- **Data Type**: Historical regulatory data (official record)
- **Free Tier**: Free government service
- **Use Case**: Research requiring official EPA historical records

Best used alongside AirNow for historical US research.

---

#### 11. Ambee Air Quality API
**Recommendation: LIMITED FREE TIER**

- **Coverage**: Global
- **Free Tier**: 400 calls/day only
- **Mostly commercial focus

---

#### 12. Clarity Movement Co.
**Recommendation: NOT SUITABLE**

- **Model**: Sensing-as-a-Service (requires hardware purchase)
- **API**: Comes with hardware, not standalone

---

## Implementation Priority

Based on coverage, free tier generosity, data quality, and community value:

| Priority | Source | Effort | Impact |
|----------|--------|--------|--------|
| 1 | Open-Meteo | Low (no auth) | High (forecasts + global) |
| 2 | EPA AirNow | Medium | High (US coverage) |
| 3 | AQICN/WAQI | Medium | High (global aggregator) |
| 4 | EEA | High (complex) | High (Europe regulatory) |
| 5 | AirQo | Medium | Medium (Africa gap) |
| 6 | OpenWeatherMap | Low | Medium (generous free tier) |
| 7 | IQAir | Medium | Medium (global + weather) |
| 8 | Sensor.Community | Medium | Low-Medium (citizen science) |
| 9 | PurpleAir | Medium | Low-Medium (points system) |

---

## Technical Considerations

### API Patterns
Most APIs follow similar patterns:
- REST/JSON responses
- API key authentication (header or query param)
- Rate limiting (requests/time window)
- Location-based queries (lat/lon or station ID)

### Data Normalisation
All sources will need normalisation to aeolus schema:
- `timestamp` (UTC)
- `pollutant` (standardised names)
- `value` (numeric)
- `units` (standardised: µg/m³ or ppb)
- `site_code`, `site_name`, `latitude`, `longitude`
- `network` (source identifier)

### Caching Strategy
Consider implementing caching for:
- Station metadata (rarely changes)
- Historical data (immutable)
- Current data (short TTL based on update frequency)

---

## Sources

- [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api)
- [EPA AirNow API Documentation](https://docs.airnowapi.org/)
- [AQICN API](https://aqicn.org/api/)
- [EEA Air Quality Download Service](https://www.eea.europa.eu/en/datahub/datahubitem-view/778ef9f5-6293-4846-badd-56a29c70880d)
- [AirQo API](https://airqo.net/products/api)
- [IQAir AirVisual API](https://api-docs.iqair.com/)
- [OpenWeatherMap Air Pollution API](https://openweathermap.org/api/air-pollution)
- [Sensor.Community](https://sensor.community/en/)
- [PurpleAir API](https://api.purpleair.com/)
- [EPA AQS API](https://aqs.epa.gov/aqsweb/documents/data_api.html)
