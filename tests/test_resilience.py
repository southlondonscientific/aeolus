"""Resilience: latching caches, retry effectiveness, and edge-case robustness."""

import ast
import math
import warnings
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests
import responses




# ---- 1. EEA ---------------------------------------------------------------
class TestSpoMappingCacheEmpty:
    @pytest.fixture(autouse=True)
    def _reset_module_state(self):
        from aeolus.sources import eea

        saved = eea._spo_to_eoi
        eea._spo_to_eoi = None
        try:
            yield
        finally:
            eea._spo_to_eoi = saved

    @pytest.mark.parametrize(
        "bad_csv",
        [
            "",  # read_csv raises -> _parse_csv_fallback -> {}
            "<html>Service unavailable</html>",  # usecols mismatch -> fallback -> {}
            "Sampling Point Id,Air Quality Station EoI Code\n",  # header only -> success branch {}
        ],
    )
    def test_cache_not_latched_on_empty_mapping(self, monkeypatch, bad_csv):
        from aeolus.sources import eea

        payloads = iter(
            [bad_csv, "Sampling Point Id,Air Quality Station EoI Code\nSPO.IE.A,IE0001\n"]
        )
        monkeypatch.setattr(eea, "_fetch_metadata_csv", lambda: next(payloads))

        assert eea._get_spo_mapping() == {}
        assert eea._spo_to_eoi is None, "empty mapping must not be cached"
        assert eea._get_spo_mapping() == {"SPO.IE.A": "IE0001"}


# ---- 2. SOS ---------------------------------------------------------------
class TestSosMappingLatch:
    @pytest.fixture(autouse=True)
    def _clear(self):
        from aeolus.sources import sos

        sos._network_mappings.clear()
        sos._get_all_timeseries_cached.cache_clear()
        yield
        sos._network_mappings.clear()
        sos._get_all_timeseries_cached.cache_clear()

    def test_get_network_mapping_does_not_latch_empty_live_build(self, tmp_path, monkeypatch):
        from aeolus.sources import sos

        monkeypatch.setattr(sos, "_MAPPING_FILE", tmp_path / "missing.json")
        builds = iter([{}, {"LIVE1": [{"ts_id": "999", "measurand": "O3", "uom": "ug/m3"}]}])
        monkeypatch.setattr(sos, "_build_station_mapping", lambda net: next(builds))

        assert sos._get_network_mapping("waqn") == {}
        assert "waqn" not in sos._network_mappings
        assert "LIVE1" in sos._get_network_mapping("waqn")

    def test_empty_timeseries_list_is_not_lru_cached(self, monkeypatch):
        from aeolus.sources import sos

        batches = iter([[], [{"id": "1"}]])
        monkeypatch.setattr(sos, "_fetch_all_timeseries", lambda: next(batches))
        meta = pd.DataFrame(
            {"site_code": ["MY1"], "latitude": [51.52], "longitude": [-0.15]}
        )
        monkeypatch.setattr(
            "aeolus.sources.regulatory.make_metadata_fetcher", lambda net: (lambda: meta)
        )
        assert sos._build_station_mapping("aurn") == {}
        sos._build_station_mapping("aurn")
        assert sos._get_all_timeseries_cached() == ({"id": "1"},)


# ---- 3. geo ---------------------------------------------------------------
@pytest.mark.parametrize(
    "lat,lon,radius",
    [(89.5, 0.0, 100.0), (-89.5, 10.0, 100.0), (90.0, 0.0, 10.0), (-17.7, 179.9, 50.0), (78.2, -179.0, 100.0)],
)
def test_near_to_bbox_stays_within_valid_coordinate_range(lat, lon, radius):
    from aeolus.geo import near_to_bbox

    min_lon, min_lat, max_lon, max_lat = near_to_bbox(lat, lon, radius)
    assert -90.0 <= min_lat < max_lat <= 90.0
    assert -180.0 <= min_lon < max_lon <= 180.0


# ---- 4. list_networks -------------------------------------------------------
def test_list_networks_hides_non_primary_backends():
    from aeolus.networks import list_networks
    from aeolus.registry import clear_registry, register_source, SOURCES

    saved = dict(SOURCES)
    clear_registry()
    try:
        spec = {
            "type": "network",
            "name": "x",
            "fetch_metadata": lambda: pd.DataFrame(),
            "fetch_data": lambda *a: pd.DataFrame(),
            "requires_api_key": False,
        }
        register_source("NET1", dict(spec))
        register_source("NET1-SOS", {**spec, "primary": False})
        result = list_networks()
        assert "NET1" in result
        assert "NET1-SOS" not in result
        assert "NET1-SOS" in list_networks(include_all=True)
    finally:
        clear_registry()
        SOURCES.update(saved)


# ---- 5. Breathe London ------------------------------------------------------
@responses.activate
def test_bl_location_filter_without_coordinate_columns(monkeypatch):
    from aeolus.sources.breathe_london import (
        BREATHE_LONDON_API_BASE,
        fetch_breathe_london_metadata,
    )

    monkeypatch.setenv("BL_API_KEY", "test_key_123")
    responses.add(
        responses.GET,
        f"{BREATHE_LONDON_API_BASE}/ListSensors",
        json=[{"SiteCode": "BL0001", "SiteName": "Camden", "Borough": "Camden"}],
        status=200,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = fetch_breathe_london_metadata(
            latitude=51.5279, longitude=-0.1328, radius_km=3
        )
    assert result.empty
    assert {"latitude", "longitude"} <= set(result.columns)


# ---- 6. AirQo ---------------------------------------------------------------
def test_airqo_keeps_zero_drops_negative():
    from aeolus.sources.airqo import create_airqo_normaliser

    df = pd.DataFrame(
        [
            {"time": "2024-01-01T00:00:00.000Z", "pm2_5": {"value": 35.5},
             "siteDetails": {"_id": "site_001", "name": "Test"}},
            {"time": "2024-01-01T01:00:00.000Z", "pm2_5": {"value": 0},
             "siteDetails": {"_id": "site_001", "name": "Test"}},
            {"time": "2024-01-01T02:00:00.000Z", "pm2_5": {"value": -5},
             "siteDetails": {"_id": "site_001", "name": "Test"}},
        ]
    )
    result = create_airqo_normaliser()(df)
    assert sorted(result["value"].tolist()) == [0.0, 35.5]


# ---- 7. AirNow --------------------------------------------------------------
def _hours(params):
    start = datetime.strptime(params["startDate"], "%Y-%m-%dT%H")
    end = datetime.strptime(params["endDate"], "%Y-%m-%dT%H")
    return pd.date_range(start, end, freq="h")


def _fake_airnow(endpoint, params):
    """Behave like AirNow: both bounds inclusive, one PM2.5 obs per hour."""
    return [
        {"Parameter": "PM2.5", "Value": 10.0, "Unit": "UG/M3",
         "UTC": ts.strftime("%Y-%m-%dT%H:%M")}
        for ts in _hours(params)
    ]


@patch("aeolus.sources.airnow._call_airnow_api", side_effect=_fake_airnow)
def test_airnow_multi_day_no_boundary_duplicates(mock_api):
    from aeolus.sources.airnow import fetch_airnow_data

    df = fetch_airnow_data(
        sites=["34d0522_m118d2437"],
        start_date=datetime(2024, 1, 15),
        end_date=datetime(2024, 1, 17, 23),
    )
    assert not df.duplicated(subset=["site_code", "date_time", "measurand"]).any()
    assert len(df) == 72


@patch("aeolus.sources.airnow._call_airnow_api", side_effect=_fake_airnow)
def test_airnow_honours_sub_day_window(mock_api):
    from aeolus.sources.airnow import fetch_airnow_data

    df = fetch_airnow_data(
        sites=["34d0522_m118d2437"],
        start_date=datetime(2024, 1, 15, 14, 30),
        end_date=datetime(2024, 1, 16, 14, 30),
    )
    assert df["date_time"].min() == pd.Timestamp("2024-01-15T14:00Z")
    assert df["date_time"].max() == pd.Timestamp("2024-01-16T14:00Z")
    assert len(df) == 25


# ---- 8. sensor_community ----------------------------------------------------
@patch("aeolus.sources.sensor_community._fetch_sensor_archive")
@patch("aeolus.sources.sensor_community._get_sensor_types_for_sites")
def test_sc_learned_type_not_reprobed(mock_get_types, mock_archive):
    from aeolus.sources import sensor_community as sc

    sc._sensor_type_cache.clear()
    mock_get_types.return_value = {}
    row = pd.DataFrame(
        {"site_code": ["12345"], "date_time": [datetime(2024, 1, 15, 10)],
         "measurand": ["PM2.5"], "value": [22.3], "units": ["ug/m3"],
         "source_network": ["SENSOR_COMMUNITY"], "ratification": ["Unvalidated"],
         "created_at": [datetime.now()]}
    )

    def fake_archive(date, sensor_type, site_id):
        return row if sensor_type == "PMS5003" else sc.empty_data_frame()

    mock_archive.side_effect = fake_archive
    sc.fetch_sensor_community_data(["12345"], datetime(2024, 1, 15), datetime(2024, 1, 17))
    sc._sensor_type_cache.clear()
    # Day 1 probes SDS011, BME280, PMS5003 (3 calls); days 2-3 go straight to PMS5003.
    assert mock_archive.call_count == 5


# ---- 9. retry no-op -----------------------------------------------------------
class TestRetryEffective:
    @responses.activate
    def test_fetch_rdata_retries_then_returns_none(self):
        from aeolus.sources.regulatory import fetch_rdata

        url = "https://example.com/test.RData"
        responses.add(responses.GET, url, body=requests.exceptions.ConnectionError("refused"))
        assert fetch_rdata(url) is None
        assert len(responses.calls) == 3

    @responses.activate
    def test_fetch_rdata_404_not_retried(self):
        from aeolus.sources.regulatory import fetch_rdata

        url = "https://example.com/MY1_1066.RData"
        responses.add(responses.GET, url, status=404)
        assert fetch_rdata(url) is None
        assert len(responses.calls) == 1

    @responses.activate
    def test_fetch_rdata_recovers_after_transient_503(self, my1_rdata_path):
        from aeolus.sources.regulatory import fetch_rdata

        fixture = Path(my1_rdata_path)
        url = "https://example.com/MY1_2023.RData"
        responses.add(responses.GET, url, status=503)
        responses.add(responses.GET, url, body=fixture.read_bytes(), status=200)
        df = fetch_rdata(url)
        assert df is not None and not df.empty
        assert len(responses.calls) == 2

    @patch("aeolus.sources.airnow.requests.get")
    def test_airnow_retries_timeout(self, mock_get, monkeypatch):
        from aeolus.sources.airnow import _call_airnow_api

        monkeypatch.setenv("AIRNOW_API_KEY", "k")
        mock_get.side_effect = requests.exceptions.Timeout()
        assert _call_airnow_api("test/endpoint") is None
        assert mock_get.call_count == 3

    @patch("aeolus.sources.sensor_community.requests.get")
    @patch("aeolus.sources.sensor_community._apply_rate_limit")
    def test_sc_retries_timeout_not_404(self, _rl, mock_get):
        from aeolus.sources.sensor_community import _make_request

        mock_get.side_effect = requests.exceptions.Timeout()
        assert _make_request("https://example.com/test") is None
        assert mock_get.call_count == 3

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_purpleair_metadata_retries_connection_error(self, mock_get_client):
        from aeolus.sources.purpleair import fetch_purpleair_metadata

        client = MagicMock()
        client.request_multiple_sensors_data.side_effect = [
            requests.exceptions.ConnectionError("reset"),
            {"fields": ["sensor_index", "name", "latitude", "longitude"],
             "data": [[1, "A", 51.5, -0.1]]},
        ]
        mock_get_client.return_value = client
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = fetch_purpleair_metadata(bbox=(-0.5, 51.3, 0.3, 51.7))
        assert client.request_multiple_sensors_data.call_count == 2
        assert len(df) == 1


def test_retry_decorated_functions_do_not_swallow_network_errors():
    """Structural guard: a retry decorator on a function that catches
    requests exceptions internally is a silent no-op."""
    retry = {"retry_on_network_error", "retry_aggressive", "retry_gentle", "with_retry"}
    swallowed = {"RequestException", "Timeout", "ConnectionError", "HTTPError", "Exception"}
    src = Path(__file__).parent.parent / "src" / "aeolus" / "sources"
    violations = []
    for path in sorted(src.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            names = set()
            for dec in node.decorator_list:
                target = dec.func if isinstance(dec, ast.Call) else dec
                names.add(getattr(target, "id", getattr(target, "attr", "")))
            if not names & retry:
                continue
            for handler in (n for n in ast.walk(node) if isinstance(n, ast.ExceptHandler)):
                types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
                caught = {getattr(t, "attr", getattr(t, "id", "")) for t in types if t is not None}
                reraises = any(isinstance(n, ast.Raise) and n.exc is None for n in ast.walk(handler))
                if caught & swallowed and not reraises:
                    violations.append(f"{path.name}:{handler.lineno} def {node.name}")
    assert not violations, "\n  ".join(["Retry-decorated functions swallow network errors:"] + violations)


def test_retry_log_does_not_leak_query_string_secrets(caplog):
    import logging

    from aeolus.decorators import retry_on_network_error

    @retry_on_network_error
    def boom():
        resp = MagicMock(status_code=500)
        raise requests.exceptions.HTTPError(
            "500 Server Error for url: https://x/?API_KEY=CANARY_KEY", response=resp
        )

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(requests.exceptions.HTTPError):
            boom()
    assert "CANARY_KEY" not in caplog.text


# ---- RData circuit-breaker --------------------------------------------------


class TestRdataCircuitBreaker:
    """Retry makes a dead host cost ~6 s per site-year URL; fail fast instead."""

    DEAD = "https://dead.example.com/openair/R_data/"
    LIVE = "https://live.example.com/openair/R_data/"

    @responses.activate
    def test_opens_after_consecutive_failures_and_stops_calling(self):
        from aeolus.sources import regulatory

        for year in range(2015, 2025):
            responses.add(
                responses.GET, f"{self.DEAD}MY1_{year}.RData", body=requests.exceptions.ConnectionError("refused")
            )
        for year in range(2015, 2025):
            assert regulatory.fetch_rdata(f"{self.DEAD}MY1_{year}.RData") is None

        # 3 URLs x 3 attempts, then the breaker opens and nothing more is sent
        threshold = regulatory._RDATA_BREAKER_FAILURES
        assert len(responses.calls) == threshold * 3

    @responses.activate
    def test_is_per_host(self, my1_rdata_path):
        from aeolus.sources import regulatory

        for year in range(2015, 2020):
            responses.add(
                responses.GET, f"{self.DEAD}MY1_{year}.RData", body=requests.exceptions.ConnectionError("refused")
            )
            regulatory.fetch_rdata(f"{self.DEAD}MY1_{year}.RData")

        url = f"{self.LIVE}MY1_2023.RData"
        responses.add(responses.GET, url, body=Path(my1_rdata_path).read_bytes(), status=200)
        df = regulatory.fetch_rdata(url)
        assert df is not None and not df.empty

    @responses.activate
    def test_missing_site_years_do_not_open_the_breaker(self, my1_rdata_path):
        from aeolus.sources import regulatory

        for year in range(1990, 2000):
            responses.add(responses.GET, f"{self.LIVE}MY1_{year}.RData", status=404)
            assert regulatory.fetch_rdata(f"{self.LIVE}MY1_{year}.RData") is None

        url = f"{self.LIVE}MY1_2023.RData"
        responses.add(responses.GET, url, body=Path(my1_rdata_path).read_bytes(), status=200)
        assert regulatory.fetch_rdata(url) is not None

    @responses.activate
    def test_probes_again_after_cooldown(self, monkeypatch, my1_rdata_path):
        from aeolus.sources import regulatory

        monkeypatch.setattr(regulatory, "_RDATA_BREAKER_COOLDOWN_S", 0)
        for year in range(2015, 2020):
            responses.add(
                responses.GET, f"{self.DEAD}MY1_{year}.RData", body=requests.exceptions.ConnectionError("refused")
            )
            regulatory.fetch_rdata(f"{self.DEAD}MY1_{year}.RData")

        url = f"{self.DEAD}MY1_2023.RData"
        responses.add(responses.GET, url, body=Path(my1_rdata_path).read_bytes(), status=200)
        assert regulatory.fetch_rdata(url) is not None
