"""Tests for the SOS (Sensor Observation Service) data source.

Tests the SOS module's station mapping, data fetching, EIONET parsing,
and get_current() routing. Uses the ``responses`` library to mock SOS API
calls, consistent with other test files in this project.
"""

import importlib
import json
import tempfile
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
import responses

from aeolus import api
from aeolus.registry import clear_registry, get_source, register_source
from aeolus.sources import sos
from aeolus.types import DATA_COLUMNS


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_registry_and_caches():
    """Clear registry and SOS caches before and after each test."""
    clear_registry()
    sos._network_mappings.clear()
    sos._get_all_timeseries_cached.cache_clear()
    yield
    clear_registry()
    sos._network_mappings.clear()
    sos._get_all_timeseries_cached.cache_clear()
    from aeolus.sources import (
        airnow,
        airqo,
        breathe_london,
        openaq,
        purpleair,
        regulatory,
        sensor_community,
    )

    for module in [
        airnow,
        airqo,
        breathe_london,
        openaq,
        purpleair,
        regulatory,
        sensor_community,
        sos,
    ]:
        importlib.reload(module)


# --- Mock metadata for coordinate matching ---

MOCK_AURN_METADATA = pd.DataFrame(
    [
        {
            "site_code": "CLL2",
            "site_name": "Camden Kerbside",
            "latitude": 51.5442,
            "longitude": -0.1752,
            "source_network": "AURN",
        },
        {
            "site_code": "MY1",
            "site_name": "Marylebone Road",
            "latitude": 51.5225,
            "longitude": -0.1546,
            "source_network": "AURN",
        },
    ]
)


# --- Mock SOS timeseries response ---

MOCK_TIMESERIES = [
    {
        "id": "3",
        "label": "http://dd.eionet.europa.eu/vocabulary/aq/pollutant/8 804 - Camden Kerbside-Nitrogen dioxide (air)",
        "uom": "ug.m-3",
        "station": {
            "properties": {"id": 804, "label": "Camden Kerbside-Nitrogen dioxide (air)"},
            "geometry": {
                "coordinates": [51.5442, -0.17523, "NaN"],
                "type": "Point",
            },
            "type": "Feature",
        },
        "parameters": {
            "phenomenon": {
                "id": "8",
                "label": "http://dd.eionet.europa.eu/vocabulary/aq/pollutant/8",
            },
            "category": {"id": "8", "label": "http://dd.eionet.europa.eu/vocabulary/aq/pollutant/8"},
            "service": {"id": "1", "label": "My Timeseries Service."},
            "offering": {"id": "804", "label": "804 - Camden Kerbside"},
            "feature": {"id": "804", "label": "Camden Kerbside"},
            "procedure": {"id": "804", "label": "804 - Camden Kerbside"},
        },
        "firstValue": {"timestamp": 1672531200000, "value": 22.0},
        "lastValue": {"timestamp": 1773914400000, "value": 44.37},
    },
    {
        "id": "5",
        "label": "http://dd.eionet.europa.eu/vocabulary/aq/pollutant/6001 806 - Camden Kerbside-PM2.5",
        "uom": "ug.m-3",
        "station": {
            "properties": {"id": 806, "label": "Camden Kerbside-PM2.5"},
            "geometry": {
                "coordinates": [51.5442, -0.17523, "NaN"],
                "type": "Point",
            },
            "type": "Feature",
        },
        "parameters": {
            "phenomenon": {
                "id": "6001",
                "label": "http://dd.eionet.europa.eu/vocabulary/aq/pollutant/6001",
            },
            "category": {"id": "6001", "label": "..."},
            "service": {"id": "1", "label": "My Timeseries Service."},
            "offering": {"id": "806", "label": "806"},
            "feature": {"id": "806", "label": "Camden Kerbside-PM2.5"},
            "procedure": {"id": "806", "label": "806"},
        },
        "firstValue": {"timestamp": 1672531200000, "value": 10.0},
        "lastValue": {"timestamp": 1773914400000, "value": 8.0},
    },
    {
        "id": "100",
        "label": "http://dd.eionet.europa.eu/vocabulary/aq/pollutant/8 900 - Marylebone Road-NO2",
        "uom": "ug.m-3",
        "station": {
            "properties": {"id": 900, "label": "Marylebone Road-NO2"},
            "geometry": {
                "coordinates": [51.5225, -0.1546, "NaN"],
                "type": "Point",
            },
            "type": "Feature",
        },
        "parameters": {
            "phenomenon": {
                "id": "8",
                "label": "http://dd.eionet.europa.eu/vocabulary/aq/pollutant/8",
            },
            "category": {"id": "8", "label": "..."},
            "service": {"id": "1", "label": "My Timeseries Service."},
            "offering": {"id": "900", "label": "900"},
            "feature": {"id": "900", "label": "Marylebone Road-NO2"},
            "procedure": {"id": "900", "label": "900"},
        },
        "firstValue": {"timestamp": 1672531200000, "value": 50.0},
        "lastValue": {"timestamp": 1773914400000, "value": 60.0},
    },
]


MOCK_GETDATA_RESPONSE = {
    "values": [
        {"timestamp": 1773792000000, "value": 59.096},
        {"timestamp": 1773795600000, "value": 55.271},
        {"timestamp": 1773799200000, "value": -99.0},  # missing sentinel
        {"timestamp": 1773802800000, "value": 50.299},
    ]
}


def _register_mock_aurn_and_sos():
    """Register a mock AURN source and SOS source with mocked metadata."""
    # Register the primary AURN source
    register_source(
        "AURN",
        {
            "type": "network",
            "name": "AURN",
            "fetch_metadata": lambda **kw: MOCK_AURN_METADATA.copy(),
            "fetch_data": lambda sites, s, e: pd.DataFrame(),
            "normalise": lambda df: df,
            "requires_api_key": False,
        },
    )

    # Register the SOS variant with mocked metadata fetcher
    register_source(
        "AURN-SOS",
        {
            "type": "network",
            "name": "AURN (SOS)",
            "primary": False,
            "fetch_metadata": lambda **kw: MOCK_AURN_METADATA.copy(),
            "fetch_data": sos.make_sos_data_fetcher("aurn"),
            "normalise": lambda df: df,
            "requires_api_key": False,
            "fetch_latest": sos.make_sos_latest_fetcher("aurn"),
        },
    )


# ============================================================================
# EIONET pollutant parsing
# ============================================================================


class TestEionetParsing:
    def test_parse_uri(self):
        result = sos._parse_eionet_id(
            "http://dd.eionet.europa.eu/vocabulary/aq/pollutant/8"
        )
        assert result == 8

    def test_parse_plain_id(self):
        assert sos._parse_eionet_id("6001") == 6001

    def test_parse_id_with_whitespace(self):
        assert sos._parse_eionet_id("  5  ") == 5

    def test_parse_invalid(self):
        assert sos._parse_eionet_id("no-number-here") is None

    def test_pollutant_map_coverage(self):
        """All expected pollutants are in the map."""
        assert sos.EIONET_POLLUTANT_MAP[8] == "NO2"
        assert sos.EIONET_POLLUTANT_MAP[5] == "PM10"
        assert sos.EIONET_POLLUTANT_MAP[6001] == "PM2.5"
        assert sos.EIONET_POLLUTANT_MAP[7] == "O3"
        assert sos.EIONET_POLLUTANT_MAP[1] == "SO2"
        assert sos.EIONET_POLLUTANT_MAP[10] == "CO"
        assert sos.EIONET_POLLUTANT_MAP[38] == "NO"
        assert sos.EIONET_POLLUTANT_MAP[9] == "NOXasNO2"


# ============================================================================
# Site name extraction
# ============================================================================


class TestSiteNameExtraction:
    def test_strip_no2_suffix(self):
        assert sos._extract_site_name("Camden Kerbside-Nitrogen dioxide (air)") == "Camden Kerbside"

    def test_strip_pm10_suffix(self):
        assert (
            sos._extract_site_name(
                "Camden Kerbside-Particulate matter less than 10 micro m (aerosol)"
            )
            == "Camden Kerbside"
        )

    def test_plain_name(self):
        assert sos._extract_site_name("Just A Name") == "Just A Name"


# ============================================================================
# Station mapping (coordinate matching)
# ============================================================================


class TestStationMapping:
    @responses.activate
    def test_mapping_matches_by_coordinates(self, monkeypatch):
        """SOS timeseries matched to AURN sites by coordinate proximity."""
        responses.add(
            responses.GET,
            f"{sos.SOS_BASE_URL}/timeseries",
            json=MOCK_TIMESERIES,
            status=200,
        )

        _register_mock_aurn_and_sos()

        # Patch make_metadata_fetcher to return our mock metadata
        monkeypatch.setattr(
            "aeolus.sources.regulatory.make_metadata_fetcher",
            lambda net: (lambda **kw: MOCK_AURN_METADATA.copy()),
        )

        sos._network_mappings.clear()
        mapping = sos._build_station_mapping("aurn")

        assert "CLL2" in mapping
        measurands = {ts["measurand"] for ts in mapping["CLL2"]}
        assert "NO2" in measurands
        assert "PM2.5" in measurands

    @responses.activate
    def test_mapping_excludes_distant_stations(self, monkeypatch):
        """SOS stations >200m from any AURN site are not mapped."""
        monkeypatch.setattr(
            "aeolus.sources.regulatory.make_metadata_fetcher",
            lambda net: (lambda **kw: MOCK_AURN_METADATA.copy()),
        )
        far_away_ts = [
            {
                "id": "999",
                "label": "pollutant/8 999 - Far Away",
                "uom": "ug.m-3",
                "station": {
                    "properties": {"id": 999, "label": "Far Away-NO2"},
                    "geometry": {
                        "coordinates": [55.0, -3.0, "NaN"],
                        "type": "Point",
                    },
                    "type": "Feature",
                },
                "parameters": {
                    "phenomenon": {"id": "8", "label": "..."},
                    "category": {"id": "8", "label": "..."},
                    "service": {"id": "1", "label": "..."},
                    "offering": {"id": "999", "label": "..."},
                    "feature": {"id": "999", "label": "..."},
                    "procedure": {"id": "999", "label": "..."},
                },
                "firstValue": {"timestamp": 1672531200000, "value": 10.0},
                "lastValue": {"timestamp": 1773914400000, "value": 20.0},
            }
        ]
        responses.add(
            responses.GET,
            f"{sos.SOS_BASE_URL}/timeseries",
            json=far_away_ts,
            status=200,
        )

        _register_mock_aurn_and_sos()
        mapping = sos._build_station_mapping("aurn")

        # No sites should be matched — the far away station is nowhere
        # near CLL2 or MY1
        for ts_list in mapping.values():
            ts_ids = {ts["ts_id"] for ts in ts_list}
            assert "999" not in ts_ids


# ============================================================================
# Data fetching
# ============================================================================


class TestDataFetching:
    @responses.activate
    def test_fetch_data_returns_standard_schema(self):
        """SOS data fetcher returns the 8-column standard schema."""
        responses.add(
            responses.GET,
            f"{sos.SOS_BASE_URL}/timeseries",
            json=MOCK_TIMESERIES,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{sos.SOS_BASE_URL}/timeseries/3/getData",
            json=MOCK_GETDATA_RESPONSE,
            status=200,
        )

        _register_mock_aurn_and_sos()
        # Pre-populate mapping to avoid extra API calls
        sos._network_mappings["aurn"] = {
            "CLL2": [{"ts_id": "3", "measurand": "NO2", "uom": "ug/m3"}],
        }

        fetcher = sos.make_sos_data_fetcher("aurn")
        df = fetcher(
            ["CLL2"],
            datetime(2026, 3, 18, tzinfo=timezone.utc),
            datetime(2026, 3, 19, tzinfo=timezone.utc),
        )

        assert not df.empty
        assert list(df.columns) == DATA_COLUMNS
        assert all(df["site_code"] == "CLL2")
        assert all(df["measurand"] == "NO2")
        assert all(df["source_network"] == "AURN")

    @responses.activate
    def test_missing_sentinel_filtered(self):
        """Values of -99.0 are filtered out."""
        responses.add(
            responses.GET,
            f"{sos.SOS_BASE_URL}/timeseries/3/getData",
            json=MOCK_GETDATA_RESPONSE,
            status=200,
        )

        sos._network_mappings["aurn"] = {
            "CLL2": [{"ts_id": "3", "measurand": "NO2", "uom": "ug/m3"}],
        }

        fetcher = sos.make_sos_data_fetcher("aurn")
        df = fetcher(
            ["CLL2"],
            datetime(2026, 3, 18, tzinfo=timezone.utc),
            datetime(2026, 3, 19, tzinfo=timezone.utc),
        )

        # The mock has 4 values, one is -99.0
        assert len(df) == 3
        assert -99.0 not in df["value"].values

    @responses.activate
    def test_no_data_returns_empty_frame(self):
        """When no data is returned, empty frame with standard schema."""
        responses.add(
            responses.GET,
            f"{sos.SOS_BASE_URL}/timeseries/3/getData",
            json={"values": []},
            status=200,
        )

        sos._network_mappings["aurn"] = {
            "CLL2": [{"ts_id": "3", "measurand": "NO2", "uom": "ug/m3"}],
        }

        fetcher = sos.make_sos_data_fetcher("aurn")
        df = fetcher(
            ["CLL2"],
            datetime(2026, 3, 18, tzinfo=timezone.utc),
            datetime(2026, 3, 19, tzinfo=timezone.utc),
        )

        assert df.empty
        assert list(df.columns) == DATA_COLUMNS

    def test_unmapped_site_returns_empty(self):
        """Requesting a site with no SOS mapping returns empty frame."""
        sos._network_mappings["aurn"] = {}

        fetcher = sos.make_sos_data_fetcher("aurn")
        df = fetcher(
            ["NONEXISTENT"],
            datetime(2026, 3, 18, tzinfo=timezone.utc),
            datetime(2026, 3, 19, tzinfo=timezone.utc),
        )

        assert df.empty

    @responses.activate
    def test_naive_dates_converted_to_utc(self):
        """Naive datetime inputs are treated as UTC."""
        responses.add(
            responses.GET,
            f"{sos.SOS_BASE_URL}/timeseries/3/getData",
            json=MOCK_GETDATA_RESPONSE,
            status=200,
        )

        sos._network_mappings["aurn"] = {
            "CLL2": [{"ts_id": "3", "measurand": "NO2", "uom": "ug/m3"}],
        }

        fetcher = sos.make_sos_data_fetcher("aurn")
        # Pass naive datetimes — should not raise
        df = fetcher(
            ["CLL2"],
            datetime(2026, 3, 18),
            datetime(2026, 3, 19),
        )

        assert not df.empty
        assert df["date_time"].dt.tz is not None


# ============================================================================
# Latest fetcher
# ============================================================================


class TestLatestFetcher:
    @responses.activate
    def test_fetch_latest_keeps_most_recent(self):
        """fetch_latest keeps only the most recent reading per site+measurand."""
        responses.add(
            responses.GET,
            f"{sos.SOS_BASE_URL}/timeseries/3/getData",
            json=MOCK_GETDATA_RESPONSE,
            status=200,
        )

        sos._network_mappings["aurn"] = {
            "CLL2": [{"ts_id": "3", "measurand": "NO2", "uom": "ug/m3"}],
        }

        fetcher = sos.make_sos_latest_fetcher("aurn")
        df = fetcher(["CLL2"])

        # Should have exactly 1 row — the latest reading for CLL2/NO2
        assert len(df) == 1
        assert df["site_code"].iloc[0] == "CLL2"
        assert df["measurand"].iloc[0] == "NO2"


# ============================================================================
# Registration
# ============================================================================


class TestRegistration:
    def test_sos_sources_registered(self):
        """All SOS network sources are registered after module import."""
        importlib.reload(sos)
        for net in ["AURN", "SAQN", "WAQN", "NI", "AQE"]:
            spec = get_source(f"{net}-SOS")
            assert spec is not None, f"{net}-SOS not registered"

    def test_sos_sources_are_not_primary(self):
        """All SOS sources have primary=False."""
        importlib.reload(sos)
        for net in ["AURN", "SAQN", "WAQN", "NI", "AQE"]:
            spec = get_source(f"{net}-SOS")
            assert spec.get("primary") is False, f"{net}-SOS should not be primary"

    def test_sos_sources_no_api_key(self):
        """SOS sources do not require an API key."""
        importlib.reload(sos)
        for net in ["AURN", "SAQN", "WAQN", "NI", "AQE"]:
            spec = get_source(f"{net}-SOS")
            assert spec["requires_api_key"] is False

    def test_sos_sources_have_fetch_latest(self):
        """SOS sources have a fetch_latest function."""
        importlib.reload(sos)
        for net in ["AURN", "SAQN", "WAQN", "NI", "AQE"]:
            spec = get_source(f"{net}-SOS")
            assert "fetch_latest" in spec
            assert callable(spec["fetch_latest"])


# ============================================================================
# get_current() routing
# ============================================================================


class TestGetCurrent:
    @responses.activate
    def test_routes_aurn_to_sos(self):
        """get_current('AURN', ...) routes to AURN-SOS."""
        responses.add(
            responses.GET,
            f"{sos.SOS_BASE_URL}/timeseries/3/getData",
            json=MOCK_GETDATA_RESPONSE,
            status=200,
        )

        _register_mock_aurn_and_sos()
        sos._network_mappings["aurn"] = {
            "CLL2": [{"ts_id": "3", "measurand": "NO2", "uom": "ug/m3"}],
        }

        df = api.get_current("AURN", sites=["CLL2"])
        assert not df.empty
        assert len(df) == 1
        assert df["site_code"].iloc[0] == "CLL2"

    @responses.activate
    def test_direct_sos_name(self):
        """get_current('AURN-SOS', ...) works directly."""
        responses.add(
            responses.GET,
            f"{sos.SOS_BASE_URL}/timeseries/3/getData",
            json=MOCK_GETDATA_RESPONSE,
            status=200,
        )

        _register_mock_aurn_and_sos()
        sos._network_mappings["aurn"] = {
            "CLL2": [{"ts_id": "3", "measurand": "NO2", "uom": "ug/m3"}],
        }

        df = api.get_current("AURN-SOS", sites=["CLL2"])
        assert not df.empty

    def test_unknown_source_raises(self):
        """get_current with unknown source raises ValueError."""
        with pytest.raises(ValueError, match="Unknown source"):
            api.get_current("NONEXISTENT", sites=["X"])

    @responses.activate
    def test_returns_standard_schema(self):
        """get_current returns the 8-column standard schema."""
        responses.add(
            responses.GET,
            f"{sos.SOS_BASE_URL}/timeseries/3/getData",
            json=MOCK_GETDATA_RESPONSE,
            status=200,
        )

        _register_mock_aurn_and_sos()
        sos._network_mappings["aurn"] = {
            "CLL2": [{"ts_id": "3", "measurand": "NO2", "uom": "ug/m3"}],
        }

        df = api.get_current("AURN", sites=["CLL2"])
        assert list(df.columns) == DATA_COLUMNS


# ============================================================================
# Static mapping
# ============================================================================


MOCK_STATIC_MAPPING = {
    "_generated": datetime.now(tz=timezone.utc).isoformat(),
    "aurn": {
        "MY1": [{"ts_id": "100", "measurand": "NO2", "uom": "ug/m3"}],
        "CLL2": [{"ts_id": "3", "measurand": "NO2", "uom": "ug/m3"}],
    },
    "saqn": {},
}


class TestStaticMapping:
    def test_load_static_mapping(self, tmp_path, monkeypatch):
        """_load_static_mapping reads JSON file correctly."""
        mapping_file = tmp_path / "_sos_mapping.json"
        mapping_file.write_text(json.dumps(MOCK_STATIC_MAPPING))
        monkeypatch.setattr(sos, "_MAPPING_FILE", mapping_file)

        result = sos._load_static_mapping()
        assert result is not None
        assert "aurn" in result
        assert "MY1" in result["aurn"]

    def test_load_returns_none_when_missing(self, tmp_path, monkeypatch):
        """_load_static_mapping returns None when file doesn't exist."""
        monkeypatch.setattr(sos, "_MAPPING_FILE", tmp_path / "nonexistent.json")
        assert sos._load_static_mapping() is None

    def test_load_returns_none_on_corrupt_json(self, tmp_path, monkeypatch):
        """_load_static_mapping returns None on invalid JSON."""
        bad_file = tmp_path / "_sos_mapping.json"
        bad_file.write_text("not valid json {{{")
        monkeypatch.setattr(sos, "_MAPPING_FILE", bad_file)
        assert sos._load_static_mapping() is None

    def test_staleness_warning(self, tmp_path, monkeypatch):
        """Warns when static mapping is older than 90 days."""
        old_date = (datetime.now(tz=timezone.utc) - timedelta(days=100)).isoformat()
        old_mapping = dict(MOCK_STATIC_MAPPING)
        old_mapping["_generated"] = old_date

        mapping_file = tmp_path / "_sos_mapping.json"
        mapping_file.write_text(json.dumps(old_mapping))
        monkeypatch.setattr(sos, "_MAPPING_FILE", mapping_file)

        with pytest.warns(sos.AeolusDataWarning, match="days old"):
            sos._load_static_mapping()

    def test_no_warning_when_fresh(self, tmp_path, monkeypatch):
        """No warning when mapping is recent."""
        mapping_file = tmp_path / "_sos_mapping.json"
        mapping_file.write_text(json.dumps(MOCK_STATIC_MAPPING))
        monkeypatch.setattr(sos, "_MAPPING_FILE", mapping_file)

        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            result = sos._load_static_mapping()

        assert result is not None

    def test_get_network_mapping_uses_static(self, tmp_path, monkeypatch):
        """_get_network_mapping uses static file when available."""
        mapping_file = tmp_path / "_sos_mapping.json"
        mapping_file.write_text(json.dumps(MOCK_STATIC_MAPPING))
        monkeypatch.setattr(sos, "_MAPPING_FILE", mapping_file)

        result = sos._get_network_mapping("aurn")
        assert "MY1" in result
        assert result["MY1"][0]["ts_id"] == "100"

    def test_get_network_mapping_falls_back_to_live(self, tmp_path, monkeypatch):
        """_get_network_mapping falls back when network not in static file."""
        # Static mapping only has aurn and saqn
        mapping_file = tmp_path / "_sos_mapping.json"
        mapping_file.write_text(json.dumps(MOCK_STATIC_MAPPING))
        monkeypatch.setattr(sos, "_MAPPING_FILE", mapping_file)

        # Mock _build_station_mapping for the fallback
        monkeypatch.setattr(
            sos,
            "_build_station_mapping",
            lambda net: {"LIVE1": [{"ts_id": "999", "measurand": "O3", "uom": "ug/m3"}]},
        )

        result = sos._get_network_mapping("waqn")
        assert "LIVE1" in result

    @responses.activate
    def test_rebuild_sos_mapping(self, tmp_path, monkeypatch):
        """rebuild_sos_mapping writes valid JSON with expected structure."""
        mapping_file = tmp_path / "_sos_mapping.json"
        monkeypatch.setattr(sos, "_MAPPING_FILE", mapping_file)

        # Mock _build_station_mapping to avoid real API calls
        monkeypatch.setattr(
            sos,
            "_build_station_mapping",
            lambda net: {"SITE1": [{"ts_id": "1", "measurand": "NO2", "uom": "ug/m3"}]},
        )

        path = sos.rebuild_sos_mapping()
        assert path == mapping_file
        assert mapping_file.exists()

        with open(mapping_file) as f:
            data = json.load(f)

        assert "_generated" in data
        for net in ["aurn", "saqn", "waqn", "ni", "aqe"]:
            assert net in data
            assert "SITE1" in data[net]
