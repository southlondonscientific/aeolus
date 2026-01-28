# Installation

## Requirements

- Python 3.11 or higher
- pip (Python package installer)

## Install from PyPI

```bash
pip install aeolus-aq
```

## Install from Source

For the latest development version:

```bash
git clone https://github.com/southlondonscientific/aeolus.git
cd aeolus
pip install -e .
```

## Development Installation

If you want to contribute to Aeolus, install with development dependencies:

```bash
git clone https://github.com/southlondonscientific/aeolus.git
cd aeolus
pip install -e ".[dev]"
```

This includes pytest and other testing tools.

## Verify Installation

```python
import aeolus
print(aeolus.__version__)
```

## Next Steps

- [Quick Start](quickstart.md) - Download your first dataset
- [Configuration](configuration.md) - Set up API keys for additional data sources
