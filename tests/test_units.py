"""Unit-string canonicalisation: one spelling per unit, whatever the upstream wrote."""

import pandas as pd
import pytest

from aeolus.units import canonical_unit


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("ug/m3", "ug/m3"), ("ug.m-3", "ug/m3"), ("ug/m-3", "ug/m3"), ("µg/m³", "ug/m3"),
        ("μg/m³", "ug/m3"), ("µg/m3", "ug/m3"), ("ug/m³", "ug/m3"), ("ugm3", "ug/m3"),
        ("UG/M3", "ug/m3"), (" ug/m3 ", "ug/m3"), ("mg.m-3", "mg/m3"), ("mg/m-3", "mg/m3"),
        ("mg/m³", "mg/m3"), ("ng.m-3", "ng/m3"), ("PPB", "ppb"), ("ppm", "ppm"),
        ("C", "C"), ("%", "%"), ("hPa", "hPa"), ("AQI", "AQI"), ("", ""),
    ],
)
def test_canonical_unit(raw, expected):
    assert canonical_unit(raw) == expected


def test_canonical_unit_passes_missing_values_through():
    assert canonical_unit(None) is None
    assert pd.isna(canonical_unit(float("nan")))


def test_metrics_accept_every_spelling_without_warning():
    import warnings

    import numpy as np

    from aeolus.metrics.base import ensure_ugm3_array

    values = np.array([1.0, 2.0, 3.0])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = ensure_ugm3_array(values, "CO", pd.Series(["mg/m-3", "μg/m³", "ug.m-3"]))
    assert out.tolist() == [1000.0, 2.0, 3.0]
