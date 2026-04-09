"""Hypothesis property-based tests for aeolus.metrics.base."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from aeolus.metrics.base import (
    MOLECULAR_WEIGHTS,
    POLLUTANT_ALIASES,
    Breakpoint,
    calculate_aqi_from_breakpoints,
    calculate_aqi_from_breakpoints_array,
    ensure_ugm3,
    ppb_to_ugm3,
    standardise_pollutant,
    ugm3_to_ppb,
)

pytestmark = pytest.mark.property

# Shared strategies
reasonable_conc = st.floats(
    min_value=0.001, max_value=50000.0, allow_nan=False, allow_infinity=False
)
gas_pollutant = st.sampled_from(list(MOLECULAR_WEIGHTS.keys()))


# ── Unit conversion round-trips ──────────────────────────────────────────────


class TestUnitConversionRoundtrip:
    @given(conc=reasonable_conc, poll=gas_pollutant)
    def test_ppb_roundtrip(self, conc, poll):
        """ppb -> ugm3 -> ppb recovers original."""
        result = ugm3_to_ppb(ppb_to_ugm3(conc, poll), poll)
        assert result == pytest.approx(conc, rel=1e-9)

    @given(conc=reasonable_conc, poll=gas_pollutant)
    def test_ugm3_roundtrip(self, conc, poll):
        """ugm3 -> ppb -> ugm3 recovers original."""
        result = ppb_to_ugm3(ugm3_to_ppb(conc, poll), poll)
        assert result == pytest.approx(conc, rel=1e-9)

    @given(conc=reasonable_conc, poll=gas_pollutant)
    def test_conversion_positive(self, conc, poll):
        """Positive concentration stays positive after conversion."""
        assert ppb_to_ugm3(conc, poll) > 0
        assert ugm3_to_ppb(conc, poll) > 0

    @given(poll=gas_pollutant)
    def test_zero_is_zero(self, poll):
        """Zero converts to zero."""
        assert ppb_to_ugm3(0.0, poll) == 0.0
        assert ugm3_to_ppb(0.0, poll) == 0.0


# ── ensure_ugm3 ─────────────────────────────────────────────────────────────


class TestEnsureUgm3:
    @given(conc=reasonable_conc, poll=gas_pollutant)
    def test_ugm3_is_identity(self, conc, poll):
        """If already ug/m3, value is unchanged."""
        assert ensure_ugm3(conc, poll, "ug/m3", warn=False) == conc

    @given(conc=reasonable_conc, poll=gas_pollutant)
    def test_ugm3_variants_identical(self, conc, poll):
        """All spellings of ug/m3 give the same result."""
        variants = ["ug/m3", "µg/m³", "ugm3", "µg/m3", "ug/m³"]
        results = [ensure_ugm3(conc, poll, v, warn=False) for v in variants]
        for r in results:
            assert r == conc

    @given(conc=reasonable_conc, poll=gas_pollutant)
    def test_ppb_matches_direct_conversion(self, conc, poll):
        """ensure_ugm3(..., 'ppb') matches ppb_to_ugm3(...)."""
        assert ensure_ugm3(conc, poll, "ppb", warn=False) == pytest.approx(
            ppb_to_ugm3(conc, poll), rel=1e-12
        )

    @given(conc=reasonable_conc, poll=gas_pollutant)
    def test_mgm3_is_times_1000(self, conc, poll):
        """mg/m3 -> ug/m3 is multiplication by 1000."""
        assert ensure_ugm3(conc, poll, "mg/m3", warn=False) == pytest.approx(
            conc * 1000, rel=1e-12
        )


# ── Pollutant standardisation ───────────────────────────────────────────────


class TestPollutantStandardisation:
    CANONICAL = ["PM2.5", "PM10", "O3", "NO2", "SO2", "CO"]

    @given(poll=st.sampled_from(CANONICAL))
    def test_canonical_is_fixed_point(self, poll):
        """Canonical names map to themselves."""
        assert standardise_pollutant(poll) == poll

    @given(alias=st.sampled_from(list(POLLUTANT_ALIASES.keys())))
    def test_alias_maps_to_canonical(self, alias):
        """Every alias maps to one of the six canonical names."""
        result = standardise_pollutant(alias)
        assert result in self.CANONICAL

    @given(alias=st.sampled_from(list(POLLUTANT_ALIASES.keys())))
    def test_idempotent(self, alias):
        """Standardising twice == standardising once."""
        once = standardise_pollutant(alias)
        twice = standardise_pollutant(once)
        assert once == twice


# ── AQI breakpoints ─────────────────────────────────────────────────────────


_TEST_BREAKPOINTS: list[Breakpoint] = [
    {"low_conc": 0.0, "high_conc": 50.0, "low_aqi": 0, "high_aqi": 50, "category": "Good", "color": "#00e400"},
    {"low_conc": 50.0, "high_conc": 100.0, "low_aqi": 50, "high_aqi": 100, "category": "Moderate", "color": "#ffff00"},
    {"low_conc": 100.0, "high_conc": 150.0, "low_aqi": 100, "high_aqi": 150, "category": "USG", "color": "#ff7e00"},
    {"low_conc": 150.0, "high_conc": 200.0, "low_aqi": 150, "high_aqi": 200, "category": "Unhealthy", "color": "#ff0000"},
    {"low_conc": 200.0, "high_conc": 500.0, "low_aqi": 200, "high_aqi": 500, "category": "V.Unhealthy", "color": "#8f3f97"},
]


class TestAQIBreakpoints:
    @given(
        c1=st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False),
        c2=st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    )
    def test_monotonicity(self, c1, c2):
        """Higher concentration -> equal or higher AQI."""
        r1 = calculate_aqi_from_breakpoints(c1, _TEST_BREAKPOINTS)
        r2 = calculate_aqi_from_breakpoints(c2, _TEST_BREAKPOINTS)
        # Both must be in range for this table
        assert r1 is not None
        assert r2 is not None
        if c1 <= c2:
            assert r1.value <= r2.value
        else:
            assert r1.value >= r2.value

    @given(
        conc=st.floats(min_value=500.01, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    def test_out_of_range_returns_none(self, conc):
        """Concentrations above all breakpoints return None."""
        result = calculate_aqi_from_breakpoints(conc, _TEST_BREAKPOINTS)
        assert result is None


# ── Vectorised AQI breakpoints ─────────────────────────────────────────────


class TestVectorisedAQIBreakpoints:
    @given(
        concs=st.lists(
            st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50,
        ),
    )
    def test_matches_scalar(self, concs):
        """Each element from the array version matches the scalar version."""
        arr = np.array(concs)
        aqi_values, cat_indices = calculate_aqi_from_breakpoints_array(arr, _TEST_BREAKPOINTS)
        for i, c in enumerate(concs):
            scalar = calculate_aqi_from_breakpoints(c, _TEST_BREAKPOINTS)
            if scalar is None:
                assert np.isnan(aqi_values[i])
                assert cat_indices[i] == -1
            else:
                assert aqi_values[i] == pytest.approx(scalar.value, rel=1e-9)

    @given(
        concs=st.lists(
            st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=50,
        ),
    )
    def test_monotonicity_array(self, concs):
        """Sorted concentrations produce non-decreasing AQI values."""
        arr = np.sort(np.array(concs))
        aqi_values, _ = calculate_aqi_from_breakpoints_array(arr, _TEST_BREAKPOINTS)
        valid = aqi_values[~np.isnan(aqi_values)]
        if len(valid) > 1:
            assert np.all(np.diff(valid) >= 0)

    @given(
        concs=st.lists(
            st.floats(min_value=500.01, max_value=1e6, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20,
        ),
    )
    def test_out_of_range_is_nan(self, concs):
        """Concentrations above all breakpoints give NaN AQI and -1 category."""
        arr = np.array(concs)
        aqi_values, cat_indices = calculate_aqi_from_breakpoints_array(arr, _TEST_BREAKPOINTS)
        assert np.all(np.isnan(aqi_values))
        assert np.all(cat_indices == -1)

    @given(
        concs=st.lists(
            st.floats(min_value=0.0, max_value=600.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50,
        ),
    )
    def test_category_indices_valid(self, concs):
        """In-range concentrations get valid category indices; out-of-range get -1."""
        arr = np.array(concs)
        aqi_values, cat_indices = calculate_aqi_from_breakpoints_array(arr, _TEST_BREAKPOINTS)
        num_categories = len(_TEST_BREAKPOINTS)
        for i in range(len(concs)):
            if np.isnan(aqi_values[i]):
                assert cat_indices[i] == -1
            else:
                assert 0 <= cat_indices[i] < num_categories
