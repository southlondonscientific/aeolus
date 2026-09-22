# Aeolus User Story Notebooks

Executable Jupyter notebooks demonstrating real-world air quality analysis workflows.
Each notebook is self-contained, tells a complete story, and can be adapted for your own research.

## Notebooks

| # | Notebook | API Keys | Personas |
|---|----------|----------|----------|
| 01 | [London Roadside vs Background NO2](01_london_no2_comparison.ipynb) | None | Researcher, Consultant |
| 02 | [Monthly PM2.5 Compliance Report](02_pm25_compliance_report.ipynb) | None | Local Authority, Consultant |
| 03 | [Low-Cost Sensor vs Reference Monitor](03_sensor_vs_reference.ipynb) | `PURPLEAIR_API_KEY` | Citizen Scientist, Student |
| 04 | [UK City Air Quality Ranking](04_uk_city_ranking.ipynb) | None | Journalist, Researcher |
| 05 | [Exposure Assessment for Health Study](05_exposure_assessment.ipynb) | `BL_API_KEY` | Health Researcher |
| 06 | [African Air Quality with AirQo](06_african_air_quality.ipynb) | `AIRQO_API_KEY` | Researcher, Student (outputs cleared 2026-09-23 pending a renewed AirQo token) |
| 07 | [Global Sensor Network Comparison](07_global_sensor_comparison.ipynb) | `PURPLEAIR_API_KEY`, `AIRQO_API_KEY` | Researcher, IoT Developer (executed 2026-09-23 with the AirQo token expired, so its AirQo column is empty) |
| 08 | [Multi-Year Trend Analysis](08_trend_analysis.ipynb) | None | Researcher, Consultant |

Outputs last executed live on 2026-09-23 with aeolus 0.5.0a1 (notebook 06 excepted, see above).

## Quick Start

```bash
# Install Aeolus with notebook dependencies
pip install --pre aeolus-aq jupyter matplotlib   # --pre: these notebooks need the 0.5 alpha

# Optional: for map visualisations in notebooks 04/05
pip install geopandas

# Set up API keys (copy .env.example to .env in the project root)
cp ../.env.example ../.env
# Edit .env with your keys

# Launch Jupyter
jupyter notebook
```

## Design Principles

- **Self-contained** - Each notebook runs independently
- **0.5 schema** - every download carries `network`, `backend`, `qa_code`, `qa_tier` and `ratification_stage`; the notebooks use those, never the deprecated `source_network`/`ratification` mirrors
- **Composable workflows** - Demonstrates Aeolus's functional, pipe-based patterns familiar to R/openair users
- **Realistic scope** - Completes in under 5 minutes; uses manageable date ranges with notes on extending
- **Narrative structure** - Markdown explains "why" before code shows "how"
- **Graceful degradation** - Notebooks requiring API keys detect missing keys early
