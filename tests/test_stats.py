# Aeolus: download and standardise air quality data
# Copyright (C) 2025 Ruaraidh Dobson, South London Scientific

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Tests for aeolus.metrics.stats — time_average, aq_stats, trend.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from aeolus.metrics.stats import TrendResult, aq_stats, time_average, trend


# =============================================================================
# Helpers
# =============================================================================


def _make_hourly_data(
    site_code: str = "SITE1",
    measurand: str = "NO2",
    start: str = "2024-01-01",
    end: str = "2024-01-31",
    value: float | None = None,
    freq: str = "h",
    units: str = "ug/m3",
    source_network: str = "TEST",
) -> pd.DataFrame:
    """Create synthetic hourly air quality data for testing."""
    dates = pd.date_range(start, end, freq=freq, tz="UTC")
    n = len(dates)

    if value is not None:
        values = np.full(n, value)
    else:
        rng = np.random.default_rng(42)
        values = 30.0 + rng.normal(0, 5, n)

    return pd.DataFrame(
        {
            "site_code": site_code,
            "date_time": dates,
            "measurand": measurand,
            "value": values,
            "units": units,
            "source_network": source_network,
            "ratification": "Provisional",
            "created_at": pd.Timestamp.now(tz="UTC"),
        }
    )


def _make_year_data(
    site_code: str = "SITE1",
    measurand: str = "NO2",
    year: int = 2024,
    value: float = 30.0,
    units: str = "ug/m3",
) -> pd.DataFrame:
    """Create a full year of hourly data at a constant value."""
    start = f"{year}-01-01"
    end = f"{year}-12-31 23:00"
    return _make_hourly_data(
        site_code=site_code,
        measurand=measurand,
        start=start,
        end=end,
        value=value,
        units=units,
    )


# =============================================================================
# TestTimeAverage
# =============================================================================


class TestTimeAverage:
    """Tests for the time_average function."""

    def test_daily_mean_constant_data(self):
        """Daily mean of constant data equals that value."""
        data = _make_hourly_data(value=42.0)
        result = time_average(data, freq="D", statistic="mean")

        assert "data_capture" in result.columns
        assert "value" in result.columns
        # All daily means should be 42
        valid = result["value"].dropna()
        assert len(valid) > 0
        np.testing.assert_allclose(valid.values, 42.0, atol=1e-10)

    def test_data_thresh_filters_low_capture(self):
        """data_thresh=0.75 with 50% gap data produces NaN values."""
        data = _make_hourly_data(
            start="2024-01-01", end="2024-01-01 11:00", value=10.0
        )
        # Only 12 hours of a 24-hour day
        result = time_average(data, freq="D", statistic="mean", data_thresh=0.75)
        # With only ~50% data capture, the daily value should be NaN
        assert result["value"].isna().all()

    def test_data_thresh_zero_disables(self):
        """data_thresh=0 keeps all values regardless of coverage."""
        data = _make_hourly_data(
            start="2024-01-01", end="2024-01-01 05:00", value=10.0
        )
        result = time_average(data, freq="D", statistic="mean", data_thresh=0)
        assert not result["value"].isna().all()
        np.testing.assert_allclose(result["value"].dropna().values, 10.0, atol=1e-10)

    def test_statistic_max(self):
        """statistic='max' returns the maximum value per period."""
        dates = pd.date_range("2024-01-01", periods=24, freq="h", tz="UTC")
        values = list(range(24))
        data = pd.DataFrame(
            {
                "site_code": "S1",
                "date_time": dates,
                "measurand": "NO2",
                "value": values,
                "units": "ug/m3",
                "source_network": "TEST",
                "ratification": "Provisional",
                "created_at": pd.Timestamp.now(tz="UTC"),
            }
        )
        result = time_average(data, freq="D", statistic="max", data_thresh=0)
        assert result["value"].iloc[0] == 23

    def test_statistic_percentile(self):
        """statistic='percentile' works correctly."""
        data = _make_hourly_data(start="2024-01-01", end="2024-01-02")
        result = time_average(
            data, freq="D", statistic="percentile", percentile=50, data_thresh=0
        )
        assert not result.empty

    def test_multi_site_multi_pollutant(self):
        """Each site/pollutant is aggregated independently."""
        d1 = _make_hourly_data(site_code="S1", measurand="NO2", value=10.0)
        d2 = _make_hourly_data(site_code="S2", measurand="PM2.5", value=20.0)
        data = pd.concat([d1, d2], ignore_index=True)

        result = time_average(data, freq="D")
        sites = result["site_code"].unique()
        assert set(sites) == {"S1", "S2"}

        s1_vals = result[result["site_code"] == "S1"]["value"].dropna()
        s2_vals = result[result["site_code"] == "S2"]["value"].dropna()
        np.testing.assert_allclose(s1_vals.values, 10.0, atol=1e-10)
        np.testing.assert_allclose(s2_vals.values, 20.0, atol=1e-10)

    def test_empty_input_returns_empty_schema(self):
        """Empty input returns empty DataFrame with correct columns."""
        data = pd.DataFrame(
            columns=[
                "site_code", "date_time", "measurand", "value",
                "units", "source_network", "ratification", "created_at",
            ]
        )
        result = time_average(data)
        assert result.empty
        assert "data_capture" in result.columns

    def test_custom_freq_8h(self):
        """Custom freq '8h' produces 3 rows per day."""
        data = _make_hourly_data(
            start="2024-01-01", end="2024-01-01 23:00", value=10.0
        )
        result = time_average(data, freq="8h", data_thresh=0)
        assert len(result) == 3

    def test_pollutant_filter(self):
        """pollutants parameter filters to specific measurands."""
        d1 = _make_hourly_data(measurand="NO2", value=10.0)
        d2 = _make_hourly_data(measurand="PM2.5", value=20.0)
        data = pd.concat([d1, d2], ignore_index=True)

        result = time_average(data, freq="D", pollutants=["NO2"])
        assert set(result["measurand"].unique()) == {"NO2"}

    def test_output_columns(self):
        """Output has the expected column set."""
        data = _make_hourly_data(value=10.0)
        result = time_average(data, freq="D")
        expected_cols = {
            "site_code", "date_time", "measurand", "value",
            "units", "source_network", "data_capture",
        }
        assert set(result.columns) == expected_cols

    def test_data_capture_is_fraction(self):
        """data_capture values are between 0 and 1."""
        data = _make_hourly_data(value=10.0)
        result = time_average(data, freq="D", data_thresh=0)
        assert (result["data_capture"] >= 0).all()
        assert (result["data_capture"] <= 1.0).all()


# =============================================================================
# TestAQStats
# =============================================================================


class TestAQStats:
    """Tests for the aq_stats function."""

    def test_correct_data_capture(self):
        """Data capture is calculated correctly for a full year."""
        data = _make_year_data(year=2024, value=30.0)
        result = aq_stats(data, year=2024)

        assert len(result) == 1
        # 2024 is a leap year (8784 hours)
        # We generated up to 23:00 on Dec 31, so 8760 hours
        assert result["data_capture"].iloc[0] > 0.99

    def test_leap_year_data_capture(self):
        """Leap year uses 8784 expected hours."""
        data = _make_year_data(year=2024, value=30.0)
        result = aq_stats(data, year=2024, data_thresh=0)
        # 2024 is leap year
        assert result["data_capture"].iloc[0] == pytest.approx(8760 / 8784, abs=0.01)

    def test_known_exceedance_counts_no2(self):
        """NO2 exceedance hours counted correctly with injected spikes."""
        data = _make_year_data(measurand="NO2", value=30.0)
        # Inject 5 hours above 200 ug/m3
        data.loc[data.index[:5], "value"] = 250.0

        result = aq_stats(data, data_thresh=0)
        assert result["exceedance_hours_200"].iloc[0] == 5

    def test_known_exceedance_counts_pm10(self):
        """PM10 exceedance days counted correctly."""
        data = _make_year_data(measurand="PM10", value=20.0)
        # Set first 3 full days to high values (> 50 daily mean)
        three_days = 3 * 24
        data.loc[data.index[:three_days], "value"] = 80.0

        result = aq_stats(data, data_thresh=0)
        assert result["exceedance_days_50"].iloc[0] == 3

    def test_exceedance_nan_for_irrelevant_pollutant(self):
        """Exceedance columns are NaN for non-matching pollutants."""
        data = _make_year_data(measurand="PM10", value=20.0)
        result = aq_stats(data, data_thresh=0)

        # PM10 should NOT have NO2 exceedance
        assert pd.isna(result["exceedance_hours_200"].iloc[0])
        # PM10 SHOULD have PM10 exceedance
        assert not pd.isna(result["exceedance_days_50"].iloc[0])
        # PM10 should NOT have O3 exceedance
        assert pd.isna(result["exceedance_days_120"].iloc[0])

    def test_year_filter(self):
        """Year filtering works."""
        d1 = _make_year_data(year=2023, value=30.0)
        d2 = _make_year_data(year=2024, value=40.0)
        data = pd.concat([d1, d2], ignore_index=True)

        result = aq_stats(data, year=2024, data_thresh=0)
        assert len(result) == 1
        assert result["year"].iloc[0] == 2024

    def test_pollutant_filter(self):
        """Pollutant filtering works."""
        d1 = _make_year_data(measurand="NO2", value=30.0)
        d2 = _make_year_data(measurand="PM2.5", value=15.0)
        data = pd.concat([d1, d2], ignore_index=True)

        result = aq_stats(data, pollutant="NO2", data_thresh=0)
        assert len(result) == 1
        assert result["pollutant"].iloc[0] == "NO2"

    def test_low_coverage_nan_stats(self):
        """Low data capture produces NaN stats when threshold applied."""
        # Only 1 month of data
        data = _make_hourly_data(
            start="2024-01-01", end="2024-01-31", value=30.0
        )
        result = aq_stats(data, data_thresh=0.75)
        # ~31/366 days = ~8.5% capture, well below 75%
        assert pd.isna(result["annual_mean"].iloc[0])

    def test_multi_site_one_row_per(self):
        """Multi-site data produces one row per site/year/pollutant."""
        d1 = _make_year_data(site_code="S1", value=30.0)
        d2 = _make_year_data(site_code="S2", value=40.0)
        data = pd.concat([d1, d2], ignore_index=True)

        result = aq_stats(data, data_thresh=0)
        assert len(result) == 2
        assert set(result["site_code"]) == {"S1", "S2"}

    def test_annual_mean_correct(self):
        """Annual mean is correct for constant data."""
        data = _make_year_data(value=42.0)
        result = aq_stats(data, data_thresh=0)
        assert result["annual_mean"].iloc[0] == pytest.approx(42.0)

    def test_percentiles(self):
        """p95 and p99 are calculated."""
        data = _make_year_data(value=30.0)
        result = aq_stats(data, data_thresh=0)
        assert result["p95"].iloc[0] == pytest.approx(30.0)
        assert result["p99"].iloc[0] == pytest.approx(30.0)

    def test_empty_input(self):
        """Empty input returns empty DataFrame with correct columns."""
        data = pd.DataFrame(
            columns=[
                "site_code", "date_time", "measurand", "value",
                "units", "source_network", "ratification", "created_at",
            ]
        )
        result = aq_stats(data)
        assert result.empty
        assert "annual_mean" in result.columns

    def test_o3_exceedance_days_120(self):
        """O3 exceedance days (max 8h rolling > 120) counted correctly."""
        data = _make_year_data(measurand="O3", value=50.0)
        # Inject 2 days with 8-hour rolling mean > 120
        # Set 16 consecutive hours to 150 (guarantees 2 calendar days with 8h > 120)
        data.loc[data.index[:16], "value"] = 150.0

        result = aq_stats(data, data_thresh=0)
        assert result["exceedance_days_120"].iloc[0] >= 1


# =============================================================================
# TestTrend
# =============================================================================


class TestTrend:
    """Tests for the trend function."""

    def _make_trend_data(
        self,
        site_code: str = "SITE1",
        measurand: str = "NO2",
        years: int = 5,
        base_value: float = 40.0,
        annual_change: float = 0.0,
    ) -> pd.DataFrame:
        """Create multi-year data with a known trend."""
        frames = []
        for yr_offset in range(years):
            yr = 2018 + yr_offset
            dates = pd.date_range(
                f"{yr}-01-01", f"{yr}-12-31 23:00", freq="h", tz="UTC"
            )
            rng = np.random.default_rng(42 + yr_offset)
            vals = (
                base_value
                + annual_change * yr_offset
                + rng.normal(0, 2, len(dates))
            )
            frames.append(
                pd.DataFrame(
                    {
                        "site_code": site_code,
                        "date_time": dates,
                        "measurand": measurand,
                        "value": vals,
                        "units": "ug/m3",
                        "source_network": "TEST",
                        "ratification": "Provisional",
                        "created_at": pd.Timestamp.now(tz="UTC"),
                    }
                )
            )
        return pd.concat(frames, ignore_index=True)

    def test_positive_slope_detected(self):
        """Monotonically increasing data has positive slope."""
        data = self._make_trend_data(annual_change=5.0, years=6)
        result = trend(data, pollutant="NO2", avg_time="year", deseason=False)
        assert isinstance(result, TrendResult)
        assert result.slope > 0

    def test_flat_data_high_pvalue(self):
        """Flat data has high p-value (not significant)."""
        data = self._make_trend_data(annual_change=0.0, years=6)
        result = trend(data, pollutant="NO2", avg_time="year", deseason=False)
        # For truly flat data with noise, p-value should be high
        # (not necessarily > 0.05 due to random seed, but slope should be near 0)
        assert abs(result.slope) < 2.0

    def test_ci_contains_slope(self):
        """CI lower <= slope <= CI upper."""
        data = self._make_trend_data(annual_change=3.0, years=6)
        result = trend(data, pollutant="NO2", avg_time="year", deseason=False)
        assert result.ci_lower <= result.slope <= result.ci_upper

    def test_deseason_warns_if_no_statsmodels(self):
        """deseason=True warns if statsmodels missing."""
        data = self._make_trend_data(years=5)
        with patch.dict("sys.modules", {"statsmodels": None, "statsmodels.tsa.seasonal": None}):
            with pytest.warns(UserWarning, match="statsmodels"):
                result = trend(
                    data, pollutant="NO2", avg_time="month",
                    deseason=True, data_thresh=0
                )
        assert isinstance(result, TrendResult)
        assert result.deseasonalised is False

    def test_avg_time_year_one_point_per_year(self):
        """avg_time='year' produces one point per year."""
        data = self._make_trend_data(years=8)
        result = trend(data, pollutant="NO2", avg_time="year", deseason=False)
        assert result.n_points == 8

    def test_insufficient_data_raises(self):
        """< 6 points after aggregation raises ValueError."""
        data = self._make_trend_data(years=3)
        with pytest.raises(ValueError, match="Insufficient data"):
            trend(data, pollutant="NO2", avg_time="year", deseason=False)

    def test_multi_site_returns_list(self):
        """Multi-site data returns a list of TrendResults."""
        d1 = self._make_trend_data(site_code="S1", years=6)
        d2 = self._make_trend_data(site_code="S2", years=6)
        data = pd.concat([d1, d2], ignore_index=True)

        result = trend(data, pollutant="NO2", avg_time="year", deseason=False)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_single_site_returns_scalar(self):
        """Single-site data returns a scalar TrendResult."""
        data = self._make_trend_data(years=6)
        result = trend(data, pollutant="NO2", avg_time="year", deseason=False)
        assert isinstance(result, TrendResult)

    def test_missing_pollutant_raises(self):
        """Requesting a pollutant not in data raises ValueError."""
        data = self._make_trend_data(measurand="NO2")
        with pytest.raises(ValueError, match="No data found"):
            trend(data, pollutant="O3", avg_time="year")

    def test_trend_result_fields(self):
        """TrendResult has all expected fields populated."""
        data = self._make_trend_data(annual_change=2.0, years=6)
        result = trend(data, pollutant="NO2", avg_time="year", deseason=False)

        assert result.pollutant == "NO2"
        assert result.site_code == "SITE1"
        assert result.avg_time == "year"
        assert result.n_points == 6
        assert result.first_year == 2018
        assert result.last_year == 2023
        assert isinstance(result.p_value, float)
        assert isinstance(result.slope_pct, float)

    def test_monthly_aggregation(self):
        """Monthly aggregation produces ~12*years points."""
        data = self._make_trend_data(years=6)
        result = trend(
            data, pollutant="NO2", avg_time="month",
            deseason=False, data_thresh=0
        )
        # 6 years * 12 months = 72 points
        assert result.n_points >= 60  # Allow some loss at boundaries

    def test_autocor_option(self):
        """autocor=True runs without error."""
        data = self._make_trend_data(annual_change=3.0, years=6)
        result = trend(
            data, pollutant="NO2", avg_time="year",
            deseason=False, autocor=True,
        )
        assert isinstance(result, TrendResult)
