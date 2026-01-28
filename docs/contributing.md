# Contributing

Thank you for your interest in contributing to Aeolus! This guide will help you get started.

## Development Setup

1. **Clone the repository**

```bash
git clone https://github.com/southlondonscientific/aeolus.git
cd aeolus
```

2. **Create a virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install development dependencies**

```bash
pip install -e ".[dev]"
```

4. **Run tests**

```bash
pytest
```

## Project Structure

```
aeolus/
├── src/aeolus/
│   ├── __init__.py          # Public API
│   ├── api.py               # Main download() function
│   ├── downloader.py        # Multi-source orchestration
│   ├── registry.py          # Source registration
│   ├── transforms.py        # Data normalisation
│   ├── sources/             # Data source implementations
│   ├── metrics/             # Air quality calculations
│   └── viz/                 # Visualization tools
├── tests/                   # Test files
├── docs/                    # Documentation (this site)
└── pyproject.toml           # Project configuration
```

## Adding a New Data Source

1. **Create the source module**

```bash
touch src/aeolus/sources/newsource.py
```

2. **Implement required functions**

```python
# src/aeolus/sources/newsource.py

def fetch_newsource_metadata():
    """Fetch site metadata from the source."""
    # Return a DataFrame with site_code, site_name, latitude, longitude
    pass

def fetch_newsource_data(sites, start_date, end_date):
    """Fetch measurement data from the source."""
    # Return raw data from the API
    pass

# Create a normaliser
from aeolus.transforms import compose, rename_columns, ...

normalise_newsource = compose(
    rename_columns({...}),
    # ... other transformations
)
```

3. **Register the source**

```python
from aeolus.registry import register_source

register_source(
    name="NEWSOURCE",
    fetch_metadata=fetch_newsource_metadata,
    fetch_data=fetch_newsource_data,
    normalise=normalise_newsource,
    source_type="network",  # or "portal"
)
```

4. **Import in __init__.py**

```python
# src/aeolus/sources/__init__.py
from . import newsource
```

5. **Add tests**

```bash
touch tests/test_newsource.py
```

## Testing

We use pytest for testing. Tests should mock HTTP calls using the `responses` library.

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=aeolus --cov-report=html

# Run specific test file
pytest tests/test_newsource.py -v

# Skip slow/integration tests
pytest -m "not slow"
pytest -m "not integration"
```

## Code Style

- Follow PEP 8
- Use type hints where practical
- Write docstrings for public functions (Google style)
- Keep functions focused and testable

## Documentation

Documentation is built with MkDocs. To preview locally:

```bash
pip install mkdocs-material mkdocstrings[python]
mkdocs serve
```

Then open http://localhost:8000 in your browser.

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Commit with a clear message
6. Push to your fork
7. Open a Pull Request

## Reporting Issues

Please use [GitHub Issues](https://github.com/southlondonscientific/aeolus/issues) to report bugs or request features. Include:

- Python version
- Aeolus version (`aeolus.__version__`)
- Minimal code to reproduce the issue
- Full error traceback

## Questions?

Open a [GitHub Discussion](https://github.com/southlondonscientific/aeolus/discussions) for questions or ideas.
