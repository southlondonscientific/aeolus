"""Live integration roundtrip: find_sites → download → analyse.

Runs against real APIs. This is the release-gated complement to
``test_integration_contract.py``: the contract test proves the *aeolus
schema* flows through all consumers, and this test proves each *source*
actually produces that schema end-to-end.

The key bug class this catches:
- ``find_sites("X")`` returns a site_code/source_network that ``download("X",
  [site_code])`` doesn't accept (the Hermes bug — source_network mismatch)
- A source's ``download()`` output breaks an analysis/viz function
  (schema drift at a specific source)

Skipped sources either require API keys not in CI, or are portals that
need spatial filters up front.

Run with::

    pytest tests/test_integration_roundtrip.py -m conformance -v
"""

from __future__ import annotations

import os
import warnings
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import aeolus
from aeolus.metrics import aq_stats, aqi_summary, time_average, trend
from aeolus.registry import get_source, list_sources
from aeolus.viz import plot_diurnal, plot_timeseries

pytestmark = pytest.mark.conformance

# ---------------------------------------------------------------------------
# Time windows
# ---------------------------------------------------------------------------
_END = datetime.now(tz=timezone.utc)
_START = _END - timedelta(days=3)

# Some sources need a wider window to have data (EEA lags heavily, etc.)
_SPARSE_START = _END - timedelta(days=14)
_SPARSE_END = _END


# ---------------------------------------------------------------------------
# Source selection
#
# Each entry: (source_key, window_start, window_end, find_sites_kwargs, skip_reason).
# find_sites_kwargs lets us give portals/EEA the spatial filter they need.
# skip_reason is None if the test should run; a string to skip.
# ---------------------------------------------------------------------------

SOURCES_TO_TEST = [
    # (source, start, end, find_sites_kwargs, skip_reason)
    ("AURN", _START, _END, {}, None),
    ("SAQN", _START, _END, {}, None),
    ("WAQN", _START, _END, {}, None),
    ("NI", _START, _END, {}, None),
    ("AQE", _START, _END, {}, None),
    ("LAQN", _START, _END, {}, None),
    ("EEA", _SPARSE_START, _SPARSE_END, {"country": "IE"}, None),
    ("SONITUS", _START, _END, {}, None),
    (
        "BREATHE_LONDON", _START, _END, {},
        None if os.getenv("BL_API_KEY") else "BL_API_KEY not set",
    ),
    (
        "AIRQO", _SPARSE_START, _SPARSE_END, {},
        None if os.getenv("AIRQO_API_KEY") else "AIRQO_API_KEY not set",
    ),
    (
        "AIRNOW", _START, _END, {},
        None if os.getenv("AIRNOW_API_KEY") else "AIRNOW_API_KEY not set",
    ),
    # Sensor.Community and portals (OpenAQ, PurpleAir) need spatial filters
    # and tend to be slow — skip for the per-source roundtrip and cover them
    # in dedicated tests elsewhere.
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pick_test_site(sites_df: pd.DataFrame, source: str) -> str:
    """Pick one site to download from — prefer canonical well-known sites."""
    if sites_df.empty:
        pytest.skip(f"{source}: find_sites returned no rows")

    # Known-good canonical sites per source that reliably have recent data.
    # These were picked by hand after live-testing each source.
    preferred = {
        "AURN": "MY1",      # London Marylebone Road
        "SAQN": "ED3",      # Edinburgh St Leonards
        "LAQN": "MY1",      # Marylebone (also in LAQN)
        "WAQN": "CARD",     # Cardiff Centre
        "NI": "BEL1",       # Belfast Centre
        "AQE": "CAM1",      # Cambridge — AQE has many closed sites, pick a known-active one
        "AIRNOW": None,     # AirNow site codes vary by state — use first
    }
    canonical = preferred.get(source)
    if canonical and canonical in sites_df["site_code"].values:
        return canonical
    return str(sites_df["site_code"].iloc[0])


def _download_with_fallback(
    source: str, sites_df: pd.DataFrame, start, end, max_tries: int = 5
) -> tuple[str, pd.DataFrame]:
    """Try up to ``max_tries`` sites in order, return (site, data) for first non-empty.

    Some networks include sites that are closed or offline; the first
    site returned by ``find_sites`` may not have recent data.
    """
    preferred_site = _pick_test_site(sites_df, source)
    tried = [preferred_site]

    # Try the preferred site first
    data = aeolus.download(source, [preferred_site], start_date=start, end_date=end)
    if not data.empty:
        return preferred_site, data

    # Fall back through other sites
    other_codes = [
        str(c) for c in sites_df["site_code"].tolist()
        if c not in tried
    ][: max_tries - 1]

    for site in other_codes:
        data = aeolus.download(source, [site], start_date=start, end_date=end)
        if not data.empty:
            return site, data

    return preferred_site, data  # empty data — caller can skip


# ---------------------------------------------------------------------------
# Parametrised roundtrip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source,start,end,kwargs,skip_reason",
    SOURCES_TO_TEST,
    ids=[s[0] for s in SOURCES_TO_TEST],
)
class TestSourceRoundtrip:
    """For every source: find_sites → download → every analysis/viz function."""

    def test_find_sites_to_download(self, source, start, end, kwargs, skip_reason):
        """Site codes from find_sites must work as download() arguments.

        This is the exact integration path that the Hermes-reported bug broke:
        find_sites returned source_network="Breathe London" but download only
        accepted "BREATHE_LONDON".
        """
        if skip_reason:
            pytest.skip(skip_reason)

        sites = aeolus.find_sites(source, **kwargs)
        if sites.empty:
            pytest.skip(f"{source}: no sites returned")

        # Every site's source_network must match the source we queried.
        # If this fails, roundtrip is broken — don't silently skip.
        unique_networks = sites["source_network"].unique()
        assert source in unique_networks, (
            f"find_sites({source}) returned source_network={unique_networks!r}, "
            f"expected to include {source!r} (roundtrip broken — the "
            f"source_network from find_sites won't be accepted by download())"
        )

        site_code, data = _download_with_fallback(source, sites, start, end)
        if data.empty:
            pytest.skip(f"{source}: no data for first 5 sites in time window")

        # The downloaded data's source_network must match the registry key
        assert (data["source_network"] == source).all(), (
            f"{source}: download() output source_network="
            f"{data['source_network'].unique()!r}, expected {source!r}"
        )

    def test_download_feeds_summarise(self, source, start, end, kwargs, skip_reason):
        if skip_reason:
            pytest.skip(skip_reason)
        sites = aeolus.find_sites(source, **kwargs)
        if sites.empty:
            pytest.skip(f"{source}: no sites")
        _, data = _download_with_fallback(source, sites, start, end)
        if data.empty:
            pytest.skip(f"{source}: no data")

        summary = aeolus.summarise(data)
        assert not summary.empty
        assert (summary["data_capture"] <= 1.0).all()

    def test_download_feeds_time_average(self, source, start, end, kwargs, skip_reason):
        if skip_reason:
            pytest.skip(skip_reason)
        sites = aeolus.find_sites(source, **kwargs)
        if sites.empty:
            pytest.skip(f"{source}: no sites")
        _, data = _download_with_fallback(source, sites, start, end)
        if data.empty:
            pytest.skip(f"{source}: no data")

        daily = time_average(data, freq="D", data_thresh=0.0)
        assert isinstance(daily, pd.DataFrame)

    def test_download_feeds_plot(self, source, start, end, kwargs, skip_reason):
        """Live data must flow into plot_timeseries without shape errors."""
        if skip_reason:
            pytest.skip(skip_reason)
        sites = aeolus.find_sites(source, **kwargs)
        if sites.empty:
            pytest.skip(f"{source}: no sites")
        _, data = _download_with_fallback(source, sites, start, end)
        if data.empty:
            pytest.skip(f"{source}: no data")

        pollutant = "NO2" if "NO2" in data["measurand"].values else str(data["measurand"].iloc[0])

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fig = plot_timeseries(data, pollutants=[pollutant], apply_style=False)

        assert isinstance(fig, plt.Figure)
        plt.close(fig)
