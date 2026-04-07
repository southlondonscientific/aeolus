"""Tests for Sonitus (Dublin City) data source."""

from unittest.mock import patch

import pytest

from aeolus.types import METADATA_COLUMNS


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
