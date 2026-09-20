# Aeolus: download UK and standardise air quality data
# Copyright (C) 2025 Ruaraidh Dobson, South London Scientific

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Local file cache for downloaded air quality data.

Caches data as Parquet files, keyed by source, site, and date range.
This avoids redundant API calls when re-running notebooks or analyses.

Cache location defaults to ``~/.cache/aeolus/`` and can be overridden
by setting the ``AEOLUS_CACHE_DIR`` environment variable.

Complete results for an explicit date range never expire. Two kinds of entry
are *volatile* and are re-fetched once older than ``AEOLUS_CACHE_VOLATILE_TTL_S``
seconds (default 3600): rolling ``last=`` windows, which are keyed on the
shorthand so a re-run hits the cache, and results missing a requested site,
which may reflect a transient failure. A ``last=`` window no longer than the
TTL is always fetched live.

Usage::

    import aeolus
    from aeolus.cache import enable_cache, disable_cache, clear_cache

    # Enable caching (all subsequent downloads are cached)
    enable_cache()

    # Downloads hit the API on first call, then use cache
    data = aeolus.download("AURN", ["MY1"], start, end)
    data = aeolus.download("AURN", ["MY1"], start, end)  # instant

    # Clear everything
    clear_cache()

    # Disable caching
    disable_cache()
"""

import hashlib
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Default cache directory
_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "aeolus"

# Volatile entries — rolling (``last=``) windows, and results missing a
# requested site — are served from cache for at most this many seconds before
# being re-fetched. One hour matches the reporting resolution of the
# regulatory networks. Complete results for explicit date ranges never expire.
try:
    _VOLATILE_TTL_S = int(os.environ.get("AEOLUS_CACHE_VOLATILE_TTL_S", "3600"))
except ValueError:
    # A malformed setting must not break ``import aeolus``
    _VOLATILE_TTL_S = 3600

# Entries live under a versioned subdirectory. Bump this whenever a release
# changes what a cached frame *means* (values, units, labels, schema): files
# written by earlier versions then stop being served, because the key alone
# cannot tell a corrected result from a wrong one. v2 = the 0.5.0 correctness
# scrub (LAQN ppb -> ug/m3, EEA labels, CO units, sentinel/NaN drops).
_CACHE_VERSION = "v2"

# Module-level state
_cache_enabled = False
_cache_dir: Path | None = None


def _get_cache_dir() -> Path:
    """Get the cache directory, creating it if needed."""
    global _cache_dir
    if _cache_dir is None:
        _cache_dir = Path(os.environ.get("AEOLUS_CACHE_DIR", _DEFAULT_CACHE_DIR))
    _cache_dir.mkdir(parents=True, exist_ok=True)
    return _cache_dir


def _entries_dir() -> Path:
    """Directory holding entries written by this cache version."""
    return _get_cache_dir() / _CACHE_VERSION


def _volatile_ttl_s(start_date: datetime, end_date: datetime, last: str | None) -> float:
    """TTL for a volatile entry. A rolling window's TTL scales with its length,
    so ``last="2h"`` is never served mostly stale; long windows cap at the default."""
    if last is None:
        return _VOLATILE_TTL_S
    window_s = abs((end_date - start_date).total_seconds())
    return min(_VOLATILE_TTL_S, window_s / 10)


def _as_utc_timestamp(dt: datetime) -> float:
    """POSIX timestamp of *dt*; naive datetimes are UTC by library convention."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _key_instant(dt: datetime) -> str:
    """Normalise a datetime for keying: the same instant always keys the same.

    Naive datetimes are UTC by library convention, so aware datetimes are
    converted to naive UTC (which also keeps pre-0.4.6 naive keys valid).
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat()


def _cache_key(
    source: str,
    site: str,
    start_date: datetime,
    end_date: datetime,
    last: str | None = None,
) -> str:
    """
    Generate a deterministic cache key for a download request.

    Rolling windows (``last=``) are keyed on the shorthand itself, not on
    the resolved timestamps, which differ on every call.

    Returns a hex string identifying this specific request.
    """
    if last is not None:
        window = f"last={''.join(last.split()).lower()}"
    else:
        window = f"{_key_instant(start_date)}|{_key_instant(end_date)}"
    parts = f"{source.upper()}|{site}|{window}"
    return hashlib.sha256(parts.encode()).hexdigest()[:16]


def _cache_path(
    source: str,
    site: str,
    start_date: datetime,
    end_date: datetime,
    last: str | None = None,
) -> Path:
    """Get the filesystem path for a cached dataset.

    Keeps the filename human-readable for single sites, but truncates
    and hashes multi-site keys to stay within filesystem limits (macOS
    enforces a 255-byte filename limit).
    """
    import re

    cache_dir = _entries_dir()
    key = _cache_key(source, site, start_date, end_date, last)
    safe_site = re.sub(r"[^\w\-]", "_", site)

    # Truncate long site strings (e.g. 321 AURN sites joined with commas).
    # Keep the first few site codes for readability, then rely on the hash.
    max_site_len = 80
    if len(safe_site) > max_site_len:
        safe_site = safe_site[:max_site_len].rstrip("_") + "_etc"

    return cache_dir / source.upper() / f"{safe_site}_{key}.parquet"


def get(
    source: str,
    site: str,
    start_date: datetime,
    end_date: datetime,
    last: str | None = None,
    sites: list[str] | None = None,
) -> pd.DataFrame | None:
    """
    Retrieve cached data if available.

    Rolling (``last=``) entries expire after the volatile TTL. When *sites* is
    given, an entry missing any of them expires the same way, so a transient
    per-site failure is retried rather than latched.

    Args:
        source: Data source name (e.g., "AURN")
        site: Site code (e.g., "MY1")
        start_date: Start of date range
        end_date: End of date range

    Returns:
        Cached DataFrame, or None if not in cache.
    """
    if not _cache_enabled:
        return None

    path = _cache_path(source, site, start_date, end_date, last)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None

    expired = time.time() - mtime > _volatile_ttl_s(start_date, end_date, last)
    # A range that ended after it was fetched held only what had been published
    # by then, so it is as volatile as a rolling window.
    open_ended = _as_utc_timestamp(end_date) > mtime
    if expired and (last is not None or open_ended):
        logger.debug("Cache expired: %s/%s (rolling or open-ended window)", source, site)
        return None

    try:
        data = pd.read_parquet(path)
    except Exception as e:  # noqa: BLE001 - a half-written or corrupt file is a miss
        logger.debug("Cache entry unreadable, refetching: %s/%s (%s)", source, site, type(e).__name__)
        return None
    if expired and sites is not None and not _covers_all_sites(data, sites):
        logger.debug("Cache expired: %s/%s (incomplete result)", source, site)
        return None

    logger.debug("Cache hit: %s/%s", source, site)
    return data


def put(
    source: str,
    site: str,
    start_date: datetime,
    end_date: datetime,
    data: pd.DataFrame,
    last: str | None = None,
) -> None:
    """
    Store data in the cache.

    Args:
        source: Data source name
        site: Site code
        start_date: Start of date range
        end_date: End of date range
        data: DataFrame to cache
    """
    if not _cache_enabled:
        return

    if data.empty:
        return

    path = _cache_path(source, site, start_date, end_date, last)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write beside the target and rename: volatile entries are rewritten every
    # TTL, and a concurrent reader must never see a half-written file.
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        data.to_parquet(tmp, index=False)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    logger.debug("Cached: %s/%s (%d rows)", source, site, len(data))


def enable_cache(cache_dir: str | Path | None = None) -> None:
    """
    Enable local file caching for downloads.

    Subsequent calls to ``aeolus.download()`` will check the cache before
    hitting the network. Cached data is stored as Parquet files.

    Args:
        cache_dir: Override the cache directory. Defaults to
                   ``~/.cache/aeolus/`` or ``AEOLUS_CACHE_DIR`` env var.

    Example::

        >>> import aeolus
        >>> from aeolus.cache import enable_cache
        >>> enable_cache()
        >>> data = aeolus.download("AURN", ["MY1"], start, end)  # fetches
        >>> data = aeolus.download("AURN", ["MY1"], start, end)  # cached
    """
    global _cache_enabled, _cache_dir
    _cache_enabled = True
    if cache_dir is not None:
        _cache_dir = Path(cache_dir)
    logger.info("Cache enabled: %s", _get_cache_dir())


def disable_cache() -> None:
    """
    Disable local file caching.

    Downloads will always go to the network. Existing cache files
    are preserved (use ``clear_cache()`` to remove them).
    """
    global _cache_enabled
    _cache_enabled = False
    logger.info("Cache disabled")


def clear_cache(source: str | None = None) -> int:
    """
    Remove cached files.

    Args:
        source: If given, only clear cache for this source.
                Otherwise clears the entire cache.

    Returns:
        Number of files removed.

    Example::

        >>> from aeolus.cache import clear_cache
        >>> clear_cache("AURN")       # clear AURN cache only
        >>> clear_cache()             # clear everything
    """
    cache_dir = _get_cache_dir()
    count = 0

    if source:
        # Current entries, plus any written by an earlier cache version
        for target in (_entries_dir() / source.upper(), cache_dir / source.upper()):
            if target.exists():
                for f in target.glob("*.parquet"):
                    f.unlink(missing_ok=True)
                    count += 1
                # Remove empty directory
                if not any(target.iterdir()):
                    target.rmdir()
    else:
        for f in cache_dir.rglob("*.parquet"):
            f.unlink(missing_ok=True)
            count += 1
        # Remove empty subdirectories, deepest first
        for d in sorted((p for p in cache_dir.rglob("*") if p.is_dir()), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()

    logger.info("Cleared %d cached files", count)
    return count


def fetch_with_cache(
    source: str,
    sites: list[str],
    start_date: datetime,
    end_date: datetime,
    fetcher,
    last: str | None = None,
) -> pd.DataFrame:
    """Fetch via *fetcher*, transparently caching the result.

    The single entry point used by every download path so that direct
    submodule calls (``aeolus.networks.download``, ``aeolus.portals.download``)
    benefit from the same cache as the top-level ``aeolus.download``.

    Args:
        source: Data source name (e.g. ``"AURN"``).
        sites: Site codes — order does not affect the cache key.
        start_date: Start of date range.
        end_date: End of date range.
        fetcher: Callable ``(sites, start_date, end_date) -> DataFrame``
            invoked on a cache miss.

    Returns:
        The cached or freshly-fetched DataFrame.
    """
    if not _cache_enabled:
        return fetcher(sites, start_date, end_date)

    # A rolling window of an hour or less is a request for live data.
    if last is not None and end_date - start_date <= timedelta(hours=1):
        return fetcher(sites, start_date, end_date)

    site_key = ",".join(sorted(sites))
    cached = get(source, site_key, start_date, end_date, last, sites)
    if cached is not None:
        return cached

    data = fetcher(sites, start_date, end_date)
    put(source, site_key, start_date, end_date, data, last)
    return data


def _covers_all_sites(data: pd.DataFrame, sites: list[str]) -> bool:
    """Whether *data* has at least one row for every requested site.

    Fetchers swallow per-site errors and return whatever succeeded, so a
    missing site may be a transient failure — or a site with genuinely no
    data in the range. The two are indistinguishable here, so an incomplete
    result is cached but treated as volatile rather than authoritative.
    """
    if data.empty or "site_code" not in data.columns:
        return False
    returned = {str(s).upper() for s in data["site_code"].dropna().unique()}
    return all(str(s).upper() in returned for s in sites)


def cache_info() -> dict:
    """
    Return information about the current cache state.

    Returns:
        dict with keys: enabled, directory, sources, total_files, total_size_mb

    Example::

        >>> from aeolus.cache import cache_info
        >>> info = cache_info()
        >>> print(f"Cache: {info['total_files']} files, {info['total_size_mb']:.1f} MB")
    """
    cache_dir = _get_cache_dir()
    # A file may be removed (clear_cache, another process) between listing
    # and stat; skip it rather than crash a read-only introspection call.
    sizes = {}
    for f in cache_dir.rglob("*.parquet"):
        try:
            sizes[f] = f.stat().st_size
        except OSError:
            continue
    total_size = sum(sizes.values())
    entries = _entries_dir()
    current = {f: size for f, size in sizes.items() if entries in f.parents}
    sources = sorted({f.parent.name for f in current})

    return {
        "enabled": _cache_enabled,
        "directory": str(cache_dir),
        "sources": sources,
        "total_files": len(current),
        "total_size_mb": sum(current.values()) / (1024 * 1024),
        # Written by an earlier cache version: never served; clear_cache() removes them
        "legacy_files": len(sizes) - len(current),
    }


def is_enabled() -> bool:
    """Return whether caching is currently enabled."""
    return _cache_enabled
