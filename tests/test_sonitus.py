"""Tests for Sonitus (Dublin City) data source."""

from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
import pytest

from aeolus.types import DATA_COLUMNS, METADATA_COLUMNS


@pytest.fixture(autouse=True)
def ensure_source_registered():
    from aeolus.sources import sonitus  # noqa: F401


MOCK_MONITORS_RESPONSE = [
    {
        "serial_number": "DCC-AQ1",
        "label": "National Air 1",
        "location": "Civic Centre",
        "latitude": "53.3442389",
        "longitude": "-6.271525",
        "last_calibrated": None,
    },
    {
        "serial_number": "TNO4435",
        "label": "Local Air 2",
        "location": "Drumcondra",
        "latitude": "53.3699",
        "longitude": "-6.2591",
        "last_calibrated": None,
    },
    {
        "serial_number": "01749",
        "label": "Noise 2",
        "location": "Bull Island",
        "latitude": "53.36866",
        "longitude": "-6.149316",
        "last_calibrated": "2025-08-07",
    },
    {
        "serial_number": "DCC-AQ5",
        "label": "National Air 5",
        "location": "Ballyfermot",
        "latitude": "53.340148",
        "longitude": "-6.35181",
        "last_calibrated": None,
    },
]


class TestFetchMetadata:
    @patch("aeolus.sources.sonitus._call_sonitus_api")
    def test_returns_standard_metadata_columns(self, mock_api):
        from aeolus.sources.sonitus import fetch_sonitus_metadata

        mock_api.return_value = MOCK_MONITORS_RESPONSE
        df = fetch_sonitus_metadata()
        for col in METADATA_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    @patch("aeolus.sources.sonitus._call_sonitus_api")
    def test_filters_noise_monitors(self, mock_api):
        from aeolus.sources.sonitus import fetch_sonitus_metadata

        mock_api.return_value = MOCK_MONITORS_RESPONSE
        df = fetch_sonitus_metadata()
        assert len(df) == 3  # DCC-AQ1, TNO4435, DCC-AQ5
        serials = df["site_code"].tolist()
        assert "01749" not in serials

    @patch("aeolus.sources.sonitus._call_sonitus_api")
    def test_serial_number_as_site_code(self, mock_api):
        from aeolus.sources.sonitus import fetch_sonitus_metadata

        mock_api.return_value = MOCK_MONITORS_RESPONSE
        df = fetch_sonitus_metadata()
        assert "DCC-AQ1" in df["site_code"].values

    @patch("aeolus.sources.sonitus._call_sonitus_api")
    def test_coordinates_are_float(self, mock_api):
        from aeolus.sources.sonitus import fetch_sonitus_metadata

        mock_api.return_value = MOCK_MONITORS_RESPONSE
        df = fetch_sonitus_metadata()
        assert df["latitude"].dtype == float
        assert df["longitude"].dtype == float

    @patch("aeolus.sources.sonitus._call_sonitus_api")
    def test_source_network_is_sonitus(self, mock_api):
        from aeolus.sources.sonitus import fetch_sonitus_metadata

        mock_api.return_value = MOCK_MONITORS_RESPONSE
        df = fetch_sonitus_metadata()
        assert all(df["source_network"] == "SONITUS")

    @patch("aeolus.sources.sonitus._call_sonitus_api")
    def test_excludes_monitors_without_coordinates(self, mock_api):
        from aeolus.sources.sonitus import fetch_sonitus_metadata

        monitors = MOCK_MONITORS_RESPONSE + [
            {
                "serial_number": "01530",
                "label": "Noise 19 Spare",
                "location": "In Office",
                "latitude": "",
                "longitude": "",
                "last_calibrated": None,
            }
        ]
        mock_api.return_value = monitors
        df = fetch_sonitus_metadata()
        assert "01530" not in df["site_code"].values


MOCK_GAS_DATA = [
    {"datetime": "2025-06-01 01:00:00", "no2": 15.5, "so2": 0.8, "co": 0.2, "no": 3.1},
    {"datetime": "2025-06-01 01:15:00", "no2": 12.3, "so2": -0.6, "co": 0.15, "no": 2.8},
]

MOCK_PM_DATA = [
    {"datetime": "2025-06-01 01:00:00", "pm1": 2.1, "pm2_5": 5.3, "pm10": 8.7, "tsp": 12.0},
    {"datetime": "2025-06-01 01:15:00", "pm1": 1.8, "pm2_5": 4.9, "pm10": 7.2, "tsp": 10.5},
]


class TestNormaliseSonitusData:
    def test_normalise_gas_data(self):
        from aeolus.sources.sonitus import normalise_sonitus_data
        normaliser = normalise_sonitus_data("DCC-AQ1")
        raw = pd.DataFrame(MOCK_GAS_DATA)
        df = normaliser(raw)
        for col in DATA_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"
        assert len(df) == 8  # 2 rows x 4 measurands
        assert set(df["measurand"]) == {"NO2", "SO2", "CO", "NO"}
        assert all(df["site_code"] == "DCC-AQ1")

    def test_normalise_pm_data(self):
        from aeolus.sources.sonitus import normalise_sonitus_data
        normaliser = normalise_sonitus_data("TNO4435")
        raw = pd.DataFrame(MOCK_PM_DATA)
        df = normaliser(raw)
        assert set(df["measurand"]) == {"PM1", "PM2.5", "PM10", "TSP"}
        assert all(df["site_code"] == "TNO4435")

    def test_units_are_ug_m3(self):
        from aeolus.sources.sonitus import normalise_sonitus_data
        normaliser = normalise_sonitus_data("DCC-AQ1")
        df = normaliser(pd.DataFrame(MOCK_GAS_DATA))
        assert all(df["units"] == "ug/m3")

    def test_source_network_is_sonitus(self):
        from aeolus.sources.sonitus import normalise_sonitus_data
        normaliser = normalise_sonitus_data("DCC-AQ1")
        df = normaliser(pd.DataFrame(MOCK_GAS_DATA))
        assert all(df["source_network"] == "SONITUS")

    def test_negative_values_passed_through(self):
        from aeolus.sources.sonitus import normalise_sonitus_data
        normaliser = normalise_sonitus_data("DCC-AQ1")
        df = normaliser(pd.DataFrame(MOCK_GAS_DATA))
        so2_vals = df[df["measurand"] == "SO2"]["value"].tolist()
        assert any(v < 0 for v in so2_vals)

    def test_ratification_is_unvalidated(self):
        from aeolus.sources.sonitus import normalise_sonitus_data
        normaliser = normalise_sonitus_data("DCC-AQ1")
        df = normaliser(pd.DataFrame(MOCK_GAS_DATA))
        assert all(df["ratification"] == "Unvalidated")


class TestFetchSonitusData:
    @patch("aeolus.sources.sonitus._call_sonitus_api")
    def test_returns_standard_columns(self, mock_api):
        from aeolus.sources.sonitus import fetch_sonitus_data
        mock_api.return_value = MOCK_GAS_DATA
        df = fetch_sonitus_data(
            ["DCC-AQ1"],
            datetime(2025, 6, 1, tzinfo=timezone.utc),
            datetime(2025, 6, 2, tzinfo=timezone.utc),
        )
        for col in DATA_COLUMNS:
            assert col in df.columns

    @patch("aeolus.sources.sonitus._call_sonitus_api")
    def test_multi_site_concatenation(self, mock_api):
        from aeolus.sources.sonitus import fetch_sonitus_data
        mock_api.side_effect = [MOCK_GAS_DATA, MOCK_PM_DATA]
        df = fetch_sonitus_data(
            ["DCC-AQ1", "TNO4435"],
            datetime(2025, 6, 1, tzinfo=timezone.utc),
            datetime(2025, 6, 2, tzinfo=timezone.utc),
        )
        assert set(df["site_code"]) == {"DCC-AQ1", "TNO4435"}

    @patch("aeolus.sources.sonitus._call_sonitus_api")
    def test_empty_response_returns_empty_frame(self, mock_api):
        from aeolus.sources.sonitus import fetch_sonitus_data
        mock_api.return_value = []
        df = fetch_sonitus_data(
            ["DCC-AQ1"],
            datetime(2025, 6, 1, tzinfo=timezone.utc),
            datetime(2025, 6, 2, tzinfo=timezone.utc),
        )
        assert len(df) == 0
        assert "site_code" in df.columns


class TestSourceRegistration:
    """Test Sonitus source is properly registered."""

    def test_sonitus_registered(self):
        from aeolus.registry import get_source

        spec = get_source("SONITUS")
        assert spec is not None
        assert spec["name"] == "Smart Dublin (Sonitus)"
        assert spec["type"] == "network"
        assert spec["requires_api_key"] is False

    def test_sonitus_in_list_sources(self):
        from aeolus.registry import list_sources

        sources = list_sources()
        assert "SONITUS" in sources
