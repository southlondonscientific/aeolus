# Test Fixtures

This directory contains sample data files used for testing Aeolus functionality.

## Purpose

These fixtures allow us to:
- Test data parsing without network calls
- Ensure consistent test results
- Test against known-good data structures
- Speed up test execution

## Contents

### AURN Fixtures

- **`aurn/MY1_2023.RData`**: Full year of hourly data from Marylebone Road monitoring station (London)
  - Site: MY1 (Marylebone Road)
  - Period: January 1 - December 31, 2023
  - Size: ~1.7 MB
  - Parameters: NO2, NOX, PM10, PM2.5, O3, etc.
  - Use for: Testing RData parsing, normalization, date filtering

### OpenAQ Fixtures

*(To be added)*

Sample JSON responses from OpenAQ API v3:
- Sensor list responses
- Hourly measurement responses
- Multi-page pagination examples
- Error responses (404, 429, etc.)

## Downloading Fixtures

If fixtures are missing, run:

```bash
cd tests/fixtures
uv run python download_test_data.py
```

This will download the MY1_2023.RData file (~1.7 MB).

## Creating New Fixtures

### For RData Files

```python
import requests

url = "https://uk-air.defra.gov.uk/openair/R_data/SITECODE_YEAR.RData"
response = requests.get(url)
with open("tests/fixtures/aurn/SITECODE_YEAR.RData", "wb") as f:
    f.write(response.content)
```

### For OpenAQ JSON Responses

Capture real API responses and sanitize:

```python
import requests
import json

# Make a real API call
response = requests.get(
    "https://api.openaq.org/v3/locations/2708/sensors",
    headers={"X-API-Key": "your_key"}
)

# Save the response
with open("tests/fixtures/openaq/sensors_response.json", "w") as f:
    json.dump(response.json(), f, indent=2)
```

**Important**: Remove or redact any sensitive information (API keys, personal data) before committing!

## Git Handling

- ✅ Small fixtures (<5 MB): Commit to git
- ⚠️ Large fixtures (>5 MB): Use Git LFS or download on-demand
- ❌ API keys or secrets: NEVER commit

Current fixtures are tracked in git since they're reasonably sized.

## Usage in Tests

### Using RData Fixtures

```python
from pathlib import Path
import rdata
import pandas as pd

def test_aurn_parsing():
    fixture_path = Path(__file__).parent / "fixtures/aurn/MY1_2023.RData"
    
    # Parse the RData file
    parsed = rdata.parser.parse_file(fixture_path)
    converted = rdata.conversion.convert(parsed)
    df = pd.DataFrame(converted[next(iter(converted))])
    
    # Test assertions
    assert not df.empty
    assert "date" in df.columns
    # ... etc
```

### Using JSON Fixtures

```python
import json
from pathlib import Path

def test_openaq_sensor_parsing():
    fixture_path = Path(__file__).parent / "fixtures/openaq/sensors_response.json"
    
    with open(fixture_path) as f:
        response_data = json.load(f)
    
    # Test assertions
    assert "results" in response_data
    # ... etc
```

## Maintenance

- Review fixtures annually to ensure they represent current API structures
- Update if API formats change
- Keep fixtures small and focused
- Document any special characteristics or edge cases captured

## License

Test fixtures are provided for testing purposes only. Data sources:
- AURN data: © Crown copyright, licensed under the Open Government Licence v3.0
- OpenAQ data: Licensed under CC BY 4.0

See main project LICENSE for details.