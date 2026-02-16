# User Story Notebooks - Technical Specification

*Target: Aeolus v0.4.0*
*Created: February 2026*

## Purpose

Executable Jupyter notebooks that exercise real-world workflows end-to-end. These serve three functions simultaneously:

1. **Validation** - Confirm Aeolus meets real user needs without friction
2. **Documentation** - Provide copy-pasteable examples for common tasks
3. **Regression testing** - Catch breaking changes in future releases

Each notebook is mapped to one or more validated user personas and represents a task that a real user would plausibly need to accomplish.

---

## User Personas

Based on research into the air quality data ecosystem (openair R package community, OpenAQ users, UK LAQM practitioners, citizen science networks, environmental consultancies), we identified 9 user groups. These are ranked by size, Python proficiency, and alignment with Aeolus's design.

### Primary (direct library users, Python-literate, high frequency)

| # | Persona | Description | Key Need |
|---|---------|-------------|----------|
| P1 | **Academic Researcher** | Atmospheric science, environmental science, geography. Heavy pandas users. Currently using openair (R) or custom scripts. | Multi-year, multi-site downloads with consistent schema. Trend analysis, summary statistics, publication-quality plots. |
| P2 | **Health / Epidemiology Researcher** | Exposure assessment for cohort studies. Working at scale (millions of participants). Overlaps with P1 but distinct workflows. | Multi-source harmonisation, precise site coordinates for distance calculations, long historical coverage (10-20 years). |
| P3 | **Environmental Consultant** | EIA practitioners at firms like Ricardo, AECOM, WSP, Arup. Download background monitoring data as inputs to dispersion models (ADMS, AERMOD). Thousands of assessments/year across the UK industry. | Fast download of nearest AURN/AQE site, annual mean statistics, exceedance counts, WHO/limit value compliance. |

### Secondary (benefit from Aeolus but may use via templates/notebooks rather than direct import)

| # | Persona | Description | Key Need |
|---|---------|-------------|----------|
| S1 | **Local Authority Officer** | Environmental Health Officers conducting LAQM duties. ~350 LAs in England alone. Limited Python skills; heavy Excel users. | Annual Status Report statistics, data capture rates, trend plots. Likely reached via notebook templates rather than direct API use. |
| S2 | **Citizen Scientist / Campaigner** | PurpleAir/Sensor.Community operators, groups like Mums for Lungs. Variable technical skills. | Compare their low-cost sensor against nearest reference monitor. Produce shareable charts for social media or council submissions. |
| S3 | **Educator / Student** | University lecturers and MSc/BSc students in environmental science, data science, or public health. | Simple, reliable examples that "just work". Low setup friction. Good pedagogical structure. |

### Tertiary / Strategic

| # | Persona | Description | Key Need |
|---|---------|-------------|----------|
| T1 | **AI / LLM Agent** | Automated analysis pipelines, RAG over environmental data, tool-use by Claude/GPT. Growing rapidly. | Predictable API, self-describing metadata (list_sources, get_source_info), comprehensive docstrings, consistent schema. |
| T2 | **Data Journalist** | Investigations for Guardian, BBC, Bureau of Investigative Journalism. Small but high-visibility group. | Fast data access under deadline pressure, AQI context for raw numbers, source attribution. |
| T3 | **Smart City / IoT Developer** | Dashboard and alert system builders. Use Aeolus for prototyping; production systems typically build direct integrations. | Multi-source normalised feeds, geocoded metadata for maps, AQI calculations for health messaging. |

---

## Notebook Specifications

### Notebook 1: Roadside vs Background NO2 in London

**File:** `notebooks/01_london_no2_comparison.ipynb`
**Primary persona:** P1 (Academic Researcher)
**Secondary personas:** P3 (Consultant), T2 (Journalist)

**Scenario:** A researcher wants to compare roadside and background NO2 concentrations across London for a full year to understand the traffic contribution to urban air pollution.

**Workflow:**
1. Fetch AURN metadata, identify London sites, classify by site type (Traffic vs Urban Background)
2. Download 12 months of data for 4-6 sites
3. Calculate annual means per site and compare against the UK limit value (40 ug/m3)
4. Plot diurnal profiles (hourly means by hour-of-day) — roadside vs background
5. Create a weekly pattern plot (are weekdays worse than weekends?)
6. Calculate the roadside increment (roadside minus background)

**Aeolus features exercised:**
- `networks.get_metadata("AURN")` + DataFrame filtering
- `download("AURN", sites, start, end)` with multiple sites
- `metrics.aqi_summary()` with daily/annual frequency
- `viz` time series and diurnal plots

**What we're validating:**
- Metadata is rich enough to filter by site type
- Multi-site download works cleanly for a full year
- Timestamps align correctly across sites for paired comparisons
- Plots are publication-quality out of the box

---

### Notebook 2: Monthly PM2.5 Compliance Report

**File:** `notebooks/02_pm25_compliance_report.ipynb`
**Primary persona:** S1 (Local Authority Officer), P3 (Consultant)
**Secondary personas:** S2 (Citizen Scientist)

**Scenario:** A local authority officer needs to produce a monthly air quality summary for their borough, checking PM2.5 against the WHO 2021 guidelines and UK limit values.

**Workflow:**
1. Download PM2.5 data from nearest AURN/AQE site(s) for the current year
2. Calculate data capture rate (% valid hours)
3. Calculate running annual mean and compare against WHO interim targets (IT-1 through IT-4) and guidelines
4. Count daily exceedances (days > 15 ug/m3 WHO guideline, days > 50 ug/m3 PM10 short-term)
5. Calculate UK DAQI distribution (how many days in each band)
6. Generate a one-page summary with key statistics and a calendar heatmap

**Aeolus features exercised:**
- `download()` with single source
- `metrics.aqi_summary(index="UK_DAQI", freq="D")`
- `metrics.aqi_check_who()`
- `viz.calendar_heatmap()`, `viz.aqi_card()`

**What we're validating:**
- Metrics calculations match official DEFRA methodology
- WHO guideline checking works end-to-end
- Calendar heatmap handles missing data gracefully
- Output is clear enough for a non-technical audience

---

### Notebook 3: Low-Cost Sensor vs Reference Monitor

**File:** `notebooks/03_sensor_vs_reference.ipynb`
**Primary persona:** S2 (Citizen Scientist)
**Secondary personas:** P1 (Researcher), S3 (Student)

**Scenario:** A citizen scientist with a PurpleAir sensor near their home wants to compare its readings against the nearest AURN reference monitor to understand how reliable their data is.

**Workflow:**
1. Fetch PurpleAir metadata for a specific sensor (by sensor index)
2. Fetch AURN metadata and find the nearest site by distance
3. Download data from both sources for the same time period (1 month)
4. Align timestamps (both should be hourly after Aeolus normalisation)
5. Scatter plot: PurpleAir PM2.5 vs AURN PM2.5 with regression line
6. Time series overlay: both sensors on the same plot
7. Calculate R-squared, RMSE, and bias
8. Discuss QA/QC flags (PurpleAir's dual-channel validation)

**Aeolus features exercised:**
- `portals.find_sites("PURPLEAIR", ...)` or `download("PURPLEAIR", [sensor_id], ...)`
- `networks.get_metadata("AURN")` + distance calculation
- `download()` with dict format (two sources)
- Cross-source DataFrame merge on `date_time`
- `viz.time_series()` with multiple sources

**What we're validating:**
- Cross-source timestamp alignment works (both produce UTC-aware hourly data)
- PurpleAir and AURN data can be meaningfully joined
- The standard schema makes cross-source comparison straightforward
- QA/QC ratification flags are present and interpretable

---

### Notebook 4: UK City Air Quality Ranking

**File:** `notebooks/04_uk_city_ranking.ipynb`
**Primary persona:** T2 (Data Journalist)
**Secondary personas:** P1 (Researcher), S1 (Local Authority)

**Scenario:** A journalist wants to produce a "worst air quality cities in the UK" ranking for a summer investigation, using official data from multiple UK regulatory networks.

**Workflow:**
1. Fetch metadata from AURN, AQE, SAQN, WAQN, NI — get all Urban Background sites
2. Download NO2 and PM2.5 data for summer months (June-August) across all sites
3. Calculate site-level summer means
4. Map sites to cities/regions using metadata
5. Rank cities by mean NO2 and PM2.5
6. Create a bar chart of the top/bottom 20 cities
7. Produce a map visualisation showing pollution levels geographically

**Aeolus features exercised:**
- `download()` with dict format across 5+ networks
- Multi-network metadata aggregation
- `metrics.aqi_summary()` for ranking
- DataFrame groupby operations on combined data

**What we're validating:**
- Multi-network download at scale (potentially 100+ sites)
- Schema consistency when combining 5 different UK networks
- Metadata provides enough geographic information for city-level aggregation
- Performance is acceptable for bulk downloads

---

### Notebook 5: Exposure Assessment for Health Study

**File:** `notebooks/05_exposure_assessment.ipynb`
**Primary persona:** P2 (Health Researcher)
**Secondary personas:** P1 (Academic)

**Scenario:** A health researcher needs pollution exposure estimates for a set of study locations (e.g. GP surgeries in London) by finding the nearest monitors and downloading their data.

**Workflow:**
1. Define study locations (list of lat/lon coordinates for 10 GP surgeries)
2. Fetch metadata from multiple sources (AURN, Breathe London, AQE)
3. For each study location, find the nearest monitor(s) within a radius
4. Download data from all relevant monitors for the study period (1 year)
5. Calculate annual and seasonal means per monitor
6. Assign exposure estimates to each study location (nearest monitor or inverse-distance weighting)
7. Summarise exposure distribution across the study population

**Aeolus features exercised:**
- Multi-source metadata aggregation with coordinates
- Distance calculations between study locations and monitors
- `download()` with large site lists
- Temporal aggregation (annual, seasonal means)

**What we're validating:**
- Metadata coordinates are precise enough for distance-based assignment
- Multi-source data can be combined for spatial coverage
- The workflow is reproducible (scriptable, no manual steps)
- Performance is acceptable for research-scale downloads

---

### Notebook 6: African Air Quality with AirQo

**File:** `notebooks/06_african_air_quality.ipynb`
**Primary persona:** P1 (Academic Researcher)
**Secondary personas:** S3 (Student)

**Scenario:** A researcher studying air quality in sub-Saharan African cities wants to compare PM2.5 levels across Kampala, Nairobi, and Lagos using AirQo data.

**Workflow:**
1. Fetch AirQo metadata, explore available cities and grids
2. Select representative sites from each city
3. Download PM2.5 data for a comparable time period
4. Calculate city-level daily means
5. Compare against WHO guidelines
6. Plot time series and boxplots by city
7. Discuss data quality considerations (sensor type, data capture)

**Aeolus features exercised:**
- `networks.get_metadata("AIRQO")` with country/city filtering
- `download("AIRQO", sites, ...)` for African network
- `metrics.aqi_check_who()` for WHO guideline comparison
- `viz.boxplot()`, `viz.time_series()`

**What we're validating:**
- AirQo source works end-to-end
- Metadata filtering by country/city is functional
- Data quality is sufficient for meaningful analysis
- WHO guideline checking contextualises the results

---

### Notebook 7: Global Sensor Network Comparison

**File:** `notebooks/07_global_sensor_comparison.ipynb`
**Primary persona:** P1 (Academic Researcher)
**Secondary personas:** T1 (AI Agent), T3 (IoT Developer)

**Scenario:** A researcher wants to compare data quality and coverage across different low-cost sensor networks (PurpleAir, Sensor.Community, AirQo) for a review paper on citizen science air quality monitoring.

**Workflow:**
1. Fetch metadata from PurpleAir, Sensor.Community, and AirQo
2. Summarise: number of sensors, geographic coverage, available measurands
3. Select co-located sensors (if any) from different networks
4. Download overlapping time periods
5. Compare measurement distributions (boxplots, density plots)
6. Assess data completeness and reporting frequency
7. Discuss ratification flags across networks

**Aeolus features exercised:**
- `list_sources()` and `get_source_info()` for discovery
- Multi-source metadata fetching
- Cross-source download and comparison
- Schema consistency across low-cost sensor sources

**What we're validating:**
- All three low-cost sensor sources work reliably
- The standard schema makes cross-network comparison possible
- Ratification/QA flags are meaningful and consistent
- Metadata is rich enough to identify co-located sensors

---

## Implementation Notes

### Directory Structure

```
notebooks/
    README.md                              # Overview and setup instructions
    01_london_no2_comparison.ipynb
    02_pm25_compliance_report.ipynb
    03_sensor_vs_reference.ipynb
    04_uk_city_ranking.ipynb
    05_exposure_assessment.ipynb
    06_african_air_quality.ipynb
    07_global_sensor_comparison.ipynb
```

### Design Principles

1. **Self-contained**: Each notebook runs independently. No shared state or imports between notebooks.
2. **Graceful degradation**: Notebooks that require API keys should detect missing keys early and display a clear message, not crash halfway through.
3. **Realistic scope**: Each notebook should complete in under 5 minutes on a reasonable connection. Use manageable date ranges (1 month for demos, note how to extend).
4. **Narrative structure**: Each notebook tells a story. Markdown cells explain the "why" before code cells show the "how".
5. **AI-friendly**: Clear section headers, docstring-like explanations, and predictable patterns that LLM agents can learn from and adapt.

### API Key Handling

Notebooks requiring API keys should start with:

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Check required keys
required_keys = {"PURPLEAIR_API_KEY": "PurpleAir"}
missing = {name: source for key, source in required_keys.items()
           if not os.environ.get(key)}
if missing:
    print(f"Missing API keys: {missing}")
    print("See .env.example for setup instructions")
```

### Notebooks by API Key Requirement

| Notebook | API Keys Required |
|----------|-------------------|
| 01 London NO2 | None (AURN is free) |
| 02 PM2.5 Compliance | None (AURN/AQE are free) |
| 03 Sensor vs Reference | `PURPLEAIR_API_KEY` |
| 04 UK City Ranking | None (all UK regulatory networks are free) |
| 05 Exposure Assessment | `BL_API_KEY` (Breathe London) |
| 06 African Air Quality | `AIRQO_API_KEY` |
| 07 Global Sensor Comparison | `PURPLEAIR_API_KEY`, `AIRQO_API_KEY` |

### Dependencies

Notebooks should only require Aeolus + standard scientific Python:

```
aeolus-aq
jupyter
matplotlib
pandas
numpy
scipy          # for regression statistics in notebook 03
geopandas      # optional, for map in notebooks 04/05
```

---

## Quality of Life Features to Support These Notebooks

The notebooks will likely reveal friction points. Based on the user research, we anticipate needing these improvements (also targeted for v0.4.0):

### High Priority

| Feature | Supports Notebooks | Supports Personas |
|---------|-------------------|-------------------|
| **`find_sites(near=(lat,lon), radius_km=N)`** | 03, 05 | P2, P3, S2 |
| **Progress indicators for downloads** | 04, 05 | All |
| **Local file caching (historical data)** | 04, 05 | P1, P2, P3 |

### Medium Priority

| Feature | Supports Notebooks | Supports Personas |
|---------|-------------------|-------------------|
| **`aeolus.summarize(data)`** convenience function | All | All |
| **Date range shorthand** (`last="30d"`) | 02 | S1, S2 |
| **Consistent API key error messages** | 03, 06, 07 | All |

### Lower Priority (consider for v0.5.0)

| Feature | Supports Notebooks | Supports Personas |
|---------|-------------------|-------------------|
| CLI interface (`aeolus download ...`) | N/A | S1, S2 |
| MCP server for LLM agents | N/A | T1 |
| CSV/Excel export helpers | 02 | S1, P3 |

---

## Success Criteria

Each notebook should:

- [ ] Run end-to-end without errors (given appropriate API keys)
- [ ] Complete in under 5 minutes
- [ ] Produce at least 2 meaningful visualisations
- [ ] Exercise at least 3 Aeolus functions/modules
- [ ] Include narrative explanation accessible to the target persona
- [ ] Handle missing data and edge cases gracefully
- [ ] Be useful as a starting point for a real analysis (not just a demo)

## Open Questions

1. **Should notebooks be tested in CI?** Could run the no-API-key ones (01, 02, 04) as part of the test suite using `nbval` or similar. The API-key ones would need secrets in CI.
2. **Should we produce static HTML renders?** For users who want to see the output without running the notebooks. Could be part of the mkdocs site.
3. **Should we include a "quick start" notebook?** A simpler notebook 00 that just demonstrates `download()`, `list_sources()`, and basic plotting in 10 lines. Aimed at persona S3 (educators).
