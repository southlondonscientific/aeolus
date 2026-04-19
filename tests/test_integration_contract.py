"""Integration contract tests for the aeolus schema.

Every source adapter produces DataFrames conforming to the documented 8-column
``DATA_COLUMNS`` schema. Every analysis and visualisation function in aeolus
consumes that schema. This test file enforces the contract between them:
**if a source produces the canonical schema, every consumer must accept it.**

Rather than downloading from each source (slow, flaky, network-dependent),
we build a deterministic synthetic DataFrame that mimics what a source produces
and pipe it through every consumer. A break here means one of:

1. A consumer silently added a new required column (schema drift)
2. A consumer broke on an edge case present in the synthetic data (e.g. NaN values)
3. A consumer's signature changed incompatibly

The live conformance suite (tests/test_conformance.py) complements this by
running real downloads, but this file runs on every PR — fast, no network.

The paired ``test_integration_roundtrip.py`` covers find_sites → download →
analysis using real APIs (release-gated via the ``conformance`` marker).
"""

from __future__ import annotations

import warnings
from datetime import datetime, timedelta, timezone
from itertools import product

import numpy as np
import pandas as pd
import pytest

import aeolus
from aeolus.metrics import (
    aq_stats,
    aqi_check_who,
    aqi_summary,
    time_average,
    trend,
)
from aeolus.viz import (
    plot_calendar,
    plot_distribution,
    plot_diurnal,
    plot_monthly,
    plot_time_variation,
    plot_timeseries,
    plot_trend,
    plot_weekly,
)

# Use non-interactive matplotlib backend so plot tests don't require a display
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


# ============================================================================
# Synthetic source fixtures
# ============================================================================
#
# Each fixture represents a realistic shape of data that a real source emits:
# • regulatory_data — multi-site, multi-pollutant, hourly, tz-aware, mg/m3 for CO
# • low_cost_data   — single site, single pollutant, 15-min resolution
# • sparse_data     — heavy NaN values, simulating patchy sensor data
# • recent_data     — last ~48 hours, reflecting get_current() output shape
# ============================================================================


def _build_data(
    sites: list[str],
    measurands: list[str],
    start: datetime,
    periods: int,
    freq: str,
    source_network: str,
    nan_fraction: float = 0.0,
    units_override: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Build a deterministic aeolus-schema DataFrame for integration testing."""
    rng = np.random.default_rng(seed=42)
    timestamps = pd.date_range(start=start, periods=periods, freq=freq, tz="UTC")

    units_override = units_override or {}
    rows = []
    for site, measurand in product(sites, measurands):
        values = rng.uniform(10, 100, size=periods)
        if nan_fraction > 0:
            mask = rng.uniform(size=periods) < nan_fraction
            values[mask] = np.nan

        units = units_override.get(measurand, "mg/m3" if measurand == "CO" else "ug/m3")

        for ts, val in zip(timestamps, values):
            rows.append({
                "site_code": site,
                "date_time": ts,
                "measurand": measurand,
                "value": val,
                "units": units,
                "source_network": source_network,
                "ratification": "None",
                "created_at": datetime.now(timezone.utc),
            })

    return pd.DataFrame(rows)


@pytest.fixture
def regulatory_data():
    """Mimics AURN/LAQN/SAQN — multi-site hourly reference data over 18 months.

    Long enough to exercise trend() (needs 6+ months) and plot_monthly() (spans
    more than one calendar month).
    """
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    return _build_data(
        sites=["S1", "S2"],
        measurands=["NO2", "PM2.5", "PM10", "O3", "CO"],
        start=start,
        periods=24 * 30 * 18,  # ~18 months hourly
        freq="1h",
        source_network="AURN",
        nan_fraction=0.05,
    )


@pytest.fixture
def low_cost_data():
    """Mimics Breathe London — single site, 15-minute resolution."""
    start = datetime(2024, 6, 1, tzinfo=timezone.utc)
    return _build_data(
        sites=["BL001"],
        measurands=["NO2", "PM2.5"],
        start=start,
        periods=4 * 24 * 30,  # 30 days at 15-min
        freq="15min",
        source_network="BREATHE_LONDON",
        nan_fraction=0.10,
    )


@pytest.fixture
def sparse_data():
    """Heavy NaN load — simulates a poorly-reporting sensor."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return _build_data(
        sites=["SP1"],
        measurands=["NO2"],
        start=start,
        periods=24 * 30,
        freq="1h",
        source_network="AURN",
        nan_fraction=0.70,
    )


@pytest.fixture
def recent_data():
    """Short window — what get_current() would produce."""
    start = datetime.now(timezone.utc) - timedelta(hours=48)
    return _build_data(
        sites=["R1"],
        measurands=["NO2", "PM2.5"],
        start=start,
        periods=48,
        freq="1h",
        source_network="AURN",
    )


# All synthetic fixtures, parametrised so each test runs against every shape
ALL_FIXTURES = ["regulatory_data", "low_cost_data", "sparse_data", "recent_data"]


# ============================================================================
# Analysis function contracts
# ============================================================================


class TestSummariseContract:
    @pytest.mark.parametrize("fixture_name", ALL_FIXTURES)
    def test_summarise_accepts_synthetic(self, fixture_name, request):
        data = request.getfixturevalue(fixture_name)
        result = aeolus.summarise(data)
        assert not result.empty
        assert {"site_code", "measurand", "records", "valid", "data_capture"} <= set(result.columns)
        assert (result["data_capture"] <= 1.0).all()
        assert (result["valid"] <= result["records"]).all()


class TestTimeAverageContract:
    @pytest.mark.parametrize("fixture_name", ALL_FIXTURES)
    @pytest.mark.parametrize("freq", ["D", "W", "ME"])
    def test_time_average_accepts_synthetic(self, fixture_name, freq, request):
        data = request.getfixturevalue(fixture_name)
        result = time_average(data, freq=freq, data_thresh=0.0)
        assert isinstance(result, pd.DataFrame)
        # Must preserve schema columns (at minimum: date_time, measurand, value)
        assert {"date_time", "measurand", "value"} <= set(result.columns)


class TestAQStatsContract:
    @pytest.mark.parametrize("fixture_name", ["regulatory_data", "low_cost_data"])
    def test_aq_stats_accepts_synthetic(self, fixture_name, request):
        data = request.getfixturevalue(fixture_name)
        result = aq_stats(data, data_thresh=0.0)
        assert isinstance(result, pd.DataFrame)
        # aq_stats produces per-site/year/pollutant stats
        assert not result.empty

    def test_aq_stats_handles_sparse(self, sparse_data):
        """With 70% NaN and data_thresh=0.0, aq_stats must still return something."""
        result = aq_stats(sparse_data, data_thresh=0.0)
        assert isinstance(result, pd.DataFrame)


class TestTrendContract:
    def test_trend_single_site_returns_trend_result(self, regulatory_data):
        single_site = regulatory_data[regulatory_data["site_code"] == "S1"]
        result = trend(single_site, pollutant="NO2", avg_time="month", deseason=False)
        # Single-site data returns a single TrendResult with expected attributes
        for attr in ("slope", "p_value", "ci_lower", "ci_upper"):
            assert hasattr(result, attr), f"TrendResult missing attribute {attr}"

    def test_trend_multi_site_returns_list(self, regulatory_data):
        result = trend(regulatory_data, pollutant="NO2", avg_time="month", deseason=False)
        # Multi-site data returns a list
        assert isinstance(result, list)
        assert all(hasattr(r, "slope") for r in result)


class TestAQISummaryContract:
    @pytest.mark.parametrize("fixture_name", ["regulatory_data", "low_cost_data"])
    def test_aqi_summary_accepts_synthetic(self, fixture_name, request):
        data = request.getfixturevalue(fixture_name)
        # aqi_summary may warn about coverage on some fixtures — that's fine
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = aqi_summary(data, index="UK_DAQI")
        assert isinstance(result, pd.DataFrame)


class TestAQIWHOContract:
    def test_aqi_check_who_accepts_regulatory(self, regulatory_data):
        result = aqi_check_who(regulatory_data, target="AQG")
        assert isinstance(result, pd.DataFrame)


# ============================================================================
# Visualisation function contracts
#
# Each plot function must accept aeolus-schema data and return a matplotlib
# Figure.  We don't assert on visual correctness — just that no exception is
# raised and we get a Figure back.
# ============================================================================


def _close_figure(fig):
    """Close a matplotlib figure to free memory between parametrised runs."""
    if fig is not None:
        plt.close(fig)


class TestVizTimeseriesContract:
    @pytest.mark.parametrize("fixture_name", ALL_FIXTURES)
    def test_plot_timeseries(self, fixture_name, request):
        data = request.getfixturevalue(fixture_name)
        fig = plot_timeseries(data, pollutants=["NO2"], apply_style=False)
        assert isinstance(fig, plt.Figure)
        _close_figure(fig)


class TestVizDiurnalContract:
    @pytest.mark.parametrize("fixture_name", ["regulatory_data", "low_cost_data"])
    def test_plot_diurnal(self, fixture_name, request):
        data = request.getfixturevalue(fixture_name)
        fig = plot_diurnal(data, pollutants=["NO2"], apply_style=False)
        assert isinstance(fig, plt.Figure)
        _close_figure(fig)


class TestVizWeeklyContract:
    @pytest.mark.parametrize("fixture_name", ["regulatory_data", "low_cost_data"])
    def test_plot_weekly(self, fixture_name, request):
        data = request.getfixturevalue(fixture_name)
        fig = plot_weekly(data, pollutants=["NO2"], apply_style=False)
        assert isinstance(fig, plt.Figure)
        _close_figure(fig)


class TestVizMonthlyContract:
    def test_plot_monthly_regulatory(self, regulatory_data):
        fig = plot_monthly(regulatory_data, pollutants=["NO2"], apply_style=False)
        assert isinstance(fig, plt.Figure)
        _close_figure(fig)


class TestVizCalendarContract:
    def test_plot_calendar_regulatory(self, regulatory_data):
        fig = plot_calendar(regulatory_data, pollutant="NO2", year=2024, apply_style=False)
        assert isinstance(fig, plt.Figure)
        _close_figure(fig)


class TestVizTimeVariationContract:
    def test_plot_time_variation_regulatory(self, regulatory_data):
        fig = plot_time_variation(regulatory_data, pollutant="NO2", apply_style=False)
        assert isinstance(fig, plt.Figure)
        _close_figure(fig)


class TestVizDistributionContract:
    def test_plot_distribution_regulatory(self, regulatory_data):
        fig = plot_distribution(regulatory_data, pollutant="NO2", apply_style=False)
        assert isinstance(fig, plt.Figure)
        _close_figure(fig)


class TestVizTrendContract:
    def test_plot_trend_single_site(self, regulatory_data):
        """plot_trend expects a single TrendResult; with multi-site data, trend()
        returns a list and the user must pick one site."""
        single_site = regulatory_data[regulatory_data["site_code"] == "S1"]
        trend_result = trend(single_site, pollutant="NO2", avg_time="month", deseason=False)
        # On single-site data, trend() returns a single TrendResult (not a list)
        fig = plot_trend(single_site, trend_result=trend_result, apply_style=False)
        assert isinstance(fig, plt.Figure)
        _close_figure(fig)

    def test_trend_multi_site_returns_list(self, regulatory_data):
        """Contract: multi-site data yields a list of TrendResult, one per site."""
        results = trend(regulatory_data, pollutant="NO2", avg_time="month", deseason=False)
        assert isinstance(results, list)
        assert len(results) == 2  # 2 sites in the fixture


# ============================================================================
# Cache roundtrip contract
# ============================================================================


class TestCacheRoundtrip:
    @pytest.mark.parametrize("fixture_name", ALL_FIXTURES)
    def test_cache_roundtrip_preserves_schema(self, fixture_name, request, tmp_path):
        """Save and load via parquet — schema and tz must be preserved."""
        data = request.getfixturevalue(fixture_name)
        path = tmp_path / "roundtrip.parquet"
        data.to_parquet(path)
        loaded = pd.read_parquet(path)

        assert set(loaded.columns) == set(data.columns)
        assert len(loaded) == len(data)
        assert loaded["date_time"].dt.tz is not None, "tz lost in roundtrip"


# ============================================================================
# Pipeline composition contract — analysis output feeds back into viz
# ============================================================================


class TestAnalysisToViz:
    """Chaining: download → time_average → plot should work without shape mismatch."""

    def test_time_average_feeds_plot_timeseries(self, regulatory_data):
        daily = time_average(regulatory_data, freq="D", data_thresh=0.0)
        fig = plot_timeseries(daily, pollutants=["NO2"], apply_style=False)
        assert isinstance(fig, plt.Figure)
        _close_figure(fig)

    def test_summarise_is_dataframe(self, regulatory_data):
        """summarise output must be a DataFrame suitable for downstream operations."""
        summary = aeolus.summarise(regulatory_data)
        # Must be sortable, filterable, groupable
        assert summary.sort_values("records") is not None
        assert summary[summary["valid"] > 0] is not None
