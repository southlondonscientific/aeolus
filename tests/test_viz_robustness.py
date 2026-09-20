"""viz robustness: sparse time axes, downsampling caps, mixed units, official colours."""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest


def _frame(dates, value, site_code="MY1", measurand="NO2", units="ug/m3"):
    """Standard-schema frame with a constant (or array) value."""
    return pd.DataFrame(
        {
            "site_code": site_code,
            "date_time": dates,
            "measurand": measurand,
            "value": value,
            "units": units,
            "source_network": "AURN",
            "ratification": "None",
            "created_at": pd.Timestamp("2024-06-01", tz="UTC"),
        }
    )


class TestIncompleteTimeAxes:
    """WP6: temporal plots must not crash (or smear) on sparse coverage."""

    @pytest.fixture
    def daytime_only(self):
        """Hours 08-17 on Mon 1, Tue 2, Wed 3 Jan 2024; value == hour."""
        hours = pd.date_range("2024-01-01 08:00", periods=10, freq="h", tz="UTC")
        dates = hours.append(hours + pd.Timedelta(days=1)).append(
            hours + pd.Timedelta(days=2)
        )
        return _frame(dates, dates.hour.astype(float))

    @pytest.mark.parametrize(
        "kwargs",
        [{"show_ci": True}, {"show_ci": False}, {"show_ci": False, "show_range": True}],
    )
    def test_diurnal_sparse_hours(self, daytime_only, kwargs):
        from aeolus.viz import plot_diurnal

        fig = plot_diurnal(daytime_only, **kwargs)

        y = np.asarray(fig.axes[0].lines[0].get_ydata(), dtype=float)
        assert len(y) == 24
        np.testing.assert_allclose(y[8:18], np.arange(8, 18))
        assert np.isnan(y[:8]).all() and np.isnan(y[18:]).all()
        plt.close(fig)

    @pytest.mark.parametrize("show_ci", [True, False])
    def test_weekly_sparse_days(self, daytime_only, show_ci):
        from aeolus.viz import plot_weekly

        fig = plot_weekly(daytime_only, show_ci=show_ci)

        heights = np.array([p.get_height() for p in fig.axes[0].patches], dtype=float)
        assert len(heights) == 7
        np.testing.assert_allclose(heights[:3], 12.5)  # mean of hours 8..17
        assert np.isnan(heights[3:]).all()
        plt.close(fig)

    def test_weekly_single_day_not_smeared_across_week(self):
        """One weekday of data used to broadcast onto all seven bars."""
        from aeolus.viz import plot_weekly

        monday = pd.date_range("2024-01-01", periods=24, freq="h", tz="UTC")
        fig = plot_weekly(_frame(monday, 10.0), show_ci=False)

        heights = np.array([p.get_height() for p in fig.axes[0].patches], dtype=float)
        assert heights[0] == 10.0
        assert np.isnan(heights[1:]).all()
        plt.close(fig)

    @pytest.mark.parametrize("show_ci", [True, False])
    def test_monthly_bar_sparse_months(self, show_ci):
        from aeolus.viz import plot_monthly

        jan = pd.date_range("2024-01-01", periods=48, freq="h", tz="UTC")
        mar = pd.date_range("2024-03-01", periods=48, freq="h", tz="UTC")
        data = pd.concat([_frame(jan, 10.0), _frame(mar, 30.0)], ignore_index=True)

        fig = plot_monthly(data, style="bar", show_ci=show_ci)

        heights = np.array([p.get_height() for p in fig.axes[0].patches], dtype=float)
        assert len(heights) == 12
        assert heights[0] == 10.0 and heights[2] == 30.0
        assert np.isnan(np.delete(heights, [0, 2])).all()
        plt.close(fig)

    def test_monthly_bar_single_month_not_smeared_across_year(self):
        """One month of data used to broadcast onto all twelve bars."""
        from aeolus.viz import plot_monthly

        jan = pd.date_range("2024-01-01", periods=48, freq="h", tz="UTC")
        fig = plot_monthly(_frame(jan, 10.0), style="bar", show_ci=False)

        heights = np.array([p.get_height() for p in fig.axes[0].patches], dtype=float)
        assert heights[0] == 10.0
        assert np.isnan(heights[1:]).all()
        plt.close(fig)

    @pytest.mark.parametrize("show_ci", [True, False])
    def test_monthly_line_sparse_months(self, show_ci):
        from aeolus.viz import plot_monthly

        jan = pd.date_range("2024-01-01", periods=48, freq="h", tz="UTC")
        fig = plot_monthly(_frame(jan, 10.0), style="line", show_ci=show_ci)

        y = np.asarray(fig.axes[0].lines[0].get_ydata(), dtype=float)
        assert len(y) == 12
        assert y[0] == 10.0
        assert np.isnan(y[1:]).all()
        plt.close(fig)

    @pytest.mark.parametrize("show_ci", [True, False])
    def test_time_variation_sparse_hours(self, daytime_only, show_ci):
        from aeolus.viz import plot_time_variation

        fig = plot_time_variation(daytime_only, "NO2", show_ci=show_ci)

        y = np.asarray(fig.axes[0].lines[0].get_ydata(), dtype=float)
        assert len(y) == 24
        np.testing.assert_allclose(y[8:18], np.arange(8, 18))
        assert np.isnan(y[:8]).all() and np.isnan(y[18:]).all()
        plt.close(fig)

    @pytest.mark.parametrize("style", ["box", "violin", "both"])
    def test_distribution_sparse_weekdays(self, daytime_only, style):
        from aeolus.viz import plot_distribution

        fig = plot_distribution(daytime_only, "NO2", group_by="weekday", style=style)

        ax = fig.axes[0]
        labels = [t.get_text() for t in ax.get_xticklabels()]
        assert labels == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        # Mean markers sit on the days that have data, and only those
        means = np.asarray(ax.collections[-1].get_offsets(), dtype=float)
        np.testing.assert_allclose(means[:3, 1], 12.5)
        assert np.isnan(means[3:, 1]).all()
        plt.close(fig)

    def test_distribution_sparse_months_labels_stay_aligned(self):
        """Jun + Jul data must land under the 6th and 7th ticks."""
        from aeolus.viz import plot_distribution

        jun = pd.date_range("2024-06-01", periods=48, freq="h", tz="UTC")
        jul = pd.date_range("2024-07-01", periods=48, freq="h", tz="UTC")
        data = pd.concat([_frame(jun, 10.0), _frame(jul, 30.0)], ignore_index=True)

        fig = plot_distribution(data, "NO2", group_by="month")

        ax = fig.axes[0]
        assert len(ax.get_xticklabels()) == 12
        means = np.asarray(ax.collections[-1].get_offsets(), dtype=float)
        assert means[5, 1] == 10.0 and means[6, 1] == 30.0
        assert np.isnan(np.delete(means[:, 1], [5, 6])).all()
        plt.close(fig)


class TestDownsampleCapAndShortSpans:
    """WP6: downsample_timeseries decimate/mean edge cases."""

    @pytest.mark.parametrize("n", [2001, 3000, 3999, 5000])
    def test_decimate_honours_target(self, n):
        from aeolus.viz.prepare import downsample_timeseries

        dates = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
        df = pd.DataFrame({"date_time": dates, "value": np.arange(float(n))})

        result = downsample_timeseries(
            df, "date_time", "value", target_points=2000, method="decimate"
        )

        assert len(result) <= 2000
        step = int(np.ceil(n / 2000))
        np.testing.assert_array_equal(result["value"].values, np.arange(0.0, n, step))

    def test_mean_sub_second_span_does_not_divide_by_zero(self):
        from aeolus.viz.prepare import downsample_timeseries

        # 10 Hz for 300 s: 3000 points, 0.15 s per target bucket -> "0s"
        dates = pd.date_range("2024-01-01", periods=3000, freq="100ms", tz="UTC")
        df = pd.DataFrame({"date_time": dates, "value": np.arange(3000.0)})

        result = downsample_timeseries(
            df, "date_time", "value", target_points=2000, method="mean"
        )

        # Falls back to 1-second buckets: 10 samples each
        assert len(result) == 300
        assert result["value"].iloc[0] == pytest.approx(4.5)
        assert result["value"].iloc[-1] == pytest.approx(2994.5)

    def test_mean_honours_target(self):
        from aeolus.viz.prepare import downsample_timeseries

        dates = pd.date_range("2024-01-01", periods=3000, freq="s", tz="UTC")
        df = pd.DataFrame({"date_time": dates, "value": np.arange(3000.0)})

        result = downsample_timeseries(
            df, "date_time", "value", target_points=2000, method="mean"
        )

        assert len(result) <= 2000
        assert result["value"].iloc[0] == pytest.approx(0.5)  # mean of 0, 1


class TestPrepareTimeseriesMixedUnits:
    """WP6: prepare_timeseries must honour the units column."""

    def test_mixed_units_converted_before_averaging(self):
        from aeolus.viz.prepare import prepare_timeseries

        dates = pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC")
        data = pd.concat(
            [
                _frame(dates, 0.4, site_code="A", measurand="CO", units="mg/m3"),
                _frame(dates, 400.0, site_code="B", measurand="CO", units="ug/m3"),
            ],
            ignore_index=True,
        )

        spec = prepare_timeseries(data, downsample=False)

        # 0.4 mg/m3 == 400 ug/m3, so the pooled mean is 400, not (0.4 + 400) / 2
        np.testing.assert_allclose(spec.data["CO"].values, 400.0)
        assert spec.units["CO"] == "ug/m3"
        assert spec.ylabel == "CO (ug/m3)"

    def test_mixed_units_categorical_column(self):
        from aeolus.viz.prepare import prepare_timeseries

        dates = pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC")
        data = pd.concat(
            [
                _frame(dates, 0.4, site_code="A", measurand="CO", units="mg/m3"),
                _frame(dates, 400.0, site_code="B", measurand="CO", units="ug/m3"),
            ],
            ignore_index=True,
        )
        data["units"] = data["units"].astype("category")
        data["measurand"] = data["measurand"].astype("category")

        spec = prepare_timeseries(data, downsample=False)

        np.testing.assert_allclose(spec.data["CO"].values, 400.0)

    def test_single_unit_left_as_reported(self):
        from aeolus.viz.prepare import prepare_timeseries

        dates = pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC")
        data = _frame(dates, 20.0, measurand="NO2", units="ppb")

        spec = prepare_timeseries(data, downsample=False)

        np.testing.assert_allclose(spec.data["NO2"].values, 20.0)
        assert spec.units["NO2"] == "ppb"

    def test_mixed_units_reach_the_drawn_line(self):
        from aeolus.viz import plot_timeseries

        dates = pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC")
        data = pd.concat(
            [
                _frame(dates, 0.4, site_code="A", measurand="CO", units="mg/m3"),
                _frame(dates, 400.0, site_code="B", measurand="CO", units="ug/m3"),
            ],
            ignore_index=True,
        )

        fig = plot_timeseries(data)

        np.testing.assert_allclose(fig.axes[0].lines[0].get_ydata(), 400.0)
        plt.close(fig)


class TestOfficialColours:
    """WP6: get_official_colours WHO degrade + UK_DAQI key collision."""

    def test_who_degrades_to_aeolus_palette(self):
        from aeolus.viz.prepare import prepare_aqi_card
        from aeolus.viz.theme import WHO_COMPLIANCE_COLOURS, get_official_colours

        assert get_official_colours("WHO") == WHO_COMPLIANCE_COLOURS
        spec = prepare_aqi_card(4, "Meets AQG", index="WHO", official_colours=True)
        assert spec.colour == WHO_COMPLIANCE_COLOURS["Meets AQG"]

    def test_who_official_card_is_drawn(self):
        from aeolus.viz import plot_aqi_card
        from aeolus.viz.theme import WHO_COMPLIANCE_COLOURS

        fig = plot_aqi_card(4, "Meets AQG", index="WHO", official_colours=True)

        expected = matplotlib.colors.to_rgba(WHO_COMPLIANCE_COLOURS["Meets AQG"])
        assert fig.axes[0].get_facecolor() == pytest.approx(expected)
        plt.close(fig)

    def test_unknown_index_still_raises(self):
        from aeolus.viz.theme import get_official_colours

        with pytest.raises(ValueError, match="No official colours"):
            get_official_colours("NOT_AN_INDEX")

    def test_uk_daqi_uses_mid_band_not_last_band(self):
        from aeolus.metrics.indices import uk_daqi
        from aeolus.viz.theme import get_official_colours

        assert get_official_colours("UK_DAQI") == {
            "Low": uk_daqi.COLORS[2],
            "Moderate": uk_daqi.COLORS[5],
            "High": uk_daqi.COLORS[8],
            "Very High": uk_daqi.COLORS[10],
        }


class TestMultiSitePooling:
    """Multi-site input is pooled by design (notebooks 01/06/07 rely on it)."""

    def _two_sites(self):
        dates = pd.date_range("2024-01-01", periods=24 * 14, freq="h", tz="UTC")
        frames = [
            pd.DataFrame(
                {
                    "site_code": site,
                    "date_time": dates,
                    "measurand": "NO2",
                    "value": value,
                    "units": "ug/m3",
                }
            )
            for site, value in [("ROAD", 90.0), ("BACK", 10.0)]
        ]
        return pd.concat(frames, ignore_index=True)

    def test_diurnal_pools_sites_and_says_so(self):
        from aeolus.viz import plot_diurnal

        fig = plot_diurnal(self._two_sites(), show_ci=False)

        ax = fig.axes[0]
        np.testing.assert_allclose(ax.lines[0].get_ydata(), 50.0)
        assert "2 sites" in ax.get_title()
        plt.close(fig)

    def test_calendar_pools_sites_and_says_so(self):
        from aeolus.viz import plot_calendar

        fig = plot_calendar(self._two_sites(), "NO2")

        ax = fig.axes[0]
        cells = np.asarray(ax.images[0].get_array(), dtype=float)
        assert np.nanmin(cells) == np.nanmax(cells) == 50.0
        assert "2 sites" in ax.get_title()
        plt.close(fig)


class TestDownsampleDropsNaNBelowTarget:
    @pytest.mark.parametrize("method", ["lttb", "decimate", "mean"])
    def test_short_series_still_drops_nan(self, method):
        from aeolus.viz.prepare import downsample_timeseries

        dates = pd.date_range("2024-01-01", periods=1000, freq="h", tz="UTC")
        values = np.arange(1000.0)
        values[::20] = np.nan  # 50 NaN, 950 valid: under the 960 target
        df = pd.DataFrame({"date_time": dates, "value": values})
        result = downsample_timeseries(
            df, "date_time", "value", target_points=960, method=method
        )
        assert len(result) <= 960
        assert not result["value"].isna().any()


class TestTemporalPlotsMixedUnits:
    """0.4 mg/m3 and 400 ug/m3 are the same CO concentration."""

    def _mixed_co(self):
        dates = pd.date_range("2024-01-01", periods=48, freq="h", tz="UTC")
        return pd.concat(
            [
                _frame(dates, 0.4, site_code="A", measurand="CO", units="mg/m3"),
                _frame(dates, 400.0, site_code="B", measurand="CO", units="ug/m3"),
            ],
            ignore_index=True,
        )

    def test_diurnal_converts_before_pooling(self):
        from aeolus.viz import plot_diurnal

        fig = plot_diurnal(self._mixed_co(), show_ci=False)
        ax = fig.axes[0]
        np.testing.assert_allclose(ax.lines[0].get_ydata(), 400.0)
        assert "ug/m3" in ax.get_ylabel()
        plt.close(fig)

    def test_weekly_converts_before_pooling(self):
        from aeolus.viz import plot_weekly

        fig = plot_weekly(self._mixed_co(), show_ci=False)
        heights = np.array([p.get_height() for p in fig.axes[0].patches], dtype=float)
        np.testing.assert_allclose(heights[~np.isnan(heights)], 400.0)
        plt.close(fig)


def test_trend_ylabel_uses_trended_pollutants_units():
    from aeolus.metrics import trend
    from aeolus.viz import plot_trend

    dates = pd.date_range("2020-01-01", "2023-12-31 23:00", freq="D", tz="UTC")
    co = _frame(dates, 0.4, measurand="CO", units="mg/m3")
    no2 = _frame(dates, np.linspace(40, 20, len(dates)), measurand="NO2")
    data = pd.concat([co, no2], ignore_index=True)  # CO rows come first
    result = trend(data, "NO2", deseason=False)
    fig = plot_trend(data, result)
    assert "ug/m3" in fig.axes[0].get_ylabel()
    plt.close(fig)
