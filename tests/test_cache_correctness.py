"""Cache correctness: rolling windows, incomplete results, key normalisation."""

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from aeolus import cache
from aeolus.cache import (
    _cache_key,
    cache_info,
    disable_cache,
    enable_cache,
    fetch_with_cache,
    put,
)


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path):
    """Ensure each test gets a clean, isolated cache directory."""
    enable_cache(cache_dir=tmp_path / "test_cache")
    yield tmp_path / "test_cache"
    disable_cache()


def _frame(sites):
    """Standard 8-column frame with one row per site."""
    return pd.DataFrame(
        {
            "site_code": list(sites),
            "date_time": pd.to_datetime(["2024-01-01 00:00"] * len(sites), utc=True),
            "measurand": ["NO2"] * len(sites),
            "value": [float(i) for i in range(len(sites))],
            "units": ["ug/m3"] * len(sites),
            "source_network": ["TEST_NET"] * len(sites),
            "ratification": ["None"] * len(sites),
            "created_at": pd.Timestamp.now(tz="UTC"),
        }
    )


def _register(fetcher, source_type="network"):
    return patch.dict(
        "aeolus.registry._SOURCES",
        {"TEST_NET": {"type": source_type, "fetch_data": fetcher, "primary": True}},
    )


# =========================================================================
# last= windows must hit the cache
# =========================================================================


class TestRollingWindowCache:
    def test_last_hits_cache_on_second_call(self, isolated_cache):
        """Repeated last= downloads reuse one cache entry."""
        from aeolus import networks

        fetcher = MagicMock(return_value=_frame(["MY1"]))
        with _register(fetcher):
            networks.download("TEST_NET", ["MY1"], last="30d")
            networks.download("TEST_NET", ["MY1"], last="30d")

        assert fetcher.call_count == 1
        assert len(list(isolated_cache.rglob("*.parquet"))) == 1

    def test_top_level_download_last_hits_cache(self, isolated_cache):
        """aeolus.download(last=...) shares the rolling-window entry."""
        import aeolus

        fetcher = MagicMock(return_value=_frame(["MY1"]))
        with _register(fetcher):
            aeolus.download("TEST_NET", ["MY1"], last="30d")
            aeolus.download("TEST_NET", ["MY1"], last="30d")
            aeolus.download({"TEST_NET": ["MY1"]}, last="30d")

        assert fetcher.call_count == 1
        assert len(list(isolated_cache.rglob("*.parquet"))) == 1

    def test_last_entry_expires_and_is_overwritten(self, isolated_cache):
        """A stale rolling-window entry is re-fetched in place, not duplicated."""
        from aeolus import networks

        fetcher = MagicMock(return_value=_frame(["MY1"]))
        with _register(fetcher):
            networks.download("TEST_NET", ["MY1"], last="30d")
            (path,) = isolated_cache.rglob("*.parquet")
            stale = time.time() - 2 * 3600
            os.utime(path, (stale, stale))

            networks.download("TEST_NET", ["MY1"], last="30d")

        assert fetcher.call_count == 2
        assert len(list(isolated_cache.rglob("*.parquet"))) == 1

    def test_short_last_window_bypasses_cache(self, isolated_cache):
        """Windows no longer than the TTL are live requests — never cached."""
        from aeolus import networks

        fetcher = MagicMock(return_value=_frame(["MY1"]))
        with _register(fetcher):
            networks.download("TEST_NET", ["MY1"], last="30min")
            networks.download("TEST_NET", ["MY1"], last="30min")

        assert fetcher.call_count == 2
        assert list(isolated_cache.rglob("*.parquet")) == []

    def test_explicit_ranges_never_expire(self, isolated_cache):
        """The TTL applies to last= windows only; explicit ranges are permanent."""
        from aeolus import networks

        start, end = datetime(2024, 1, 1), datetime(2024, 1, 31)
        fetcher = MagicMock(return_value=_frame(["MY1"]))
        with _register(fetcher):
            networks.download("TEST_NET", ["MY1"], start, end)
            (path,) = isolated_cache.rglob("*.parquet")
            stale = time.time() - 30 * 86400
            os.utime(path, (stale, stale))
            networks.download("TEST_NET", ["MY1"], start, end)

        assert fetcher.call_count == 1


# =========================================================================
# Finding 2 — incomplete results must not be latched as authoritative
# =========================================================================


class TestIncompleteResultsExpire:
    def test_missing_site_is_retried_after_ttl(self, isolated_cache):
        """A result missing a requested site is cached only for the volatile TTL."""
        start, end = datetime(2024, 1, 1), datetime(2024, 1, 31)
        # First fetch: KC1 fails transiently (the fetcher swallowed the error).
        fetcher = MagicMock(side_effect=[_frame(["MY1"]), _frame(["KC1", "MY1"])])
        sites = ["MY1", "KC1"]

        first = fetch_with_cache("TEST_NET", sites, start, end, fetcher)
        assert set(first["site_code"]) == {"MY1"}

        # Within the TTL a re-run is still instant (bulk pulls with a closed site)
        fetch_with_cache("TEST_NET", sites, start, end, fetcher)
        assert fetcher.call_count == 1

        (path,) = isolated_cache.rglob("*.parquet")
        two_hours_ago = time.time() - 7200
        os.utime(path, (two_hours_ago, two_hours_ago))

        healed = fetch_with_cache("TEST_NET", sites, start, end, fetcher)
        assert fetcher.call_count == 2
        assert set(healed["site_code"]) == {"MY1", "KC1"}

        # Now complete: an explicit range never expires
        (path,) = isolated_cache.rglob("*.parquet")
        os.utime(path, (two_hours_ago, two_hours_ago))
        fetch_with_cache("TEST_NET", sites, start, end, fetcher)
        assert fetcher.call_count == 2

    def test_complete_result_cached_case_insensitively(self, isolated_cache):
        """Requested 'my1' is satisfied by returned 'MY1' (regulatory upper-cases)."""
        start, end = datetime(2024, 1, 1), datetime(2024, 1, 31)
        fetcher = MagicMock(return_value=_frame(["MY1"]))

        fetch_with_cache("TEST_NET", ["my1"], start, end, fetcher)
        fetch_with_cache("TEST_NET", ["my1"], start, end, fetcher)
        assert fetcher.call_count == 1


# =========================================================================
# tz-insensitive key
# =========================================================================


class TestCacheKeyTimezone:
    def test_naive_and_utc_aware_same_key(self):
        """Naive datetimes are UTC by library convention — same instant, same key."""
        naive = _cache_key("AURN", "MY1", datetime(2024, 1, 1), datetime(2024, 1, 31))
        aware = _cache_key(
            "AURN",
            "MY1",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
        )
        assert naive == aware

    def test_non_utc_offset_same_instant_same_key(self):
        bst = timezone(timedelta(hours=1))
        utc_key = _cache_key(
            "AURN",
            "MY1",
            datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 6, 2, 0, 0, tzinfo=timezone.utc),
        )
        bst_key = _cache_key(
            "AURN",
            "MY1",
            datetime(2024, 6, 1, 1, 0, tzinfo=bst),
            datetime(2024, 6, 2, 1, 0, tzinfo=bst),
        )
        assert utc_key == bst_key

    def test_naive_key_unchanged_from_v045(self):
        """Existing on-disk entries keyed with naive datetimes stay valid."""
        key = _cache_key("AURN", "MY1", datetime(2024, 1, 1), datetime(2024, 1, 31))
        assert key == "100812a6ff04675c"


# =========================================================================
# cache_info survives concurrent removal
# =========================================================================


class TestCacheInfoConcurrentRemoval:
    def test_file_removed_between_listing_and_stat(self, isolated_cache):
        start, end = datetime(2024, 1, 1), datetime(2024, 1, 31)
        put("AURN", "MY1", start, end, _frame(["MY1"]))
        put("SAQN", "ED3", start, end, _frame(["ED3"]))

        real_rglob = Path.rglob

        def rglob_then_remove(self, pattern):
            found = sorted(real_rglob(self, pattern))
            found[0].unlink()  # another process clears it mid-call
            return iter(found)

        with patch.object(Path, "rglob", rglob_then_remove):
            info = cache_info()

        assert info["total_files"] == 1
        assert info["sources"] == ["SAQN"]
        assert info["total_size_mb"] > 0


# =========================================================================
# Folded test-quality items
# =========================================================================


class TestFetchWithCacheSiteKey:
    def test_site_order_does_not_affect_key(self, isolated_cache):
        start, end = datetime(2024, 1, 1), datetime(2024, 1, 31)
        data = _frame(["A", "B"])
        fetcher = MagicMock(return_value=data)

        first = fetch_with_cache("TEST_NET", ["B", "A"], start, end, fetcher)
        second = fetch_with_cache("TEST_NET", ["A", "B"], start, end, fetcher)

        assert fetcher.call_count == 1
        assert len(list(isolated_cache.rglob("*.parquet"))) == 1
        pd.testing.assert_frame_equal(first, data)
        pd.testing.assert_frame_equal(second.reset_index(drop=True), data)

    def test_different_site_sets_do_not_collide(self, isolated_cache):
        start, end = datetime(2024, 1, 1), datetime(2024, 1, 31)
        fetcher = MagicMock(side_effect=[_frame(["A", "B"]), _frame(["A"])])

        fetch_with_cache("TEST_NET", ["A", "B"], start, end, fetcher)
        subset = fetch_with_cache("TEST_NET", ["A"], start, end, fetcher)

        assert fetcher.call_count == 2
        assert set(subset["site_code"]) == {"A"}


def test_cache_disabled_in_fresh_interpreter():
    """The module default is disabled — checked free of the autouse fixture."""
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            "import aeolus.cache as c; print(c.is_enabled(), c._cache_enabled)",
        ],
        capture_output=True,
        text=True,
        check=True,
        env={k: v for k, v in os.environ.items() if k != "AEOLUS_CACHE_DIR"},
    )
    assert out.stdout.split() == ["False", "False"]


def test_invalid_ttl_env_var_does_not_break_import():
    out = subprocess.run(
        [sys.executable, "-c", "import aeolus.cache as c; print(c._VOLATILE_TTL_S)"],
        capture_output=True,
        text=True,
        env={**os.environ, "AEOLUS_CACHE_VOLATILE_TTL_S": "1h"},
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "3600"
