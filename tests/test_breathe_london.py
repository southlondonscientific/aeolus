"""
Tests for Breathe London data source.

Tests the API calls, metadata fetching, data fetching, and normalization
pipeline with mocked HTTP responses.
"""

from datetime import datetime

import pandas as pd
import pytest
import responses

from aeolus.sources.breathe_london import (
    BREATHE_LONDON_API_BASE,
    SPECIES_MAP,
    _call_breathe_london_api,
    _create_metadata_normalizer,
    create_breathe_london_normalizer,
    fetch_breathe_london_data,
    fetch_breathe_london_metadata,
)

# ============================================================================
# Fixtures for Mock API Responses
# ============================================================================


@pytest.fixture
def mock_sensors_response():
    """Mock response from ListSensors endpoint."""
    return [
        {
            "SiteCode": "BL0001",
            "SiteName": "Camden - Euston Road",
            "Latitude": 51.5279,
            "Longitude": -0.1328,
            "Borough": "Camden",
            "SiteType": "Roadside",
            "Species": ["NO2", "PM2.5"],
        },
        {
            "SiteCode": "BL0002",
            "SiteName": "Westminster - Marylebone Road",
            "Latitude": 51.5225,
            "Longitude": -0.1546,
            "Borough": "Westminster",
            "SiteType": "Roadside",
            "Species": ["NO2", "PM2.5", "PM10"],
        },
        {
            "SiteCode": "BL0003",
            "SiteName": "Hackney - Mare Street",
            "Latitude": 51.5452,
            "Longitude": -0.0553,
            "Borough": "Hackney",
            "SiteType": "Urban Background",
            "Species": ["NO2"],
        },
    ]


@pytest.fixture
def mock_single_sensor_response():
    """Mock response for a single sensor."""
    return [
        {
            "SiteCode": "BL0001",
            "SiteName": "Camden - Euston Road",
            "Latitude": 51.5279,
            "Longitude": -0.1328,
            "Borough": "Camden",
        }
    ]


@pytest.fixture
def mock_sensor_data_response():
    """Mock response from SensorData endpoint."""
    return [
        {
            "SiteCode": "BL0001",
            "DateTime": "2024-01-01T00:00:00Z",
            "Species": "NO2",
            "ScaledValue": 45.2,
            "Units": "ug.m-3",
            "RatificationStatus": "Ratified",
        },
        {
            "SiteCode": "BL0001",
            "DateTime": "2024-01-01T01:00:00Z",
            "Species": "NO2",
            "ScaledValue": 42.8,
            "Units": "ug.m-3",
            "RatificationStatus": "Ratified",
        },
        {
            "SiteCode": "BL0001",
            "DateTime": "2024-01-01T02:00:00Z",
            "Species": "PM2.5",
            "ScaledValue": 18.5,
            "Units": "ug.m-3",
            "RatificationStatus": "Unvalidated",
        },
    ]


@pytest.fixture
def mock_sensor_data_with_nulls():
    """Mock response with null values."""
    return [
        {
            "SiteCode": "BL0001",
            "DateTime": "2024-01-01T00:00:00Z",
            "Species": "NO2",
            "ScaledValue": 45.2,
            "Units": "ug.m-3",
        },
        {
            "SiteCode": "BL0001",
            "DateTime": "2024-01-01T01:00:00Z",
            "Species": "NO2",
            "ScaledValue": None,  # Null value
            "Units": "ug.m-3",
        },
        {
            "SiteCode": "BL0001",
            "DateTime": None,  # Null timestamp
            "Species": "PM2.5",
            "ScaledValue": 18.5,
            "Units": "ug.m-3",
        },
    ]


@pytest.fixture
def mock_empty_response():
    """Mock empty response."""
    return []


# ============================================================================
# Tests for _call_breathe_london_api()
# ============================================================================


class TestCallBreatheLondonApi:
    """Tests for the low-level API caller."""

    @responses.activate
    def test_success(self, mock_sensors_response, monkeypatch):
        """Test successful API call."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            json=mock_sensors_response,
            status=200,
        )

        result = _call_breathe_london_api("ListSensors", {})

        assert result == mock_sensors_response
        assert len(responses.calls) == 1

    @responses.activate
    def test_includes_api_key_header(self, monkeypatch):
        """Test that API key is included in request headers."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            json=[],
            status=200,
        )

        _call_breathe_london_api("ListSensors", {})

        assert responses.calls[0].request.headers["X-API-KEY"] == "test_key_123"

    @responses.activate
    def test_includes_accept_header(self, monkeypatch):
        """Test that Accept header is set to JSON."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            json=[],
            status=200,
        )

        _call_breathe_london_api("ListSensors", {})

        assert responses.calls[0].request.headers["Accept"] == "application/json"

    def test_raises_without_api_key(self, monkeypatch):
        """Test that missing API key raises ValueError."""
        monkeypatch.delenv("BL_API_KEY", raising=False)

        with pytest.raises(ValueError, match="Breathe London API key required"):
            _call_breathe_london_api("ListSensors", {})

    def test_error_message_includes_setup_instructions(self, monkeypatch):
        """Test that error message includes instructions for getting API key."""
        monkeypatch.delenv("BL_API_KEY", raising=False)

        with pytest.raises(ValueError, match="BL_API_KEY"):
            _call_breathe_london_api("ListSensors", {})

    @responses.activate
    def test_includes_query_params(self, monkeypatch):
        """Test that query parameters are passed correctly."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            json=[],
            status=200,
        )

        params = {"borough": "Camden", "species": "NO2"}
        _call_breathe_london_api("ListSensors", params)

        request_url = responses.calls[0].request.url
        assert "borough=Camden" in request_url
        assert "species=NO2" in request_url

    @responses.activate
    def test_handles_http_error(self, monkeypatch):
        """Test that HTTP errors are raised."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            status=500,
        )

        import requests

        with pytest.raises(requests.HTTPError):
            _call_breathe_london_api("ListSensors", {})

    @responses.activate
    def test_handles_401_unauthorized(self, monkeypatch):
        """Test that 401 unauthorized errors are raised."""
        monkeypatch.setenv("BL_API_KEY", "invalid_key")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            status=401,
        )

        import requests

        with pytest.raises(requests.HTTPError):
            _call_breathe_london_api("ListSensors", {})


# ============================================================================
# Tests for fetch_breathe_london_metadata()
# ============================================================================


class TestFetchBreatheLondonMetadata:
    """Tests for metadata fetching."""

    @responses.activate
    def test_fetches_all_sensors(self, mock_sensors_response, monkeypatch):
        """Test fetching all sensors without filters."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            json=mock_sensors_response,
            status=200,
        )

        result = fetch_breathe_london_metadata()

        assert len(result) == 3
        assert "site_code" in result.columns
        assert "site_name" in result.columns
        assert "latitude" in result.columns
        assert "longitude" in result.columns
        assert "source_network" in result.columns

    @responses.activate
    def test_normalizes_column_names(self, mock_sensors_response, monkeypatch):
        """Test that column names are normalized to standard schema."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            json=mock_sensors_response,
            status=200,
        )

        result = fetch_breathe_london_metadata()

        # Should have standardized names
        assert "site_code" in result.columns
        assert "site_name" in result.columns
        # Original names should be renamed
        assert "SiteCode" not in result.columns
        assert "SiteName" not in result.columns

    @responses.activate
    def test_adds_source_network(self, mock_sensors_response, monkeypatch):
        """Test that source_network column is added."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            json=mock_sensors_response,
            status=200,
        )

        result = fetch_breathe_london_metadata()

        assert (result["source_network"] == "Breathe London").all()

    @responses.activate
    def test_filters_by_borough(self, mock_single_sensor_response, monkeypatch):
        """Test filtering by borough."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            json=mock_single_sensor_response,
            status=200,
        )

        result = fetch_breathe_london_metadata(borough="Camden")

        # Check that filter was passed to API
        assert "borough=Camden" in responses.calls[0].request.url
        assert len(result) == 1

    @responses.activate
    def test_filters_by_species(self, mock_single_sensor_response, monkeypatch):
        """Test filtering by species."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            json=mock_single_sensor_response,
            status=200,
        )

        result = fetch_breathe_london_metadata(species="NO2")

        assert "species=NO2" in responses.calls[0].request.url

    @responses.activate
    def test_filters_by_location(self, mock_single_sensor_response, monkeypatch):
        """Test filtering by geographic location."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            json=mock_single_sensor_response,
            status=200,
        )

        result = fetch_breathe_london_metadata(
            latitude=51.5074, longitude=-0.1278, radius_km=5
        )

        request_url = responses.calls[0].request.url
        assert "latitude=51.5074" in request_url
        assert "longitude=-0.1278" in request_url
        assert "radius_km=5" in request_url

    @responses.activate
    def test_returns_empty_dataframe_on_no_results(
        self, mock_empty_response, monkeypatch
    ):
        """Test that empty response returns empty DataFrame."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            json=mock_empty_response,
            status=200,
        )

        result = fetch_breathe_london_metadata()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @responses.activate
    def test_returns_empty_dataframe_on_api_error(self, monkeypatch):
        """Test that API errors return empty DataFrame with warning."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            status=500,
        )

        result = fetch_breathe_london_metadata()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @responses.activate
    def test_ignores_none_filter_values(self, mock_sensors_response, monkeypatch):
        """Test that None filter values are not included in query."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            json=mock_sensors_response,
            status=200,
        )

        result = fetch_breathe_london_metadata(borough="Camden", species=None)

        request_url = responses.calls[0].request.url
        assert "borough=Camden" in request_url
        assert "species" not in request_url


# ============================================================================
# Tests for fetch_breathe_london_data()
# ============================================================================


class TestFetchBreatheLondonData:
    """Tests for data fetching."""

    @responses.activate
    def test_fetches_single_site(self, mock_sensor_data_response, monkeypatch):
        """Test fetching data for a single site."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/SensorData",
            json=mock_sensor_data_response,
            status=200,
        )

        result = fetch_breathe_london_data(
            sites=["BL0001"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert not result.empty
        assert len(result) == 3
        assert "site_code" in result.columns
        assert "date_time" in result.columns
        assert "measurand" in result.columns
        assert "value" in result.columns

    @responses.activate
    def test_formats_date_parameters(self, mock_sensor_data_response, monkeypatch):
        """Test that date parameters are formatted correctly."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/SensorData",
            json=mock_sensor_data_response,
            status=200,
        )

        fetch_breathe_london_data(
            sites=["BL0001"],
            start_date=datetime(2024, 1, 1, 0, 0, 0),
            end_date=datetime(2024, 1, 31, 23, 59, 59),
        )

        request_url = responses.calls[0].request.url
        assert "startTime=2024-01-01T00%3A00%3A00Z" in request_url
        assert "endTime=2024-01-31T23%3A59%3A59Z" in request_url

    @responses.activate
    def test_includes_site_code_param(self, mock_sensor_data_response, monkeypatch):
        """Test that SiteCode parameter is included."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/SensorData",
            json=mock_sensor_data_response,
            status=200,
        )

        fetch_breathe_london_data(
            sites=["BL0001"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        request_url = responses.calls[0].request.url
        assert "SiteCode=BL0001" in request_url

    @responses.activate
    def test_fetches_multiple_sites(self, mock_sensor_data_response, monkeypatch):
        """Test fetching data for multiple sites."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        # Mock response for each site
        for site in ["BL0001", "BL0002"]:
            responses.add(
                responses.GET,
                f"{BREATHE_LONDON_API_BASE}/SensorData",
                json=mock_sensor_data_response,
                status=200,
            )

        result = fetch_breathe_london_data(
            sites=["BL0001", "BL0002"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        # Should make two API calls
        assert len(responses.calls) == 2
        assert not result.empty

    @responses.activate
    def test_continues_on_single_site_failure(
        self, mock_sensor_data_response, monkeypatch
    ):
        """Test that failure for one site doesn't stop other sites."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        # First site fails
        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/SensorData",
            status=500,
        )
        # Second site succeeds
        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/SensorData",
            json=mock_sensor_data_response,
            status=200,
        )

        result = fetch_breathe_london_data(
            sites=["BL0001", "BL0002"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        # Should still have data from successful site
        assert not result.empty

    @responses.activate
    def test_returns_empty_on_all_failures(self, monkeypatch):
        """Test that empty DataFrame returned when all sites fail."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/SensorData",
            status=500,
        )

        result = fetch_breathe_london_data(
            sites=["BL0001"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert result.empty
        assert "site_code" in result.columns

    @responses.activate
    def test_returns_empty_on_no_data(self, mock_empty_response, monkeypatch):
        """Test that empty response returns empty DataFrame."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/SensorData",
            json=mock_empty_response,
            status=200,
        )

        result = fetch_breathe_london_data(
            sites=["BL0001"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert result.empty

    @responses.activate
    def test_normalizes_output_schema(self, mock_sensor_data_response, monkeypatch):
        """Test that output has normalized schema."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/SensorData",
            json=mock_sensor_data_response,
            status=200,
        )

        result = fetch_breathe_london_data(
            sites=["BL0001"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

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
        assert list(result.columns) == expected_columns

    @responses.activate
    def test_adds_source_network(self, mock_sensor_data_response, monkeypatch):
        """Test that source_network is added."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/SensorData",
            json=mock_sensor_data_response,
            status=200,
        )

        result = fetch_breathe_london_data(
            sites=["BL0001"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert (result["source_network"] == "Breathe London").all()


# ============================================================================
# Tests for create_breathe_london_normalizer()
# ============================================================================


class TestBreatheLondonNormalizer:
    """Tests for the data normalization pipeline."""

    def test_renames_columns(self):
        """Test that columns are renamed to standard names."""
        normalizer = create_breathe_london_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001"],
                "DateTime": ["2024-01-01T00:00:00Z"],
                "Species": ["NO2"],
                "ScaledValue": [45.2],
                "Units": ["ug.m-3"],
            }
        )

        result = normalizer(df)

        assert "site_code" in result.columns
        assert "date_time" in result.columns
        assert "measurand" in result.columns
        assert "value" in result.columns
        assert "units" in result.columns

    def test_parses_timestamps(self):
        """Test that timestamps are parsed to datetime."""
        normalizer = create_breathe_london_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001"],
                "DateTime": ["2024-01-01T00:00:00Z"],
                "Species": ["NO2"],
                "ScaledValue": [45.2],
                "Units": ["ug.m-3"],
            }
        )

        result = normalizer(df)

        assert pd.api.types.is_datetime64_any_dtype(result["date_time"])

    def test_standardizes_species_names(self):
        """Test that species names are standardized."""
        normalizer = create_breathe_london_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001", "BL0001"],
                "DateTime": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
                "Species": ["NO2", "PM2.5"],
                "ScaledValue": [45.2, 18.5],
                "Units": ["ug.m-3", "ug.m-3"],
            }
        )

        result = normalizer(df)

        assert set(result["measurand"].unique()) == {"NO2", "PM2.5"}

    def test_standardizes_units(self):
        """Test that units are standardized."""
        normalizer = create_breathe_london_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001", "BL0001"],
                "DateTime": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
                "Species": ["NO2", "PM2.5"],
                "ScaledValue": [45.2, 18.5],
                "Units": ["ug.m-3", "µg/m³"],
            }
        )

        result = normalizer(df)

        # Both should be standardized to "ug/m3"
        assert (result["units"] == "ug/m3").all()

    def test_adds_ratification_status(self):
        """Test that ratification status is handled."""
        normalizer = create_breathe_london_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001", "BL0001"],
                "DateTime": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
                "Species": ["NO2", "PM2.5"],
                "ScaledValue": [45.2, 18.5],
                "Units": ["ug.m-3", "ug.m-3"],
                "RatificationStatus": ["Ratified", None],
            }
        )

        result = normalizer(df)

        assert "ratification" in result.columns
        assert result["ratification"].iloc[0] == "Ratified"
        assert result["ratification"].iloc[1] == "Unvalidated"

    def test_adds_default_ratification_when_missing(self):
        """Test that default ratification is added when column missing."""
        normalizer = create_breathe_london_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001"],
                "DateTime": ["2024-01-01T00:00:00Z"],
                "Species": ["NO2"],
                "ScaledValue": [45.2],
                "Units": ["ug.m-3"],
            }
        )

        result = normalizer(df)

        assert (result["ratification"] == "Unvalidated").all()

    def test_adds_source_network(self):
        """Test that source_network column is added."""
        normalizer = create_breathe_london_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001"],
                "DateTime": ["2024-01-01T00:00:00Z"],
                "Species": ["NO2"],
                "ScaledValue": [45.2],
                "Units": ["ug.m-3"],
            }
        )

        result = normalizer(df)

        assert (result["source_network"] == "Breathe London").all()

    def test_adds_created_at(self):
        """Test that created_at timestamp is added."""
        normalizer = create_breathe_london_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001"],
                "DateTime": ["2024-01-01T00:00:00Z"],
                "Species": ["NO2"],
                "ScaledValue": [45.2],
                "Units": ["ug.m-3"],
            }
        )

        result = normalizer(df)

        assert "created_at" in result.columns

    def test_filters_null_values(self):
        """Test that rows with null essential values are filtered."""
        normalizer = create_breathe_london_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001", "BL0001", "BL0001"],
                "DateTime": ["2024-01-01T00:00:00Z", None, "2024-01-01T02:00:00Z"],
                "Species": ["NO2", "NO2", None],
                "ScaledValue": [45.2, None, 18.5],
                "Units": ["ug.m-3", "ug.m-3", "ug.m-3"],
            }
        )

        result = normalizer(df)

        # Only first row should remain (others have null essential values)
        assert len(result) == 1
        assert result["value"].iloc[0] == 45.2

    def test_selects_correct_columns(self):
        """Test that only standard columns are in output."""
        normalizer = create_breathe_london_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001"],
                "DateTime": ["2024-01-01T00:00:00Z"],
                "Species": ["NO2"],
                "ScaledValue": [45.2],
                "Units": ["ug.m-3"],
                "ExtraColumn": ["should be dropped"],
            }
        )

        result = normalizer(df)

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
        assert list(result.columns) == expected_columns

    def test_handles_empty_dataframe(self):
        """Test that empty DataFrame is handled gracefully."""
        normalizer = create_breathe_london_normalizer()

        df = pd.DataFrame(
            columns=["SiteCode", "DateTime", "Species", "ScaledValue", "Units"]
        )

        result = normalizer(df)

        assert result.empty

    def test_handles_missing_units_column(self):
        """Test that missing units column is handled."""
        normalizer = create_breathe_london_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001"],
                "DateTime": ["2024-01-01T00:00:00Z"],
                "Species": ["NO2"],
                "ScaledValue": [45.2],
            }
        )

        result = normalizer(df)

        assert "units" in result.columns
        assert result["units"].iloc[0] == ""


# ============================================================================
# Tests for _create_metadata_normalizer()
# ============================================================================


class TestMetadataNormalizer:
    """Tests for metadata normalization."""

    def test_renames_columns(self):
        """Test that columns are renamed to standard names."""
        normalizer = _create_metadata_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001"],
                "SiteName": ["Test Site"],
                "Latitude": [51.5],
                "Longitude": [-0.1],
            }
        )

        result = normalizer(df)

        assert "site_code" in result.columns
        assert "site_name" in result.columns
        assert "latitude" in result.columns
        assert "longitude" in result.columns

    def test_adds_source_network(self):
        """Test that source_network is added."""
        normalizer = _create_metadata_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001"],
                "SiteName": ["Test Site"],
                "Latitude": [51.5],
                "Longitude": [-0.1],
            }
        )

        result = normalizer(df)

        assert (result["source_network"] == "Breathe London").all()

    def test_preserves_extra_columns(self):
        """Test that extra columns are preserved."""
        normalizer = _create_metadata_normalizer()

        df = pd.DataFrame(
            {
                "SiteCode": ["BL0001"],
                "SiteName": ["Test Site"],
                "Latitude": [51.5],
                "Longitude": [-0.1],
                "Borough": ["Camden"],
                "SiteType": ["Roadside"],
            }
        )

        result = normalizer(df)

        # Extra columns should be preserved
        assert "Borough" in result.columns
        assert "SiteType" in result.columns


# ============================================================================
# Tests for SPECIES_MAP
# ============================================================================


class TestSpeciesMap:
    """Tests for species name mapping."""

    def test_maps_known_species(self):
        """Test that known species are mapped correctly."""
        assert SPECIES_MAP["NO2"] == "NO2"
        assert SPECIES_MAP["PM2.5"] == "PM2.5"
        assert SPECIES_MAP["PM10"] == "PM10"
        assert SPECIES_MAP["NO"] == "NO"
        assert SPECIES_MAP["O3"] == "O3"
        assert SPECIES_MAP["CO"] == "CO"

    def test_all_expected_species_present(self):
        """Test that all expected species are in the map."""
        expected_species = ["NO2", "PM2.5", "PM10", "NO", "O3", "CO"]
        for species in expected_species:
            assert species in SPECIES_MAP


# ============================================================================
# Tests for source registration
# ============================================================================


class TestSourceRegistration:
    """Tests for source registration."""

    def test_breathe_london_is_registered(self):
        """Test that Breathe London is registered as a source."""
        from aeolus.registry import _SOURCES, get_source, register_source

        # Re-register if cleared by other tests
        if "BREATHE_LONDON" not in _SOURCES:
            register_source(
                "BREATHE_LONDON",
                {
                    "type": "network",
                    "name": "Breathe London",
                    "fetch_metadata": fetch_breathe_london_metadata,
                    "fetch_data": fetch_breathe_london_data,
                    "normalise": create_breathe_london_normalizer(),
                    "requires_api_key": True,
                },
            )

        source = get_source("BREATHE_LONDON")

        assert source is not None
        assert source["name"] == "Breathe London"
        assert source["type"] == "network"
        assert source["requires_api_key"] is True

    def test_registered_with_correct_functions(self):
        """Test that correct functions are registered."""
        from aeolus.registry import _SOURCES, get_source, register_source

        # Re-register if cleared by other tests
        if "BREATHE_LONDON" not in _SOURCES:
            register_source(
                "BREATHE_LONDON",
                {
                    "type": "network",
                    "name": "Breathe London",
                    "fetch_metadata": fetch_breathe_london_metadata,
                    "fetch_data": fetch_breathe_london_data,
                    "normalise": create_breathe_london_normalizer(),
                    "requires_api_key": True,
                },
            )

        source = get_source("BREATHE_LONDON")

        # Check function names match (handles reloaded modules)
        assert source["fetch_metadata"].__name__ == "fetch_breathe_london_metadata"
        assert source["fetch_data"].__name__ == "fetch_breathe_london_data"


# ============================================================================
# Integration-style tests
# ============================================================================


class TestBreatheLondonIntegration:
    """Integration-style tests for full workflows."""

    @responses.activate
    def test_full_metadata_workflow(self, mock_sensors_response, monkeypatch):
        """Test complete metadata fetching workflow."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/ListSensors",
            json=mock_sensors_response,
            status=200,
        )

        result = fetch_breathe_london_metadata()

        # Verify complete schema
        assert not result.empty
        assert len(result) == 3
        assert result["site_code"].tolist() == ["BL0001", "BL0002", "BL0003"]
        assert (result["source_network"] == "Breathe London").all()
        assert result["latitude"].dtype == float or "float" in str(
            result["latitude"].dtype
        )

    @responses.activate
    def test_full_data_workflow(self, mock_sensor_data_response, monkeypatch):
        """Test complete data fetching workflow."""
        monkeypatch.setenv("BL_API_KEY", "test_key_123")

        responses.add(
            responses.GET,
            f"{BREATHE_LONDON_API_BASE}/SensorData",
            json=mock_sensor_data_response,
            status=200,
        )

        result = fetch_breathe_london_data(
            sites=["BL0001"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        # Verify complete schema and data
        assert not result.empty
        assert len(result) == 3
        assert set(result["measurand"].unique()) == {"NO2", "PM2.5"}
        assert (result["source_network"] == "Breathe London").all()
        assert (result["units"] == "ug/m3").all()
        assert pd.api.types.is_datetime64_any_dtype(result["date_time"])


# ============================================================================
# Live Integration Tests (require network access and API key)
# ============================================================================


@pytest.mark.integration
class TestLiveIntegration:
    """
    Integration tests that hit the live Breathe London API.

    These tests are skipped by default. Run with:
        pytest -m integration tests/test_breathe_london.py

    Requires BL_API_KEY environment variable to be set.
    """

    @pytest.fixture(autouse=True)
    def check_api_key(self):
        """Skip tests if API key is not available."""
        import os

        if not os.environ.get("BL_API_KEY"):
            pytest.skip("BL_API_KEY not set")

    def test_live_fetch_all_metadata(self):
        """Test fetching all sensor metadata."""
        df = fetch_breathe_london_metadata()

        assert not df.empty
        assert "site_code" in df.columns
        assert "site_name" in df.columns
        assert "latitude" in df.columns
        assert "longitude" in df.columns
        assert all(df["source_network"] == "Breathe London")

        # Breathe London covers Greater London
        assert len(df) > 10  # Should have many sensors
        assert df["latitude"].min() > 51.0
        assert df["latitude"].max() < 52.0

    def test_live_fetch_metadata_by_borough(self):
        """Test fetching metadata filtered by borough."""
        df = fetch_breathe_london_metadata(borough="Camden")

        if not df.empty:
            # All should be in Camden
            assert all(df["source_network"] == "Breathe London")

    def test_live_fetch_metadata_by_species(self):
        """Test fetching metadata filtered by species."""
        df = fetch_breathe_london_metadata(species="NO2")

        assert not df.empty
        assert "site_code" in df.columns

    def test_live_fetch_metadata_by_location(self):
        """Test fetching metadata by location (central London)."""
        df = fetch_breathe_london_metadata(
            latitude=51.5074,
            longitude=-0.1278,
            radius_km=5,
        )

        if not df.empty:
            # Should be near central London
            assert df["latitude"].mean() > 51.4
            assert df["latitude"].mean() < 51.6

    def test_live_fetch_historical_data(self):
        """Test fetching historical data."""
        # First get a valid site code
        metadata = fetch_breathe_london_metadata()

        if metadata.empty:
            pytest.skip("No metadata available")

        site_code = metadata["site_code"].iloc[0]

        # Fetch data from last month (recent data should be available)
        from datetime import timedelta

        end_date = datetime.now() - timedelta(days=7)
        start_date = end_date - timedelta(days=3)

        df = fetch_breathe_london_data(
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
            assert all(df["source_network"] == "Breathe London")

            # Values should be reasonable
            assert df["value"].min() >= 0
            assert df["value"].max() < 1000

    def test_live_fetch_multiple_sites(self):
        """Test fetching data for multiple sites."""
        # Get a few site codes
        metadata = fetch_breathe_london_metadata()

        if len(metadata) < 2:
            pytest.skip("Not enough sites available")

        site_codes = metadata["site_code"].head(3).tolist()

        from datetime import timedelta

        end_date = datetime.now() - timedelta(days=7)
        start_date = end_date - timedelta(days=1)

        df = fetch_breathe_london_data(
            sites=site_codes,
            start_date=start_date,
            end_date=end_date,
        )

        if not df.empty:
            # Should have data from multiple sites
            assert len(df["site_code"].unique()) >= 1

    def test_live_aeolus_networks_api(self):
        """Test using aeolus.networks API with Breathe London."""
        import aeolus

        df = aeolus.networks.get_metadata("BREATHE_LONDON")

        assert not df.empty
        assert "site_code" in df.columns
        assert "latitude" in df.columns

    def test_live_full_workflow(self):
        """Test complete workflow: get metadata, then download data."""
        import aeolus

        # Get sites
        sites = aeolus.networks.get_metadata("BREATHE_LONDON")

        if sites.empty:
            pytest.skip("No sites found")

        site_codes = sites["site_code"].head(2).tolist()

        # Download data
        from datetime import timedelta

        end_date = datetime.now() - timedelta(days=7)
        start_date = end_date - timedelta(days=1)

        df = aeolus.download(
            "BREATHE_LONDON",
            site_codes,
            start_date,
            end_date,
        )

        # Verify structure even if empty
        expected_cols = {"site_code", "date_time", "measurand", "value", "units"}
        assert expected_cols.issubset(set(df.columns))
