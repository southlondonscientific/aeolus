"""
Tests for the local file cache module.

Tests cover:
- Cache key generation (deterministic, unique per request)
- Cache get/put lifecycle
- Enable/disable toggling
- Cache clearing (full and per-source)
- Cache info reporting
- Integration with download() flow
- Edge cases (empty DataFrames, missing directories)
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from aeolus.cache import (
    _cache_key,
    _cache_path,
    cache_info,
    clear_cache,
    disable_cache,
    enable_cache,
    get,
    is_enabled,
    put,
)


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path):
    """Ensure each test gets a clean, isolated cache directory."""
    enable_cache(cache_dir=tmp_path / "test_cache")
    yield tmp_path / "test_cache"
    disable_cache()


@pytest.fixture
def sample_data():
    """Standard 8-column test DataFrame."""
    return pd.DataFrame(
        {
            "site_code": ["MY1", "MY1", "MY1"],
            "date_time": pd.to_datetime(
                ["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-01 02:00"],
                utc=True,
            ),
            "measurand": ["NO2", "NO2", "NO2"],
            "value": [45.2, 38.1, 42.0],
            "units": ["ug/m3", "ug/m3", "ug/m3"],
            "source_network": ["AURN", "AURN", "AURN"],
            "ratification": ["None", "None", "None"],
            "created_at": pd.Timestamp.now(tz="UTC"),
        }
    )


# =========================================================================
# Cache key tests
# =========================================================================


class TestCacheKey:
    def test_deterministic(self):
        """Same inputs produce the same key."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        key1 = _cache_key("AURN", "MY1", start, end)
        key2 = _cache_key("AURN", "MY1", start, end)
        assert key1 == key2

    def test_different_sites_different_keys(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        key1 = _cache_key("AURN", "MY1", start, end)
        key2 = _cache_key("AURN", "KC1", start, end)
        assert key1 != key2

    def test_different_dates_different_keys(self):
        key1 = _cache_key("AURN", "MY1", datetime(2024, 1, 1), datetime(2024, 1, 31))
        key2 = _cache_key("AURN", "MY1", datetime(2024, 2, 1), datetime(2024, 2, 28))
        assert key1 != key2

    def test_different_sources_different_keys(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        key1 = _cache_key("AURN", "MY1", start, end)
        key2 = _cache_key("SAQN", "MY1", start, end)
        assert key1 != key2

    def test_case_normalisation(self):
        """Source names are uppercased."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        key1 = _cache_key("aurn", "MY1", start, end)
        key2 = _cache_key("AURN", "MY1", start, end)
        assert key1 == key2

    def test_key_length(self):
        """Keys are 16-char hex strings."""
        key = _cache_key("AURN", "MY1", datetime(2024, 1, 1), datetime(2024, 1, 31))
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)


# =========================================================================
# Cache path tests
# =========================================================================


class TestCachePath:
    def test_path_structure(self, isolated_cache):
        path = _cache_path("AURN", "MY1", datetime(2024, 1, 1), datetime(2024, 1, 31))
        assert path.parent.name == "AURN"
        assert path.suffix == ".parquet"
        assert "MY1" in path.stem

    def test_source_directory(self, isolated_cache):
        """Different sources get different directories."""
        p1 = _cache_path("AURN", "MY1", datetime(2024, 1, 1), datetime(2024, 1, 31))
        p2 = _cache_path("SAQN", "ED3", datetime(2024, 1, 1), datetime(2024, 1, 31))
        assert p1.parent.name == "AURN"
        assert p2.parent.name == "SAQN"

    def test_long_site_list_filename_within_limit(self, isolated_cache):
        """Many sites joined together must not exceed filesystem filename limits."""
        # Simulate AURN's 321 sites joined by commas (as _fetch_single_source does)
        fake_sites = ",".join(f"SITE{i:03d}" for i in range(321))
        path = _cache_path("AURN", fake_sites, datetime(2024, 1, 1), datetime(2024, 1, 31))
        # macOS filename limit is 255 bytes
        assert len(path.name.encode()) <= 255, (
            f"Cache filename is {len(path.name.encode())} bytes, exceeds 255-byte limit"
        )

    def test_long_site_list_still_unique(self, isolated_cache):
        """Different long site lists produce different cache paths."""
        sites_a = ",".join(f"SITE{i:03d}" for i in range(321))
        sites_b = ",".join(f"SITE{i:03d}" for i in range(1, 322))
        start, end = datetime(2024, 1, 1), datetime(2024, 1, 31)
        path_a = _cache_path("AURN", sites_a, start, end)
        path_b = _cache_path("AURN", sites_b, start, end)
        assert path_a != path_b


# =========================================================================
# Get/Put lifecycle
# =========================================================================


class TestGetPut:
    def test_miss_returns_none(self):
        result = get("AURN", "MY1", datetime(2024, 1, 1), datetime(2024, 1, 31))
        assert result is None

    def test_put_then_get(self, sample_data):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        put("AURN", "MY1", start, end, sample_data)
        result = get("AURN", "MY1", start, end)

        assert result is not None
        assert len(result) == len(sample_data)
        assert list(result.columns) == list(sample_data.columns)
        pd.testing.assert_frame_equal(
            result.reset_index(drop=True),
            sample_data.reset_index(drop=True),
        )

    def test_empty_dataframe_not_cached(self):
        """Empty DataFrames should not be stored."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        put("AURN", "MY1", start, end, pd.DataFrame())
        result = get("AURN", "MY1", start, end)
        assert result is None

    def test_different_keys_independent(self, sample_data):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        put("AURN", "MY1", start, end, sample_data)

        # Different site should miss
        result = get("AURN", "KC1", start, end)
        assert result is None

        # Original should still hit
        result = get("AURN", "MY1", start, end)
        assert result is not None


# =========================================================================
# Enable/Disable
# =========================================================================


class TestEnableDisable:
    def test_disabled_by_default(self):
        """Cache starts disabled (we enable in fixture, so test via fresh module state)."""
        disable_cache()
        assert not is_enabled()

    def test_enable(self):
        enable_cache()
        assert is_enabled()

    def test_disable(self):
        enable_cache()
        disable_cache()
        assert not is_enabled()

    def test_disabled_get_returns_none(self, sample_data):
        """When disabled, get() always returns None even if file exists."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        # Put while enabled
        enable_cache()
        put("AURN", "MY1", start, end, sample_data)

        # Disable — should return None
        disable_cache()
        result = get("AURN", "MY1", start, end)
        assert result is None

    def test_disabled_put_does_nothing(self, isolated_cache):
        """When disabled, put() is a no-op."""
        disable_cache()
        data = pd.DataFrame({"a": [1, 2, 3]})
        put("AURN", "MY1", datetime(2024, 1, 1), datetime(2024, 1, 31), data)

        # No files should be created
        assert len(list(isolated_cache.rglob("*.parquet"))) == 0

    def test_custom_cache_dir(self, tmp_path):
        custom = tmp_path / "custom_cache"
        enable_cache(cache_dir=custom)
        assert is_enabled()

        data = pd.DataFrame({"a": [1]})
        put("AURN", "MY1", datetime(2024, 1, 1), datetime(2024, 1, 31), data)
        assert custom.exists()
        assert len(list(custom.rglob("*.parquet"))) == 1


# =========================================================================
# Clear cache
# =========================================================================


class TestClearCache:
    def test_clear_all(self, sample_data):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        put("AURN", "MY1", start, end, sample_data)
        put("SAQN", "ED3", start, end, sample_data)

        count = clear_cache()
        assert count == 2
        assert get("AURN", "MY1", start, end) is None
        assert get("SAQN", "ED3", start, end) is None

    def test_clear_specific_source(self, sample_data):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        put("AURN", "MY1", start, end, sample_data)
        put("SAQN", "ED3", start, end, sample_data)

        count = clear_cache(source="AURN")
        assert count == 1
        assert get("AURN", "MY1", start, end) is None
        # SAQN should still be cached
        assert get("SAQN", "ED3", start, end) is not None

    def test_clear_empty_cache(self):
        count = clear_cache()
        assert count == 0


# =========================================================================
# Cache info
# =========================================================================


class TestCacheInfo:
    def test_empty_cache_info(self):
        info = cache_info()
        assert info["enabled"] is True
        assert info["total_files"] == 0
        assert info["total_size_mb"] == 0.0
        assert info["sources"] == []

    def test_populated_cache_info(self, sample_data):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        put("AURN", "MY1", start, end, sample_data)
        put("SAQN", "ED3", start, end, sample_data)

        info = cache_info()
        assert info["total_files"] == 2
        assert info["total_size_mb"] > 0
        assert set(info["sources"]) == {"AURN", "SAQN"}


# =========================================================================
# Integration with download flow
# =========================================================================


class TestDownloadIntegration:
    def test_cache_used_on_second_call(self, sample_data, isolated_cache):
        """Top-level api.download caches across calls."""
        from unittest.mock import MagicMock

        from aeolus import api

        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        mock_fetcher = MagicMock(return_value=sample_data)

        with patch.dict(
            "aeolus.registry._SOURCES",
            {
                "TEST_NET": {
                    "type": "network",
                    "fetch_data": mock_fetcher,
                    "primary": True,
                }
            },
        ):
            enable_cache(cache_dir=isolated_cache)
            result1 = api._fetch_single_source("TEST_NET", ["MY1"], start, end)
            assert mock_fetcher.call_count == 1

            result2 = api._fetch_single_source("TEST_NET", ["MY1"], start, end)
            assert mock_fetcher.call_count == 1  # cache hit

            pd.testing.assert_frame_equal(
                result1.reset_index(drop=True),
                result2.reset_index(drop=True),
            )

    def test_networks_download_uses_cache(self, sample_data, isolated_cache):
        """Direct aeolus.networks.download calls share the cache."""
        from unittest.mock import MagicMock

        from aeolus import networks

        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        mock_fetcher = MagicMock(return_value=sample_data)

        with patch.dict(
            "aeolus.registry._SOURCES",
            {
                "TEST_NET": {
                    "type": "network",
                    "fetch_data": mock_fetcher,
                    "primary": True,
                }
            },
        ):
            enable_cache(cache_dir=isolated_cache)
            networks.download("TEST_NET", ["MY1"], start, end)
            networks.download("TEST_NET", ["MY1"], start, end)
            assert mock_fetcher.call_count == 1

    def test_portals_download_uses_cache(self, sample_data, isolated_cache):
        """Direct aeolus.portals.download calls share the cache."""
        from unittest.mock import MagicMock

        from aeolus import portals

        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        mock_fetcher = MagicMock(return_value=sample_data)

        with patch.dict(
            "aeolus.registry._SOURCES",
            {
                "TEST_PORTAL": {
                    "type": "portal",
                    "fetch_data": mock_fetcher,
                    "primary": True,
                }
            },
        ):
            enable_cache(cache_dir=isolated_cache)
            portals.download("TEST_PORTAL", ["LOC1"], start, end)
            portals.download("TEST_PORTAL", ["LOC1"], start, end)
            assert mock_fetcher.call_count == 1
