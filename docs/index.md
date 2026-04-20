# Aeolus

**Download and standardise air quality data from monitoring networks worldwide.**

Aeolus provides a unified Python interface for accessing air quality data from multiple sources, automatically normalising everything into a consistent pandas DataFrame format.

## Features

- **Unified API** - One interface for all data sources
- **Site discovery** - Find nearby monitoring sites with `find_sites()`
- **Near-real-time data** - Latest readings via `get_current()` (UK regulatory networks)
- **Automatic normalisation** - Consistent data format regardless of source
- **Multiple networks** - UK regulatory networks, global platforms, low-cost sensors
- **Analysis functions** - Time averaging, regulatory statistics, trend detection
- **Built-in metrics** - Calculate AQI from 7 international standards
- **Visualisation tools** - Publication-ready plots including openair-style temporal variation
- **Local caching** - Parquet-based download cache for fast re-runs
- **Progress indicators** - Optional tqdm progress bars for bulk downloads

## Supported Data Sources

| Source | Coverage | API Key Required |
|--------|----------|------------------|
| AURN | UK regulatory network | No |
| SAQN | Scottish network | No |
| WAQN | Welsh network | No |
| NI | Northern Ireland network | No |
| AQE | Air Quality England (local authorities) | No |
| LAQN | London Air Quality Network (~250 sites) | No |
| EEA | European Environment Agency (40+ countries, 7,000+ stations) | No |
| OpenAQ | Global (100+ countries) | Yes |
| Breathe London | London low-cost sensors | Yes |
| AirQo | African cities | Yes |
| EPA AirNow | US, Canada, Mexico (2,500+ stations) | Yes |
| PurpleAir | Global (30,000+ sensors) | Yes |
| Sensor.Community | Global citizen science (35,000+ sensors) | No |
| Sonitus | Smart Dublin, Ireland | No |

## Quick Example

```python
import aeolus
from datetime import datetime

# Download data from UK regulatory network
data = aeolus.download(
    sources="AURN",
    sites=["MY1", "KC1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Data is a standardised pandas DataFrame
print(data.head())
```

## Installation

```bash
pip install aeolus-aq
```

See the [Installation Guide](getting-started/installation.md) for more options.

## User Story Notebooks

Learn by example with 8 executable Jupyter notebooks covering real-world workflows:

| Notebook | Scenario | API Key |
|----------|----------|---------|
| [01 London NO2](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/01_london_no2_comparison.ipynb) | Roadside vs background NO2 comparison | None |
| [02 PM2.5 Compliance](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/02_pm25_compliance_report.ipynb) | Monthly compliance report with WHO guidelines | None |
| [03 Sensor vs Reference](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/03_sensor_vs_reference.ipynb) | PurpleAir vs AURN comparison | PurpleAir |
| [04 UK City Ranking](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/04_uk_city_ranking.ipynb) | Multi-network city ranking | None |
| [05 Exposure Assessment](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/05_exposure_assessment.ipynb) | Health study exposure estimates | Breathe London |
| [06 African Air Quality](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/06_african_air_quality.ipynb) | AirQo network analysis | AirQo |
| [07 Global Sensors](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/07_global_sensor_comparison.ipynb) | Cross-network sensor comparison | PurpleAir + AirQo |
| [08 Trend Analysis](https://github.com/southlondonscientific/aeolus/tree/main/notebooks/08_trend_analysis.ipynb) | Multi-year Theil-Sen trend detection | None |

## Getting Help

- [GitHub Issues](https://github.com/southlondonscientific/aeolus/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/southlondonscientific/aeolus/discussions) - Questions and community support

## License

Aeolus is released under the [GPL-3.0 License](https://www.gnu.org/licenses/gpl-3.0.en.html).
