# Aeolus

**Download and standardise air quality data from monitoring networks worldwide.**

Aeolus provides a unified Python interface for accessing air quality data from multiple sources, automatically normalising everything into a consistent pandas DataFrame format.

## Features

- **Unified API** - One interface for all data sources
- **Automatic normalisation** - Consistent data format regardless of source
- **Multiple networks** - UK regulatory networks, global platforms, low-cost sensors
- **Built-in metrics** - Calculate AQI, exceedances, data capture rates
- **Visualization tools** - Ready-made plots for air quality analysis

## Supported Data Sources

| Source | Coverage | API Key Required |
|--------|----------|------------------|
| AURN | UK regulatory network | No |
| SAQN | Scottish network | No |
| WAQN | Welsh network | No |
| NI | Northern Ireland network | No |
| OpenAQ | Global (100+ countries) | Yes |
| Breathe London | London low-cost sensors | Yes |
| AirQo | African cities | Yes |
| EPA AirNow | US, Canada, Mexico (2,500+ stations) | Yes |
| PurpleAir | Global (30,000+ sensors) | Yes |
| Sensor.Community | Global citizen science (35,000+ sensors) | No |

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

## Getting Help

- [GitHub Issues](https://github.com/southlondonscientific/aeolus/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/southlondonscientific/aeolus/discussions) - Questions and community support

## License

Aeolus is released under the [GPL-3.0 License](https://www.gnu.org/licenses/gpl-3.0.en.html).
