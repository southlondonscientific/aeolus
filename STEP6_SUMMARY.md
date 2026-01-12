# Step 6: Retry Logic - Simple Explanation

## What We Built

We added automatic retry logic to network requests so the system doesn't fail on temporary network problems.

## The Problem

When downloading air quality data from the internet:
- Networks can be flaky (temporary connection drops)
- Servers can be temporarily overloaded (500 errors)
- Requests can timeout

Before: One network hiccup = your download fails ❌

After: Temporary problems get automatically retried ✓

## The Solution

Created a "retry decorator" - a wrapper that automatically retries failed network requests.

### How It Works

1. **Try the request** (attempt 1)
2. **If it fails** → wait 1 second → try again (attempt 2)
3. **If it still fails** → wait 2 seconds → try again (attempt 3)
4. **If that fails** → give up and report error

The wait time doubles each attempt (exponential backoff) to give struggling servers time to recover.

### What Gets Retried

✓ Connection errors (can't reach server)
✓ Timeouts (server too slow to respond)
✓ 5xx server errors (server temporarily broken)

✗ 4xx client errors (bad request - your fault, retrying won't help)

## What Changed

### Added New File: `decorators.py`

Contains reusable decorators:
- `@with_retry()` - main retry logic
- `@retry_on_network_error` - pre-configured for standard use
- `@with_logging()` - add logging to functions
- `@with_timeout()` - ensure requests have timeouts

### Updated: `regulatory.py`

Added one line to the `fetch_rdata()` function:

```python
@retry_on_network_error  # ← This line makes it automatically retry
def fetch_rdata(url: str) -> pd.DataFrame | None:
    # ... rest of function
```

That's it! Now all data fetches have automatic retry.

## Real-World Impact

**Before:**
```
Network hiccup → Download fails → You have to manually retry → Annoying
```

**After:**
```
Network hiccup → Automatic retry (1 second) → Success → You didn't even notice
```

## Example

```python
from aeolus.decorators import with_retry

# Make any function automatically retry on network errors
@with_retry(max_attempts=3, min_wait=1.0, max_wait=10.0)
def download_data(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

# Now it will retry up to 3 times if network fails
data = download_data("https://api.example.com/data")
```

## Key Takeaway

**One decorator line = automatic resilience to network problems**

Your data downloads are now much more reliable without any extra code in the main logic.