# Overview

Aeolus is organised around two types of data sources:

## Networks vs Portals

**Networks** are discrete monitoring networks operated by specific organisations:

- AURN (UK government regulatory network)
- SAQN (Scottish network)
- Breathe London (London low-cost sensors)
- AirQo (African cities)

**Portals** are aggregation platforms that collect data from multiple sources:

- OpenAQ (global data from 100+ countries)

## The Unified API

While you can access networks and portals through their specific submodules, the simplest approach is the unified `download()` function:

```python
import aeolus
from datetime import datetime

start = datetime(2024, 1, 1)
end = datetime(2024, 1, 31)

# Single source
data = aeolus.download("AURN", ["MY1"], start, end)

# Multiple sources
data = aeolus.download(
    {"AURN": ["MY1"], "OpenAQ": ["2178"]},
    start_date=start,
    end_date=end
)
```

## Data Standardisation

All sources return data in a consistent format:

```
site_code | site_name | date_time | measurand | value | units | source_network | ratification
----------|-----------|-----------|-----------|-------|-------|----------------|-------------
MY1       | Marylebone| 2024-01-01| NO2       | 45.2  | ug/m3 | AURN           | Ratified
```

This makes it easy to combine and compare data from different sources.

## Time Conventions

Aeolus uses **left-closed intervals** for timestamps. A timestamp of `13:00` represents the period from `12:00` to `13:00`.

This matches the convention used by most regulatory networks.
