# UK Networks

The UK operates several regional air quality monitoring networks that provide high-quality, reference-grade data.

## AURN (Automatic Urban and Rural Network)

The UK's primary national air quality monitoring network, operated by the Environment Agency.

### Coverage

- ~150 monitoring sites across England, Wales, Scotland, and Northern Ireland
- Mix of urban background, roadside, and rural sites
- Continuous monitoring since 1973

### Available Pollutants

- Nitrogen dioxide (NO2)
- Ozone (O3)
- Particulate matter (PM2.5, PM10)
- Sulphur dioxide (SO2)
- Carbon monoxide (CO)

### Usage

```python
import aeolus
from datetime import datetime

# Get all AURN sites
sites = aeolus.networks.get_metadata("AURN")
print(sites[['site_code', 'site_name', 'location_type', 'latitude', 'longitude']])

# Download data
data = aeolus.download(
    sources="AURN",
    sites=["MY1", "KC1"],  # Marylebone Road, Kensington
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

### Location Types

| Type | Description |
|------|-------------|
| Urban Background | Representative of city-wide exposure |
| Urban Traffic | Near major roads |
| Suburban | Residential areas |
| Rural | Away from direct sources |

## SAQN (Scottish Air Quality Network)

Additional monitoring sites operated by the Scottish Environment Protection Agency (SEPA).

> **Note**: `SAQD` is also accepted as an alias for `SAQN` for backwards compatibility.

```python
import aeolus
from datetime import datetime

# Get SAQN sites
sites = aeolus.networks.get_metadata("SAQN")

# Download
data = aeolus.download(
    sources="SAQN",
    sites=["ED3"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

## WAQN (Welsh Air Quality Network)

Welsh monitoring network operated by Natural Resources Wales.

```python
import aeolus
from datetime import datetime

data = aeolus.download(
    sources="WAQN",
    sites=["CARD"],  # Cardiff
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

## NI (Northern Ireland Network)

Northern Ireland network operated by the Department of Agriculture, Environment and Rural Affairs.

```python
import aeolus
from datetime import datetime

data = aeolus.download(
    sources="NI",
    sites=["BEL1"],  # Belfast
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

## AQE (Air Quality England)

Local authority monitoring sites across England, providing additional coverage beyond the national AURN network.

```python
import aeolus
from datetime import datetime

sites = aeolus.networks.get_metadata("AQE")
data = aeolus.download(
    sources="AQE",
    sites=sites["site_code"].head(3).tolist(),
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

## LOCAL (Local Authority Networks)

Additional local authority monitoring networks in England.

```python
import aeolus
from datetime import datetime

sites = aeolus.networks.get_metadata("LOCAL")
data = aeolus.download(
    sources="LOCAL",
    sites=sites["site_code"].head(3).tolist(),
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

## LMAM (London Air Quality Mesh)

Greater London monitoring network providing additional coverage across the capital.

```python
import aeolus
from datetime import datetime

sites = aeolus.networks.get_metadata("LMAM")
data = aeolus.download(
    sources="LMAM",
    sites=sites["site_code"].head(3).tolist(),
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```

## Data Quality

UK regulatory networks provide **ratified data**:

- Quality assured by trained personnel
- Calibrated reference-grade instruments
- Regular maintenance and audits
- Traceable to national standards

Data is typically ratified within 6-12 months of collection. Recent data may be marked as provisional.

## Combining UK Networks

Download from multiple UK networks simultaneously:

```python
data = aeolus.download(
    sources={
        "AURN": ["MY1", "KC1"],
        "SAQN": ["ED3", "GLA4"],
        "WAQN": ["CARD"],
    },
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)
```
