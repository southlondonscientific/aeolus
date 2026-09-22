# Configuration

Some data sources require API keys. This guide explains how to set them up.

## Environment Variables

Aeolus reads API keys from environment variables. Export them in your shell:

```bash
export OPENAQ_API_KEY=your_openaq_key_here
export PURPLEAIR_API_KEY=your_purpleair_key_here
export BL_API_KEY=your_breathe_london_key_here
export AIRQO_API_KEY=your_airqo_token_here
export AIRNOW_API_KEY=your_airnow_key_here
```

### Using a .env file (optional)

If you prefer using a `.env` file, you can use `python-dotenv` to load it:

```bash
pip install python-dotenv
```

Create a `.env` file in your project root:

```bash
# .env
OPENAQ_API_KEY=your_openaq_key_here
PURPLEAIR_API_KEY=your_purpleair_key_here
BL_API_KEY=your_breathe_london_key_here
AIRQO_API_KEY=your_airqo_token_here
AIRNOW_API_KEY=your_airnow_key_here
```

Then load it before using Aeolus:

```python
from dotenv import load_dotenv
load_dotenv()

import aeolus
# Now API keys are available
```

## Aeolus settings

All optional. Read from the environment when first needed.

| Variable | Default | Effect |
|---|---|---|
| `AEOLUS_LEGACY_COLUMNS` | `1` | `0` drops the deprecated `source_network` and `ratification` mirrors — use it to prove your code has migrated to 0.5 |
| `AEOLUS_CACHE_DIR` | `~/.cache/aeolus` | Where downloads are cached (a versioned sub-directory per cache format, currently `v4`) |
| `AEOLUS_CACHE_VOLATILE_TTL_S` | `3600` | How long a download whose window touches "now" (e.g. `last="7d"`) is served from cache before it is refreshed |
| `AEOLUS_METADATA_TTL_S` | `86400` | How long AURN-family site metadata (the `ratified_to` join) is memoised |
| `AEOLUS_RDATA_BREAKER_FAILURES` | `3` | Consecutive failures after which an openair RData host fails fast |
| `AEOLUS_RDATA_BREAKER_COOLDOWN_S` | `60` | How long that host fails fast before Aeolus probes it again |
| `AEOLUS_SOS_BREAKER_FAILURES` | `5` | The same, for the UK-AIR SOS near-real-time endpoint |
| `AEOLUS_SOS_BREAKER_COOLDOWN_S` | `60` | Cool-down for the SOS breaker |

`AEOLUS_LEGACY_COLUMNS` is also settable in code: `aeolus.options.legacy_columns = False`.

## Obtaining API Keys

### OpenAQ

1. Go to [OpenAQ Explorer](https://explore.openaq.org/)
2. Create a free account
3. Navigate to your account settings to find your API key

### PurpleAir

1. Visit [PurpleAir](https://www.purpleair.com/)
2. Create an account and go to your [API Keys page](https://develop.purpleair.com/keys)
3. Generate a read-only API key

### Breathe London

1. Visit the [Breathe London API documentation](https://www.breathelondon.org/developers)
2. Request API access through their developer portal

### AirQo

1. Visit [AirQo](https://airqo.net/)
2. Contact their team to request API access

### AirNow

1. Visit [AirNow API](https://docs.airnowapi.org/)
2. Register for a free API key
3. Keys are typically issued within a few minutes

## Sources Without API Keys

These sources work without any configuration:

- **AURN** - UK Automatic Urban and Rural Network
- **SAQN** - Scottish Air Quality Network (also known as SAQD)
- **WAQN** - Welsh Air Quality Network
- **NI** - Northern Ireland Air Quality Network
- **AQE** - Air Quality England
- **LAQN** - London Air Quality Network
- **SENSOR_COMMUNITY** - Global citizen science network

## Verifying Configuration

Check that your API keys are configured correctly:

```python
import aeolus

# List all sources and their status
sources = aeolus.list_sources()
for source in sources:
    info = aeolus.get_source_info(source)
    print(f"{source}: {info}")
```

## Next Steps

- [Data Sources](../guide/sources.md) - Detailed information on each source
- [Downloading Data](../guide/downloading.md) - Start downloading data
