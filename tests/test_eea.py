"""Tests for EEA data source."""

import io
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from aeolus.types import DATA_COLUMNS, METADATA_COLUMNS


@pytest.fixture(autouse=True)
def ensure_source_registered():
    """Ensure EEA source is registered."""
    from aeolus.sources import eea  # noqa: F401


MOCK_ESRI_RESPONSE = {
    "features": [
        {
            "attributes": {
                "AirQualityStationEoICode": "IE0131A",
                "AQStationName": "Dublin Blanchardstown",
                "Country": "Ireland",
                "CountryCode": "IE",
                "PopupInfo": (
                    "<p>PM10</a>, ug/m<sup>3</sup>, (2013 - 2024) </p>"
                    "<p>NO2</a>, ug/m<sup>3</sup>, (2013 - 2024) </p>"
                ),
            },
            "geometry": {"x": -709094.02, "y": 7054644.44},
        },
        {
            "attributes": {
                "AirQualityStationEoICode": "IE007CP",
                "AQStationName": "Limerick Peoples Park",
                "Country": "Ireland",
                "CountryCode": "IE",
                "PopupInfo": "<p>O3</a>, ug/m<sup>3</sup>, (2020 - 2024) </p>",
            },
            "geometry": {"x": -960542.49, "y": 6920096.15},
        },
    ]
}


class TestFetchMetadata:
    @patch("aeolus.sources.eea._call_esri_api")
    def test_returns_standard_metadata_columns(self, mock_api):
        from aeolus.sources.eea import fetch_eea_metadata

        mock_api.return_value = MOCK_ESRI_RESPONSE
        df = fetch_eea_metadata(country="IE")

        for col in METADATA_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"
        assert len(df) == 2
        assert df.iloc[0]["site_code"] == "IE0131A"
        assert df.iloc[0]["source_network"] == "EEA"

    @patch("aeolus.sources.eea._call_esri_api")
    def test_converts_web_mercator_to_wgs84(self, mock_api):
        from aeolus.sources.eea import fetch_eea_metadata

        mock_api.return_value = MOCK_ESRI_RESPONSE
        df = fetch_eea_metadata(country="IE")

        assert -7.0 < df.iloc[0]["longitude"] < -6.0
        assert 53.0 < df.iloc[0]["latitude"] < 54.0

    @patch("aeolus.sources.eea._call_esri_api")
    def test_country_filter_passed_to_api(self, mock_api):
        from aeolus.sources.eea import fetch_eea_metadata

        mock_api.return_value = {"features": []}
        fetch_eea_metadata(country="DE")

        call_kwargs = mock_api.call_args
        assert "DE" in str(call_kwargs)

    @patch("aeolus.sources.eea._call_esri_api")
    def test_bbox_filter_uses_spatial_query(self, mock_api):
        from aeolus.sources.eea import fetch_eea_metadata

        mock_api.return_value = {"features": []}
        fetch_eea_metadata(bbox=(-7.0, 51.0, -6.0, 54.0))

        assert mock_api.called

    @patch("aeolus.sources.eea._call_esri_api")
    def test_no_filters_fetches_all_with_pagination(self, mock_api):
        from aeolus.sources.eea import fetch_eea_metadata

        page1 = {"features": [MOCK_ESRI_RESPONSE["features"][0]] * 2000, "exceededTransferLimit": True}
        page2 = {"features": [MOCK_ESRI_RESPONSE["features"][1]] * 500}
        mock_api.side_effect = [page1, page2]

        df = fetch_eea_metadata()
        assert len(df) == 2500
        assert mock_api.call_count == 2

    @patch("aeolus.sources.eea._call_esri_api")
    def test_empty_response_returns_empty_metadata_frame(self, mock_api):
        from aeolus.sources.eea import fetch_eea_metadata

        mock_api.return_value = {"features": []}
        df = fetch_eea_metadata(country="XX")

        assert len(df) == 0
        for col in METADATA_COLUMNS:
            assert col in df.columns
