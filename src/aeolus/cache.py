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
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Default cache directory
_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "aeolus"

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


def _cache_key(source: str, site: str, start_date: datetime, end_date: datetime) -> str:
    """
    Generate a deterministic cache key for a download request.

    Returns a hex string identifying this specific request.
    """
    parts = f"{source.upper()}|{site}|{start_date.isoformat()}|{end_date.isoformat()}"
    return hashlib.sha256(parts.encode()).hexdigest()[:16]


def _cache_path(source: str, site: str, start_date: datetime, end_date: datetime) -> Path:
    """Get the filesystem path for a cached dataset."""
    cache_dir = _get_cache_dir()
    key = _cache_key(source, site, start_date, end_date)
    return cache_dir / source.upper() / f"{site}_{key}.parquet"


def get(
    source: str, site: str, start_date: datetime, end_date: datetime
) -> pd.DataFrame | None:
    """
    Retrieve cached data if available.

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

    path = _cache_path(source, site, start_date, end_date)
    if path.exists():
        logger.debug("Cache hit: %s/%s", source, site)
        return pd.read_parquet(path)

    return None


def put(
    source: str,
    site: str,
    start_date: datetime,
    end_date: datetime,
    data: pd.DataFrame,
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

    path = _cache_path(source, site, start_date, end_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    data.to_parquet(path, index=False)
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
        target = cache_dir / source.upper()
        if target.exists():
            for f in target.glob("*.parquet"):
                f.unlink()
                count += 1
            # Remove empty directory
            if not any(target.iterdir()):
                target.rmdir()
    else:
        for f in cache_dir.rglob("*.parquet"):
            f.unlink()
            count += 1
        # Remove empty subdirectories
        for d in sorted(cache_dir.glob("*/"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()

    logger.info("Cleared %d cached files", count)
    return count


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
    files = list(cache_dir.rglob("*.parquet"))
    total_size = sum(f.stat().st_size for f in files)
    sources = sorted({f.parent.name for f in files})

    return {
        "enabled": _cache_enabled,
        "directory": str(cache_dir),
        "sources": sources,
        "total_files": len(files),
        "total_size_mb": total_size / (1024 * 1024),
    }


def is_enabled() -> bool:
    """Return whether caching is currently enabled."""
    return _cache_enabled
