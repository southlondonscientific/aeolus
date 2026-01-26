# Air Quality Index Sources and References

This document provides authoritative references for all AQI indices and calculations
implemented in the `aeolus.metrics` module. Scientists and researchers can use these
sources to verify our implementations.

## Unit Conversion

### Molecular Weights

Source: **NIST WebBook** (National Institute of Standards and Technology)
- URL: https://webbook.nist.gov/chemistry/
- Secondary: PubChem https://pubchem.ncbi.nlm.nih.gov/

| Pollutant | NIST Value (g/mol) | Our Value |
|-----------|-------------------|-----------|
| NO₂       | 46.0055           | 46.01     |
| O₃        | 47.9982           | 48.00     |
| SO₂       | 64.0638           | 64.07     |
| CO        | 28.0101           | 28.01     |

### Molar Volume

The molar volume at standard conditions (25°C, 1 atm) is 24.45 L/mol.

Derivation from ideal gas law:
```
V = nRT/P = (1 mol × 0.082057 L·atm/(mol·K) × 298.15 K) / 1 atm = 24.465 L/mol
```

This is the standard reference condition used by:
- UK DEFRA: https://uk-air.defra.gov.uk/
- US EPA for ambient air quality
- EU air quality directives

Reference: UK DEFRA Technical Guidance
- URL: https://uk-air.defra.gov.uk/assets/documents/reports/cat06/0502160851_Conversion_Factors_Between_ppb_and.pdf

**Note**: Some regulations use 20°C (293.15K), giving 24.04 L/mol. We use 25°C as it
is the most common reference in international AQI standards.

---

## UK DAQI (Daily Air Quality Index)

### Primary Source

**COMEAP (Committee on the Medical Effects of Air Pollutants) / DEFRA**

- Main page: https://uk-air.defra.gov.uk/air-pollution/daqi
- Technical specification: https://uk-air.defra.gov.uk/air-pollution/daqi?view=more-info

### Implementation Document

"Update on Implementation of the Daily Air Quality Index - Information for Data
Providers and Publishers"
- Publisher: Department for Environment, Food & Rural Affairs (DEFRA)
- Date: April 2013
- URL: https://uk-air.defra.gov.uk/assets/documents/reports/cat14/1304251155_Update_on_Implementation_of_the_DAQI_April_2013_Final.pdf

### Version History

| Version | Date | Changes |
|---------|------|---------|
| Current | April 2013 | Current 10-band system with PM2.5 |
| Original | 2012 | Initial DAQI launch |

**Note**: The UK DAQI is under review and may change. Monitor DEFRA announcements.

### Key Specifications

- Scale: 1-10 (Low 1-3, Moderate 4-6, High 7-9, Very High 10)
- Pollutants: PM2.5, PM10, O3, NO₂, SO₂
- Averaging: 24-hour running mean for PM; 8-hour running mean for O3; 1-hour for NO₂, SO₂
- Rounding: Concentrations rounded to nearest integer before breakpoint lookup
- Coverage: 75% data capture required

---

## US EPA AQI

### Primary Source

**40 CFR Part 58, Appendix G - Uniform Air Quality Index (AQI) and Daily Reporting**

- eCFR (Electronic Code of Federal Regulations):
  https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-58/appendix-Appendix%20G%20to%20Part%2058
- Cornell LII: https://www.law.cornell.edu/cfr/text/40/appendix-G_to_part_58

### Technical Guidance

"Technical Assistance Document for the Reporting of Daily Air Quality"
- Publisher: US EPA / AirNow
- URL: https://document.airnow.gov/technical-assistance-document-for-the-reporting-of-daily-air-quailty.pdf
- Alternate: https://www.airnow.gov/sites/default/files/2020-05/aqi-technical-assistance-document-sept2018.pdf

### NowCast Algorithm

"NowCast Fact Sheet"
- Publisher: US EPA
- URL: https://www.epa.gov/sites/default/files/2018-01/documents/nowcastfactsheet.pdf
- Forum discussion: https://forum.airnowtech.org/t/the-nowcast-for-pm2-5-and-pm10/172

### Version History

| Version | Effective Date | Changes |
|---------|---------------|---------|
| Current | May 6, 2024 | PM2.5 breakpoints revised (annual standard now 9 µg/m³) |
| Previous | December 2012 | Added PM2.5 1-hour breakpoints |
| Original | 1999 | Initial AQI replacing PSI |

**2024 PM2.5 Update Details**:
- Federal Register: https://www.federalregister.gov/documents/2024/02/07/2024-02637/reconsideration-of-the-national-ambient-air-quality-standards-for-particulate-matter
- Fact Sheet: https://www.epa.gov/system/files/documents/2024-02/pm-naaqs-air-quality-index-fact-sheet.pdf

### Key Specifications

- Scale: 0-500
- Categories: Good (0-50), Moderate (51-100), Unhealthy for Sensitive Groups (101-150),
  Unhealthy (151-200), Very Unhealthy (201-300), Hazardous (301-500)
- Pollutants: O₃, PM2.5, PM10, CO, SO₂, NO₂
- O₃: Uses 8-hour average; 1-hour values used only when AQI > 100
- PM: 24-hour average; NowCast for real-time
- Truncation: Values truncated (not rounded) per pollutant-specific rules

---

## China AQI

### Primary Source

**HJ 633-2012: Technical Regulation on Ambient Air Quality Index (Trial)**

- Publisher: Ministry of Environmental Protection of China
- Effective: January 1, 2016 (nationwide); earlier in some cities
- Standard number: HJ 633-2012

Related standard:
- **GB 3095-2012: Ambient Air Quality Standards**

### Reference

- Overview: https://www.transportpolicy.net/standard/china-air-quality-standards/
- AQI Hub summary: https://aqihub.info/indices/china

### Version History

| Version | Effective Date | Changes |
|---------|---------------|---------|
| HJ 633-2012 | Jan 1, 2016 | New AQI system with PM2.5 and O3 |
| API (previous) | Pre-2012 | Air Pollution Index (replaced) |

### Key Specifications

- Scale: 0-500
- Categories: 优 Excellent (0-50), 良 Good (51-100), 轻度污染 Lightly Polluted (101-150),
  中度污染 Moderately Polluted (151-200), 重度污染 Heavily Polluted (201-300),
  严重污染 Severely Polluted (301-500)
- Pollutants: PM2.5, PM10, O₃, NO₂, SO₂, CO
- O₃: 8-hour average (or 1-hour when higher)
- PM: 24-hour average
- CO: Reported in mg/m³ (not µg/m³)

---

## EU CAQI (Common Air Quality Index)

### Primary Source

**CITEAIR Project (Common Information to European Air)**

- Project document: https://www.europarl.europa.eu/meetdocs/2004_2009/documents/dv/citeair_/citeair_en.pdf
- Website (historical): www.airqualitynow.eu

### Academic Reference

Van den Elshout, S., Léger, K., & Nussio, F. (2008). "Comparing urban air quality in
Europe in real time: A review of existing air quality indices and the proposal of a
common alternative." *Environment International*, 34(5), 720-726.

Updated methodology:
Van den Elshout, S., Barber, K., & Léger, K. (2014). "CAQI Common Air Quality Index—
Update with PM2.5 and sensitivity analysis." *Science of The Total Environment*,
488-489, 461-468. https://doi.org/10.1016/j.scitotenv.2013.10.060

### EEA Technical Paper

"Air Quality and Air Quality Indices: A World Apart?"
- Publisher: European Environment Agency (EEA/EIONET)
- URL: https://www.eionet.europa.eu/etcs/etc-atni/products/etc-atni-reports/etcacc_technpaper_2005_5_aq_indices/

### Version History

| Version | Date | Changes |
|---------|------|---------|
| Updated | 2014 | Added PM2.5 |
| Original | 2006 | Initial CAQI (CITEAIR project) |

**Note**: The EU also has a newer European Air Quality Index (EAQI) from 2017,
which differs from CAQI. We implement CAQI as it is more widely documented.

### Key Specifications

- Scale: 0-100+ (displayed as categories 1-6)
- Categories: Very Low (0-25), Low (25-50), Medium (50-75), High (75-100), Very High (>100)
- Two variants:
  - **Roadside**: Mandatory NO₂ + PM10; optional PM2.5, CO
  - **Background**: Mandatory NO₂ + O₃ + PM10; optional PM2.5, SO₂, CO
- Averaging: Hourly values (also daily version exists)

---

## India NAQI (National Air Quality Index)

### Primary Source

**Central Pollution Control Board (CPCB)**

- Main page: https://www.cpcb.nic.in/National-Air-Quality-Index/
- Portal: https://cpcb.nic.in/naqi/
- Real-time data: https://airquality.cpcb.gov.in/AQI_India/

### Launch Information

- Press release: https://www.pib.gov.in/newsite/printrelease.aspx?relid=110654
- Launch date: October 17, 2014
- Developed by: IIT Kanpur with CPCB expert committee

### Version History

| Version | Date | Changes |
|---------|------|---------|
| Current | October 2014 | Initial launch |

### Key Specifications

- Scale: 0-500
- Categories: Good (0-50), Satisfactory (51-100), Moderate (101-200), Poor (201-300),
  Very Poor (301-400), Severe (401-500)
- Pollutants: PM2.5, PM10, O₃, NO₂, SO₂, CO, NH₃, Pb
- Unique: Includes ammonia (NH₃) and lead (Pb)
- O₃: 8-hour average (1-hour when concentration > 168 µg/m³)
- PM: 24-hour average

---

## WHO Guidelines (2021)

### Primary Source

**WHO Global Air Quality Guidelines: Particulate Matter (PM2.5 and PM10), Ozone,
Nitrogen Dioxide, Sulfur Dioxide and Carbon Monoxide**

- Publisher: World Health Organization
- Date: September 22, 2021
- ISBN: 978-92-4-003422-8
- Main page: https://www.who.int/publications/i/item/9789240034228
- Direct PDF: https://iris.who.int/bitstream/handle/10665/345334/9789240034433-eng.pdf
- NCBI Bookshelf: https://www.ncbi.nlm.nih.gov/books/NBK574594/

### Version History

| Version | Date | Key Changes |
|---------|------|-------------|
| 2021 | September 2021 | Significantly stricter; PM2.5 annual AQG now 5 µg/m³ (was 10) |
| 2005 | 2005 | Previous guidelines |
| 2000 | 2000 | Second edition |
| 1987 | 1987 | First edition |

### Key Specifications

**Air Quality Guideline (AQG) - Strictest targets:**

| Pollutant | Averaging | AQG Value |
|-----------|-----------|-----------|
| PM2.5 | Annual | 5 µg/m³ |
| PM2.5 | 24-hour | 15 µg/m³ |
| PM10 | Annual | 15 µg/m³ |
| PM10 | 24-hour | 45 µg/m³ |
| O₃ | Peak season 8-hour | 60 µg/m³ |
| NO₂ | Annual | 10 µg/m³ |
| NO₂ | 24-hour | 25 µg/m³ |
| SO₂ | 24-hour | 40 µg/m³ |
| CO | 24-hour | 4 mg/m³ |

**Interim Targets (IT-1 to IT-4):**

The WHO provides interim targets for countries that cannot immediately meet AQG values.
IT-1 is the least strict (closest to current conditions), IT-4 is closest to AQG.

---

## Document Maintenance

**Last updated**: January 2025

**Retrieval dates for online sources**: January 2025

When updating this document or the implementation, verify that:
1. Regulatory sources have not been superseded
2. Breakpoint values match current official publications
3. Version history is accurate

Report discrepancies to: https://github.com/[repo]/issues
