# Installation

## Requirements

- Python 3.11 or higher
- pip (Python package installer)

## Install from PyPI

```bash
pip install --pre aeolus-aq
```

These docs describe 0.5, which is published as a pre-release (`0.5.0a1`) for consumers to migrate against; without `--pre`, pip installs the last 0.4 release. See [Migrating to 0.5](../guide/migrating-to-0.5.md).

## Optional Extras

Some data sources and features require optional dependencies that are not installed by default:

| Extra | Install command | Provides |
|-------|----------------|----------|
| `openaq` | `pip install aeolus-aq[openaq]` | OpenAQ portal access (wraps the official `openaq` SDK) |
| `purpleair` | `pip install aeolus-aq[purpleair]` | PurpleAir portal access |
| `stats` | `pip install aeolus-aq[stats]` | `statsmodels` for deseasonalisation in `trend()` |
| `progress` | `pip install aeolus-aq[progress]` | `tqdm` progress bars for bulk downloads |
| `all` | `pip install aeolus-aq[all]` | All of the above (OpenAQ + PurpleAir + stats) |

Conda users: `conda install -c conda-forge aeolus_aq` installs the core package; then `pip install openaq purpleair-api statsmodels tqdm` for the optional sources and features. 0.5 alphas are pip-only; conda-forge carries the last 0.4 release until 0.5.0 final.

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
