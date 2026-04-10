"""Hypothesis property tests for the LAQN data source.

Tests that the LAQN normalisation pipeline produces conformant output
regardless of the shape or content of upstream API responses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from aeolus.sources.laqn import (
    SPECIES_MAP,
    UNITS_MAP,
    _month_ranges,
    fetch_laqn_data,
    fetch_laqn_metadata,
)
from aeolus.types import DATA_COLUMNS, METADATA_COLUMNS

pytestmark = pytest.mark.property

# ---------------------------------------------------------------------------
# Strategies for generating realistic LAQN API responses
# ---------------------------------------------------------------------------

laqn_species = st.sampled_from(list(SPECIES_MAP.keys()))

laqn_values = (
    st.floats(min_value=-10.0, max_value=2000.0, allow_nan=False, allow_infinity=False)
    .map(lambda x: f"{x:.1f}")
) | st.just("")  # empty string = missing


@st.composite
def laqn_data_points(draw, min_size=0, max_size=50):
    """Generate a list of LAQN API data point dicts."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    points = []
    for _ in range(n):
        dt = draw(
            st.datetimes(
                min_value=datetime(2020, 1, 1),
                max_value=datetime(2026, 12, 31),
            )
        )
        points.append({
            "@SpeciesCode": draw(laqn_species),
            "@MeasurementDateGMT": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "@Value": draw(laqn_values),
        })
    return points


@st.composite
def laqn_site_dicts(draw, min_size=1, max_size=20):
    """Generate a list of LAQN API site metadata dicts."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    sites = []
    for i in range(n):
        has_coords = draw(st.booleans())
        lat = draw(st.floats(min_value=51.2, max_value=51.7, allow_nan=False, allow_infinity=False))
        lon = draw(st.floats(min_value=-0.5, max_value=0.3, allow_nan=False, allow_infinity=False))
        sites.append({
            "@SiteCode": f"T{i:02d}",
            "@SiteName": f"Test Site {i}",
            "@SiteType": draw(st.sampled_from(["Urban Background", "Kerbside", "Suburban"])),
            "@Latitude": f"{lat:.6f}" if has_coords else "",
            "@Longitude": f"{lon:.6f}" if has_coords else "",
            "@DateOpened": "2020-01-01 00:00:00",
            "@DateClosed": "",
            "@LocalAuthorityCode": str(i),
            "@LocalAuthorityName": f"Borough {i}",
            "@DataOwner": "Test",
            "@DataManager": "ERG",
            "@SiteLink": "",
        })
    return sites


# ---------------------------------------------------------------------------
# _month_ranges properties
# ---------------------------------------------------------------------------


class TestMonthRangesProperties:
    """Property tests for the month-chunking helper."""

    @given(
        start=st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2029, 12, 1)),
        span_days=st.integers(min_value=1, max_value=365 * 3),
    )
    @settings(max_examples=100, deadline=None)
    def test_ranges_cover_full_span(self, start, span_days):
        """Month ranges should cover the entire requested period without gaps."""
        from datetime import timedelta
        end = start + timedelta(days=span_days)
        ranges = list(_month_ranges(start, end))

        assert len(ranges) >= 1
        assert ranges[0][0] == start
        assert ranges[-1][1] == end

        # No gaps between consecutive chunks
        for i in range(len(ranges) - 1):
            assert ranges[i][1] == ranges[i + 1][0]

    @given(
        start=st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2029, 12, 1)),
        span_days=st.integers(min_value=1, max_value=365 * 3),
    )
    @settings(max_examples=100, deadline=None)
    def test_each_chunk_within_one_month(self, start, span_days):
        """Each chunk should span at most one calendar month boundary."""
        from datetime import timedelta
        end = start + timedelta(days=span_days)
        ranges = list(_month_ranges(start, end))

        for chunk_start, chunk_end in ranges:
            assert chunk_start <= chunk_end
            # A chunk should not span more than ~31 days
            assert (chunk_end - chunk_start).days <= 31


# ---------------------------------------------------------------------------
# Metadata normalisation properties
# ---------------------------------------------------------------------------


class TestMetadataNormalisationProperties:
    """Property tests for LAQN metadata normalisation."""

    @given(sites=laqn_site_dicts(min_size=1, max_size=30))
    @settings(max_examples=50, deadline=None)
    def test_metadata_always_has_standard_columns(self, sites):
        """Output always contains standard metadata columns."""
        with patch("aeolus.sources.laqn._get_json") as mock:
            mock.return_value = {"Sites": {"Site": sites}}
            result = fetch_laqn_metadata()

        for col in METADATA_COLUMNS:
            assert col in result.columns

    @given(sites=laqn_site_dicts(min_size=1, max_size=30))
    @settings(max_examples=50, deadline=None)
    def test_metadata_excludes_missing_coordinates(self, sites):
        """Sites with empty lat/lon should be excluded."""
        with patch("aeolus.sources.laqn._get_json") as mock:
            mock.return_value = {"Sites": {"Site": sites}}
            result = fetch_laqn_metadata()

        sites_with_coords = sum(1 for s in sites if s["@Latitude"] and s["@Longitude"])
        assert len(result) == sites_with_coords

    @given(sites=laqn_site_dicts(min_size=1, max_size=30))
    @settings(max_examples=50, deadline=None)
    def test_metadata_source_network_always_laqn(self, sites):
        """source_network column should always be 'LAQN'."""
        with patch("aeolus.sources.laqn._get_json") as mock:
            mock.return_value = {"Sites": {"Site": sites}}
            result = fetch_laqn_metadata()

        if not result.empty:
            assert (result["source_network"] == "LAQN").all()

    @given(sites=laqn_site_dicts(min_size=1, max_size=30))
    @settings(max_examples=50, deadline=None)
    def test_metadata_coordinates_are_numeric(self, sites):
        """Latitude and longitude should be float type."""
        with patch("aeolus.sources.laqn._get_json") as mock:
            mock.return_value = {"Sites": {"Site": sites}}
            result = fetch_laqn_metadata()

        if not result.empty:
            assert result["latitude"].dtype == float
            assert result["longitude"].dtype == float


# ---------------------------------------------------------------------------
# Data normalisation properties
# ---------------------------------------------------------------------------


class TestDataNormalisationProperties:
    """Property tests for LAQN data normalisation."""

    @given(points=laqn_data_points(min_size=1, max_size=80))
    @settings(max_examples=50, deadline=None)
    def test_data_always_has_standard_columns(self, points):
        """Output always contains standard 8-column data schema."""
        response = {"AirQualityData": {"@SiteCode": "T01", "Data": points}}

        with patch("aeolus.sources.laqn._get_json") as mock:
            mock.return_value = response
            start = datetime(2020, 1, 1, tzinfo=timezone.utc)
            end = datetime(2020, 1, 31, tzinfo=timezone.utc)
            result = fetch_laqn_data(["T01"], start, end)

        for col in DATA_COLUMNS:
            assert col in result.columns

    @given(points=laqn_data_points(min_size=1, max_size=80))
    @settings(max_examples=50, deadline=None)
    def test_data_source_network_always_laqn(self, points):
        """source_network column should always be 'LAQN'."""
        response = {"AirQualityData": {"@SiteCode": "T01", "Data": points}}

        with patch("aeolus.sources.laqn._get_json") as mock:
            mock.return_value = response
            start = datetime(2020, 1, 1, tzinfo=timezone.utc)
            end = datetime(2020, 1, 31, tzinfo=timezone.utc)
            result = fetch_laqn_data(["T01"], start, end)

        if not result.empty:
            assert (result["source_network"] == "LAQN").all()

    @given(points=laqn_data_points(min_size=1, max_size=80))
    @settings(max_examples=50, deadline=None)
    def test_data_values_are_numeric(self, points):
        """value column should be numeric (float)."""
        response = {"AirQualityData": {"@SiteCode": "T01", "Data": points}}

        with patch("aeolus.sources.laqn._get_json") as mock:
            mock.return_value = response
            start = datetime(2020, 1, 1, tzinfo=timezone.utc)
            end = datetime(2020, 1, 31, tzinfo=timezone.utc)
            result = fetch_laqn_data(["T01"], start, end)

        if not result.empty:
            assert pd.api.types.is_float_dtype(result["value"])

    @given(points=laqn_data_points(min_size=1, max_size=80))
    @settings(max_examples=50, deadline=None)
    def test_data_timestamps_are_utc(self, points):
        """date_time column should be UTC-aware."""
        response = {"AirQualityData": {"@SiteCode": "T01", "Data": points}}

        with patch("aeolus.sources.laqn._get_json") as mock:
            mock.return_value = response
            start = datetime(2020, 1, 1, tzinfo=timezone.utc)
            end = datetime(2020, 1, 31, tzinfo=timezone.utc)
            result = fetch_laqn_data(["T01"], start, end)

        if not result.empty:
            assert result["date_time"].dt.tz is not None

    @given(points=laqn_data_points(min_size=1, max_size=80))
    @settings(max_examples=50, deadline=None)
    def test_empty_values_excluded(self, points):
        """Rows with empty @Value should never appear in output."""
        response = {"AirQualityData": {"@SiteCode": "T01", "Data": points}}

        with patch("aeolus.sources.laqn._get_json") as mock:
            mock.return_value = response
            start = datetime(2020, 1, 1, tzinfo=timezone.utc)
            end = datetime(2020, 1, 31, tzinfo=timezone.utc)
            result = fetch_laqn_data(["T01"], start, end)

        non_empty_points = sum(
            1 for p in points
            if p["@Value"].strip() != "" and p["@SpeciesCode"] in SPECIES_MAP
        )
        assert len(result) <= non_empty_points

    @given(points=laqn_data_points(min_size=1, max_size=80))
    @settings(max_examples=50, deadline=None)
    def test_co_units_are_mg_m3(self, points):
        """CO rows should have units='mg/m3', others 'ug/m3'."""
        response = {"AirQualityData": {"@SiteCode": "T01", "Data": points}}

        with patch("aeolus.sources.laqn._get_json") as mock:
            mock.return_value = response
            start = datetime(2020, 1, 1, tzinfo=timezone.utc)
            end = datetime(2020, 1, 31, tzinfo=timezone.utc)
            result = fetch_laqn_data(["T01"], start, end)

        if not result.empty:
            co = result[result["measurand"] == "CO"]
            non_co = result[result["measurand"] != "CO"]
            if not co.empty:
                assert (co["units"] == "mg/m3").all()
            if not non_co.empty:
                assert (non_co["units"] == "ug/m3").all()

    @given(points=laqn_data_points(min_size=1, max_size=80))
    @settings(max_examples=50, deadline=None)
    def test_all_measurands_are_standard_names(self, points):
        """measurand column should only contain standard aeolus names."""
        response = {"AirQualityData": {"@SiteCode": "T01", "Data": points}}
        standard_names = set(SPECIES_MAP.values())

        with patch("aeolus.sources.laqn._get_json") as mock:
            mock.return_value = response
            start = datetime(2020, 1, 1, tzinfo=timezone.utc)
            end = datetime(2020, 1, 31, tzinfo=timezone.utc)
            result = fetch_laqn_data(["T01"], start, end)

        if not result.empty:
            assert set(result["measurand"].unique()).issubset(standard_names)


# ---------------------------------------------------------------------------
# Species mapping properties
# ---------------------------------------------------------------------------


class TestSpeciesMapProperties:
    """Property tests for the species code mapping."""

    @given(code=st.sampled_from(list(SPECIES_MAP.keys())))
    def test_all_mapped_values_are_standard(self, code):
        """Every mapped value should be a recognised aeolus measurand."""
        standard = {"CO", "NO2", "O3", "PM10", "PM2.5", "SO2"}
        assert SPECIES_MAP[code] in standard

    def test_fine_and_pm25_map_to_same_value(self):
        """FINE and PM25 are both PM2.5 — mapping must be consistent."""
        assert SPECIES_MAP["FINE"] == SPECIES_MAP["PM25"] == "PM2.5"
