"""Time conventions: every `date_time` is tz-aware UTC and marks the START of its
averaging interval; request windows mean the same instants on any machine."""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

UTC = timezone.utc
PLUS5 = timezone(timedelta(hours=5))


@pytest.fixture
def new_york_clock(monkeypatch):
    """A machine whose local zone is not UTC."""
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


# ---- the shared helper ------------------------------------------------------


def test_to_utc_treats_naive_as_utc_and_converts_aware(new_york_clock):
    from aeolus._dates import to_utc

    assert to_utc(datetime(2024, 1, 1, 12)) == datetime(2024, 1, 1, 12, tzinfo=UTC)
    assert to_utc(datetime(2024, 1, 1, 17, tzinfo=PLUS5)) == datetime(2024, 1, 1, 12, tzinfo=UTC)
    assert to_utc(datetime(2024, 1, 1, 17, tzinfo=PLUS5)).utcoffset() == timedelta(0)


# ---- request windows --------------------------------------------------------


def test_sonitus_unix_window_ignores_machine_zone(new_york_clock):
    from aeolus.sources.sonitus import _datetime_to_unix

    assert _datetime_to_unix(datetime(2024, 1, 1, 12)) == str(int(datetime(2024, 1, 1, 12, tzinfo=UTC).timestamp()))


def test_purpleair_window_ignores_machine_zone(new_york_clock):
    from aeolus.sources import purpleair

    client = MagicMock()
    client.request_sensor_historic_data.return_value = {"fields": [], "data": []}
    with patch.object(purpleair, "_get_purpleair_client", return_value=client):
        purpleair.fetch_purpleair_data(["123"], datetime(2024, 1, 1, 12), datetime(2024, 1, 1, 18))
    kwargs = client.request_sensor_historic_data.call_args.kwargs
    assert kwargs["start_timestamp"] == int(datetime(2024, 1, 1, 12, tzinfo=UTC).timestamp())


def test_breathe_london_window_converts_aware_dates_to_utc(monkeypatch):
    from aeolus.sources import breathe_london as bl

    seen = {}
    monkeypatch.setattr(bl, "_call_breathe_london_api", lambda endpoint, params: seen.update(params) or [])
    bl.fetch_breathe_london_data(["BL0001"], datetime(2024, 1, 1, 17, tzinfo=PLUS5), datetime(2024, 1, 2, 17, tzinfo=PLUS5))
    assert seen["startTime"] == "2024-01-01T12:00:00Z"


def test_eea_window_converts_aware_dates_to_utc(monkeypatch):
    from aeolus.sources import eea

    seen = {}
    monkeypatch.setattr(eea, "_download_parquet", lambda body: seen.update(body) or None)
    eea.fetch_eea_data(["IE005AP"], datetime(2024, 1, 1, 17, tzinfo=PLUS5), datetime(2024, 1, 2, 17, tzinfo=PLUS5))
    assert seen["dateTimeStart"] == "2024-01-01T12:00:00Z"


# ---- response stamps --------------------------------------------------------


def _eea_raw(samplingpoint, start):
    return pd.DataFrame({
        "Samplingpoint": [samplingpoint], "Pollutant": [8], "Start": [pd.Timestamp(start)],
        "End": [pd.Timestamp(start) + pd.Timedelta(hours=1)], "Value": [20.0], "Unit": ["ug.m-3"],
        "AggType": ["hour"], "Validity": [1], "Verification": [2],
    })


@pytest.mark.parametrize(
    "samplingpoint, start, expected",
    [
        # EEA publishes hourly Start/End in fixed UTC+1 (its download page says so)
        ("DE/SPO.DE_DEBB021_NO2_dataGroup1", "2024-01-01 01:00", "2024-01-01 00:00"),
        ("DE/SPO.DE_DEBB021_NO2_dataGroup1", "2024-07-01 01:00", "2024-07-01 00:00"),
        # Italy's up-to-date feed is on local civil time instead: CET in winter, CEST in summer
        ("IT/SPO.IT1168A_8_chemi_1998-01-30_00:00:00", "2024-01-01 01:00", "2024-01-01 00:00"),
        ("IT/SPO.IT1168A_8_chemi_1998-01-30_00:00:00", "2024-07-01 02:00", "2024-07-01 00:00"),
    ],
)
def test_eea_stamps_are_converted_to_utc(samplingpoint, start, expected):
    from aeolus.sources import eea

    code = samplingpoint.split("/")[1]
    with patch.object(eea, "_get_spo_mapping", return_value={code: "X0001A", samplingpoint: "X0001A"}):
        out = eea.normalise_eea_data()(_eea_raw(samplingpoint, start))
    assert out["date_time"].dt.tz is not None
    assert out["date_time"].iloc[0] == pd.Timestamp(expected, tz="UTC")


def test_sonitus_stamp_marks_the_start_of_its_15_minute_bin():
    """Sonitus stamps the END of each 15-minute bin (verified against EEA Irish twins)."""
    from aeolus.sources.sonitus import normalise_sonitus_data

    raw = pd.DataFrame([{"datetime": "2026-09-20 09:15:00", "no2": 8.5}])
    out = normalise_sonitus_data("DCC-AQ1")(raw)
    assert out["date_time"].iloc[0] == pd.Timestamp("2026-09-20 09:00", tz="UTC")


def test_sonitus_covers_the_requested_window_despite_server_local_time_filter(monkeypatch):
    """The server filters by Dublin local time, so in summer a plain request loses
    the first hour. Ask wider, then trim to what was requested."""
    from aeolus.sources import sonitus

    asked = {}

    def fake(endpoint, extra_body=None):
        asked.update(extra_body)
        stamps = pd.date_range("2026-07-01 08:00", "2026-07-01 15:00", freq="15min")
        return [{"datetime": str(t), "no2": 1.0} for t in stamps]

    monkeypatch.setattr(sonitus, "_call_sonitus_api", fake)
    start, end = datetime(2026, 7, 1, 10, tzinfo=UTC), datetime(2026, 7, 1, 12, tzinfo=UTC)
    out = sonitus.fetch_sonitus_data(["DCC-AQ1"], start, end)
    assert int(asked["start"]) <= int(start.timestamp()) - 3600
    assert int(asked["end"]) >= int(end.timestamp()) + 3600
    assert out["date_time"].min() == pd.Timestamp(start)
    assert out["date_time"].max() <= pd.Timestamp(end)


def test_openaq_stamp_is_the_start_of_the_period():
    from aeolus.sources import openaq

    measurement = MagicMock()
    measurement.value = 5.0
    measurement.period.datetime_from.utc = datetime(2024, 1, 1, 11)
    measurement.period.datetime_to.utc = datetime(2024, 1, 1, 12)
    assert openaq._period_start(measurement) == datetime(2024, 1, 1, 11)


def test_airnow_current_observation_uses_its_local_time_zone():
    from aeolus.sources.airnow import _observation_time_utc

    obs = {"DateObserved": "2026-09-20", "HourObserved": 10, "LocalTimeZone": "PST"}
    assert _observation_time_utc(obs) == pd.Timestamp("2026-09-20 18:00", tz="UTC")
    obs["LocalTimeZone"] = "EDT"
    assert _observation_time_utc(obs) == pd.Timestamp("2026-09-20 14:00", tz="UTC")
    obs["LocalTimeZone"] = "???"
    assert _observation_time_utc(obs) is None


def test_laqn_erg_trims_to_the_requested_window(monkeypatch):
    from aeolus.sources import laqn

    stamps = pd.date_range("2023-03-25 00:00", "2023-03-27 23:00", freq="h")
    payload = {"AirQualityData": {"Data": [
        {"@SpeciesCode": "NO2", "@MeasurementDateGMT": str(t), "@Value": "10"} for t in stamps
    ]}}
    monkeypatch.setattr(laqn, "_get_json", lambda url: payload)
    start, end = datetime(2023, 3, 25, 6, tzinfo=UTC), datetime(2023, 3, 26, 6, tzinfo=UTC)
    out = laqn.fetch_laqn_erg_data(["MY1"], start, end)
    assert out["date_time"].min() == pd.Timestamp(start)
    assert out["date_time"].max() == pd.Timestamp(end)
