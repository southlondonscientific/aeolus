# Aeolus: download and standardise air quality data
# Copyright (C) 2025 Ruaraidh Dobson, South London Scientific

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Comprehensive tests for the aeolus.viz module.

Tests cover:
- Theme and colour utilities
- Font registration
- Data preparation and downsampling (LTTB algorithm)
- Time series plotting
- AQI card plotting
"""

from datetime import datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for testing
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

# =============================================================================
# Theme Tests
# =============================================================================


class TestColourPalette:
    """Tests for the Aeolus colour palette."""

    def test_aeolus_6_band_has_all_categories(self):
        """Test that all 6 bands are defined."""
        from aeolus.viz.theme import AEOLUS_6_BAND

        expected = [
            "good",
            "moderate",
            "unhealthy_sensitive",
            "unhealthy",
            "very_unhealthy",
            "hazardous",
        ]
        for cat in expected:
            assert cat in AEOLUS_6_BAND
            assert AEOLUS_6_BAND[cat].startswith("#")

    def test_sls_yellow_is_moderate(self):
        """Test that SLS Yellow is used for moderate category."""
        from aeolus.viz.theme import AEOLUS_6_BAND, SLS_YELLOW

        assert AEOLUS_6_BAND["moderate"] == SLS_YELLOW

    def test_uk_daqi_colours_defined(self):
        """Test that UK DAQI colours are defined."""
        from aeolus.viz.theme import UK_DAQI_COLOURS

        assert "Low" in UK_DAQI_COLOURS
        assert "Moderate" in UK_DAQI_COLOURS
        assert "High" in UK_DAQI_COLOURS
        assert "Very High" in UK_DAQI_COLOURS

    def test_us_epa_colours_defined(self):
        """Test that US EPA colours are defined."""
        from aeolus.viz.theme import US_EPA_COLOURS

        expected = [
            "Good",
            "Moderate",
            "Unhealthy for Sensitive Groups",
            "Unhealthy",
            "Very Unhealthy",
            "Hazardous",
        ]
        for cat in expected:
            assert cat in US_EPA_COLOURS

    def test_index_colours_mapping(self):
        """Test that INDEX_COLOURS contains all indices."""
        from aeolus.viz.theme import INDEX_COLOURS

        expected_indices = [
            "UK_DAQI",
            "US_EPA",
            "CHINA",
            "EU_CAQI_ROADSIDE",
            "INDIA_NAQI",
        ]
        for idx in expected_indices:
            assert idx in INDEX_COLOURS


class TestColourUtilities:
    """Tests for colour utility functions."""

    def test_needs_dark_text_yellow(self):
        """Test that yellow backgrounds need dark text."""
        from aeolus.viz.theme import SLS_YELLOW, needs_dark_text

        assert needs_dark_text(SLS_YELLOW) is True

    def test_needs_dark_text_dark_purple(self):
        """Test that dark purple backgrounds need light text."""
        from aeolus.viz.theme import AEOLUS_6_BAND, needs_dark_text

        assert needs_dark_text(AEOLUS_6_BAND["hazardous"]) is False

    def test_needs_dark_text_green(self):
        """Test that green background needs dark text."""
        from aeolus.viz.theme import AEOLUS_6_BAND, needs_dark_text

        # Emerald green is light enough to need dark text
        assert needs_dark_text(AEOLUS_6_BAND["good"]) is True

    def test_needs_dark_text_with_hash(self):
        """Test that function handles colors with or without #."""
        from aeolus.viz.theme import needs_dark_text

        assert needs_dark_text("#FFFFFF") is True
        assert needs_dark_text("FFFFFF") is True
        assert needs_dark_text("#000000") is False
        assert needs_dark_text("000000") is False

    def test_get_colour_for_category_default(self):
        """Test getting colour for a category."""
        from aeolus.viz.theme import get_colour_for_category

        colour = get_colour_for_category("Good", index="US_EPA")
        assert colour.startswith("#")

    def test_get_colour_for_category_uk_daqi(self):
        """Test getting colour for UK DAQI category."""
        from aeolus.viz.theme import get_colour_for_category

        colour = get_colour_for_category("Low", index="UK_DAQI")
        assert colour.startswith("#")

    def test_get_colour_for_value_uk_daqi(self):
        """Test getting colour for numeric UK DAQI value."""
        from aeolus.viz.theme import AEOLUS_6_BAND, get_colour_for_value

        # Band 1-3 should be green
        colour_1 = get_colour_for_value(1, index="UK_DAQI")
        colour_3 = get_colour_for_value(3, index="UK_DAQI")
        assert colour_1 == colour_3 == AEOLUS_6_BAND["good"]

        # Band 10 should be hazardous
        colour_10 = get_colour_for_value(10, index="UK_DAQI")
        assert colour_10 == AEOLUS_6_BAND["hazardous"]


class TestFontRegistration:
    """Tests for font registration."""

    def test_fonts_directory_exists(self):
        """Test that the fonts directory exists."""
        from aeolus.viz.theme import _FONTS_DIR

        assert _FONTS_DIR.exists()
        assert _FONTS_DIR.is_dir()

    def test_font_files_present(self):
        """Test that font files are present."""
        from aeolus.viz.theme import _FONTS_DIR

        ttf_files = list(_FONTS_DIR.glob("*.ttf"))
        assert len(ttf_files) >= 4  # Regular, Medium, SemiBold, Bold

    def test_ofl_license_present(self):
        """Test that OFL license is included."""
        from aeolus.viz.theme import _FONTS_DIR

        ofl_file = _FONTS_DIR / "OFL.txt"
        assert ofl_file.exists()

    def test_register_fonts_succeeds(self):
        """Test that font registration succeeds."""
        from aeolus.viz.theme import _register_fonts

        result = _register_fonts()
        assert result is True

    def test_get_font_family_returns_plex(self):
        """Test that get_font_family returns IBM Plex Sans."""
        from aeolus.viz.theme import get_font_family

        family = get_font_family()
        assert family == "IBM Plex Sans"


class TestApplyStyle:
    """Tests for apply_aeolus_style function."""

    def test_apply_style_sets_font(self):
        """Test that apply_aeolus_style sets the correct font."""
        from aeolus.viz.theme import apply_aeolus_style

        apply_aeolus_style()
        # font.family can be a string or list depending on matplotlib version
        font_family = plt.rcParams["font.family"]
        if isinstance(font_family, list):
            assert "IBM Plex Sans" in font_family
        else:
            assert font_family == "IBM Plex Sans"

    def test_apply_style_sets_dpi(self):
        """Test that apply_aeolus_style sets print DPI."""
        from aeolus.viz.theme import DPI_PRINT, apply_aeolus_style

        apply_aeolus_style()
        assert plt.rcParams["savefig.dpi"] == DPI_PRINT

    def test_apply_style_enables_grid(self):
        """Test that apply_aeolus_style enables grid."""
        from aeolus.viz.theme import apply_aeolus_style

        apply_aeolus_style()
        assert plt.rcParams["axes.grid"] is True


# =============================================================================
# LTTB Downsampling Tests
# =============================================================================


class TestLTTBDownsampling:
    """Tests for Largest Triangle Three Buckets downsampling."""

    def test_lttb_reduces_points(self):
        """Test that LTTB reduces number of points."""
        from aeolus.viz.prepare import lttb_downsample

        n = 1000
        x = np.arange(n, dtype=float)
        y = np.sin(x / 50) + np.random.random(n) * 0.1

        x_down, y_down = lttb_downsample(x, y, target_points=100)

        assert len(x_down) == 100
        assert len(y_down) == 100

    def test_lttb_preserves_endpoints(self):
        """Test that LTTB preserves first and last points."""
        from aeolus.viz.prepare import lttb_downsample

        n = 1000
        x = np.arange(n, dtype=float)
        y = np.sin(x / 50)

        x_down, y_down = lttb_downsample(x, y, target_points=100)

        assert x_down[0] == x[0]
        assert x_down[-1] == x[-1]
        assert y_down[0] == y[0]
        assert y_down[-1] == y[-1]

    def test_lttb_preserves_peaks(self):
        """Test that LTTB preserves significant peaks."""
        from aeolus.viz.prepare import lttb_downsample

        # Create data with a clear peak
        n = 1000
        x = np.arange(n, dtype=float)
        y = np.zeros(n)
        y[500] = 100.0  # Significant peak

        x_down, y_down = lttb_downsample(x, y, target_points=50)

        # The peak should be preserved
        assert 100.0 in y_down

    def test_lttb_no_reduction_if_below_target(self):
        """Test that LTTB returns original data if below target."""
        from aeolus.viz.prepare import lttb_downsample

        x = np.array([1.0, 2.0, 3.0])
        y = np.array([1.0, 4.0, 2.0])

        x_down, y_down = lttb_downsample(x, y, target_points=100)

        np.testing.assert_array_equal(x_down, x)
        np.testing.assert_array_equal(y_down, y)

    def test_lttb_minimum_3_points(self):
        """Test that LTTB returns at least 3 points."""
        from aeolus.viz.prepare import lttb_downsample

        x = np.arange(100, dtype=float)
        y = np.random.random(100)

        x_down, y_down = lttb_downsample(x, y, target_points=1)

        assert len(x_down) >= 3


class TestDownsampleTimeseries:
    """Tests for downsample_timeseries function."""

    @pytest.fixture
    def sample_df(self):
        """Create sample time series DataFrame."""
        dates = pd.date_range("2024-01-01", periods=1000, freq="h")
        return pd.DataFrame(
            {
                "date_time": dates,
                "value": np.sin(np.arange(1000) / 50) * 50 + 50,
            }
        )

    def test_downsample_reduces_points(self, sample_df):
        """Test that downsampling reduces points."""
        from aeolus.viz.prepare import downsample_timeseries

        result = downsample_timeseries(
            sample_df, "date_time", "value", target_points=100
        )

        assert len(result) == 100

    def test_downsample_preserves_columns(self, sample_df):
        """Test that downsampling preserves column names."""
        from aeolus.viz.prepare import downsample_timeseries

        result = downsample_timeseries(
            sample_df, "date_time", "value", target_points=100
        )

        assert "date_time" in result.columns
        assert "value" in result.columns

    def test_downsample_handles_nan(self, sample_df):
        """Test that downsampling handles NaN values."""
        from aeolus.viz.prepare import downsample_timeseries

        sample_df.loc[sample_df.index[:50], "value"] = np.nan

        result = downsample_timeseries(
            sample_df, "date_time", "value", target_points=100
        )

        # Should still return results, skipping NaN values
        assert len(result) <= 100
        assert not result["value"].isna().any()


# =============================================================================
# Data Preparation Tests
# =============================================================================


class TestPrepareTimeseries:
    """Tests for prepare_timeseries function."""

    @pytest.fixture
    def sample_aeolus_data(self):
        """Create sample data in aeolus format."""
        dates = pd.date_range("2024-01-01", periods=100, freq="h")
        data = []
        for dt in dates:
            data.append(
                {
                    "date_time": dt,
                    "measurand": "PM2.5",
                    "value": np.random.uniform(10, 50),
                    "units": "ug/m3",
                    "site_name": "Test Site",
                }
            )
            data.append(
                {
                    "date_time": dt,
                    "measurand": "NO2",
                    "value": np.random.uniform(20, 80),
                    "units": "ug/m3",
                    "site_name": "Test Site",
                }
            )
        return pd.DataFrame(data)

    def test_prepare_returns_spec(self, sample_aeolus_data):
        """Test that prepare_timeseries returns TimeSeriesSpec."""
        from aeolus.viz.prepare import TimeSeriesSpec, prepare_timeseries

        spec = prepare_timeseries(sample_aeolus_data)

        assert isinstance(spec, TimeSeriesSpec)
        assert spec.data is not None
        assert len(spec.pollutants) > 0

    def test_prepare_pivots_data(self, sample_aeolus_data):
        """Test that data is pivoted to wide format."""
        from aeolus.viz.prepare import prepare_timeseries

        spec = prepare_timeseries(sample_aeolus_data)

        assert "date_time" in spec.data.columns
        assert "PM2.5" in spec.data.columns
        assert "NO2" in spec.data.columns

    def test_prepare_filters_pollutants(self, sample_aeolus_data):
        """Test that specific pollutants can be selected."""
        from aeolus.viz.prepare import prepare_timeseries

        spec = prepare_timeseries(sample_aeolus_data, pollutants=["PM2.5"])

        assert spec.pollutants == ["PM2.5"]
        assert "NO2" not in spec.data.columns

    def test_prepare_extracts_units(self, sample_aeolus_data):
        """Test that units are extracted."""
        from aeolus.viz.prepare import prepare_timeseries

        spec = prepare_timeseries(sample_aeolus_data)

        assert "PM2.5" in spec.units
        assert spec.units["PM2.5"] == "ug/m3"

    def test_prepare_extracts_site_name(self, sample_aeolus_data):
        """Test that site name is extracted."""
        from aeolus.viz.prepare import prepare_timeseries

        spec = prepare_timeseries(sample_aeolus_data)

        assert spec.site_name == "Test Site"

    def test_prepare_with_downsampling(self, sample_aeolus_data):
        """Test downsampling option."""
        from aeolus.viz.prepare import prepare_timeseries

        spec = prepare_timeseries(sample_aeolus_data, downsample=50)

        assert spec.was_downsampled is True
        assert spec.display_points < spec.original_points

    def test_prepare_without_downsampling(self, sample_aeolus_data):
        """Test disabling downsampling."""
        from aeolus.viz.prepare import prepare_timeseries

        spec = prepare_timeseries(sample_aeolus_data, downsample=False)

        assert spec.was_downsampled is False
        assert spec.display_points == spec.original_points

    def test_prepare_raises_on_missing_columns(self):
        """Test that missing columns raise an error."""
        from aeolus.viz.prepare import prepare_timeseries

        bad_data = pd.DataFrame({"foo": [1, 2, 3]})

        with pytest.raises(ValueError, match="missing required columns"):
            prepare_timeseries(bad_data)

    def test_prepare_warns_on_missing_pollutants(self, sample_aeolus_data):
        """Test warning for requesting missing pollutants."""
        from aeolus.viz.prepare import prepare_timeseries

        with pytest.warns(UserWarning, match="not in data"):
            prepare_timeseries(sample_aeolus_data, pollutants=["PM2.5", "O3"])

    def test_prepare_guideline_stored(self, sample_aeolus_data):
        """Test that guideline values are stored."""
        from aeolus.viz.prepare import prepare_timeseries

        spec = prepare_timeseries(
            sample_aeolus_data,
            guideline=40,
            guideline_label="WHO AQG",
        )

        assert spec.guideline_value == 40
        assert spec.guideline_label == "WHO AQG"


class TestMultiPollutantDownsampling:
    """Tests for multi-pollutant downsampling preserving all features."""

    @pytest.fixture
    def multi_pollutant_data(self):
        """Create data where different pollutants peak at different times."""
        dates = pd.date_range("2024-01-01", periods=1000, freq="h")
        data = []
        for i, dt in enumerate(dates):
            # PM2.5 peaks at i=300
            pm25 = 20 + (80 if i == 300 else 0)
            # NO2 peaks at i=500
            no2 = 30 + (100 if i == 500 else 0)
            # O3 peaks at i=700
            o3 = 25 + (90 if i == 700 else 0)

            data.append(
                {"date_time": dt, "measurand": "PM2.5", "value": pm25, "units": "ug/m3"}
            )
            data.append(
                {"date_time": dt, "measurand": "NO2", "value": no2, "units": "ug/m3"}
            )
            data.append(
                {"date_time": dt, "measurand": "O3", "value": o3, "units": "ug/m3"}
            )

        return pd.DataFrame(data)

    def test_all_peaks_preserved(self, multi_pollutant_data):
        """Test that peaks for all pollutants are preserved."""
        from aeolus.viz.prepare import prepare_timeseries

        spec = prepare_timeseries(
            multi_pollutant_data,
            pollutants=["PM2.5", "NO2", "O3"],
            downsample=100,
        )

        # All peaks should be preserved
        assert spec.data["PM2.5"].max() == 100  # 20 + 80
        assert spec.data["NO2"].max() == 130  # 30 + 100
        assert spec.data["O3"].max() == 115  # 25 + 90


# =============================================================================
# AQI Card Preparation Tests
# =============================================================================


class TestPrepareAQICard:
    """Tests for prepare_aqi_card function."""

    def test_prepare_returns_spec(self):
        """Test that prepare_aqi_card returns AQICardSpec."""
        from aeolus.viz.prepare import AQICardSpec, prepare_aqi_card

        spec = prepare_aqi_card(45, "Moderate", index="US_EPA")

        assert isinstance(spec, AQICardSpec)
        assert spec.value == 45
        assert spec.category == "Moderate"

    def test_prepare_sets_colour(self):
        """Test that colour is set correctly."""
        from aeolus.viz.prepare import prepare_aqi_card

        spec = prepare_aqi_card(45, "Moderate", index="US_EPA")

        assert spec.colour.startswith("#")

    def test_prepare_sets_text_colour(self):
        """Test that text colour is set for contrast."""
        from aeolus.viz.prepare import prepare_aqi_card

        spec = prepare_aqi_card(45, "Moderate", index="US_EPA")

        # Moderate is yellow, needs dark text
        assert spec.text_colour != "#FFFFFF"

    def test_prepare_with_title(self):
        """Test that title is stored."""
        from aeolus.viz.prepare import prepare_aqi_card

        spec = prepare_aqi_card(45, "Moderate", title="Daily AQI")

        assert spec.title == "Daily AQI"

    def test_prepare_with_subtitle(self):
        """Test that subtitle is stored."""
        from aeolus.viz.prepare import prepare_aqi_card

        spec = prepare_aqi_card(45, "Moderate", subtitle="Based on PM2.5")

        assert spec.subtitle == "Based on PM2.5"


# =============================================================================
# Plotting Tests
# =============================================================================


class TestPlotTimeseries:
    """Tests for plot_timeseries function."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for plotting."""
        dates = pd.date_range("2024-01-01", periods=100, freq="h")
        data = []
        for dt in dates:
            data.append(
                {
                    "date_time": dt,
                    "measurand": "PM2.5",
                    "value": np.random.uniform(10, 50),
                    "units": "ug/m3",
                }
            )
        return pd.DataFrame(data)

    def test_returns_figure(self, sample_data):
        """Test that plot_timeseries returns a Figure."""
        from aeolus.viz import plot_timeseries

        fig = plot_timeseries(sample_data)

        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_applies_style_by_default(self, sample_data):
        """Test that Aeolus style is applied by default."""
        from aeolus.viz import plot_timeseries

        fig = plot_timeseries(sample_data)

        # Font should be IBM Plex Sans
        font_family = plt.rcParams["font.family"]
        if isinstance(font_family, list):
            assert "IBM Plex Sans" in font_family
        else:
            assert font_family == "IBM Plex Sans"
        plt.close(fig)

    def test_can_skip_style(self, sample_data):
        """Test that style application can be skipped."""
        from aeolus.viz import plot_timeseries

        # Reset to default first
        plt.rcdefaults()

        fig = plot_timeseries(sample_data, apply_style=False)

        # Font should not be IBM Plex Sans
        assert plt.rcParams["font.family"] != "IBM Plex Sans"
        plt.close(fig)

    def test_custom_title(self, sample_data):
        """Test that custom title is applied."""
        from aeolus.viz import plot_timeseries

        fig = plot_timeseries(sample_data, title="Test Title")

        ax = fig.axes[0]
        assert ax.get_title() == "Test Title"
        plt.close(fig)

    def test_custom_figsize(self, sample_data):
        """Test that custom figsize is applied."""
        from aeolus.viz import plot_timeseries

        fig = plot_timeseries(sample_data, figsize=(5, 3))

        width, height = fig.get_size_inches()
        assert width == 5
        assert height == 3
        plt.close(fig)

    def test_figsize_preset(self, sample_data):
        """Test that figsize presets work."""
        from aeolus.viz import plot_timeseries

        fig = plot_timeseries(sample_data, figsize="single_column")

        width, height = fig.get_size_inches()
        assert width == 3.5
        assert height == 2.5
        plt.close(fig)

    def test_with_guideline(self, sample_data):
        """Test that guideline is drawn."""
        from aeolus.viz import plot_timeseries

        fig = plot_timeseries(sample_data, guideline=25, guideline_label="WHO AQG")

        ax = fig.axes[0]
        # Should have horizontal line
        lines = [l for l in ax.get_lines() if len(l.get_xdata()) == 2]
        assert len(lines) >= 1  # At least one guideline
        plt.close(fig)

    def test_downsampling_notice(self, sample_data):
        """Test that downsampling notice is shown."""
        from aeolus.viz import plot_timeseries

        # Add more data to trigger downsampling
        dates = pd.date_range("2024-01-01", periods=5000, freq="h")
        large_data = pd.DataFrame(
            {
                "date_time": dates,
                "measurand": "PM2.5",
                "value": np.random.uniform(10, 50, size=5000),
                "units": "ug/m3",
            }
        )

        fig = plot_timeseries(large_data, downsample=1000)

        # Should have annotation about downsampling
        texts = [t.get_text() for t in fig.axes[0].texts]
        assert any("Showing" in t for t in texts)
        plt.close(fig)

    def test_can_use_existing_axes(self, sample_data):
        """Test that an existing axes can be used."""
        from aeolus.viz import plot_timeseries

        fig, ax = plt.subplots()

        result_fig = plot_timeseries(sample_data, ax=ax)

        assert result_fig is fig
        plt.close(fig)


class TestPlotAQICard:
    """Tests for plot_aqi_card function."""

    def test_returns_figure(self):
        """Test that plot_aqi_card returns a Figure."""
        from aeolus.viz import plot_aqi_card

        fig = plot_aqi_card(45, "Moderate")

        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_background_colour(self):
        """Test that background colour is set."""
        from aeolus.viz import plot_aqi_card

        fig = plot_aqi_card(45, "Moderate")

        ax = fig.axes[0]
        # Background should be set (not white)
        facecolor = ax.get_facecolor()
        assert facecolor != (1.0, 1.0, 1.0, 1.0)  # Not white
        plt.close(fig)

    def test_value_displayed(self):
        """Test that value is displayed."""
        from aeolus.viz import plot_aqi_card

        fig = plot_aqi_card(45, "Moderate")

        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert "45" in texts
        plt.close(fig)

    def test_category_displayed(self):
        """Test that category is displayed."""
        from aeolus.viz import plot_aqi_card

        fig = plot_aqi_card(45, "Moderate")

        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert any("Moderate" in t for t in texts)
        plt.close(fig)

    def test_can_hide_category(self):
        """Test that category can be hidden."""
        from aeolus.viz import plot_aqi_card

        fig = plot_aqi_card(45, "Moderate", show_category=False)

        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert not any("Moderate" in t for t in texts)
        plt.close(fig)

    def test_title_displayed(self):
        """Test that title is displayed."""
        from aeolus.viz import plot_aqi_card

        fig = plot_aqi_card(45, "Moderate", title="Daily AQI")

        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert "Daily AQI" in texts
        plt.close(fig)

    def test_custom_figsize(self):
        """Test custom figsize."""
        from aeolus.viz import plot_aqi_card

        fig = plot_aqi_card(45, "Moderate", figsize=(4, 4))

        width, height = fig.get_size_inches()
        assert width == 4
        assert height == 4
        plt.close(fig)


class TestPlotAQIComparison:
    """Tests for plot_aqi_comparison function."""

    def test_returns_figure(self):
        """Test that plot_aqi_comparison returns a Figure."""
        from aeolus.viz import plot_aqi_comparison

        fig = plot_aqi_comparison(
            before_value=67,
            before_category="Moderate",
            after_value=32,
            after_category="Good",
        )

        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_two_panels(self):
        """Test that comparison has two panels."""
        from aeolus.viz import plot_aqi_comparison

        fig = plot_aqi_comparison(
            before_value=67,
            before_category="Moderate",
            after_value=32,
            after_category="Good",
        )

        assert len(fig.axes) == 2
        plt.close(fig)

    def test_values_displayed(self):
        """Test that both values are displayed."""
        from aeolus.viz import plot_aqi_comparison

        fig = plot_aqi_comparison(
            before_value=67,
            before_category="Moderate",
            after_value=32,
            after_category="Good",
        )

        all_texts = []
        for ax in fig.axes:
            all_texts.extend([t.get_text() for t in ax.texts])

        assert "67" in all_texts
        assert "32" in all_texts
        plt.close(fig)

    def test_custom_titles(self):
        """Test custom before/after titles."""
        from aeolus.viz import plot_aqi_comparison

        fig = plot_aqi_comparison(
            before_value=67,
            before_category="Moderate",
            after_value=32,
            after_category="Good",
            before_title="Pre-intervention",
            after_title="Post-intervention",
        )

        all_texts = []
        for ax in fig.axes:
            all_texts.extend([t.get_text() for t in ax.texts])

        assert "Pre-intervention" in all_texts
        assert "Post-intervention" in all_texts
        plt.close(fig)


# =============================================================================
# Integration Tests
# =============================================================================


class TestVisualisationIntegration:
    """Integration tests for the visualisation module."""

    def test_full_workflow(self):
        """Test complete workflow from data to saved figure."""
        import os
        import tempfile

        from aeolus.viz import plot_timeseries

        # Create sample data
        dates = pd.date_range("2024-01-01", periods=200, freq="h")
        data = pd.DataFrame(
            {
                "date_time": list(dates) * 2,
                "measurand": ["PM2.5"] * 200 + ["NO2"] * 200,
                "value": list(np.random.uniform(10, 50, 200))
                + list(np.random.uniform(20, 80, 200)),
                "units": ["ug/m3"] * 400,
            }
        )

        # Create plot
        fig = plot_timeseries(
            data,
            pollutants=["PM2.5", "NO2"],
            title="Test Integration",
            guideline=40,
        )

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            fig.savefig(f.name, dpi=150)
            assert os.path.exists(f.name)
            assert os.path.getsize(f.name) > 0
            os.unlink(f.name)

        plt.close(fig)

    def test_aqi_card_workflow(self):
        """Test AQI card creation workflow."""
        import os
        import tempfile

        from aeolus.viz import plot_aqi_card

        fig = plot_aqi_card(
            value=42,
            category="Good",
            index="US_EPA",
            title="Today's AQI",
        )

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            fig.savefig(f.name, dpi=150)
            assert os.path.exists(f.name)
            assert os.path.getsize(f.name) > 0
            os.unlink(f.name)

        plt.close(fig)

    def test_module_public_api(self):
        """Test that all expected functions are in public API."""
        from aeolus import viz

        assert hasattr(viz, "plot_timeseries")
        assert hasattr(viz, "plot_aqi_card")
        assert hasattr(viz, "plot_aqi_comparison")
        assert hasattr(viz, "AEOLUS_6_BAND")
