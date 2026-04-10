"""Hypothesis property tests for the Sonitus data source.

Tests that the Sonitus normalisation pipeline produces conformant output
regardless of the shape or content of upstream API responses.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from aeolus.sources.sonitus import (
    COLUMN_TO_MEASURAND,
    MEASURAND_COLUMNS,
    normalise_sonitus_data,
    normalise_sonitus_metadata,
    _is_air_quality_monitor,
)
from aeolus.types import DATA_COLUMNS, METADATA_COLUMNS

pytestmark = pytest.mark.property


# ---------------------------------------------------------------------------
# Strategies for generating realistic Sonitus API responses
# ---------------------------------------------------------------------------


sonitus_aq_columns = st.sampled_from(list(COLUMN_TO_MEASURAND.keys()))


@st.composite
def sonitus_data_rows(draw, min_rows=1, max_rows=50, n_pollutants=None):
    """Generate a DataFrame mimicking raw Sonitus data API response."""
    n = draw(st.integers(min_value=min_rows, max_value=max_rows))

    if n == 0:
        return pd.DataFrame(columns=["datetime"])

    # Pick 1-4 pollutant columns to include
    if n_pollutants is None:
        n_pollutants = draw(st.integers(min_value=1, max_value=4))
    all_cols = list(COLUMN_TO_MEASURAND.keys())
    selected = draw(
        st.lists(
            st.sampled_from(all_cols),
            min_size=min(n_pollutants, len(all_cols)),
            max_size=min(n_pollutants, len(all_cols)),
            unique=True,
        )
    )

    data: dict = {
        "datetime": [
            draw(st.datetimes(
                min_value=datetime(2020, 1, 1),
                max_value=datetime(2026, 12, 31),
            )).strftime("%Y-%m-%d %H:%M:%S")
            for _ in range(n)
        ],
    }

    for col in selected:
        data[col] = draw(st.lists(
            st.floats(min_value=-10.0, max_value=500.0, allow_nan=False, allow_infinity=False)
            | st.just(float("nan")),
            min_size=n, max_size=n,
        ))

    return pd.DataFrame(data)


@st.composite
def sonitus_monitor_dicts(draw, min_size=1, max_size=10):
    """Generate a list of Sonitus monitor metadata dicts."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    monitors = []
    for i in range(n):
        label_prefix = draw(st.sampled_from([
            "National Air", "Local Air", "Noise ", "Gas ",
            "Former Local Air", "Traffic Noise",
        ]))
        monitors.append({
            "serial_number": f"DCC-AQ-{i:03d}",
            "label": f"{label_prefix} Monitor {i}",
            "location": f"Test Location {i}",
            "latitude": str(draw(st.floats(
                min_value=53.2, max_value=53.5,
                allow_nan=False, allow_infinity=False,
            ))),
            "longitude": str(draw(st.floats(
                min_value=-6.5, max_value=-6.1,
                allow_nan=False, allow_infinity=False,
            ))),
        })
    return monitors


# ---------------------------------------------------------------------------
# Data normalisation properties
# ---------------------------------------------------------------------------


class TestSonitusDataNormalisationProperties:
    """Property tests for Sonitus data normalisation."""

    @given(df=sonitus_data_rows(min_rows=1, max_rows=50))
    @settings(max_examples=50, deadline=None)
    def test_output_has_standard_columns(self, df):
        """Normalised output always has the standard 8-column schema."""
        normaliser = normalise_sonitus_data("TEST01")
        result = normaliser(df)

        for col in DATA_COLUMNS:
            assert col in result.columns

    @given(df=sonitus_data_rows(min_rows=1, max_rows=50))
    @settings(max_examples=50, deadline=None)
    def test_source_network_always_sonitus(self, df):
        """source_network column should always be 'SONITUS'."""
        normaliser = normalise_sonitus_data("TEST01")
        result = normaliser(df)

        if not result.empty:
            assert (result["source_network"] == "SONITUS").all()

    @given(df=sonitus_data_rows(min_rows=1, max_rows=50))
    @settings(max_examples=50, deadline=None)
    def test_site_code_matches_input(self, df):
        """site_code should match the code passed to the normaliser."""
        normaliser = normalise_sonitus_data("XYZ123")
        result = normaliser(df)

        if not result.empty:
            assert (result["site_code"] == "XYZ123").all()

    @given(df=sonitus_data_rows(min_rows=1, max_rows=50))
    @settings(max_examples=50, deadline=None)
    def test_measurands_are_standard_names(self, df):
        """measurand column should only contain standard names."""
        normaliser = normalise_sonitus_data("TEST01")
        result = normaliser(df)

        standard_names = set(COLUMN_TO_MEASURAND.values())
        if not result.empty:
            assert set(result["measurand"].unique()).issubset(standard_names)

    @given(df=sonitus_data_rows(min_rows=1, max_rows=50))
    @settings(max_examples=50, deadline=None)
    def test_row_count_is_melted(self, df):
        """Output rows should equal input rows * number of pollutant columns."""
        normaliser = normalise_sonitus_data("TEST01")
        result = normaliser(df)

        present_cols = [c for c in df.columns if c in MEASURAND_COLUMNS]
        if present_cols and not df.empty:
            expected_max = len(df) * len(present_cols)
            assert len(result) <= expected_max

    @given(df=sonitus_data_rows(min_rows=1, max_rows=50))
    @settings(max_examples=50, deadline=None)
    def test_ratification_is_unvalidated(self, df):
        """Sonitus data should be marked as Unvalidated."""
        normaliser = normalise_sonitus_data("TEST01")
        result = normaliser(df)

        if not result.empty:
            assert (result["ratification"] == "Unvalidated").all()


# ---------------------------------------------------------------------------
# Metadata normalisation properties
# ---------------------------------------------------------------------------


class TestSonitusMetadataNormalisationProperties:
    """Property tests for Sonitus metadata normalisation."""

    @given(monitors=sonitus_monitor_dicts(min_size=1, max_size=20))
    @settings(max_examples=50, deadline=None)
    def test_metadata_has_standard_columns(self, monitors):
        """Normalised metadata always has the standard columns."""
        raw = pd.DataFrame(monitors)
        normaliser = normalise_sonitus_metadata()
        result = normaliser(raw)

        for col in METADATA_COLUMNS:
            assert col in result.columns

    @given(monitors=sonitus_monitor_dicts(min_size=1, max_size=20))
    @settings(max_examples=50, deadline=None)
    def test_metadata_source_network_always_sonitus(self, monitors):
        """source_network column should always be 'SONITUS'."""
        raw = pd.DataFrame(monitors)
        normaliser = normalise_sonitus_metadata()
        result = normaliser(raw)

        if not result.empty:
            assert (result["source_network"] == "SONITUS").all()

    @given(monitors=sonitus_monitor_dicts(min_size=1, max_size=20))
    @settings(max_examples=50, deadline=None)
    def test_metadata_coordinates_are_numeric(self, monitors):
        """Latitude and longitude should be float type."""
        raw = pd.DataFrame(monitors)
        normaliser = normalise_sonitus_metadata()
        result = normaliser(raw)

        if not result.empty:
            assert result["latitude"].dtype == float
            assert result["longitude"].dtype == float


# ---------------------------------------------------------------------------
# Monitor classification properties
# ---------------------------------------------------------------------------


class TestMonitorClassificationProperties:
    """Property tests for the air quality monitor filter."""

    @given(
        label=st.sampled_from([
            "National Air Quality Monitor 1",
            "Local Air Quality Monitor 2",
            "Gas Sensor 3",
            "Former Local Air Monitor",
        ])
    )
    def test_aq_labels_are_classified_as_aq(self, label):
        """Monitors with AQ label prefixes should be classified as AQ."""
        monitor = {"label": label, "serial_number": "X"}
        assert _is_air_quality_monitor(monitor) is True

    @given(
        label=st.sampled_from([
            "Noise Monitor 1",
            "Traffic Noise Sensor",
            "Environmental Noise",
        ])
    )
    def test_noise_labels_with_non_aq_serial_not_classified(self, label):
        """Noise monitors without AQ serial should not be classified as AQ."""
        monitor = {"label": label, "serial_number": "NOISE-001"}
        assert _is_air_quality_monitor(monitor) is False
