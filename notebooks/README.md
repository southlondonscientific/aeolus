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
| 06 | [African Air Quality with AirQo](06_african_air_quality.ipynb) | `AIRQO_API_KEY` | Researcher, Student |
| 07 | [Global Sensor Network Comparison](07_global_sensor_comparison.ipynb) | `PURPLEAIR_API_KEY`, `AIRQO_API_KEY` | Researcher, IoT Developer |

## Quick Start

```bash
# Install Aeolus with notebook dependencies
pip install aeolus-aq jupyter matplotlib

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
- **Composable workflows** - Demonstrates Aeolus's functional, pipe-based patterns familiar to R/openair users
- **Realistic scope** - Completes in under 5 minutes; uses manageable date ranges with notes on extending
- **Narrative structure** - Markdown explains "why" before code shows "how"
- **Graceful degradation** - Notebooks requiring API keys detect missing keys early
