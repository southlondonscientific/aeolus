import pandas as pd
import pytest

import aeolus.sources  # noqa: F401
from aeolus.schema import DATA_COLUMNS, empty_public_frame, finalise_data_frame


def adapter_frame(network="AURN", ratification="None", **extra):
    base = {
        "site_code": ["MY1"], "date_time": [pd.Timestamp("2024-01-01", tz="UTC")], "measurand": ["NO2"],
        "value": [41.6], "units": ["ug/m3"], "source_network": [network],
        "ratification": [ratification], "created_at": [pd.Timestamp("2024-06-01", tz="UTC")],
    }
    return pd.DataFrame({**base, **{k: [v] for k, v in extra.items()}})


def test_public_columns_and_order():
    assert DATA_COLUMNS == [
        "site_code", "network", "date_time", "measurand", "value", "units",
        "qa_code", "qa_tier", "ratification_stage", "backend",
        "source_network", "ratification", "created_at",
    ]
    assert list(finalise_data_frame(adapter_frame(), "AURN").columns) == DATA_COLUMNS
    assert list(empty_public_frame().columns) == DATA_COLUMNS


def test_network_and_backend_come_from_the_source_route_not_the_adapter():
    out = finalise_data_frame(adapter_frame(network="whatever"), "AURN-SOS")
    assert out.loc[0, "network"] == "AURN" and out.loc[0, "backend"] == "SOS"
    assert out.loc[0, "source_network"] == "AURN"  # the mirror equals `network`


def test_unwired_adapter_is_unknown_and_keeps_its_ratification_string():
    out = finalise_data_frame(adapter_frame("PURPLEAIR", ratification="Channel Disagreement"), "PURPLEAIR")
    assert out.loc[0, "qa_code"] is None
    assert out.loc[0, "qa_tier"] == "unknown"
    assert out.loc[0, "ratification_stage"] == "not_applicable"   # PurpleAir's network default
    assert out.loc[0, "ratification"] == "Channel Disagreement"   # unchanged for consumers


def test_wired_adapter_derives_tier_stage_and_mirror():
    out = finalise_data_frame(adapter_frame("AURN", qa_code="verified"), "AURN")
    assert out.loc[0, "qa_code"] == "verified"
    assert out.loc[0, "qa_tier"] == "reference_full_qc"
    assert out.loc[0, "ratification_stage"] == "ratified"
    assert out.loc[0, "ratification"] == "Ratified"


def test_values_units_and_times_are_untouched():
    before = adapter_frame()
    out = finalise_data_frame(before.copy(), "AURN")
    for col in ("site_code", "date_time", "measurand", "value", "units", "created_at"):
        pd.testing.assert_series_equal(out[col], before[col])


def test_empty_adapter_frame_gives_empty_public_frame():
    out = finalise_data_frame(adapter_frame().iloc[0:0], "AURN")
    assert out.empty and list(out.columns) == DATA_COLUMNS


def test_finalising_twice_is_harmless():
    once = finalise_data_frame(adapter_frame("AURN", qa_code="verified"), "AURN")
    pd.testing.assert_frame_equal(finalise_data_frame(once.copy(), "AURN"), once)


def test_requested_range_attr_survives():
    frame = adapter_frame()
    frame.attrs["aeolus_requested_range"] = ["2024-01-01T00:00:00+00:00", "2024-01-02T00:00:00+00:00"]
    assert finalise_data_frame(frame, "AURN").attrs == frame.attrs
