# Step 7: Clean Public API - Simple Explanation

## What We Built

A simple, user-friendly interface that makes Aeolus easy to use. No need to understand the internal architecture - just import and go.

## The Problem

**Before:** Users needed to understand internal structure (registries, sources, specs)

```python
# Too complicated - users need to know about registries
import aeolus.sources
from aeolus.registry import get_source

aurn = get_source("AURN")
data = aurn["fetch_data"](sites, start_date, end_date)
```

**After:** Simple, clean API that "just works"

```python
# Easy - looks like any other Python library
import aeolus

data = aeolus.download("AURN", sites=["MY1"], start_date=..., end_date=...)
```

## What Changed

### Created `api.py` with Simple Functions

**Main functions:**
- `list_sources()` - See what's available
- `get_metadata(source)` - Get site information
- `download(sources, sites, start_date, end_date)` - Download data
- `get_source_info(source)` - Check if API key needed
- `download_all_sites()` - Download entire networks

**Bonus aliases** (for users who prefer different names):
- `get_sites()` = `get_metadata()`
- `fetch()` = `download()`

### Updated `__init__.py`

Now when you `import aeolus`, you get clean functions automatically:

```python
import aeolus

aeolus.list_sources()  # Works!
aeolus.download(...)   # Works!
```

**Backwards compatibility maintained:** Old functions still work so existing code won't break.

## Real-World Usage

### Example 1: Simple Download

```python
import aeolus
from datetime import datetime

# Just three lines to download data
data = aeolus.download(
    sources="AURN",
    sites=["MY1"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

print(f"Got {len(data)} measurements")
```

### Example 2: Multiple Sources

```python
# Download from multiple networks at once
data = aeolus.download(
    sources=["AURN", "SAQN", "WAQN"],
    sites=["MY1", "GLA4", "CDF"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Automatically combined into one DataFrame
print(data['source_network'].unique())  # ['AURN', 'SAQN', 'WAQN']
```

### Example 3: Explore What's Available

```python
# What networks can I use?
sources = aeolus.list_sources()
print(sources)  # ['AQE', 'AURN', 'LMAM', 'LOCAL', 'NI', 'SAQD', 'SAQN', 'WAQN']

# What sites does AURN have?
sites = aeolus.get_metadata("AURN")
print(f"AURN has {len(sites)} monitoring sites")
print(sites[['site_code', 'site_name', 'location_type']].head())
```

## Key Features

### 1. Combine Multiple Sources

```python
# Returns one big DataFrame with all data
data = aeolus.download(
    sources=["AURN", "SAQN"],
    sites=["MY1", "GLA4"],
    start_date=...,
    end_date=...,
    combine=True  # Default
)
```

### 2. Keep Sources Separate

```python
# Returns a dictionary: {"AURN": df1, "SAQN": df2}
data_by_source = aeolus.download(
    sources=["AURN", "SAQN"],
    sites=["MY1", "GLA4"],
    start_date=...,
    end_date=...,
    combine=False
)

# Process each source separately
for source, df in data_by_source.items():
    print(f"{source}: {len(df)} records")
```

### 3. Graceful Error Handling

If one source fails, others still work:

```python
# If SAQN fails, you still get AURN data
data = aeolus.download(
    sources=["AURN", "SAQN"],
    sites=["MY1"],
    start_date=...,
    end_date=...
)
# Warning logged but download continues
```

## Updated README

Added comprehensive examples showing:
- Quick start guide
- Multiple download patterns
- How to filter and transform data
- Working with metadata
- Database storage

## Key Takeaway

**Aeolus now feels like a finished library, not internal plumbing.**

Before you needed to understand: registries, sources, specs, factory functions, closures...

Now you just need to know: `aeolus.download()`

The complexity is hidden. The power is preserved. The API is clean.