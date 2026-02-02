"""
Tests for AirQo data source.

Tests the API calls, metadata fetching, data fetching, and normalization
pipeline with mocked HTTP responses.
"""

from datetime import datetime

import pandas as pd
import pytest
import responses

from aeolus.sources.airqo import (
    AIRQO_API_BASE,
    PARAMETER_MAP,
    _call_airqo_api,
    _create_metadata_normalizer,
    create_airqo_normalizer,
    fetch_airqo_data,
    fetch_airqo_data_by_grid,
    fetch_airqo_grids,
    fetch_airqo_metadata,
)

# ============================================================================
# Fixtures for Mock API Responses
# ============================================================================


@pytest.fixture
def mock_sites_response():
    """Mock response from sites metadata endpoint."""
    return {
        "success": True,
        "message": "Successfully retrieved sites",
        "sites": [
            {
                "_id": "site_001",
                "name": "Kampala Central",
                "city": "Kampala",
                "country": "Uganda",
                "region": "Central",
                "description": "Urban monitoring station",
                "approximate_latitude": 0.3163,
                "approximate_longitude": 32.5822,
            },
            {
                "_id": "site_002",
                "name": "Nairobi Industrial",
                "city": "Nairobi",
                "country": "Kenya",
                "region": "Nairobi",
                "description": "Industrial area monitor",
                "approximate_latitude": -1.2921,
                "approximate_longitude": 36.8219,
            },
            {
                "_id": "site_003",
                "name": "Lagos Ikeja",
                "city": "Lagos",
                "country": "Nigeria",
                "region": "Lagos State",
                "description": "Suburban monitoring",
                "approximate_latitude": 6.6018,
                "approximate_longitude": 3.3515,
            },
        ],
    }


@pytest.fixture
def mock_grids_response():
    """Mock response from grids metadata endpoint."""
    return {
        "success": True,
        "message": "Successfully retrieved grids",
        "grids": [
            {
                "_id": "grid_kampala",
                "name": "kampala",
                "admin_level": "city",
                "visibility": True,
                "createdAt": "2023-01-01T00:00:00.000Z",
            },
            {
                "_id": "grid_nairobi",
                "name": "nairobi",
                "admin_level": "city",
                "visibility": True,
                "createdAt": "2023-01-01T00:00:00.000Z",
            },
        ],
    }


@pytest.fixture
def mock_measurements_response():
    """Mock response from measurements endpoint."""
    return {
        "success": True,
        "isCache": False,
        "message": "Successfully retrieved measurements",
        "meta": {"total": 3, "skip": 0, "limit": 100, "page": 1, "pages": 1},
        "measurements": [
            {
                "device": "aq_001",
                "device_id": "device_001",
                "is_reading_primary": True,
                "site_id": "site_001",
                "time": "2024-01-01T00:00:00.000Z",
                "pm2_5": {"value": 35.5},
                "pm10": {"value": 52.0},
                "frequency": "hourly",
                "timeDifferenceHours": 0,
                "aqi_color": "#FFFF00",
                "aqi_category": "Moderate",
                "aqi_color_name": "Yellow",
                "siteDetails": {
                    "_id": "site_001",
                    "name": "Kampala Central",
                    "formatted_name": "Kampala Central Station",
                    "city": "Kampala",
                    "country": "Uganda",
                    "approximate_latitude": 0.3163,
                    "approximate_longitude": 32.5822,
                },
            },
            {
                "device": "aq_001",
                "device_id": "device_001",
                "is_reading_primary": True,
                "site_id": "site_001",
                "time": "2024-01-01T01:00:00.000Z",
                "pm2_5": {"value": 38.2},
                "pm10": {"value": 55.8},
                "frequency": "hourly",
                "timeDifferenceHours": 1,
                "aqi_color": "#FFFF00",
                "aqi_category": "Moderate",
                "aqi_color_name": "Yellow",
                "siteDetails": {
                    "_id": "site_001",
                    "name": "Kampala Central",
                    "formatted_name": "Kampala Central Station",
                    "city": "Kampala",
                    "country": "Uganda",
                    "approximate_latitude": 0.3163,
                    "approximate_longitude": 32.5822,
                },
            },
            {
                "device": "aq_001",
                "device_id": "device_001",
                "is_reading_primary": True,
                "site_id": "site_001",
                "time": "2024-01-01T02:00:00.000Z",
                "pm2_5": {"value": 32.1},
                "pm10": {"value": 48.5},
                "frequency": "hourly",
                "timeDifferenceHours": 2,
                "aqi_color": "#FFFF00",
                "aqi_category": "Moderate",
                "aqi_color_name": "Yellow",
                "siteDetails": {
                    "_id": "site_001",
                    "name": "Kampala Central",
                    "formatted_name": "Kampala Central Station",
                    "city": "Kampala",
                    "country": "Uganda",
                    "approximate_latitude": 0.3163,
                    "approximate_longitude": 32.5822,
                },
            },
        ],
    }


@pytest.fixture
def mock_empty_measurements_response():
    """Mock empty measurements response."""
    return {
        "success": True,
        "isCache": False,
        "message": "No measurements found",
        "meta": {"total": 0, "skip": 0, "limit": 100, "page": 1, "pages": 0},
        "measurements": [],
    }


@pytest.fixture
def mock_error_response():
    """Mock error response."""
    return {
        "success": False,
        "message": "Invalid authentication",
        "error": "Unauthorized.",
    }


@pytest.fixture
def mock_empty_sites_response():
    """Mock response when sites endpoint returns empty (but succeeds)."""
    return {
        "success": True,
        "message": "successfully retrieved the site details",
        "meta": {"total": 0, "totalResults": 0, "limit": 30, "skip": 0, "page": 1},
        "sites": [],
    }


@pytest.fixture
def mock_grids_summary_response():
    """Mock response from grids/summary endpoint with embedded sites."""
    return {
        "success": True,
        "message": "Successfully retrieved grids",
        "grids": [
            {
                "_id": "grid_kampala",
                "name": "kampala_city",
                "long_name": "Kampala City",
                "numberOfSites": 2,
                "sites": [
                    {
                        "_id": "site_001",
                        "name": "Kampala Central",
                        "formatted_name": "Kampala Central Station",
                        "approximate_latitude": 0.3163,
                        "approximate_longitude": 32.5822,
                        "country": "Uganda",
                        "city": "Kampala",
                    },
                    {
                        "_id": "site_002",
                        "name": "Kampala North",
                        "formatted_name": "Kampala North Station",
                        "approximate_latitude": 0.35,
                        "approximate_longitude": 32.60,
                        "country": "Uganda",
                        "city": "Kampala",
                    },
                ],
            },
            {
                "_id": "grid_nairobi",
                "name": "nairobi_city",
                "long_name": "Nairobi City",
                "numberOfSites": 1,
                "sites": [
                    {
                        "_id": "site_003",
                        "name": "Nairobi Central",
                        "formatted_name": "Nairobi Central Station",
                        "approximate_latitude": -1.2921,
                        "approximate_longitude": 36.8219,
                        "country": "Kenya",
                        "city": "Nairobi",
                    },
                ],
            },
        ],
    }


# ============================================================================
# Tests for _call_airqo_api()
# ============================================================================


class TestCallAirQoApi:
    """Tests for the low-level API caller."""

    @responses.activate
    def test_success(self, mock_sites_response, monkeypatch):
        """Test successful API call."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_sites_response,
            status=200,
        )

        result = _call_airqo_api("devices/metadata/sites")

        assert result == mock_sites_response
        assert len(responses.calls) == 1

    @responses.activate
    def test_includes_token_param(self, mock_sites_response, monkeypatch):
        """Test that token is included in request params."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_sites_response,
            status=200,
        )

        _call_airqo_api("devices/metadata/sites")

        assert "token=test_token_123" in responses.calls[0].request.url

    @responses.activate
    def test_includes_accept_header(self, mock_sites_response, monkeypatch):
        """Test that Accept header is set to JSON."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_sites_response,
            status=200,
        )

        _call_airqo_api("devices/metadata/sites")

        assert responses.calls[0].request.headers["Accept"] == "application/json"

    def test_raises_without_token(self, monkeypatch):
        """Test that missing token raises ValueError."""
        monkeypatch.delenv("AIRQO_API_KEY", raising=False)

        with pytest.raises(ValueError, match="AirQo API key required"):
            _call_airqo_api("devices/metadata/sites")

    def test_error_message_includes_setup_instructions(self, monkeypatch):
        """Test that error message includes instructions for getting token."""
        monkeypatch.delenv("AIRQO_API_KEY", raising=False)

        with pytest.raises(ValueError, match="analytics.airqo.net"):
            _call_airqo_api("devices/metadata/sites")

    @responses.activate
    def test_includes_extra_params(self, mock_sites_response, monkeypatch):
        """Test that extra parameters are passed correctly."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_sites_response,
            status=200,
        )

        params = {"startTime": "2024-01-01", "endTime": "2024-01-02"}
        _call_airqo_api("devices/metadata/sites", params)

        request_url = responses.calls[0].request.url
        assert "startTime=2024-01-01" in request_url
        assert "endTime=2024-01-02" in request_url

    @responses.activate
    def test_handles_401_unauthorized(self, monkeypatch):
        """Test that 401 unauthorized raises ValueError."""
        monkeypatch.setenv("AIRQO_API_KEY", "invalid_token")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            status=401,
        )

        with pytest.raises(ValueError, match="authentication failed"):
            _call_airqo_api("devices/metadata/sites")

    @responses.activate
    def test_handles_429_rate_limit(self, monkeypatch):
        """Test that 429 rate limit raises HTTPError."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            status=429,
        )

        import requests

        with pytest.raises(requests.HTTPError, match="rate limit"):
            _call_airqo_api("devices/metadata/sites")

    @responses.activate
    def test_handles_500_server_error(self, monkeypatch):
        """Test that 500 errors are raised."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            status=500,
        )

        import requests

        with pytest.raises(requests.HTTPError):
            _call_airqo_api("devices/metadata/sites")


# ============================================================================
# Tests for fetch_airqo_metadata()
# ============================================================================


class TestFetchAirQoMetadata:
    """Tests for metadata fetching."""

    @responses.activate
    def test_fetches_all_sites(self, mock_sites_response, monkeypatch):
        """Test fetching all sites without filters."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_sites_response,
            status=200,
        )

        result = fetch_airqo_metadata()

        assert len(result) == 3
        assert "site_code" in result.columns
        assert "site_name" in result.columns
        assert "latitude" in result.columns
        assert "longitude" in result.columns
        assert "source_network" in result.columns

    @responses.activate
    def test_normalizes_column_names(self, mock_sites_response, monkeypatch):
        """Test that column names are normalized to standard schema."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_sites_response,
            status=200,
        )

        result = fetch_airqo_metadata()

        # Should have standardized names
        assert "site_code" in result.columns
        assert "site_name" in result.columns
        assert "city" in result.columns
        assert "country" in result.columns

    @responses.activate
    def test_adds_source_network(self, mock_sites_response, monkeypatch):
        """Test that source_network column is added."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_sites_response,
            status=200,
        )

        result = fetch_airqo_metadata()

        assert (result["source_network"] == "AirQo").all()

    @responses.activate
    def test_filters_by_country(self, mock_sites_response, monkeypatch):
        """Test filtering by country."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_sites_response,
            status=200,
        )

        result = fetch_airqo_metadata(country="Uganda")

        # Should filter to Uganda only
        assert len(result) == 1
        assert result["country"].iloc[0] == "Uganda"

    @responses.activate
    def test_returns_empty_on_api_error(self, monkeypatch):
        """Test that API errors return empty DataFrame with warning."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            status=500,
        )

        result = fetch_airqo_metadata()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @responses.activate
    def test_returns_empty_on_unsuccessful_response(
        self, mock_error_response, monkeypatch
    ):
        """Test that unsuccessful API response returns empty DataFrame."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_error_response,
            status=200,
        )

        result = fetch_airqo_metadata()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @responses.activate
    def test_falls_back_to_grids_summary_when_sites_empty(
        self, mock_empty_sites_response, mock_grids_summary_response, monkeypatch
    ):
        """Test that grids/summary is used as fallback when sites endpoint returns empty."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        # First call to sites returns empty
        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_empty_sites_response,
            status=200,
        )

        # Fallback call to grids/summary returns sites
        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/grids/summary",
            json=mock_grids_summary_response,
            status=200,
        )

        result = fetch_airqo_metadata()

        # Should have extracted 3 sites from the grids
        assert len(result) == 3
        assert "site_code" in result.columns
        assert "source_network" in result.columns
        assert (result["source_network"] == "AirQo").all()

    @responses.activate
    def test_fallback_adds_grid_info_to_sites(
        self, mock_empty_sites_response, mock_grids_summary_response, monkeypatch
    ):
        """Test that grid name and ID are added to sites from fallback."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_empty_sites_response,
            status=200,
        )

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/grids/summary",
            json=mock_grids_summary_response,
            status=200,
        )

        result = fetch_airqo_metadata()

        # Grid info should be present
        assert "grid_name" in result.columns
        assert "grid_id" in result.columns

    @responses.activate
    def test_fallback_returns_empty_when_grids_also_empty(
        self, mock_empty_sites_response, monkeypatch
    ):
        """Test that empty DataFrame is returned when both endpoints return empty."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_empty_sites_response,
            status=200,
        )

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/grids/summary",
            json={"success": True, "message": "No grids", "grids": []},
            status=200,
        )

        result = fetch_airqo_metadata()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @responses.activate
    def test_fallback_handles_grids_endpoint_failure(
        self, mock_empty_sites_response, monkeypatch
    ):
        """Test that fallback handles grids endpoint failure gracefully."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_empty_sites_response,
            status=200,
        )

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/grids/summary",
            status=500,
        )

        result = fetch_airqo_metadata()

        # Should return empty DataFrame, not raise exception
        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ============================================================================
# Tests for fetch_airqo_grids()
# ============================================================================


class TestFetchAirQoGrids:
    """Tests for grid metadata fetching."""

    @responses.activate
    def test_fetches_grids(self, mock_grids_response, monkeypatch):
        """Test fetching available grids."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/grids",
            json=mock_grids_response,
            status=200,
        )

        result = fetch_airqo_grids()

        assert len(result) == 2
        assert "grid_id" in result.columns
        assert "name" in result.columns

    @responses.activate
    def test_renames_id_column(self, mock_grids_response, monkeypatch):
        """Test that _id is renamed to grid_id."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/grids",
            json=mock_grids_response,
            status=200,
        )

        result = fetch_airqo_grids()

        assert "grid_id" in result.columns
        assert "_id" not in result.columns

    @responses.activate
    def test_returns_empty_on_error(self, monkeypatch):
        """Test that errors return empty DataFrame."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/grids",
            status=500,
        )

        result = fetch_airqo_grids()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ============================================================================
# Tests for fetch_airqo_data()
# ============================================================================


class TestFetchAirQoData:
    """Tests for data fetching."""

    @responses.activate
    def test_fetches_single_site(self, mock_measurements_response, monkeypatch):
        """Test fetching data for a single site."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/measurements/sites/site_001/historical",
            json=mock_measurements_response,
            status=200,
        )

        result = fetch_airqo_data(
            sites=["site_001"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert not result.empty
        assert "site_code" in result.columns
        assert "date_time" in result.columns
        assert "measurand" in result.columns
        assert "value" in result.columns

    @responses.activate
    def test_formats_date_parameters(self, mock_measurements_response, monkeypatch):
        """Test that date parameters are formatted correctly."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/measurements/sites/site_001/historical",
            json=mock_measurements_response,
            status=200,
        )

        fetch_airqo_data(
            sites=["site_001"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        request_url = responses.calls[0].request.url
        assert "startTime=2024-01-01T00%3A00%3A00.000Z" in request_url
        assert "endTime=2024-01-31T23%3A59%3A59.000Z" in request_url

    @responses.activate
    def test_fetches_multiple_sites(self, mock_measurements_response, monkeypatch):
        """Test fetching data for multiple sites."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        # Mock response for each site
        for site in ["site_001", "site_002"]:
            responses.add(
                responses.GET,
                f"{AIRQO_API_BASE}/devices/measurements/sites/{site}/historical",
                json=mock_measurements_response,
                status=200,
            )

        result = fetch_airqo_data(
            sites=["site_001", "site_002"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        # Should make two API calls
        assert len(responses.calls) == 2
        assert not result.empty

    @responses.activate
    def test_continues_on_single_site_failure(
        self, mock_measurements_response, monkeypatch
    ):
        """Test that failure for one site doesn't stop other sites."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        # First site fails
        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/measurements/sites/site_001/historical",
            status=500,
        )
        # Second site succeeds
        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/measurements/sites/site_002/historical",
            json=mock_measurements_response,
            status=200,
        )

        result = fetch_airqo_data(
            sites=["site_001", "site_002"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        # Should still have data from successful site
        assert not result.empty

    @responses.activate
    def test_returns_empty_on_no_data(
        self, mock_empty_measurements_response, monkeypatch
    ):
        """Test that empty response returns empty DataFrame."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/measurements/sites/site_001/historical",
            json=mock_empty_measurements_response,
            status=200,
        )

        result = fetch_airqo_data(
            sites=["site_001"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert result.empty

    @responses.activate
    def test_normalizes_output_schema(self, mock_measurements_response, monkeypatch):
        """Test that output has normalized schema."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/measurements/sites/site_001/historical",
            json=mock_measurements_response,
            status=200,
        )

        result = fetch_airqo_data(
            sites=["site_001"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        expected_columns = [
            "site_code",
            "site_name",
            "date_time",
            "measurand",
            "value",
            "units",
            "source_network",
            "ratification",
            "created_at",
        ]
        assert list(result.columns) == expected_columns

    @responses.activate
    def test_adds_source_network(self, mock_measurements_response, monkeypatch):
        """Test that source_network is added."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/measurements/sites/site_001/historical",
            json=mock_measurements_response,
            status=200,
        )

        result = fetch_airqo_data(
            sites=["site_001"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert (result["source_network"] == "AirQo").all()


# ============================================================================
# Tests for fetch_airqo_data_by_grid()
# ============================================================================


class TestFetchAirQoDataByGrid:
    """Tests for grid-based data fetching."""

    @responses.activate
    def test_fetches_grid_data(self, mock_measurements_response, monkeypatch):
        """Test fetching data for a grid."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/measurements/grids/grid_kampala/historical",
            json=mock_measurements_response,
            status=200,
        )

        result = fetch_airqo_data_by_grid(
            grid_id="grid_kampala",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert not result.empty
        assert "site_code" in result.columns

    @responses.activate
    def test_returns_empty_on_error(self, monkeypatch):
        """Test that errors return empty DataFrame."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/measurements/grids/grid_kampala/historical",
            status=500,
        )

        result = fetch_airqo_data_by_grid(
            grid_id="grid_kampala",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert result.empty


# ============================================================================
# Tests for create_airqo_normalizer()
# ============================================================================


class TestAirQoNormalizer:
    """Tests for the data normalization pipeline."""

    def test_extracts_site_info_from_nested_structure(self):
        """Test that site info is extracted from siteDetails."""
        normalizer = create_airqo_normalizer()

        df = pd.DataFrame(
            [
                {
                    "time": "2024-01-01T00:00:00.000Z",
                    "pm2_5": {"value": 35.5},
                    "pm10": {"value": 52.0},
                    "siteDetails": {
                        "_id": "site_001",
                        "name": "Test Site",
                        "formatted_name": "Test Site Station",
                        "city": "Kampala",
                        "country": "Uganda",
                        "approximate_latitude": 0.3163,
                        "approximate_longitude": 32.5822,
                    },
                }
            ]
        )

        result = normalizer(df)

        assert "site_001" in result["site_code"].values
        assert "Test Site Station" in result["site_name"].values

    def test_melts_pollutants_to_long_format(self):
        """Test that PM2.5 and PM10 columns are melted to long format."""
        normalizer = create_airqo_normalizer()

        df = pd.DataFrame(
            [
                {
                    "time": "2024-01-01T00:00:00.000Z",
                    "pm2_5": {"value": 35.5},
                    "pm10": {"value": 52.0},
                    "siteDetails": {
                        "_id": "site_001",
                        "name": "Test Site",
                        "city": "Kampala",
                        "country": "Uganda",
                    },
                }
            ]
        )

        result = normalizer(df)

        # Should have 2 rows (one for PM2.5, one for PM10)
        assert len(result) == 2
        assert set(result["measurand"].unique()) == {"PM2.5", "PM10"}

    def test_parses_timestamps(self):
        """Test that timestamps are parsed to datetime."""
        normalizer = create_airqo_normalizer()

        df = pd.DataFrame(
            [
                {
                    "time": "2024-01-01T00:00:00.000Z",
                    "pm2_5": {"value": 35.5},
                    "siteDetails": {"_id": "site_001", "name": "Test"},
                }
            ]
        )

        result = normalizer(df)

        assert pd.api.types.is_datetime64_any_dtype(result["date_time"])

    def test_standardizes_parameter_names(self):
        """Test that parameter names are standardized."""
        normalizer = create_airqo_normalizer()

        df = pd.DataFrame(
            [
                {
                    "time": "2024-01-01T00:00:00.000Z",
                    "pm2_5": {"value": 35.5},
                    "pm10": {"value": 52.0},
                    "siteDetails": {"_id": "site_001", "name": "Test"},
                }
            ]
        )

        result = normalizer(df)

        # Should use standard names
        assert "PM2.5" in result["measurand"].values
        assert "PM10" in result["measurand"].values

    def test_adds_units(self):
        """Test that units column is added."""
        normalizer = create_airqo_normalizer()

        df = pd.DataFrame(
            [
                {
                    "time": "2024-01-01T00:00:00.000Z",
                    "pm2_5": {"value": 35.5},
                    "siteDetails": {"_id": "site_001", "name": "Test"},
                }
            ]
        )

        result = normalizer(df)

        assert (result["units"] == "ug/m3").all()

    def test_adds_indicative_ratification(self):
        """Test that low-cost sensor data is marked as Indicative."""
        normalizer = create_airqo_normalizer()

        df = pd.DataFrame(
            [
                {
                    "time": "2024-01-01T00:00:00.000Z",
                    "pm2_5": {"value": 35.5},
                    "siteDetails": {"_id": "site_001", "name": "Test"},
                }
            ]
        )

        result = normalizer(df)

        assert (result["ratification"] == "Indicative").all()

    def test_adds_source_network(self):
        """Test that source_network column is added."""
        normalizer = create_airqo_normalizer()

        df = pd.DataFrame(
            [
                {
                    "time": "2024-01-01T00:00:00.000Z",
                    "pm2_5": {"value": 35.5},
                    "siteDetails": {"_id": "site_001", "name": "Test"},
                }
            ]
        )

        result = normalizer(df)

        assert (result["source_network"] == "AirQo").all()

    def test_adds_created_at(self):
        """Test that created_at timestamp is added."""
        normalizer = create_airqo_normalizer()

        df = pd.DataFrame(
            [
                {
                    "time": "2024-01-01T00:00:00.000Z",
                    "pm2_5": {"value": 35.5},
                    "siteDetails": {"_id": "site_001", "name": "Test"},
                }
            ]
        )

        result = normalizer(df)

        assert "created_at" in result.columns

    def test_filters_invalid_values(self):
        """Test that zero/negative values are filtered out."""
        normalizer = create_airqo_normalizer()

        df = pd.DataFrame(
            [
                {
                    "time": "2024-01-01T00:00:00.000Z",
                    "pm2_5": {"value": 35.5},
                    "siteDetails": {"_id": "site_001", "name": "Test"},
                },
                {
                    "time": "2024-01-01T01:00:00.000Z",
                    "pm2_5": {"value": 0},  # Invalid
                    "siteDetails": {"_id": "site_001", "name": "Test"},
                },
                {
                    "time": "2024-01-01T02:00:00.000Z",
                    "pm2_5": {"value": -5},  # Invalid
                    "siteDetails": {"_id": "site_001", "name": "Test"},
                },
            ]
        )

        result = normalizer(df)

        # Only first row should remain
        assert len(result) == 1
        assert result["value"].iloc[0] == 35.5

    def test_filters_null_timestamps(self):
        """Test that rows with null timestamps are filtered."""
        normalizer = create_airqo_normalizer()

        df = pd.DataFrame(
            [
                {
                    "time": "2024-01-01T00:00:00.000Z",
                    "pm2_5": {"value": 35.5},
                    "siteDetails": {"_id": "site_001", "name": "Test"},
                },
                {
                    "time": None,
                    "pm2_5": {"value": 40.0},
                    "siteDetails": {"_id": "site_001", "name": "Test"},
                },
            ]
        )

        result = normalizer(df)

        # Only first row should remain
        assert len(result) == 1

    def test_selects_correct_columns(self):
        """Test that only standard columns are in output."""
        normalizer = create_airqo_normalizer()

        df = pd.DataFrame(
            [
                {
                    "time": "2024-01-01T00:00:00.000Z",
                    "pm2_5": {"value": 35.5},
                    "siteDetails": {"_id": "site_001", "name": "Test"},
                    "extra_column": "should be dropped",
                    "aqi_category": "Moderate",
                }
            ]
        )

        result = normalizer(df)

        expected_columns = [
            "site_code",
            "site_name",
            "date_time",
            "measurand",
            "value",
            "units",
            "source_network",
            "ratification",
            "created_at",
        ]
        assert list(result.columns) == expected_columns


# ============================================================================
# Tests for _create_metadata_normalizer()
# ============================================================================


class TestMetadataNormalizer:
    """Tests for metadata normalization."""

    def test_extracts_location_from_approximate_fields(self):
        """Test that lat/long are extracted from approximate fields."""
        normalizer = _create_metadata_normalizer()

        df = pd.DataFrame(
            [
                {
                    "_id": "site_001",
                    "name": "Test Site",
                    "approximate_latitude": 0.3163,
                    "approximate_longitude": 32.5822,
                }
            ]
        )

        result = normalizer(df)

        assert "latitude" in result.columns
        assert "longitude" in result.columns
        assert result["latitude"].iloc[0] == 0.3163

    def test_renames_columns(self):
        """Test that columns are renamed to standard names."""
        normalizer = _create_metadata_normalizer()

        df = pd.DataFrame(
            [
                {
                    "_id": "site_001",
                    "name": "Test Site",
                    "city": "Kampala",
                    "country": "Uganda",
                }
            ]
        )

        result = normalizer(df)

        assert "site_code" in result.columns
        assert "site_name" in result.columns

    def test_adds_source_network(self):
        """Test that source_network is added."""
        normalizer = _create_metadata_normalizer()

        df = pd.DataFrame([{"_id": "site_001", "name": "Test Site"}])

        result = normalizer(df)

        assert (result["source_network"] == "AirQo").all()


# ============================================================================
# Tests for PARAMETER_MAP
# ============================================================================


class TestParameterMap:
    """Tests for parameter name mapping."""

    def test_maps_known_parameters(self):
        """Test that known parameters are mapped correctly."""
        assert PARAMETER_MAP["pm2_5"] == "PM2.5"
        assert PARAMETER_MAP["pm10"] == "PM10"
        assert PARAMETER_MAP["no2"] == "NO2"
        assert PARAMETER_MAP["o3"] == "O3"
        assert PARAMETER_MAP["so2"] == "SO2"
        assert PARAMETER_MAP["co"] == "CO"


# ============================================================================
# Tests for source registration
# ============================================================================


class TestSourceRegistration:
    """Tests for source registration."""

    def test_airqo_is_registered(self):
        """Test that AirQo is registered as a source."""
        from aeolus.registry import get_source

        source = get_source("AIRQO")

        assert source is not None
        assert source["name"] == "AirQo"
        assert source["type"] == "network"
        assert source["requires_api_key"] is True

    def test_registered_with_correct_functions(self):
        """Test that correct functions are registered."""
        from aeolus.registry import get_source

        source = get_source("AIRQO")

        assert source["fetch_metadata"] == fetch_airqo_metadata
        assert source["fetch_data"] == fetch_airqo_data


# ============================================================================
# Integration-style tests
# ============================================================================


class TestAirQoIntegration:
    """Integration-style tests for full workflows."""

    @responses.activate
    def test_full_metadata_workflow(self, mock_sites_response, monkeypatch):
        """Test complete metadata fetching workflow."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/metadata/sites",
            json=mock_sites_response,
            status=200,
        )

        result = fetch_airqo_metadata()

        # Verify complete schema
        assert not result.empty
        assert len(result) == 3
        assert (result["source_network"] == "AirQo").all()
        assert "latitude" in result.columns
        assert "longitude" in result.columns

    @responses.activate
    def test_full_data_workflow(self, mock_measurements_response, monkeypatch):
        """Test complete data fetching workflow."""
        monkeypatch.setenv("AIRQO_API_KEY", "test_token_123")

        responses.add(
            responses.GET,
            f"{AIRQO_API_BASE}/devices/measurements/sites/site_001/historical",
            json=mock_measurements_response,
            status=200,
        )

        result = fetch_airqo_data(
            sites=["site_001"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        # Verify complete schema and data
        assert not result.empty
        # 3 measurements x 2 pollutants = 6 rows
        assert len(result) == 6
        assert set(result["measurand"].unique()) == {"PM2.5", "PM10"}
        assert (result["source_network"] == "AirQo").all()
        assert (result["units"] == "ug/m3").all()
        assert pd.api.types.is_datetime64_any_dtype(result["date_time"])
