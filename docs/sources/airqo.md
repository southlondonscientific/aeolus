# AirQo

[AirQo](https://airqo.net/) operates a network of low-cost air quality sensors across African cities, with a focus on Uganda and expanding to other countries.

## Overview

- **Coverage**: Uganda, Kenya, and expanding across Africa
- **Sensors**: 200+ low-cost monitors
- **Data quality**: Indicative (machine learning calibrated)
- **API key**: Required
- **Operator**: Makerere University, Uganda

## Getting an API Key

1. Visit [AirQo Analytics](https://analytics.airqo.net/) and create an account
2. Go to Account Settings → API tab
3. Register a new CLIENT application to generate credentials
4. Create an access token
5. Set the environment variable:

```bash
export AIRQO_API_KEY=your_key_here
```

## Available Pollutants

- PM2.5 (primary focus)
- PM10

## Finding Sites

```python
import aeolus

# Get all AirQo sites
sites = aeolus.networks.get_metadata("AIRQO")

# View available sites
print(sites[['site_code', 'site_name', 'city', 'country']])
```

## Downloading Data

```python
import aeolus
from datetime import datetime

data = aeolus.download(
    sources="AIRQO",
    sites=["site_id_1", "site_id_2"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

## Data Quality

AirQo sensors use machine learning calibration:

- Calibrated against reference monitors where available
- Quality flags indicate confidence levels
- Best for understanding spatial and temporal patterns
- Data marked as `ratification='Indicative'`

## Coverage Areas

### Uganda
- Kampala (dense network)
- Other major cities

### Kenya
- Nairobi
- Expanding coverage

### Other Countries
- Network expanding across East and West Africa

## Example: Kampala Analysis

```python
import aeolus
from datetime import datetime

# Get Kampala sites
sites = aeolus.networks.get_metadata("AIRQO")
kampala_sites = sites[sites['city'] == 'Kampala']['site_code'].tolist()

# Download data
data = aeolus.download(
    sources="AIRQO",
    sites=kampala_sites[:10],  # First 10 sites
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Daily patterns
data['hour'] = data['date_time'].dt.hour
hourly_mean = data.groupby('hour')['value'].mean()
```

## Use Cases

AirQo data is particularly valuable for:

1. **Urban planning** - Understanding pollution hotspots
2. **Health studies** - Exposure assessment in African cities
3. **Policy development** - Evidence for air quality regulations
4. **Research** - Filling data gaps in under-monitored regions

## Resources

- [AirQo Website](https://airqo.net/)
- [AirQo Platform](https://platform.airqo.net/) - Interactive data explorer
- [Research Publications](https://airqo.net/research)
