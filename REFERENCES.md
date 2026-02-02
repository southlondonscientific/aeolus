# References

This document lists the sources, methodologies, and acknowledgements for aeolus.

## Contributors

### Code

- **Ruaraidh Dobson** - Project creator, architecture, documentation
- **Claude (Anthropic)** - Code implementation, including data source integrations (PurpleAir, Breathe London, AirQo, OpenAQ), AQI calculations, QA/QC methodology, test suites, and documentation

### Data and Methodology

The following organisations and individuals have contributed data, APIs, methodologies, or foundational work that aeolus builds upon. See detailed sections below.

---

## Data Sources

### UK Regulatory Networks

Aeolus accesses UK regulatory air quality data via the openair project's data files.

**openair R Package**

Carslaw, D.C. and K. Ropkins (2012). openair — an R package for air quality data analysis. *Environmental Modelling & Software*, 27-28, 52-61. https://doi.org/10.1016/j.envsoft.2011.09.008

- Website: https://davidcarslaw.github.io/openair/
- GitHub: https://github.com/davidcarslaw/openair

The openair project provides pre-processed data files from UK regulatory monitoring networks. If you use aeolus with UK data, please cite the openair paper above.

**Data Sources:**

| Network | Operator | Data URL |
|---------|----------|----------|
| AURN | DEFRA | https://uk-air.defra.gov.uk/openair/R_data/ |
| SAQN | Scottish Environment Protection Agency | https://www.scottishairquality.scot/openair/R_data/ |
| WAQN | Natural Resources Wales | https://airquality.gov.wales/sites/default/files/openair/R_data/ |
| NI | DAERA Northern Ireland | https://www.airqualityni.co.uk/openair/R_data/ |
| AQE | Air Quality England (Ricardo) | https://airqualityengland.co.uk/assets/openair/R_data/ |
| LOCAL/LMAM | Local authority networks | https://uk-air.defra.gov.uk/openair/LMAM/R_data/ |

### OpenAQ

OpenAQ is a non-profit organisation providing open access to global air quality data.

- Website: https://openaq.org/
- API Documentation: https://docs.openaq.org/
- API Base URL: https://api.openaq.org/v3

OpenAQ aggregates data from government monitoring stations and low-cost sensor networks across 100+ countries.

### Breathe London

Breathe London is operated by Imperial College London's Environmental Research Group (ERG).

- Website: https://www.breathelondon.org/
- API Documentation: https://www.breathelondon.org/developers
- Data Licence: Open Government Licence v3.0

The network provides high-density air quality monitoring across London using a combination of reference-grade and indicative monitors.

### AirQo

AirQo is operated by Makerere University, Uganda, with a mission to bridge the air quality data gap in Africa.

- Website: https://airqo.net/
- API Documentation: https://docs.airqo.net/airqo-rest-api-documentation/
- Platform: https://analytics.airqo.net/

AirQo operates 200+ low-cost sensors across 16+ African cities.

### PurpleAir

PurpleAir operates a global network of 30,000+ low-cost air quality sensors.

- Website: https://www.purpleair.com/
- API Documentation: https://api.purpleair.com/
- Developer Portal: https://develop.purpleair.com/
- Map: https://map.purpleair.com/

---

## Air Quality Index Standards

### UK Daily Air Quality Index (DAQI)

**Standard:** DEFRA Daily Air Quality Index

- URL: https://uk-air.defra.gov.uk/air-pollution/daqi
- Technical Document: DEFRA (2013). "Update on Implementation of the Daily Air Quality Index"
- Document URL: https://uk-air.defra.gov.uk/assets/documents/reports/cat14/1304251155_Update_on_Implementation_of_the_DAQI_April_2013_Final.pdf

Developed by DEFRA in consultation with COMEAP (Committee on the Medical Effects of Air Pollutants). Uses a 1-10 scale with four bands: Low (1-3), Moderate (4-6), High (7-9), Very High (10).

### US EPA Air Quality Index

**Standard:** 40 CFR Part 58, Appendix G - Uniform Air Quality Index (AQI) and Daily Reporting

- URL: https://www.airnow.gov/aqi/aqi-basics/
- CFR Citation: https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-58/appendix-Appendix%20G%20to%20Part%2058
- PM2.5 Breakpoint Update (2024): Federal Register 89 FR 16202 (February 7, 2024)
- Fact Sheet: https://www.epa.gov/system/files/documents/2024-02/pm-naaqs-air-quality-index-fact-sheet.pdf

**NowCast Algorithm:**

- Fact Sheet: https://www.epa.gov/sites/default/files/2018-01/documents/nowcastfactsheet.pdf
- Technical Discussion: https://forum.airnowtech.org/t/the-nowcast-for-pm2-5-and-pm10/172

The NowCast algorithm provides real-time AQI estimates by weighting recent hourly measurements based on concentration stability.

### EU Common Air Quality Index (CAQI)

**Standard:** CITEAIR Project Common Air Quality Index

- URL: https://airindex.eea.europa.eu/AQI/index.html
- Technical Document: https://www.europarl.europa.eu/meetdocs/2004_2009/documents/dv/citeair_/citeair_en.pdf

**Academic Reference:**

Van den Elshout, S., Barber, K., & Léger, K. (2014). CAQI Common Air Quality Index—Update with PM2.5 and sensitivity analysis. *Science of The Total Environment*, 488-489, 461-468. https://doi.org/10.1016/j.scitotenv.2013.10.060

Note: The EU has since introduced the European Air Quality Index (EAQI) in 2017, which differs from CAQI. Aeolus implements the original CAQI with roadside and background variants.

### China Air Quality Index

**Standard:** HJ 633-2012 Technical Regulation on Ambient Air Quality Index (Trial)

- Related Standard: GB 3095-2012 Ambient Air Quality Standards
- Effective Date: January 1, 2016 (nationwide implementation)

Replaced the previous Air Pollution Index (API) system. Uses mg/m³ for CO (not µg/m³) per Chinese standard.

### India National Air Quality Index (NAQI)

**Standard:** Central Pollution Control Board (CPCB) National Air Quality Index

- URL: https://cpcb.nic.in/National-Air-Quality-Index/
- Press Release: https://www.pib.gov.in/newsite/printrelease.aspx?relid=110654
- Launch Date: October 17, 2014 (under Swachh Bharat Abhiyan)

Developed by CPCB in collaboration with IIT Kanpur. Uniquely includes NH3 (ammonia) and Pb (lead) among the monitored pollutants.

### WHO Air Quality Guidelines

**Standard:** WHO Global Air Quality Guidelines (2021)

- URL: https://www.who.int/publications/i/item/9789240034228
- Direct PDF: https://iris.who.int/bitstream/handle/10665/345334/9789240034433-eng.pdf
- ISBN: 978-92-4-003422-8
- Published: September 22, 2021

Key changes from 2005 guidelines:
- PM2.5 annual: 5 µg/m³ (was 10)
- PM2.5 24-hour: 15 µg/m³ (was 25)
- NO2 annual: 10 µg/m³ (was 40)
- NO2 24-hour: 25 µg/m³ (new)

Includes Interim Targets (IT-1 through IT-4) for progressive improvement in areas where current pollution levels are high.

---

## QA/QC Methodologies

### PurpleAir Dual-Channel Agreement

PurpleAir sensors contain two laser particle counters (Channel A and Channel B) for redundancy. Aeolus uses concentration-dependent thresholds to validate channel agreement.

**Source:** PurpleAir Community Forum - "PurpleAir PM2.5 ATM QAQC"

- URL: https://community.purpleair.com/t/purpleair-pm2-5-atm-qaqc/1066
- Accessed: February 2026

**Thresholds implemented:**

| Concentration Range | Threshold Type | Value | Rationale |
|---------------------|----------------|-------|-----------|
| < 0.3 µg/m³ | Detection limit | Flag as invalid | Below sensor noise floor |
| 0.3 - 100 µg/m³ | Absolute | ±10 µg/m³ | At low concentrations, absolute error dominates |
| 100 - 1000 µg/m³ | Relative | ±10% | At high concentrations, relative error dominates |
| > 1000 µg/m³ | Saturation limit | Flag as invalid | Sensor saturation |

**Rationale:** At low concentrations, a fixed percentage threshold would be too strict. At high concentrations, a fixed absolute threshold would be too lenient. The hybrid approach matches the error characteristics of low-cost optical particle counters.

**Additional PurpleAir References:**

- Confidence Score Calculation: https://community.purpleair.com/t/how-the-confidence-score-is-calculated/10641
- Channel A and B Explanation: https://community.purpleair.com/t/what-are-channel-a-and-channel-b/3643

### PurpleAir Correction Factors

For reference, the following paper discusses PurpleAir accuracy and correction equations:

Holder, A.L., et al. (2022). Correction and Accuracy of PurpleAir PM2.5 Measurements for Extreme Wildfire Smoke. *Sensors*, 22(24), 9669. https://doi.org/10.3390/s22249669

Note: Aeolus does not currently apply correction factors to PurpleAir data. Users requiring corrected data should apply appropriate corrections for their use case.

### EPA Low-Cost Sensor Performance Targets

The US EPA has published performance targets for PM2.5 sensors:

- Air Sensor Performance Targets: https://www.epa.gov/air-sensor-toolbox/air-sensor-performance-targets-and-testing-protocols

These targets inform sensor evaluation but are not directly used for real-time QA/QC in aeolus.

---

## Software Dependencies

Aeolus builds on excellent open-source software:

- **pandas** - Data manipulation and analysis
- **requests** - HTTP library for API access
- **matplotlib** - Visualisation
- **purpleair-api** - PurpleAir API wrapper by Carlos Santos (carlkidcrypto)
  - PyPI: https://pypi.org/project/purpleair-api/
  - GitHub: https://github.com/carlkidcrypto/purpleair_api
- **openaq** - OpenAQ Python SDK
  - PyPI: https://pypi.org/project/openaq/
- **rdata** - R data file reader (for UK regulatory data)

---

## Licence

Aeolus is released under the GNU General Public License v3.0 or later.

Data accessed through aeolus is subject to the terms of the respective data providers. Users are responsible for ensuring compliance with data usage terms.

---

## Contributing

If you identify errors in the methodology, know of better sources, or would like to contribute:

- GitHub Issues: https://github.com/southlondonscientific/aeolus/issues
- Email: ruaraidh.dobson@gmail.com
