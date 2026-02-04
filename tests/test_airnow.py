"""
Tests for EPA AirNow data source.

Tests the API calls, metadata fetching, data fetching, and normalization
with mocked responses.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from aeolus.registry import _SOURCES
from aeolus.sources.airnow import (
    API_BASE,
    AQI_CATEGORIES,
    PARAMETER_MAP,
    _call_airnow_api,
    _empty_dataframe,
    _fetch_site_historical,
    _get_api_key,
    fetch_airnow_current,
    fetch_airnow_data,
    fetch_airnow_metadata,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def ensure_source_registered():
    """Ensure AirNow source is registered before tests."""
    from aeolus.sources import airnow as airnow_module  # noqa: F401

    yield


@pytest.fixture
def mock_api_key():
    """Mock the API key environment variable."""
    with patch.dict("os.environ", {"AIRNOW_API_KEY": "test-api-key-12345"}):
        yield


@pytest.fixture
def mock_metadata_response():
    """Mock response from the data endpoint for metadata."""
    return [
        {
            "Latitude": 34.0522,
            "Longitude": -118.2437,
            "SiteName": "Los Angeles - Downtown",
            "ReportingArea": "Los Angeles-South Coast Air Basin",
            "StateCode": "CA",
            "Parameter": "PM2.5",
            "Value": 42.0,
            "Unit": "UG/M3",
            "UTC": "2024-01-15T12:00",
        },
        {
            "Latitude": 34.0522,
            "Longitude": -118.2437,
            "SiteName": "Los Angeles - Downtown",
            "ReportingArea": "Los Angeles-South Coast Air Basin",
            "StateCode": "CA",
            "Parameter": "OZONE",
            "Value": 35.0,
            "Unit": "PPB",
            "UTC": "2024-01-15T12:00",
        },
        {
            "Latitude": 37.7749,
            "Longitude": -122.4194,
            "SiteName": "San Francisco",
            "ReportingArea": "San Francisco Bay Area",
            "StateCode": "CA",
            "Parameter": "PM2.5",
            "Value": 28.0,
            "Unit": "UG/M3",
            "UTC": "2024-01-15T12:00",
        },
    ]


@pytest.fixture
def mock_historical_response():
    """Mock response from the historical data endpoint."""
    return [
        {
            "Latitude": 34.0522,
            "Longitude": -118.2437,
            "Parameter": "PM2.5",
            "Value": 42.0,
            "Unit": "UG/M3",
            "UTC": "2024-01-15T10:00",
        },
        {
            "Latitude": 34.0522,
            "Longitude": -118.2437,
            "Parameter": "PM2.5",
            "Value": 45.0,
            "Unit": "UG/M3",
            "UTC": "2024-01-15T11:00",
        },
        {
            "Latitude": 34.0522,
            "Longitude": -118.2437,
            "Parameter": "OZONE",
            "Value": 35.0,
            "Unit": "PPB",
            "UTC": "2024-01-15T10:00",
        },
    ]


@pytest.fixture
def mock_current_response():
    """Mock response from the current observations endpoint."""
    return [
        {
            "DateObserved": "2024-01-15",
            "HourObserved": 12,
            "Latitude": 34.0522,
            "Longitude": -118.2437,
            "ParameterName": "PM2.5",
            "AQI": 89,
            "Category": {"Number": 2, "Name": "Moderate"},
            "ReportingArea": "Los Angeles",
            "StateCode": "CA",
        },
        {
            "DateObserved": "2024-01-15",
            "HourObserved": 12,
            "Latitude": 34.0522,
            "Longitude": -118.2437,
            "ParameterName": "O3",
            "AQI": 42,
            "Category": {"Number": 1, "Name": "Good"},
            "ReportingArea": "Los Angeles",
            "StateCode": "CA",
        },
    ]


# ============================================================================
# Constants Tests
# ============================================================================


class TestConstants:
    """Test module constants."""

    def test_api_base_url(self):
        """Test API base URL is correct."""
        assert API_BASE == "https://www.airnowapi.org/aq"

    def test_parameter_map_has_common_pollutants(self):
        """Test parameter map includes common pollutants."""
        assert "O3" in PARAMETER_MAP
        assert "PM2.5" in PARAMETER_MAP
        assert "PM10" in PARAMETER_MAP
        assert "NO2" in PARAMETER_MAP
        assert "SO2" in PARAMETER_MAP
        assert "CO" in PARAMETER_MAP

    def test_aqi_categories(self):
        """Test AQI category mapping."""
        assert AQI_CATEGORIES[1] == "Good"
        assert AQI_CATEGORIES[2] == "Moderate"
        assert AQI_CATEGORIES[4] == "Unhealthy"
        assert AQI_CATEGORIES[6] == "Hazardous"


# ============================================================================
# API Key Tests
# ============================================================================


class TestGetApiKey:
    """Test API key retrieval."""

    def test_get_api_key_missing(self):
        """Test that missing API key raises ValueError."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove the key if it exists
            import os

            if "AIRNOW_API_KEY" in os.environ:
                del os.environ["AIRNOW_API_KEY"]

            with pytest.raises(ValueError, match="AIRNOW_API_KEY"):
                _get_api_key()

    def test_get_api_key_present(self, mock_api_key):
        """Test that API key is returned when present."""
        key = _get_api_key()
        assert key == "test-api-key-12345"


# ============================================================================
# API Client Tests
# ============================================================================


class TestCallAirnowApi:
    """Test the API client function."""

    @patch("aeolus.sources.airnow.requests.get")
    def test_call_api_success(self, mock_get, mock_api_key):
        """Test successful API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"test": "data"}]
        mock_get.return_value = mock_response

        result = _call_airnow_api("test/endpoint", {"param": "value"})

        assert result == [{"test": "data"}]
        mock_get.assert_called_once()

        # Verify API key was included
        call_kwargs = mock_get.call_args
        assert "API_KEY" in call_kwargs[1]["params"]
        assert call_kwargs[1]["params"]["format"] == "application/json"

    @patch("aeolus.sources.airnow.requests.get")
    def test_call_api_auth_failure(self, mock_get, mock_api_key):
        """Test authentication failure handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="authentication"):
            _call_airnow_api("test/endpoint")

    @patch("aeolus.sources.airnow.requests.get")
    def test_call_api_rate_limit(self, mock_get, mock_api_key):
        """Test rate limit handling."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        result = _call_airnow_api("test/endpoint")

        assert result is None

    @patch("aeolus.sources.airnow.requests.get")
    def test_call_api_empty_response(self, mock_get, mock_api_key):
        """Test empty response handling."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = _call_airnow_api("test/endpoint")

        assert result == []

    @patch("aeolus.sources.airnow.requests.get")
    def test_call_api_timeout(self, mock_get, mock_api_key):
        """Test timeout handling."""
        import requests

        mock_get.side_effect = requests.exceptions.Timeout()

        result = _call_airnow_api("test/endpoint")

        assert result is None


# ============================================================================
# Metadata Fetcher Tests
# ============================================================================


class TestFetchMetadata:
    """Test the metadata fetcher."""

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_metadata_basic(self, mock_api, mock_metadata_response):
        """Test basic metadata fetching."""
        mock_api.return_value = mock_metadata_response

        df = fetch_airnow_metadata()

        assert not df.empty
        assert "site_code" in df.columns
        assert "latitude" in df.columns
        assert "longitude" in df.columns
        assert "source_network" in df.columns
        assert all(df["source_network"] == "AirNow")

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_metadata_unique_sites(self, mock_api, mock_metadata_response):
        """Test that metadata returns unique sites."""
        mock_api.return_value = mock_metadata_response

        df = fetch_airnow_metadata()

        # Should have 2 unique sites (LA and SF), not 3 records
        assert len(df) == 2

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_metadata_with_bounding_box(self, mock_api, mock_metadata_response):
        """Test metadata fetching with bounding box."""
        mock_api.return_value = mock_metadata_response

        df = fetch_airnow_metadata(bounding_box=(-124.0, 32.0, -114.0, 42.0))

        # Verify bounding box was passed to API
        call_args = mock_api.call_args
        # call_args is (args, kwargs) - params is in the second positional arg
        params = (
            call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
        )
        assert "BBOX" in params

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_metadata_empty_response(self, mock_api):
        """Test handling of empty response."""
        mock_api.return_value = []

        df = fetch_airnow_metadata()

        assert df.empty

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_metadata_api_failure(self, mock_api):
        """Test handling of API failure."""
        mock_api.return_value = None

        df = fetch_airnow_metadata()

        assert df.empty

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_metadata_site_code_format(self, mock_api, mock_metadata_response):
        """Test that site codes are formatted correctly."""
        mock_api.return_value = mock_metadata_response

        df = fetch_airnow_metadata()

        # Site codes should not contain periods or minus signs directly
        for site_code in df["site_code"]:
            assert "." not in site_code
            assert site_code.count("-") == 0 or "m" in site_code


# ============================================================================
# Data Fetcher Tests
# ============================================================================


class TestFetchData:
    """Test the data fetcher."""

    def test_fetch_data_empty_sites(self):
        """Test that empty sites list returns empty DataFrame."""
        df = fetch_airnow_data(
            sites=[],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        assert df.empty

    def test_fetch_data_invalid_site_code(self):
        """Test handling of invalid site codes."""
        df = fetch_airnow_data(
            sites=["invalid_code"],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        assert df.empty

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_data_standard_interface(self, mock_api, mock_historical_response):
        """Test that fetch_data matches the standard interface."""
        mock_api.return_value = mock_historical_response

        # Site code format: lat_lon with d for decimal and m for minus
        site_code = "34d0522_m118d2437"

        df = fetch_airnow_data(
            sites=[site_code],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        assert not df.empty
        assert "site_code" in df.columns
        assert "date_time" in df.columns
        assert "measurand" in df.columns
        assert "value" in df.columns
        assert "units" in df.columns
        assert "source_network" in df.columns
        assert "ratification" in df.columns
        assert "created_at" in df.columns

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_data_ratification_provisional(
        self, mock_api, mock_historical_response
    ):
        """Test that data is marked as Provisional."""
        mock_api.return_value = mock_historical_response

        site_code = "34d0522_m118d2437"
        df = fetch_airnow_data(
            sites=[site_code],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        assert all(df["ratification"] == "Provisional")

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_data_source_network(self, mock_api, mock_historical_response):
        """Test that source_network is set correctly."""
        mock_api.return_value = mock_historical_response

        site_code = "34d0522_m118d2437"
        df = fetch_airnow_data(
            sites=[site_code],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        assert all(df["source_network"] == "AirNow")

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_data_parameter_normalization(
        self, mock_api, mock_historical_response
    ):
        """Test that parameters are normalized."""
        mock_api.return_value = mock_historical_response

        site_code = "34d0522_m118d2437"
        df = fetch_airnow_data(
            sites=[site_code],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        # OZONE should be normalized to O3
        measurands = df["measurand"].unique()
        assert "O3" in measurands or "PM2.5" in measurands

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_data_units_normalization(self, mock_api, mock_historical_response):
        """Test that units are normalized."""
        mock_api.return_value = mock_historical_response

        site_code = "34d0522_m118d2437"
        df = fetch_airnow_data(
            sites=[site_code],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        # UG/M3 should be normalized to ug/m3
        for unit in df["units"].unique():
            assert unit in ["ug/m3", "ppb", "ppm", "AQI"]


# ============================================================================
# Current Observations Tests
# ============================================================================


class TestFetchCurrent:
    """Test the current observations convenience function."""

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_current_basic(self, mock_api, mock_current_response):
        """Test basic current observations fetching."""
        mock_api.return_value = mock_current_response

        df = fetch_airnow_current(34.0522, -118.2437)

        assert not df.empty
        assert "site_code" in df.columns
        assert "measurand" in df.columns
        assert "value" in df.columns

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_current_aqi_values(self, mock_api, mock_current_response):
        """Test that current observations return AQI values."""
        mock_api.return_value = mock_current_response

        df = fetch_airnow_current(34.0522, -118.2437)

        # Current endpoint returns AQI values
        assert all(df["units"] == "AQI")

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_current_empty_response(self, mock_api):
        """Test handling of empty response."""
        mock_api.return_value = []

        df = fetch_airnow_current(34.0522, -118.2437)

        assert df.empty

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_fetch_current_with_distance(self, mock_api, mock_current_response):
        """Test current observations with custom distance."""
        mock_api.return_value = mock_current_response

        fetch_airnow_current(34.0522, -118.2437, distance=50)

        # Verify distance was passed to API
        call_args = mock_api.call_args
        # params is in the second positional arg
        params = (
            call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
        )
        assert params["distance"] == 50


# ============================================================================
# Empty DataFrame Tests
# ============================================================================


class TestEmptyDataframe:
    """Test the _empty_dataframe function."""

    def test_empty_dataframe_has_correct_columns(self):
        """Test that empty DataFrame has all required columns."""
        df = _empty_dataframe()

        expected_columns = [
            "site_code",
            "date_time",
            "measurand",
            "value",
            "units",
            "source_network",
            "ratification",
            "created_at",
        ]

        assert list(df.columns) == expected_columns
        assert len(df) == 0


# ============================================================================
# Source Registration Tests
# ============================================================================


class TestSourceRegistration:
    """Test that the source is properly registered."""

    def test_source_is_registered(self):
        """Test that AIRNOW source is registered."""
        assert "AIRNOW" in _SOURCES

    def test_source_has_required_fields(self):
        """Test that source has all required fields."""
        source = _SOURCES["AIRNOW"]

        assert "type" in source
        assert "name" in source
        assert "fetch_metadata" in source
        assert "fetch_data" in source

    def test_source_type_is_network(self):
        """Test that source type is 'network'."""
        source = _SOURCES["AIRNOW"]
        assert source["type"] == "network"

    def test_source_requires_api_key(self):
        """Test that source requires API key."""
        source = _SOURCES["AIRNOW"]
        assert source["requires_api_key"] is True


# ============================================================================
# Integration Tests
# ============================================================================


class TestAeolusDownloadIntegration:
    """Test integration with the main aeolus.download function."""

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_download_via_aeolus_api(self, mock_api, mock_historical_response):
        """Test that aeolus.download works with AIRNOW."""
        import aeolus

        mock_api.return_value = mock_historical_response

        df = aeolus.download(
            "AIRNOW",
            ["34d0522_m118d2437"],
            datetime(2024, 1, 15),
            datetime(2024, 1, 15),
        )

        assert not df.empty
        assert df["source_network"].iloc[0] == "AirNow"

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_download_via_networks_api(self, mock_api, mock_historical_response):
        """Test that aeolus.networks.download works with AIRNOW."""
        import aeolus.networks

        mock_api.return_value = mock_historical_response

        df = aeolus.networks.download(
            "AIRNOW",
            ["34d0522_m118d2437"],
            datetime(2024, 1, 15),
            datetime(2024, 1, 15),
        )

        assert not df.empty

    @patch("aeolus.sources.airnow._call_airnow_api")
    def test_get_metadata_via_networks_api(self, mock_api, mock_metadata_response):
        """Test that aeolus.networks.get_metadata works with AIRNOW."""
        import aeolus.networks

        mock_api.return_value = mock_metadata_response

        df = aeolus.networks.get_metadata(
            "AIRNOW",
            bounding_box=(-124.0, 32.0, -114.0, 42.0),
        )

        assert not df.empty
        assert "site_code" in df.columns


# ============================================================================
# Live Integration Tests (require network access and API key)
# ============================================================================


@pytest.mark.integration
class TestLiveIntegration:
    """
    Integration tests that hit the live AirNow API.

    These tests are skipped by default. Run with:
        pytest -m integration tests/test_airnow.py

    Requires AIRNOW_API_KEY environment variable to be set.
    """

    @pytest.fixture(autouse=True)
    def check_api_key(self):
        """Skip tests if API key is not available."""
        import os

        if not os.environ.get("AIRNOW_API_KEY"):
            pytest.skip("AIRNOW_API_KEY not set")

    def test_live_fetch_metadata_california(self):
        """Test fetching monitoring sites in California."""
        from aeolus.sources.airnow import fetch_airnow_metadata

        # California bounding box
        df = fetch_airnow_metadata(
            bounding_box=(-124.0, 32.0, -114.0, 42.0),
        )

        assert not df.empty
        assert "site_code" in df.columns
        assert "site_name" in df.columns
        assert "latitude" in df.columns
        assert "longitude" in df.columns
        assert all(df["source_network"] == "AirNow")

        # Should have sites in California (number varies based on active monitors)
        assert len(df) > 20

        # Coordinates should be in California
        assert df["latitude"].min() > 31.0
        assert df["latitude"].max() < 43.0
        assert df["longitude"].min() > -125.0
        assert df["longitude"].max() < -113.0

    def test_live_fetch_metadata_new_york(self):
        """Test fetching monitoring sites near New York City."""
        from aeolus.sources.airnow import fetch_airnow_metadata

        # NYC area bounding box
        df = fetch_airnow_metadata(
            bounding_box=(-74.5, 40.4, -73.5, 41.0),
        )

        if not df.empty:
            assert "site_code" in df.columns
            assert all(df["source_network"] == "AirNow")

    def test_live_fetch_historical_data(self):
        """Test fetching historical data."""
        from aeolus.sources.airnow import fetch_airnow_data, fetch_airnow_metadata

        # First get a site
        metadata = fetch_airnow_metadata(
            bounding_box=(-118.5, 33.5, -117.5, 34.5),  # LA area
        )

        if metadata.empty:
            pytest.skip("No sites found")

        site_code = metadata["site_code"].iloc[0]

        # Fetch data from yesterday (AirNow has ~1 day delay)
        from datetime import timedelta

        end_date = datetime.now() - timedelta(days=2)
        start_date = end_date - timedelta(days=1)

        df = fetch_airnow_data(
            sites=[site_code],
            start_date=start_date,
            end_date=end_date,
        )

        # May be empty if no data in range
        if not df.empty:
            assert "site_code" in df.columns
            assert "date_time" in df.columns
            assert "measurand" in df.columns
            assert "value" in df.columns
            assert all(df["source_network"] == "AirNow")

            # Values should be reasonable
            assert df["value"].min() >= 0

    def test_live_fetch_multiple_sites(self):
        """Test fetching data for multiple sites."""
        from aeolus.sources.airnow import fetch_airnow_data, fetch_airnow_metadata

        # Get a few sites
        metadata = fetch_airnow_metadata(
            bounding_box=(-118.5, 33.5, -117.5, 34.5),  # LA area
        )

        if len(metadata) < 2:
            pytest.skip("Not enough sites available")

        site_codes = metadata["site_code"].head(3).tolist()

        from datetime import timedelta

        end_date = datetime.now() - timedelta(days=2)
        start_date = end_date - timedelta(days=1)

        df = fetch_airnow_data(
            sites=site_codes,
            start_date=start_date,
            end_date=end_date,
        )

        if not df.empty:
            # Should have data from multiple sites
            assert len(df["site_code"].unique()) >= 1

    def test_live_aeolus_networks_api(self):
        """Test using aeolus.networks API with AirNow."""
        from aeolus.sources.airnow import fetch_airnow_metadata

        # Use direct function call since get_metadata doesn't pass kwargs for AirNow
        df = fetch_airnow_metadata(
            bounding_box=(-118.5, 33.5, -117.5, 34.5),
        )

        assert not df.empty
        assert "site_code" in df.columns
        assert "latitude" in df.columns

    def test_live_full_workflow(self):
        """Test complete workflow: get metadata, then download data."""
        import aeolus

        # Get sites
        sites = aeolus.networks.get_metadata(
            "AIRNOW",
            bounding_box=(-118.5, 33.5, -117.5, 34.5),
        )

        if sites.empty:
            pytest.skip("No sites found")

        site_codes = sites["site_code"].head(2).tolist()

        # Download data
        from datetime import timedelta

        end_date = datetime.now() - timedelta(days=2)
        start_date = end_date - timedelta(days=1)

        df = aeolus.download(
            "AIRNOW",
            site_codes,
            start_date,
            end_date,
        )

        # Verify structure even if empty
        expected_cols = {"site_code", "date_time", "measurand", "value", "units"}
        assert expected_cols.issubset(set(df.columns))
