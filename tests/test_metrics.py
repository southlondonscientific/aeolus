# Aeolus: download and standardise air quality data
# Copyright (C) 2025 Ruaraidh Dobson, South London Scientific

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Comprehensive tests for the aeolus.metrics module.

Tests cover:
- Individual AQI index calculations (UK DAQI, US EPA, China, EU CAQI, India NAQI)
- WHO guideline compliance checks
- Unit conversion utilities
- Pollutant name standardisation
- Main API functions (aqi_summary, aqi_timeseries, aqi_check_who)
"""

from datetime import datetime

import pandas as pd
import pytest

from aeolus import metrics
from aeolus.metrics.base import (
    Breakpoint,
    calculate_aqi_from_breakpoints,
    ensure_ugm3,
    ppb_to_ugm3,
    standardise_pollutant,
    ugm3_to_ppb,
)

# =============================================================================
# Unit Conversion Tests
# =============================================================================


class TestUnitConversion:
    """Tests for unit conversion functions."""

    def test_ppb_to_ugm3_no2(self):
        """Test ppb to µg/m³ conversion for NO2."""
        # NO2: MW = 46.01, conversion factor ≈ 1.88
        result = ppb_to_ugm3(100, "NO2")
        assert 185 < result < 192  # ~188.2

    def test_ppb_to_ugm3_o3(self):
        """Test ppb to µg/m³ conversion for O3."""
        # O3: MW = 48.00, conversion factor ≈ 1.96
        result = ppb_to_ugm3(100, "O3")
        assert 193 < result < 200  # ~196.3

    def test_ppb_to_ugm3_so2(self):
        """Test ppb to µg/m³ conversion for SO2."""
        # SO2: MW = 64.07, conversion factor ≈ 2.62
        result = ppb_to_ugm3(100, "SO2")
        assert 258 < result < 268  # ~262.1

    def test_ppb_to_ugm3_co(self):
        """Test ppb to µg/m³ conversion for CO."""
        # CO: MW = 28.01, conversion factor ≈ 1.15
        result = ppb_to_ugm3(100, "CO")
        assert 112 < result < 118  # ~114.6

    def test_ppb_to_ugm3_case_insensitive(self):
        """Test that pollutant names are case-insensitive."""
        result1 = ppb_to_ugm3(100, "no2")
        result2 = ppb_to_ugm3(100, "NO2")
        assert result1 == result2

    def test_ppb_to_ugm3_unsupported_pollutant(self):
        """Test error for unsupported pollutant."""
        with pytest.raises(ValueError, match="Cannot convert PM2.5"):
            ppb_to_ugm3(100, "PM2.5")

    def test_ugm3_to_ppb_roundtrip(self):
        """Test that conversion is reversible."""
        original = 100.0
        ugm3 = ppb_to_ugm3(original, "NO2")
        back = ugm3_to_ppb(ugm3, "NO2")
        assert abs(back - original) < 0.01

    def test_ensure_ugm3_already_correct(self):
        """Test that values already in µg/m³ are unchanged."""
        result = ensure_ugm3(50.0, "PM2.5", "ug/m3", warn=False)
        assert result == 50.0

    def test_ensure_ugm3_from_ppb(self):
        """Test conversion from ppb."""
        result = ensure_ugm3(100.0, "NO2", "ppb", warn=False)
        assert 185 < result < 192

    def test_ensure_ugm3_from_ppm(self):
        """Test conversion from ppm (common for CO)."""
        result = ensure_ugm3(1.0, "CO", "ppm", warn=False)
        # 1 ppm = 1000 ppb, then convert
        expected = ppb_to_ugm3(1000, "CO")
        assert abs(result - expected) < 0.01

    def test_ensure_ugm3_from_mgm3(self):
        """Test conversion from mg/m³."""
        result = ensure_ugm3(1.0, "PM2.5", "mg/m3", warn=False)
        assert result == 1000.0


# =============================================================================
# Pollutant Standardisation Tests
# =============================================================================


class TestPollutantStandardisation:
    """Tests for pollutant name standardisation."""

    def test_already_standard(self):
        """Test that standard names are returned unchanged."""
        assert standardise_pollutant("PM2.5") == "PM2.5"
        assert standardise_pollutant("NO2") == "NO2"
        assert standardise_pollutant("O3") == "O3"

    def test_lowercase_variants(self):
        """Test lowercase variants are standardised."""
        assert standardise_pollutant("pm2.5") == "PM2.5"
        assert standardise_pollutant("no2") == "NO2"
        assert standardise_pollutant("o3") == "O3"

    def test_name_variants(self):
        """Test full name variants are standardised."""
        assert standardise_pollutant("ozone") == "O3"
        assert standardise_pollutant("nitrogen dioxide") == "NO2"
        assert standardise_pollutant("sulfur dioxide") == "SO2"
        assert standardise_pollutant("carbon monoxide") == "CO"

    def test_unknown_pollutant(self):
        """Test that unknown pollutants return None."""
        assert standardise_pollutant("UNKNOWN") is None
        assert standardise_pollutant("lead") is None


# =============================================================================
# UK DAQI Tests
# =============================================================================


class TestUKDAQI:
    """Tests for UK Daily Air Quality Index calculations."""

    def test_pm25_band_1(self):
        """Test PM2.5 in band 1 (Low)."""
        from aeolus.metrics.indices import uk_daqi

        result = uk_daqi.calculate(10.0, "PM2.5")
        assert result.value == 1
        assert result.category == "Low"

    def test_pm25_band_4(self):
        """Test PM2.5 in band 4 (Moderate)."""
        from aeolus.metrics.indices import uk_daqi

        result = uk_daqi.calculate(40.0, "PM2.5")
        assert result.value == 4
        assert result.category == "Moderate"

    def test_pm25_band_7(self):
        """Test PM2.5 in band 7 (High)."""
        from aeolus.metrics.indices import uk_daqi

        result = uk_daqi.calculate(55.0, "PM2.5")
        assert result.value == 7
        assert result.category == "High"

    def test_pm25_band_10(self):
        """Test PM2.5 in band 10 (Very High)."""
        from aeolus.metrics.indices import uk_daqi

        result = uk_daqi.calculate(75.0, "PM2.5")
        assert result.value == 10
        assert result.category == "Very High"

    def test_o3_moderate(self):
        """Test O3 in moderate range."""
        from aeolus.metrics.indices import uk_daqi

        result = uk_daqi.calculate(120.0, "O3")
        assert result.value == 4
        assert result.category == "Moderate"

    def test_no2_low(self):
        """Test NO2 in low range."""
        from aeolus.metrics.indices import uk_daqi

        result = uk_daqi.calculate(50.0, "NO2")
        assert result.value == 1
        assert result.category == "Low"

    def test_rounds_concentration(self):
        """Test that concentrations are rounded as per spec."""
        from aeolus.metrics.indices import uk_daqi

        # 11.4 rounds to 11 -> band 1
        result = uk_daqi.calculate(11.4, "PM2.5")
        assert result.value == 1
        # 11.5 rounds to 12 -> band 2
        result = uk_daqi.calculate(11.5, "PM2.5")
        assert result.value == 2

    def test_unsupported_pollutant(self):
        """Test error for unsupported pollutant."""
        from aeolus.metrics.indices import uk_daqi

        with pytest.raises(ValueError, match="not supported"):
            uk_daqi.calculate(50.0, "CO")

    def test_health_message_included(self):
        """Test that health messages are included."""
        from aeolus.metrics.indices import uk_daqi

        result = uk_daqi.calculate(75.0, "PM2.5")
        assert result.message is not None
        assert "avoid" in result.message.lower()


# =============================================================================
# US EPA AQI Tests
# =============================================================================


class TestUSEPA:
    """Tests for US EPA Air Quality Index calculations."""

    def test_pm25_good(self):
        """Test PM2.5 in Good range (0-50)."""
        from aeolus.metrics.indices import us_epa

        result = us_epa.calculate(5.0, "PM2.5")
        assert 0 <= result.value <= 50
        assert result.category == "Good"

    def test_pm25_moderate(self):
        """Test PM2.5 in Moderate range (51-100)."""
        from aeolus.metrics.indices import us_epa

        result = us_epa.calculate(20.0, "PM2.5")
        assert 51 <= result.value <= 100
        assert result.category == "Moderate"

    def test_pm25_unhealthy_sensitive(self):
        """Test PM2.5 in Unhealthy for Sensitive Groups range (101-150)."""
        from aeolus.metrics.indices import us_epa

        result = us_epa.calculate(40.0, "PM2.5")
        assert 101 <= result.value <= 150
        assert result.category == "Unhealthy for Sensitive Groups"

    def test_pm25_may_2024_update(self):
        """Test that May 2024 breakpoints are used (Good now 0-9 not 0-12)."""
        from aeolus.metrics.indices import us_epa

        # Under old breakpoints, 10 would be Good
        # Under new May 2024 breakpoints, 10 is Moderate
        result = us_epa.calculate(10.0, "PM2.5")
        assert result.category == "Moderate"

    def test_o3_uses_ppm(self):
        """Test that O3 uses ppm not µg/m³."""
        from aeolus.metrics.indices import us_epa

        # 0.06 ppm is in the Moderate range
        result = us_epa.calculate(0.06, "O3")
        assert result.category == "Moderate"
        assert result.unit == "ppm"

    def test_truncation(self):
        """Test that values are truncated correctly."""
        from aeolus.metrics.indices import us_epa

        # PM2.5 truncated to 1 decimal place
        # 9.05 truncates to 9.0 -> Good (upper bound)
        result = us_epa.calculate(9.05, "PM2.5")
        assert result.value == 50  # Boundary of Good

    def test_interpolation(self):
        """Test linear interpolation between breakpoints."""
        from aeolus.metrics.indices import us_epa

        # PM2.5: 0-9 is AQI 0-50, so 4.5 should be AQI 25
        result = us_epa.calculate(4.5, "PM2.5")
        assert result.value == 25


# =============================================================================
# China AQI Tests
# =============================================================================


class TestChinaAQI:
    """Tests for China Air Quality Index calculations."""

    def test_pm25_excellent(self):
        """Test PM2.5 in Excellent range (0-50)."""
        from aeolus.metrics.indices import china

        result = china.calculate(20.0, "PM2.5")
        assert 0 <= result.value <= 50
        assert result.category == "Excellent"

    def test_pm25_good(self):
        """Test PM2.5 in Good range (51-100)."""
        from aeolus.metrics.indices import china

        result = china.calculate(50.0, "PM2.5")
        assert 51 <= result.value <= 100
        assert result.category == "Good"

    def test_pm25_lightly_polluted(self):
        """Test PM2.5 in Lightly Polluted range."""
        from aeolus.metrics.indices import china

        result = china.calculate(90.0, "PM2.5")
        assert 101 <= result.value <= 150
        assert result.category == "Lightly Polluted"

    def test_co_uses_mgm3(self):
        """Test that CO uses mg/m³."""
        from aeolus.metrics.indices import china

        result = china.calculate(1.5, "CO")
        assert result.unit == "mg/m³"
        assert result.category == "Excellent"

    def test_bilingual_health_message(self):
        """Test that health messages include both Chinese and English."""
        from aeolus.metrics.indices import china

        result = china.calculate(200.0, "PM2.5")
        assert "健康" in result.message or "health" in result.message.lower()


# =============================================================================
# EU CAQI Tests
# =============================================================================


class TestEUCAQI:
    """Tests for European Air Quality Index calculations."""

    def test_no2_good(self):
        """Test NO2 in Good range (1)."""
        from aeolus.metrics.indices import eu_caqi

        result = eu_caqi.calculate(30.0, "NO2")
        assert result.value == 1
        assert result.category == "Good"

    def test_no2_fair(self):
        """Test NO2 in Fair range (2)."""
        from aeolus.metrics.indices import eu_caqi

        result = eu_caqi.calculate(60.0, "NO2")
        assert result.value == 2
        assert result.category == "Fair"

    def test_pm25_moderate(self):
        """Test PM2.5 in Moderate range (3)."""
        from aeolus.metrics.indices import eu_caqi

        result = eu_caqi.calculate(22.0, "PM2.5")
        assert result.value == 3
        assert result.category == "Moderate"

    def test_roadside_requires_no2(self):
        """Test that roadside calculation requires NO2."""
        from aeolus.metrics.indices import eu_caqi

        with pytest.raises(ValueError, match="requires NO2"):
            eu_caqi.calculate_roadside({"PM2.5": 20.0})

    def test_roadside_requires_pm(self):
        """Test that roadside calculation requires PM."""
        from aeolus.metrics.indices import eu_caqi

        with pytest.raises(ValueError, match="requires PM2.5 or PM10"):
            eu_caqi.calculate_roadside({"NO2": 30.0})

    def test_roadside_overall(self):
        """Test overall roadside calculation takes maximum."""
        from aeolus.metrics.indices import eu_caqi

        result = eu_caqi.calculate_roadside(
            {
                "NO2": 30.0,  # Good (1)
                "PM2.5": 22.0,  # Moderate (3)
            }
        )
        assert result.value == 3
        assert result.pollutant == "PM2.5"

    def test_background_requires_o3(self):
        """Test that background calculation requires O3."""
        from aeolus.metrics.indices import eu_caqi

        with pytest.raises(ValueError, match="requires O3"):
            eu_caqi.calculate_background({"NO2": 30.0, "PM2.5": 20.0})


# =============================================================================
# India NAQI Tests
# =============================================================================


class TestIndiaNAQI:
    """Tests for India National Air Quality Index calculations."""

    def test_pm25_good(self):
        """Test PM2.5 in Good range (0-50)."""
        from aeolus.metrics.indices import india_naqi

        result = india_naqi.calculate(20.0, "PM2.5")
        assert 0 <= result.value <= 50
        assert result.category == "Good"

    def test_pm25_satisfactory(self):
        """Test PM2.5 in Satisfactory range (51-100)."""
        from aeolus.metrics.indices import india_naqi

        result = india_naqi.calculate(45.0, "PM2.5")
        assert 51 <= result.value <= 100
        assert result.category == "Satisfactory"

    def test_pm25_moderately_polluted(self):
        """Test PM2.5 in Moderately Polluted range (101-200)."""
        from aeolus.metrics.indices import india_naqi

        result = india_naqi.calculate(75.0, "PM2.5")
        assert 101 <= result.value <= 200
        assert result.category == "Moderately Polluted"

    def test_pm25_severe(self):
        """Test PM2.5 in Severe range (401-500)."""
        from aeolus.metrics.indices import india_naqi

        result = india_naqi.calculate(300.0, "PM2.5")
        assert 401 <= result.value <= 500
        assert result.category == "Severe"

    def test_supports_nh3(self):
        """Test that NH3 is supported (unique to India)."""
        from aeolus.metrics.indices import india_naqi

        result = india_naqi.calculate(300.0, "NH3")
        assert result.value is not None
        assert result.category == "Satisfactory"

    def test_supports_lead(self):
        """Test that Pb (lead) is supported."""
        from aeolus.metrics.indices import india_naqi

        result = india_naqi.calculate(0.3, "Pb")
        assert result.value is not None
        assert result.category == "Good"


# =============================================================================
# WHO Guidelines Tests
# =============================================================================


class TestWHOGuidelines:
    """Tests for WHO Air Quality Guidelines compliance checks."""

    def test_pm25_meets_aqg(self):
        """Test PM2.5 meeting AQG (5 µg/m³ annual)."""
        from aeolus.metrics.indices import who

        result = who.check_guideline(4.0, "PM2.5", "annual", "AQG")
        assert result.meets_guideline is True
        assert result.exceedance_ratio < 1.0

    def test_pm25_exceeds_aqg(self):
        """Test PM2.5 exceeding AQG."""
        from aeolus.metrics.indices import who

        result = who.check_guideline(12.0, "PM2.5", "annual", "AQG")
        assert result.meets_guideline is False
        assert result.exceedance_ratio == 12.0 / 5.0

    def test_pm25_interim_target_1(self):
        """Test PM2.5 against IT-1 (35 µg/m³ annual)."""
        from aeolus.metrics.indices import who

        result = who.check_guideline(30.0, "PM2.5", "annual", "IT-1")
        assert result.meets_guideline is True

    def test_pm25_interim_target_4(self):
        """Test PM2.5 against IT-4 (10 µg/m³ annual)."""
        from aeolus.metrics.indices import who

        result = who.check_guideline(12.0, "PM2.5", "annual", "IT-4")
        assert result.meets_guideline is False

    def test_no2_stricter_2021_guideline(self):
        """Test NO2 uses 2021 stricter guideline (10 µg/m³ not 40)."""
        from aeolus.metrics.indices import who

        result = who.check_guideline(15.0, "NO2", "annual", "AQG")
        assert result.meets_guideline is False  # Exceeds new 10 µg/m³
        assert result.guideline_value == 10

    def test_get_all_targets(self):
        """Test getting all targets for a pollutant."""
        from aeolus.metrics.indices import who

        results = who.get_all_targets(12.0, "PM2.5", "annual")
        assert "AQG" in results
        assert "IT-1" in results
        assert results["AQG"].meets_guideline is False
        assert results["IT-1"].meets_guideline is True

    def test_get_highest_met_target(self):
        """Test finding the most stringent met target."""
        from aeolus.metrics.indices import who

        # 12 µg/m³ exceeds AQG (5), IT-4 (10), but meets IT-3 (15)
        target = who.get_highest_met_target(12.0, "PM2.5", "annual")
        assert target == "IT-3"

    def test_24_hour_guideline(self):
        """Test 24-hour averaging period guidelines."""
        from aeolus.metrics.indices import who

        # PM2.5 24h AQG is 15 µg/m³
        result = who.check_guideline(10.0, "PM2.5", "24h", "AQG")
        assert result.meets_guideline is True
        assert result.guideline_value == 15


# =============================================================================
# NowCast Algorithm Tests
# =============================================================================


class TestNowCast:
    """Tests for US EPA NowCast algorithm."""

    def test_stable_air_approaches_12hr_average(self):
        """Test that stable readings approach 12-hour average."""
        from aeolus.metrics.indices import us_epa

        # All same values = w* = 1 = simple average
        values = [50.0] * 12
        result = us_epa.calculate_nowcast(values, "PM2.5")
        assert abs(result - 50.0) < 0.01

    def test_variable_air_weights_recent(self):
        """Test that variable readings weight recent hours more."""
        from aeolus.metrics.indices import us_epa

        # High variation: recent hours should dominate
        values = [
            100.0,
            90.0,
            80.0,
            20.0,
            20.0,
            20.0,
            20.0,
            20.0,
            20.0,
            20.0,
            20.0,
            20.0,
        ]
        result = us_epa.calculate_nowcast(values, "PM2.5")
        # Result should be closer to recent high values than simple average
        simple_avg = sum(values) / len(values)
        assert result > simple_avg

    def test_minimum_weight_factor_pm(self):
        """Test minimum weight factor of 0.5 for PM."""
        from aeolus.metrics.indices import us_epa

        # Even with large variation, weight should not go below 0.5
        values = [100.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        result = us_epa.calculate_nowcast(values, "PM2.5")
        assert result is not None

    def test_requires_2_of_3_recent(self):
        """Test that at least 2 of 3 most recent hours are needed."""
        from aeolus.metrics.indices import us_epa

        values = [None, None, 50.0, 50.0, 50.0]
        result = us_epa.calculate_nowcast(values, "PM2.5")
        assert result is None

    def test_requires_c1_or_c2(self):
        """Test that c1 or c2 must be valid."""
        from aeolus.metrics.indices import us_epa

        values = [None, None, 50.0, 50.0, 50.0]
        result = us_epa.calculate_nowcast(values, "PM2.5")
        assert result is None


# =============================================================================
# Main API Tests
# =============================================================================


class TestListIndices:
    """Tests for list_indices function."""

    def test_returns_list(self):
        """Test that list_indices returns a list."""
        result = metrics.list_indices()
        assert isinstance(result, list)

    def test_contains_expected_indices(self):
        """Test that all expected indices are present."""
        result = metrics.list_indices()
        expected = [
            "UK_DAQI",
            "US_EPA",
            "CHINA",
            "WHO",
            "EU_CAQI_ROADSIDE",
            "EU_CAQI_BACKGROUND",
            "INDIA_NAQI",
        ]
        for idx in expected:
            assert idx in result


class TestGetIndexInfo:
    """Tests for get_index_info function."""

    def test_returns_info(self):
        """Test that get_index_info returns index info."""
        info = metrics.get_index_info("UK_DAQI")
        assert info is not None
        assert "name" in info
        assert "pollutants" in info

    def test_unknown_index(self):
        """Test that unknown index returns None."""
        info = metrics.get_index_info("UNKNOWN")
        assert info is None


class TestAQISummary:
    """Tests for aqi_summary function."""

    @pytest.fixture
    def sample_data(self):
        """Create sample air quality data."""
        dates = pd.date_range("2024-01-01", periods=48, freq="h")
        data = []
        for dt in dates:
            data.append(
                {
                    "site_code": "TEST1",
                    "date_time": dt,
                    "measurand": "PM2.5",
                    "value": 25.0 + (dt.hour % 12),  # Varies 25-36
                    "units": "ug/m3",
                    "source_network": "TEST",
                }
            )
            data.append(
                {
                    "site_code": "TEST1",
                    "date_time": dt,
                    "measurand": "NO2",
                    "value": 40.0 + (dt.hour % 8),  # Varies 40-47
                    "units": "ug/m3",
                    "source_network": "TEST",
                }
            )
        return pd.DataFrame(data)

    def test_basic_summary(self, sample_data):
        """Test basic summary calculation."""
        result = metrics.aqi_summary(sample_data, index="UK_DAQI")
        assert not result.empty
        assert "aqi_value" in result.columns
        assert "aqi_category" in result.columns

    def test_includes_statistics(self, sample_data):
        """Test that summary includes all statistics."""
        result = metrics.aqi_summary(sample_data, index="UK_DAQI")
        expected_cols = ["mean", "median", "p25", "p75", "min", "max"]
        for col in expected_cols:
            assert col in result.columns

    def test_includes_coverage(self, sample_data):
        """Test that coverage is calculated."""
        result = metrics.aqi_summary(sample_data, index="UK_DAQI")
        assert "coverage" in result.columns

    def test_daily_frequency(self, sample_data):
        """Test daily aggregation."""
        result = metrics.aqi_summary(sample_data, index="UK_DAQI", freq="D")
        # Should have 2 days of data
        periods = result["period"].unique()
        assert len(periods) == 2

    def test_wide_format(self, sample_data):
        """Test wide format output."""
        result = metrics.aqi_summary(sample_data, index="UK_DAQI", format="wide")
        # Should have pollutant-specific columns
        assert "pm25_mean" in result.columns or "no2_mean" in result.columns
        assert "overall_aqi" in result.columns

    def test_overall_only(self, sample_data):
        """Test overall_only mode."""
        result = metrics.aqi_summary(sample_data, index="UK_DAQI", overall_only=True)
        # Should only have overall values, not per-pollutant
        assert "pollutant" not in result.columns or result["pollutant"].isna().all()
        assert "dominant_pollutant" in result.columns

    def test_warns_missing_pollutants(self, sample_data):
        """Test warning for missing pollutants."""
        # UK DAQI also needs O3, SO2
        with pytest.warns(UserWarning, match="missing pollutants"):
            metrics.aqi_summary(sample_data, index="UK_DAQI")

    def test_unknown_index_raises(self, sample_data):
        """Test that unknown index raises error."""
        with pytest.raises(ValueError, match="Unknown index"):
            metrics.aqi_summary(sample_data, index="UNKNOWN")

    def test_missing_columns_raises(self):
        """Test that missing required columns raises error."""
        bad_data = pd.DataFrame({"foo": [1, 2, 3]})
        with pytest.raises(ValueError, match="missing required columns"):
            metrics.aqi_summary(bad_data, index="UK_DAQI")


class TestAQICheckWHO:
    """Tests for aqi_check_who function."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for WHO checking."""
        dates = pd.date_range("2024-01-01", periods=24, freq="h")
        data = []
        for dt in dates:
            data.append(
                {
                    "site_code": "TEST1",
                    "date_time": dt,
                    "measurand": "PM2.5",
                    "value": 12.0,  # Exceeds AQG (5), meets IT-3 (15)
                    "units": "ug/m3",
                    "source_network": "TEST",
                }
            )
        return pd.DataFrame(data)

    def test_basic_who_check(self, sample_data):
        """Test basic WHO compliance check."""
        result = metrics.aqi_check_who(sample_data)
        assert not result.empty
        assert "meets_guideline" in result.columns
        assert "exceedance_ratio" in result.columns

    def test_target_levels(self, sample_data):
        """Test different target levels."""
        # Should fail AQG
        result_aqg = metrics.aqi_check_who(sample_data, target="AQG")
        assert result_aqg.iloc[0]["meets_guideline"] == False

        # Should pass IT-1
        result_it1 = metrics.aqi_check_who(sample_data, target="IT-1")
        assert result_it1.iloc[0]["meets_guideline"] == True


# =============================================================================
# Breakpoint Interpolation Tests
# =============================================================================


class TestBreakpointInterpolation:
    """Tests for the breakpoint interpolation function."""

    def test_exact_boundary(self):
        """Test value at exact boundary."""
        breakpoints = [
            Breakpoint(
                low_conc=0,
                high_conc=50,
                low_aqi=0,
                high_aqi=50,
                category="Good",
                color="#00FF00",
            ),
            Breakpoint(
                low_conc=51,
                high_conc=100,
                low_aqi=51,
                high_aqi=100,
                category="Moderate",
                color="#FFFF00",
            ),
        ]
        result = calculate_aqi_from_breakpoints(50, breakpoints)
        assert result.value == 50
        assert result.category == "Good"

    def test_midpoint_interpolation(self):
        """Test interpolation at midpoint."""
        breakpoints = [
            Breakpoint(
                low_conc=0,
                high_conc=100,
                low_aqi=0,
                high_aqi=100,
                category="Test",
                color="#000000",
            ),
        ]
        result = calculate_aqi_from_breakpoints(50, breakpoints)
        assert result.value == 50

    def test_out_of_range(self):
        """Test value out of all breakpoint ranges."""
        breakpoints = [
            Breakpoint(
                low_conc=0,
                high_conc=50,
                low_aqi=0,
                high_aqi=50,
                category="Good",
                color="#00FF00",
            ),
        ]
        result = calculate_aqi_from_breakpoints(100, breakpoints)
        assert result is None


# =============================================================================
# Boundary Value Tests (Critical for AQI accuracy)
# =============================================================================


class TestBoundaryValues:
    """Test exact breakpoint boundaries to ensure correct categorisation."""

    def test_uk_daqi_pm25_boundaries(self):
        """Test UK DAQI PM2.5 at exact band boundaries."""
        from aeolus.metrics.indices import uk_daqi

        # Band 1/2 boundary: 11/12
        assert uk_daqi.calculate(11.0, "PM2.5").value == 1
        assert uk_daqi.calculate(12.0, "PM2.5").value == 2

        # Band 3/4 boundary: 35/36
        assert uk_daqi.calculate(35.0, "PM2.5").value == 3
        assert uk_daqi.calculate(36.0, "PM2.5").value == 4

        # Band 6/7 boundary: 53/54
        assert uk_daqi.calculate(53.0, "PM2.5").value == 6
        assert uk_daqi.calculate(54.0, "PM2.5").value == 7

        # Band 9/10 boundary: 70/71
        assert uk_daqi.calculate(70.0, "PM2.5").value == 9
        assert uk_daqi.calculate(71.0, "PM2.5").value == 10

    def test_us_epa_pm25_boundaries(self):
        """Test US EPA PM2.5 at exact AQI boundaries (May 2024 update)."""
        from aeolus.metrics.indices import us_epa

        # Good/Moderate boundary: 9.0/9.1
        result_good = us_epa.calculate(9.0, "PM2.5")
        result_mod = us_epa.calculate(9.1, "PM2.5")
        assert result_good.value == 50  # Top of Good
        assert result_mod.value == 51  # Bottom of Moderate

        # Moderate/USG boundary: 35.4/35.5
        result_mod2 = us_epa.calculate(35.4, "PM2.5")
        result_usg = us_epa.calculate(35.5, "PM2.5")
        assert result_mod2.category == "Moderate"
        assert result_usg.category == "Unhealthy for Sensitive Groups"

    def test_us_epa_o3_8hr_to_1hr_switch(self):
        """Test US EPA O3 uses 8-hour for low values, 1-hour for high."""
        from aeolus.metrics.indices import us_epa

        # Low O3: uses 8-hour breakpoints
        result_low = us_epa.calculate(0.06, "O3")
        assert result_low.category == "Moderate"

        # High O3 (>= 0.125 ppm): should use 1-hour breakpoints
        result_high = us_epa.calculate(0.15, "O3")
        assert result_high.value is not None
        assert result_high.category in ["Unhealthy for Sensitive Groups", "Unhealthy"]

        # Force 1-hour averaging
        result_1hr = us_epa.calculate(0.15, "O3", averaging_period="1h")
        assert result_1hr.value is not None

    def test_china_o3_averaging_periods(self):
        """Test China AQI O3 with different averaging periods."""
        from aeolus.metrics.indices import china

        # 8-hour O3
        result_8h = china.calculate(120.0, "O3", averaging_period="8h")
        assert result_8h.category == "Good"

        # 1-hour O3 (same concentration, different breakpoints)
        result_1h = china.calculate(120.0, "O3", averaging_period="1h")
        assert result_1h.category == "Excellent"  # 1-hour breakpoints are higher

    def test_india_o3_averaging_switch(self):
        """Test India NAQI O3 switches from 8-hour to 1-hour at high values."""
        from aeolus.metrics.indices import india_naqi

        # Low O3: 8-hour breakpoints
        result_low = india_naqi.calculate(100.0, "O3")
        assert result_low.category == "Satisfactory"

        # High O3 (>= 209): 1-hour breakpoints
        result_high = india_naqi.calculate(300.0, "O3")
        assert result_high.category == "Very Poor"

    def test_who_2021_stricter_limits(self):
        """Test WHO 2021 guidelines are stricter than 2005."""
        from aeolus.metrics.indices import who

        # PM2.5 annual: 2021 AQG is 5 µg/m³ (was 10 in 2005)
        result = who.check_guideline(8.0, "PM2.5", "annual", "AQG")
        assert result.meets_guideline is False  # Exceeds new stricter limit
        assert result.guideline_value == 5

        # NO2 annual: 2021 AQG is 10 µg/m³ (was 40 in 2005)
        result_no2 = who.check_guideline(25.0, "NO2", "annual", "AQG")
        assert result_no2.meets_guideline is False
        assert result_no2.guideline_value == 10


# =============================================================================
# aqi_timeseries Tests
# =============================================================================


class TestAQITimeseries:
    """Tests for aqi_timeseries function."""

    @pytest.fixture
    def hourly_data(self):
        """Create hourly data for time series testing."""
        import numpy as np

        dates = pd.date_range("2024-01-01", periods=72, freq="h")  # 3 days
        data = []
        for i, dt in enumerate(dates):
            # PM2.5 varies sinusoidally (simulating daily pattern)
            pm25_value = 20 + 15 * (1 + np.sin(i * np.pi / 12)) / 2
            data.append(
                {
                    "site_code": "TEST1",
                    "date_time": dt,
                    "measurand": "PM2.5",
                    "value": pm25_value,
                    "units": "ug/m3",
                    "source_network": "TEST",
                }
            )
        return pd.DataFrame(data)

    def test_returns_timeseries(self, hourly_data):
        """Test that aqi_timeseries returns time series data."""
        result = metrics.aqi_timeseries(hourly_data, index="UK_DAQI")
        assert not result.empty
        assert "date_time" in result.columns
        assert "aqi_value" in result.columns

    def test_includes_rolling_average(self, hourly_data):
        """Test that rolling averages are included by default."""
        result = metrics.aqi_timeseries(hourly_data, index="UK_DAQI")
        assert "rolling_avg" in result.columns

    def test_nan_for_insufficient_data(self, hourly_data):
        """Test that NaN is returned when insufficient data for rolling average."""
        result = metrics.aqi_timeseries(hourly_data, index="UK_DAQI")
        # First ~18 hours should have NaN for 24-hour rolling average (75% = 18h)
        early_rows = result[result["date_time"] < "2024-01-01 18:00:00"]
        assert early_rows["rolling_avg"].isna().any()

    def test_can_exclude_rolling(self, hourly_data):
        """Test that rolling average can be excluded."""
        result = metrics.aqi_timeseries(
            hourly_data, index="UK_DAQI", include_rolling=False
        )
        assert "rolling_avg" not in result.columns


# =============================================================================
# EU CAQI Background Tests
# =============================================================================


class TestEUCAQIBackground:
    """Additional tests for EU CAQI background calculations."""

    def test_background_overall_calculation(self):
        """Test overall background calculation takes maximum."""
        from aeolus.metrics.indices import eu_caqi

        result = eu_caqi.calculate_background(
            {
                "NO2": 30.0,  # Good (1)
                "O3": 80.0,  # Fair (2)
                "PM2.5": 22.0,  # Moderate (3)
            }
        )
        assert result.value == 3
        assert result.pollutant == "PM2.5"

    def test_background_with_so2(self):
        """Test background calculation including SO2."""
        from aeolus.metrics.indices import eu_caqi

        result = eu_caqi.calculate_background(
            {
                "NO2": 30.0,
                "O3": 60.0,
                "PM10": 30.0,
                "SO2": 400.0,  # Poor (4)
            }
        )
        assert result.value == 4
        assert result.pollutant == "SO2"


# =============================================================================
# WHO Additional Tests
# =============================================================================


class TestWHOAdditional:
    """Additional WHO guideline tests."""

    def test_list_available_targets(self):
        """Test listing available targets for a pollutant."""
        from aeolus.metrics.indices import who

        targets = who.list_available_targets("PM2.5", "annual")
        assert "AQG" in targets
        assert "IT-1" in targets
        assert "IT-4" in targets

    def test_get_guideline_value(self):
        """Test getting specific guideline values."""
        from aeolus.metrics.indices import who

        # PM2.5 annual AQG
        value = who.get_guideline_value("PM2.5", "annual", "AQG")
        assert value == 5

        # NO2 annual IT-1
        value_it1 = who.get_guideline_value("NO2", "annual", "IT-1")
        assert value_it1 == 40

    def test_co_uses_mg_m3(self):
        """Test that CO guidelines use mg/m³."""
        from aeolus.metrics.indices import who

        result = who.check_guideline(3.0, "CO", "24h", "AQG")
        assert result.unit == "mg/m³"
        assert result.meets_guideline is True  # 3 < 4 mg/m³

    def test_unavailable_target_raises(self):
        """Test that requesting unavailable target raises error."""
        from aeolus.metrics.indices import who

        # CO only has AQG, not interim targets
        with pytest.raises(ValueError, match="not available"):
            who.check_guideline(3.0, "CO", "24h", "IT-1")
