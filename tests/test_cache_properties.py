"""Hypothesis property-based tests for aeolus.cache module."""

from datetime import datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
import pandas as pd

from aeolus.cache import _cache_key, _cache_path, enable_cache, disable_cache, get, put
from conftest_strategies import aeolus_dataframes, site_codes, timestamps

pytestmark = pytest.mark.property

sources = st.sampled_from(["AURN", "SAQN", "BREATHE_LONDON", "SENSOR_COMMUNITY"])


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path):
    enable_cache(cache_dir=tmp_path / "prop_cache")
    yield tmp_path / "prop_cache"
    disable_cache()


class TestCacheKeyProperties:
    """Property tests for _cache_key()."""

    @given(source=sources, site=site_codes, start=timestamps, end=timestamps)
    def test_deterministic(self, source, site, start, end):
        """Same inputs always produce the same key."""
        key1 = _cache_key(source, site, start, end)
        key2 = _cache_key(source, site, start, end)
        assert key1 == key2

    @given(source=sources, site=site_codes, start=timestamps, end=timestamps)
    def test_key_is_hex(self, source, site, start, end):
        """Keys are 16-char lowercase hex strings."""
        key = _cache_key(source, site, start, end)
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)

    @given(
        source=st.sampled_from(["aurn", "Aurn", "AURN", "AuRn"]),
        site=site_codes,
        start=timestamps,
        end=timestamps,
    )
    def test_case_insensitive_source(self, source, site, start, end):
        """Source casing does not affect the key (source.upper() is applied)."""
        key = _cache_key(source, site, start, end)
        key_upper = _cache_key(source.upper(), site, start, end)
        assert key == key_upper


class TestCachePathProperties:
    """Property tests for _cache_path()."""

    @given(
        source=sources,
        site=st.text(min_size=1, max_size=500),
        start=timestamps,
        end=timestamps,
    )
    def test_filename_within_255_bytes(self, source, site, start, end):
        """Filename never exceeds macOS 255-byte limit."""
        path = _cache_path(source, site, start, end)
        filename_bytes = len(path.name.encode("utf-8"))
        assert filename_bytes <= 255

    @given(source=sources, site=site_codes, start=timestamps, end=timestamps)
    def test_path_has_parquet_extension(self, source, site, start, end):
        """All cache paths end in .parquet."""
        path = _cache_path(source, site, start, end)
        assert path.suffix == ".parquet"

    @given(source=sources, site=site_codes, start=timestamps, end=timestamps)
    def test_path_under_source_directory(self, source, site, start, end):
        """Parent directory name is source.upper()."""
        path = _cache_path(source, site, start, end)
        assert path.parent.name == source.upper()


class TestCacheRoundtrip:
    """Property tests for put/get roundtrip."""

    @given(data=st.data())
    @settings(max_examples=20)
    def test_put_get_roundtrip(self, data):
        """Data survives a put/get cycle (length and columns match)."""
        source = data.draw(sources)
        site = data.draw(site_codes)
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        df = data.draw(aeolus_dataframes(min_rows=1, max_rows=20))

        put(source, site, start, end, df)
        result = get(source, site, start, end)

        assert result is not None
        assert len(result) == len(df)
        assert list(result.columns) == list(df.columns)

    @given(data=st.data())
    @settings(max_examples=10)
    def test_roundtrip_preserves_values(self, data):
        """Numeric 'value' column survives Parquet serialisation."""
        source = data.draw(sources)
        site = data.draw(site_codes)
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        df = data.draw(aeolus_dataframes(min_rows=1, max_rows=20))

        put(source, site, start, end, df)
        result = get(source, site, start, end)

        assert result is not None
        pd.testing.assert_series_equal(
            result["value"].reset_index(drop=True),
            df["value"].reset_index(drop=True),
            check_dtype=False,
        )

    @given(data=st.data())
    @settings(max_examples=10)
    def test_roundtrip_preserves_timezone(self, data):
        """UTC timezone info survives Parquet serialisation."""
        source = data.draw(sources)
        site = data.draw(site_codes)
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        df = data.draw(aeolus_dataframes(min_rows=1, max_rows=20))

        put(source, site, start, end, df)
        result = get(source, site, start, end)

        assert result is not None
        assert result["date_time"].dt.tz is not None, "date_time lost timezone"
        assert result["created_at"].dt.tz is not None, "created_at lost timezone"
        pd.testing.assert_series_equal(
            result["date_time"].reset_index(drop=True),
            df["date_time"].reset_index(drop=True),
            check_dtype=False,
        )
        pd.testing.assert_series_equal(
            result["created_at"].reset_index(drop=True),
            df["created_at"].reset_index(drop=True),
            check_dtype=False,
        )
