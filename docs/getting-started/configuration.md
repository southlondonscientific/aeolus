# Configuration

Some data sources require API keys. This guide explains how to set them up.

## Environment Variables

Aeolus reads API keys from environment variables. Export them in your shell:

```bash
export OPENAQ_API_KEY=your_openaq_key_here
export BL_API_KEY=your_breathe_london_key_here
export AIRQO_API_TOKEN=your_airqo_token_here
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
BL_API_KEY=your_breathe_london_key_here
AIRQO_API_TOKEN=your_airqo_token_here
```

Then load it before using Aeolus:

```python
from dotenv import load_dotenv
load_dotenv()

import aeolus
# Now API keys are available
```

## Obtaining API Keys

### OpenAQ

1. Go to [OpenAQ Explorer](https://explore.openaq.org/)
2. Create a free account
3. Navigate to your account settings to find your API key

### Breathe London

1. Visit the [Breathe London API documentation](https://www.breathelondon.org/developers)
2. Request API access through their developer portal

### AirQo

1. Visit [AirQo](https://airqo.net/)
2. Contact their team to request API access

## Sources Without API Keys

These sources work without any configuration:

- **AURN** - UK Automatic Urban and Rural Network
- **SAQN** - Scottish Air Quality Network  
- **WAQN** - Welsh Air Quality Network
- **NI** - Northern Ireland Air Quality Network

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
