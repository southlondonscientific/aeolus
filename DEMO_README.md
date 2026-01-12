# Aeolus Demo Script

This guide explains how to use the comprehensive demonstration script (`demo.py`) to explore all features of Aeolus.

## Quick Start

### Run the Full Interactive Demo

```bash
python demo.py
```

This will run through all 12 demonstrations, pausing between each one. Press Enter to continue to the next demo, or Ctrl+C to exit.

## What the Demo Covers

### 1. List Available Data Sources
Shows all registered air quality networks and whether they require API keys.

### 2. Get Site Metadata
Demonstrates fetching site information including location types, coordinates, and breakdowns by site characteristics.

### 3. Simple Data Download
Downloads data from a single site (Marylebone Road) and shows the data structure.

### 4. Download from Multiple Sources
Shows how to download from multiple networks (AURN, SAQN, WAQN) simultaneously.

### 5. Keep Sources Separate
Demonstrates the `combine=False` option to get separate DataFrames for each source.

### 6. Filter and Transform Data
Shows how to use `pipe()` to filter data (e.g., NO2 only) and calculate statistics.

### 7. Reusable Transformation Pipelines
Demonstrates creating reusable pipelines with `compose()` for consistent data processing.

### 8. Smart Downloads Using Metadata
Shows how to filter metadata (e.g., urban background sites only) before downloading data.

### 9. Time Series Analysis
Analyzes PM2.5 concentrations over time, showing daily statistics and hourly patterns.

### 10. Multi-Site Comparison
Compares NO2 levels across different types of London sites (traffic, suburban, urban background).

### 11. Error Handling and Resilience
Demonstrates how Aeolus handles errors gracefully and automatically retries failed requests.

### 12. Advanced Transformations
Shows complex transformation patterns including calculated columns, rush hour filtering, and aggregations.

## Running Individual Demos

You can also run specific demonstrations by modifying the script or by copying the demo functions into your own code.

Each demo function is self-contained and can be run independently:

```python
from demo import demo_1_list_sources, demo_3_simple_download

# Run specific demos
demo_1_list_sources()
demo_3_simple_download()
```

## Quick Feature Test

For a fast overview without interactive prompts, run:

```bash
python << 'EOF'
import sys
sys.path.insert(0, 'src')

from datetime import datetime
import aeolus

# List sources
print("Sources:", aeolus.list_sources())

# Get metadata
sites = aeolus.get_metadata("AURN")
print(f"\nSites: {len(sites)}")

# Download data
data = aeolus.download(
    sources="AURN",
    sites=["MY1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 2)
)
print(f"Downloaded: {len(data)} measurements")
EOF
```

## What You'll See

### Detailed Output
Each demo provides:
- Clear section headers
- Step-by-step explanations
- Sample data displays
- Statistics and summaries
- Visual elements (bars, tables)
- Tips for best practices

### Real Data
The demo downloads real air quality data from UK monitoring networks. Each request may take a few seconds depending on network speed.

### Network Requirements
You'll need:
- Active internet connection
- Access to UK air quality network servers
- A few minutes to complete the full demo

## Sites Used in Demos

The demos use these representative sites:
- **MY1**: Marylebone Road, London (busy traffic site)
- **BX1**: Bexley, London (suburban)
- **LH2**: Hillingdon, London (urban background)
- **GLA4**: Glasgow (Scottish site)
- **CDF**: Cardiff (Welsh site)

## Expected Runtime

- Full interactive demo: ~5-10 minutes (with reading time)
- Quick test: ~30 seconds
- Individual demo: ~30-60 seconds each

## Tips

1. **Start with Demo 1-3** to understand the basics
2. **Demo 6-7** are crucial for learning data transformations
3. **Demo 10** shows practical analysis patterns
4. **Demo 11** explains error handling (important for production use)

## Troubleshooting

### Network Errors
If you see 404 errors for certain sites, this is normal - not all sites have data for all years. The system handles this gracefully.

### Slow Downloads
First-time downloads may be slower as the data is fetched. The retry logic ensures robust downloads.

### Warnings
The demo script automatically suppresses harmless warnings from the `rdata` library about POSIXct date conversion. These are cosmetic and don't affect functionality.

If you see pandas FutureWarnings about `observed=`, these have been fixed by adding `observed=True` to all groupby operations.

### Import Errors
Make sure you're running from the aeolus directory and that all dependencies are installed:
```bash
pip install -e .
```

## Learn More

After running the demos, check out:
- `README.md` - Full documentation
- `example.py` - Additional usage examples
- `STEP7_SUMMARY.md` - Public API overview
- `CHANGES.md` - What's new in this version

## Questions?

Contact: ruaraidh.dobson@gmail.com