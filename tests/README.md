# Aeolus Test Suite

Comprehensive test suite for the Aeolus air quality data library.

## Quick Start

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=aeolus --cov-report=html

# Run specific test file
uv run pytest tests/test_transforms.py -v

# Run specific test
uv run pytest tests/test_transforms.py::test_pipe_applies_functions_in_order -v
```

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures and utilities
├── test_transforms.py       # Tests for pure transformation functions
├── test_registry.py         # Tests for source registration
├── fixtures/                # Test data files
│   ├── README.md           # Fixture documentation
│   ├── aurn/               # AURN test data
│   │   └── MY1_2023.RData # Real data from Marylebone Road
│   └── openaq/             # OpenAQ mock responses (future)
└── README.md               # This file
```

## Current Status

- **Total Tests**: 63
- **Coverage**: 35% overall
  - `transforms.py`: 74%
  - `registry.py`: 60%
  - `types.py`: 100%
- **Status**: ✅ All passing

See [PHASE1_SUMMARY.md](PHASE1_SUMMARY.md) for detailed results.

## Test Categories

### Unit Tests (Fast)
Pure functions with no external dependencies.

```bash
# Run only unit tests
uv run pytest tests/test_transforms.py tests/test_registry.py
```

### Integration Tests (Medium - Future)
Test components working together with mocked network calls.

```bash
# Run integration tests (when available)
uv run pytest -m integration
```

### End-to-End Tests (Slow - Future)
Test against real APIs (requires API keys).

```bash
# Run only live tests
uv run pytest -m live

# Skip slow tests
uv run pytest -m "not slow"
```

## Writing Tests

### Using Fixtures

Common fixtures are available from `conftest.py`:

```python
def test_with_sample_data(sample_wide_df):
    """Use pre-configured sample DataFrame."""
    assert len(sample_wide_df) == 5
    assert "NO2" in sample_wide_df.columns

def test_with_real_data(my1_raw_data):
    """Use real AURN data from fixture."""
    assert len(my1_raw_data) == 8760  # Full year
    assert my1_raw_data["code"].iloc[0] == "MY1"
```

### Available Fixtures

- `sample_wide_df` - Sample data in wide format
- `sample_long_df` - Sample data in long format  
- `sample_df_with_nulls` - Sample with null values
- `empty_df` - Empty DataFrame with schema
- `my1_raw_data` - Real AURN data from MY1 2023
- `my1_january` - MY1 data filtered to January 2023
- `mock_openaq_sensor_response` - Mock OpenAQ sensors API response
- `mock_openaq_measurements_response` - Mock OpenAQ measurements response

### Test Naming Convention

- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

Examples:
```python
def test_pipe_applies_functions_in_order():
    """Test that pipe applies functions in correct order."""
    # Arrange
    df = pd.DataFrame({"a": [1, 2, 3]})
    
    # Act
    result = pipe(df, transform1, transform2)
    
    # Assert
    assert result["expected_column"].tolist() == [1, 2, 3]
```

## Running Tests with Options

### Coverage Reports

```bash
# Terminal coverage report
uv run pytest --cov=aeolus --cov-report=term-missing

# HTML coverage report (opens in browser)
uv run pytest --cov=aeolus --cov-report=html
open htmlcov/index.html
```

### Verbose Output

```bash
# Show each test name
uv run pytest -v

# Show even more detail
uv run pytest -vv

# Show print statements
uv run pytest -s
```

### Running Specific Tests

```bash
# By file
uv run pytest tests/test_transforms.py

# By test name
uv run pytest tests/test_transforms.py::test_pipe_applies_functions_in_order

# By pattern
uv run pytest -k "pipe"  # Runs all tests with "pipe" in name

# By marker
uv run pytest -m integration
```

### Debugging Failed Tests

```bash
# Stop at first failure
uv run pytest -x

# Show local variables on failure
uv run pytest -l

# Drop into debugger on failure
uv run pytest --pdb

# Show full diff for assertion failures
uv run pytest -vv
```

## Test Fixtures

Test fixtures are located in `tests/fixtures/`. See [fixtures/README.md](fixtures/README.md) for details.

### Using Real Data

```python
from pathlib import Path
import rdata
import pandas as pd

def test_with_aurn_fixture():
    """Example of loading AURN test fixture."""
    fixture_path = Path(__file__).parent / "fixtures/aurn/MY1_2023.RData"
    
    parsed = rdata.parser.parse_file(fixture_path)
    converted = rdata.conversion.convert(parsed)
    df = pd.DataFrame(converted[next(iter(converted))])
    
    # Your test assertions here
    assert not df.empty
```

## Continuous Integration

(Future) Tests will run automatically on:
- Every commit (unit tests)
- Pull requests (unit + integration tests)
- Nightly (all tests including live API tests)

## Contributing

When adding new features:

1. **Write tests first** (TDD approach)
2. **Use existing fixtures** where possible
3. **Add new fixtures** to `fixtures/` if needed
4. **Mock external calls** (network, file system)
5. **Aim for 80%+ coverage** of new code
6. **Document complex tests** with clear docstrings

### Example Test Structure

```python
def test_new_feature():
    """
    Test that new feature works correctly.
    
    This test checks that:
    - Input is validated
    - Transformation is applied
    - Output has correct schema
    """
    # Arrange (setup)
    input_data = create_test_data()
    
    # Act (execute)
    result = new_feature(input_data)
    
    # Assert (verify)
    assert result is not None
    assert "expected_column" in result.columns
    assert len(result) > 0
```

## Troubleshooting

### Tests Won't Run

```bash
# Ensure dev dependencies are installed
uv pip install -e ".[dev]"

# Check pytest is available
uv run pytest --version
```

### Fixture Not Found

```bash
# Re-download test fixtures
cd tests/fixtures
uv run python download_test_data.py
```

### Import Errors

```bash
# Reinstall package in editable mode
uv pip install -e .
```

### Coverage Not Working

```bash
# Install pytest-cov
uv pip install pytest-cov

# Clear cache and rerun
rm -rf .pytest_cache
uv run pytest --cov=aeolus
```

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Test fixtures guide](fixtures/README.md)
- [Phase 1 results](PHASE1_SUMMARY.md)

## Questions?

For questions about testing:
- Check existing tests for examples
- See [PHASE1_SUMMARY.md](PHASE1_SUMMARY.md) for approach
- Contact: ruaraidh.dobson@gmail.com