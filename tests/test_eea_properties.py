"""Hypothesis property tests for the EEA data source.

Tests that the EEA normalisation pipeline produces conformant output
regardless of the shape or content of upstream API responses.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from aeolus.sources.eea import (
    POLLUTANT_CODE_MAP,
    VERIFICATION_MAP,
    normalise_eea_data,
)
from aeolus.types import DATA_COLUMNS

pytestmark = pytest.mark.property

# ---------------------------------------------------------------------------
# Strategies for generating realistic EEA Parquet rows
# ---------------------------------------------------------------------------

eea_pollutant_codes = st.sampled_from(list(POLLUTANT_CODE_MAP.keys()))
eea_verification_codes = st.sampled_from([1, 2, 3])
eea_validity = st.integers(min_value=-1, max_value=3)

eea_samplingpoints = st.from_regex(
    r"[A-Z]{2}/SPO\.[A-Z]{2}\.[A-Z0-9]{4,10}", fullmatch=True
)


@st.composite
def eea_raw_dataframes(draw, min_rows=1, max_rows=50):
    """Generate a DataFrame mimicking raw EEA Parquet data before normalisation."""
    n = draw(st.integers(min_value=min_rows, max_value=max_rows))

    if n == 0:
        return pd.DataFrame(columns=[
            "Samplingpoint", "Pollutant", "Start", "Value",
            "Unit", "Validity", "Verification",
        ])

    data = {
        "Samplingpoint": draw(st.lists(eea_samplingpoints, min_size=n, max_size=n)),
        "Pollutant": draw(st.lists(eea_pollutant_codes, min_size=n, max_size=n)),
        "Start": [
            draw(st.datetimes(
                min_value=datetime(2015, 1, 1),
                max_value=datetime(2026, 12, 31),
            )).strftime("%Y-%m-%d %H:%M:%S+00:00")
            for _ in range(n)
        ],
        "Value": draw(st.lists(
            st.floats(min_value=-10.0, max_value=2000.0, allow_nan=False, allow_infinity=False),
            min_size=n, max_size=n,
        )),
        "Unit": draw(st.lists(
            st.sampled_from(["ug.m-3", "mg.m-3", "ug/m3"]),
            min_size=n, max_size=n,
        )),
        "Validity": draw(st.lists(eea_validity, min_size=n, max_size=n)),
        "Verification": draw(st.lists(eea_verification_codes, min_size=n, max_size=n)),
    }

    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Normalisation pipeline properties
# ---------------------------------------------------------------------------


class TestEEANormalisationProperties:
    """Property tests for the EEA data normalisation pipeline."""

    @given(df=eea_raw_dataframes(min_rows=1, max_rows=50))
    @settings(max_examples=50, deadline=None)
    def test_output_has_standard_columns(self, df):
        """Normalised output always has the standard 8-column schema."""
        normaliser = normalise_eea_data()
        result = normaliser(df)

        for col in DATA_COLUMNS:
            assert col in result.columns

    @given(df=eea_raw_dataframes(min_rows=1, max_rows=50))
    @settings(max_examples=50, deadline=None)
    def test_invalid_rows_filtered(self, df):
        """Rows with Validity < 1 should be excluded."""
        normaliser = normalise_eea_data()
        result = normaliser(df)

        valid_input_rows = (df["Validity"] >= 1).sum()
        assert len(result) <= valid_input_rows

    @given(df=eea_raw_dataframes(min_rows=1, max_rows=50))
    @settings(max_examples=50, deadline=None)
    def test_source_network_always_eea(self, df):
        """source_network column should always be 'EEA'."""
        normaliser = normalise_eea_data()
        result = normaliser(df)

        if not result.empty:
            assert (result["source_network"] == "EEA").all()

    @given(df=eea_raw_dataframes(min_rows=1, max_rows=50))
    @settings(max_examples=50, deadline=None)
    def test_values_are_numeric(self, df):
        """value column should be numeric."""
        normaliser = normalise_eea_data()
        result = normaliser(df)

        if not result.empty:
            assert pd.api.types.is_float_dtype(result["value"])

    @given(df=eea_raw_dataframes(min_rows=1, max_rows=50))
    @settings(max_examples=50, deadline=None)
    def test_ratification_is_valid(self, df):
        """ratification column should only contain known values."""
        normaliser = normalise_eea_data()
        result = normaliser(df)

        valid_ratifications = {"Provisional", "Verified"}
        if not result.empty:
            assert set(result["ratification"].unique()).issubset(valid_ratifications)

    @given(df=eea_raw_dataframes(min_rows=1, max_rows=50))
    @settings(max_examples=50, deadline=None)
    def test_measurands_are_standard_names(self, df):
        """measurand column should only contain mapped pollutant names."""
        normaliser = normalise_eea_data()
        result = normaliser(df)

        standard_names = set(POLLUTANT_CODE_MAP.values())
        if not result.empty:
            result_measurands = set(result["measurand"].dropna().unique())
            assert result_measurands.issubset(standard_names)

    @given(df=eea_raw_dataframes(min_rows=1, max_rows=50))
    @settings(max_examples=50, deadline=None)
    def test_units_normalised(self, df):
        """'ug.m-3' should be normalised to 'ug/m3'."""
        normaliser = normalise_eea_data()
        result = normaliser(df)

        if not result.empty:
            assert "ug.m-3" not in result["units"].values


# ---------------------------------------------------------------------------
# Mapping properties
# ---------------------------------------------------------------------------


class TestEEAMappingProperties:
    """Property tests for EEA constant mappings."""

    @given(code=st.sampled_from(list(POLLUTANT_CODE_MAP.keys())))
    def test_pollutant_map_returns_string(self, code):
        assert isinstance(POLLUTANT_CODE_MAP[code], str)

    @given(code=st.sampled_from(list(VERIFICATION_MAP.keys())))
    def test_verification_map_returns_string(self, code):
        assert isinstance(VERIFICATION_MAP[code], str)
        assert VERIFICATION_MAP[code] in {"Provisional", "Verified"}
