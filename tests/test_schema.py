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


# ---- end to end: the convergence points and the cache ------------------------

from datetime import datetime  # noqa: E402
from unittest.mock import patch  # noqa: E402

import aeolus  # noqa: E402
from aeolus.registry import get_source  # noqa: E402


def _fake_fetcher(sites, start, end):
    return adapter_frame("AURN")


def test_download_returns_the_public_schema():
    with patch.dict(get_source("AURN"), {"fetch_data": _fake_fetcher}):
        out = aeolus.download("AURN", ["MY1"], datetime(2024, 1, 1), datetime(2024, 1, 2))
    assert list(out.columns) == DATA_COLUMNS
    assert out.loc[0, "network"] == "AURN" and out.loc[0, "backend"] == "RDATA"


def test_the_cache_holds_public_frames(tmp_path):
    from aeolus import cache

    cache.enable_cache(cache_dir=tmp_path)
    try:
        with patch.dict(get_source("AURN"), {"fetch_data": _fake_fetcher}):
            aeolus.download("AURN", ["MY1"], datetime(2024, 1, 1), datetime(2024, 1, 2))
        (path,) = tmp_path.rglob("*.parquet")
        assert "v4" in path.parts  # bumped when real QA codes landed
        assert list(pd.read_parquet(path).columns) == DATA_COLUMNS
    finally:
        cache.disable_cache()


def test_pre_v3_cache_entries_are_never_served(tmp_path):
    """Old entries hold values and columns this release changed; the versioned
    directory keeps them out without inspecting them."""
    from aeolus import cache

    cache.enable_cache(cache_dir=tmp_path)
    try:
        start, end = datetime(2024, 1, 1), datetime(2024, 1, 2)
        legacy = tmp_path / "v2" / "AURN" / "MY1_100812a6ff04675c.parquet"
        legacy.parent.mkdir(parents=True)
        adapter_frame("AURN").to_parquet(legacy)
        assert cache.get("AURN", "MY1", start, end) is None
        assert cache.cache_info()["legacy_files"] == 1
    finally:
        cache.disable_cache()


def test_unregistered_custom_source_is_its_own_unknown_network():
    out = finalise_data_frame(adapter_frame("MYNET", ratification="whatever"), "MYNET")
    row = out.iloc[0]
    assert (row["network"], row["backend"], row["qa_tier"]) == ("MYNET", "MYNET", "unknown")
    assert row["ratification_stage"] is None and row["ratification"] == "whatever"


# ---- legacy mirrors: the switch and the one-time warning --------------------

import warnings  # noqa: E402

import aeolus.options  # noqa: E402
from aeolus import schema  # noqa: E402


def test_mirrors_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(aeolus.options, "legacy_columns", False)
    out = finalise_data_frame(adapter_frame(), "AURN")
    assert "source_network" not in out.columns and "ratification" not in out.columns
    assert list(out.columns) == [c for c in DATA_COLUMNS if c not in schema.LEGACY_DATA_COLUMNS]
    assert list(empty_public_frame().columns) == list(out.columns)


def test_deprecation_warning_is_raised_once_per_process(monkeypatch):
    monkeypatch.setattr(schema, "_warned_legacy", False)
    with pytest.warns(DeprecationWarning, match="source_network.*ratification.*AEOLUS_LEGACY_COLUMNS"):
        finalise_data_frame(adapter_frame(), "AURN")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        finalise_data_frame(adapter_frame(), "AURN")


def test_no_warning_when_mirrors_are_off(monkeypatch):
    monkeypatch.setattr(schema, "_warned_legacy", False)
    monkeypatch.setattr(aeolus.options, "legacy_columns", False)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        finalise_data_frame(adapter_frame(), "AURN")


# ---- metadata identity columns and the network= alias -----------------------


def metadata_frame(**extra):
    base = {"site_code": ["MY1"], "site_name": ["Marylebone Road"], "latitude": [51.52],
            "longitude": [-0.15], "source_network": ["AURN"], "measurands": [["NO2"]]}
    return pd.DataFrame({**base, **{k: [v] for k, v in extra.items()}})


def test_metadata_gains_identity_columns():
    from aeolus.schema import METADATA_COLUMNS, finalise_metadata_frame

    out = finalise_metadata_frame(metadata_frame(location_type="Kerbside"), "AURN")
    assert list(out.columns) == METADATA_COLUMNS + ["location_type"]
    row = out.iloc[0]
    assert (row["network"], row["country"], row["instrument_class"], row["backend"]) == ("AURN", "GB", "reference", "RDATA")
    assert row["provider"] is None and row["source_network"] == "AURN"


def test_lmam_provider_comes_from_pcode():
    from aeolus.schema import finalise_metadata_frame

    out = finalise_metadata_frame(metadata_frame(pcode="sussex"), "LMAM")
    assert out.loc[0, "provider"] == "sussex"


def test_find_sites_returns_identity_columns():
    from aeolus.schema import METADATA_COLUMNS

    with patch.dict(get_source("AURN"), {"fetch_metadata": lambda **kw: metadata_frame()}):
        out = aeolus.find_sites("AURN")
    assert list(out.columns) == METADATA_COLUMNS
    assert out.loc[0, "country"] == "GB"


def test_network_keyword_is_an_alias_for_the_source():
    with patch.dict(get_source("AURN"), {"fetch_data": _fake_fetcher}):
        a = aeolus.download("AURN", ["MY1"], datetime(2024, 1, 1), datetime(2024, 1, 2))
        b = aeolus.download(network="AURN", sites=["MY1"], start_date=datetime(2024, 1, 1), end_date=datetime(2024, 1, 2))
    pd.testing.assert_frame_equal(a.drop(columns="created_at"), b.drop(columns="created_at"))


def test_network_and_sources_together_is_an_error():
    with pytest.raises(TypeError, match="network.*sources"):
        aeolus.download("AURN", ["MY1"], datetime(2024, 1, 1), datetime(2024, 1, 2), network="AURN")
