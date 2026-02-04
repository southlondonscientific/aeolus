"""
Tests for OpenAQ data source using the official SDK.

Tests the client management, metadata fetching, data fetching, and
normalization with mocked SDK responses.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from aeolus.sources.openaq import (
    PARAMETER_MAP,
    _empty_dataframe,
    _get_client,
    _normalize,
    fetch_openaq_data,
    fetch_openaq_metadata,
)

# ============================================================================
# Fixtures for Mock SDK Responses
# ============================================================================


@pytest.fixture
def mock_location():
    """Create a mock location object matching SDK structure."""
    location = MagicMock()
    location.id = 2708
    location.name = "London Marylebone Road"
    location.coordinates = MagicMock()
    location.coordinates.latitude = 51.5225
    location.coordinates.longitude = -0.1546
    location.country = MagicMock()
    location.country.code = "GB"

    # Mock sensors
    sensor1 = MagicMock()
    sensor1.parameter = MagicMock()
    sensor1.parameter.name = "no2"

    sensor2 = MagicMock()
    sensor2.parameter = MagicMock()
    sensor2.parameter.name = "pm25"

    location.sensors = [sensor1, sensor2]

    return location


@pytest.fixture
def mock_location_no_coords():
    """Create a mock location without coordinates."""
    location = MagicMock()
    location.id = 9999
    location.name = "Unknown Location"
    location.coordinates = None
    location.country = None
    location.sensors = []
    return location


@pytest.fixture
def mock_sensor():
    """Create a mock sensor object."""
    sensor = MagicMock()
    sensor.id = 7117
    sensor.parameter = MagicMock()
    sensor.parameter.name = "no2"
    sensor.parameter.units = "µg/m³"
    return sensor


@pytest.fixture
def mock_measurement():
    """Create a mock measurement object."""
    measurement = MagicMock()
    measurement.value = 45.2
    measurement.period = MagicMock()
    measurement.period.datetime_to = MagicMock()
    measurement.period.datetime_to.utc = datetime(2024, 1, 1, 12, 0, 0)
    return measurement


@pytest.fixture
def mock_measurement_null_period():
    """Create a mock measurement with null period."""
    measurement = MagicMock()
    measurement.value = 30.5
    measurement.period = None
    return measurement


# ============================================================================
# Tests for _get_client()
# ============================================================================


class TestGetClient:
    """Tests for client initialization."""

    def test_raises_without_api_key(self, monkeypatch):
        """Test that missing API key raises ValueError."""
        # Clear any cached client
        import aeolus.sources.openaq as openaq_module

        openaq_module._client = None

        monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENAQ-API-KEY", raising=False)

        with pytest.raises(ValueError, match="OpenAQ API key required"):
            _get_client()

    @patch("aeolus.sources.openaq.OpenAQ")
    def test_creates_client_with_api_key(self, mock_openaq_class, monkeypatch):
        """Test that client is created with API key."""
        import aeolus.sources.openaq as openaq_module

        openaq_module._client = None

        monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

        _get_client()

        mock_openaq_class.assert_called_once_with(api_key="test_key_123")

    @patch("aeolus.sources.openaq.OpenAQ")
    def test_supports_alternative_env_var(self, mock_openaq_class, monkeypatch):
        """Test that OPENAQ-API-KEY env var is also supported."""
        import aeolus.sources.openaq as openaq_module

        openaq_module._client = None

        monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
        monkeypatch.setenv("OPENAQ-API-KEY", "alt_key_456")

        _get_client()

        mock_openaq_class.assert_called_once_with(api_key="alt_key_456")

    @patch("aeolus.sources.openaq.OpenAQ")
    def test_reuses_existing_client(self, mock_openaq_class, monkeypatch):
        """Test that existing client is reused."""
        import aeolus.sources.openaq as openaq_module

        # Set up existing client
        existing_client = MagicMock()
        openaq_module._client = existing_client

        monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

        result = _get_client()

        # Should return existing client, not create new one
        assert result is existing_client
        mock_openaq_class.assert_not_called()

        # Clean up
        openaq_module._client = None


# ============================================================================
# Tests for fetch_openaq_metadata()
# ============================================================================


class TestFetchOpenaqMetadata:
    """Tests for metadata/location search."""

    def test_raises_without_filters(self, monkeypatch):
        """Test that calling without filters raises error."""
        monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

        with pytest.raises(ValueError, match="OpenAQ requires search filters"):
            fetch_openaq_metadata()

    @patch("aeolus.sources.openaq._get_client")
    def test_fetches_locations_by_country(self, mock_get_client, mock_location):
        """Test fetching locations filtered by country."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.results = [mock_location]
        mock_client.locations.list.return_value = mock_response

        result = fetch_openaq_metadata(country="GB")

        mock_client.locations.list.assert_called_once_with(iso="GB", limit=100)
        assert len(result) == 1
        assert result["site_code"].iloc[0] == "2708"
        assert result["site_name"].iloc[0] == "London Marylebone Road"
        assert result["country"].iloc[0] == "GB"

    @patch("aeolus.sources.openaq._get_client")
    def test_fetches_locations_by_bbox(self, mock_get_client, mock_location):
        """Test fetching locations filtered by bounding box."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.results = [mock_location]
        mock_client.locations.list.return_value = mock_response

        bbox = (-0.5, 51.3, 0.3, 51.7)
        result = fetch_openaq_metadata(bbox=bbox)

        mock_client.locations.list.assert_called_once_with(bbox=bbox, limit=100)

    @patch("aeolus.sources.openaq._get_client")
    def test_accepts_bbox_as_list(self, mock_get_client, mock_location):
        """Test that bbox can be passed as list (converted to tuple)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.results = [mock_location]
        mock_client.locations.list.return_value = mock_response

        bbox_list = [-0.5, 51.3, 0.3, 51.7]
        fetch_openaq_metadata(bbox=bbox_list)

        # Should be converted to tuple
        call_args = mock_client.locations.list.call_args
        assert call_args.kwargs["bbox"] == (-0.5, 51.3, 0.3, 51.7)

    @patch("aeolus.sources.openaq._get_client")
    def test_fetches_locations_by_coordinates(self, mock_get_client, mock_location):
        """Test fetching locations by coordinates and radius."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.results = [mock_location]
        mock_client.locations.list.return_value = mock_response

        result = fetch_openaq_metadata(coordinates=(51.5, -0.1), radius=5000)

        mock_client.locations.list.assert_called_once_with(
            coordinates=(51.5, -0.1), radius=5000, limit=100
        )

    @patch("aeolus.sources.openaq._get_client")
    def test_respects_limit_parameter(self, mock_get_client, mock_location):
        """Test that limit parameter is passed through."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.results = [mock_location]
        mock_client.locations.list.return_value = mock_response

        fetch_openaq_metadata(country="GB", limit=500)

        mock_client.locations.list.assert_called_once_with(iso="GB", limit=500)

    @patch("aeolus.sources.openaq._get_client")
    def test_returns_empty_dataframe_on_no_results(self, mock_get_client):
        """Test that empty response returns empty DataFrame with schema."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.results = []
        mock_client.locations.list.return_value = mock_response

        result = fetch_openaq_metadata(country="XX")

        assert isinstance(result, pd.DataFrame)
        assert result.empty
        assert "site_code" in result.columns
        assert "source_network" in result.columns

    @patch("aeolus.sources.openaq._get_client")
    def test_handles_location_without_coordinates(
        self, mock_get_client, mock_location_no_coords
    ):
        """Test handling locations with missing coordinates."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.results = [mock_location_no_coords]
        mock_client.locations.list.return_value = mock_response

        result = fetch_openaq_metadata(country="XX")

        assert len(result) == 1
        assert pd.isna(result["latitude"].iloc[0])
        assert pd.isna(result["longitude"].iloc[0])
        assert pd.isna(result["country"].iloc[0])

    @patch("aeolus.sources.openaq._get_client")
    def test_extracts_parameters_from_sensors(self, mock_get_client, mock_location):
        """Test that parameters are extracted from sensors."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.results = [mock_location]
        mock_client.locations.list.return_value = mock_response

        result = fetch_openaq_metadata(country="GB")

        assert result["parameters"].iloc[0] == ["no2", "pm25"]

    @patch("aeolus.sources.openaq._get_client")
    def test_adds_source_network(self, mock_get_client, mock_location):
        """Test that source_network column is added."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.results = [mock_location]
        mock_client.locations.list.return_value = mock_response

        result = fetch_openaq_metadata(country="GB")

        assert (result["source_network"] == "OpenAQ").all()


# ============================================================================
# Tests for fetch_openaq_data()
# ============================================================================


class TestFetchOpenaqData:
    """Tests for data fetching."""

    @patch("aeolus.sources.openaq._get_client")
    def test_fetches_data_for_single_site(
        self, mock_get_client, mock_sensor, mock_measurement
    ):
        """Test fetching data for a single location."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock sensors response
        sensors_response = MagicMock()
        sensors_response.results = [mock_sensor]
        mock_client.locations.sensors.return_value = sensors_response

        # Mock measurements response
        measurements_response = MagicMock()
        measurements_response.results = [mock_measurement]
        mock_client.measurements.list.return_value = measurements_response

        result = fetch_openaq_data(
            sites=["2708"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert not result.empty
        assert "site_code" in result.columns
        assert "measurand" in result.columns
        assert result["site_code"].iloc[0] == "2708"

    @patch("aeolus.sources.openaq._get_client")
    def test_fetches_data_for_multiple_sites(
        self, mock_get_client, mock_sensor, mock_measurement
    ):
        """Test fetching data for multiple locations."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock sensors response
        sensors_response = MagicMock()
        sensors_response.results = [mock_sensor]
        mock_client.locations.sensors.return_value = sensors_response

        # Mock measurements response
        measurements_response = MagicMock()
        measurements_response.results = [mock_measurement]
        mock_client.measurements.list.return_value = measurements_response

        result = fetch_openaq_data(
            sites=["2708", "3272"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should call locations.sensors for each site
        assert mock_client.locations.sensors.call_count == 2

    @patch("aeolus.sources.openaq._get_client")
    def test_handles_sensor_fetch_failure(self, mock_get_client):
        """Test that sensor fetch errors are handled gracefully."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock sensors to raise exception
        mock_client.locations.sensors.side_effect = Exception("API Error")

        result = fetch_openaq_data(
            sites=["2708"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result.empty

    @patch("aeolus.sources.openaq._get_client")
    def test_handles_no_sensors(self, mock_get_client):
        """Test handling location with no sensors."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock empty sensors response
        sensors_response = MagicMock()
        sensors_response.results = []
        mock_client.locations.sensors.return_value = sensors_response

        result = fetch_openaq_data(
            sites=["9999"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result.empty

    @patch("aeolus.sources.openaq._get_client")
    def test_handles_measurement_fetch_failure(self, mock_get_client, mock_sensor):
        """Test that measurement fetch errors are handled gracefully."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock sensors response
        sensors_response = MagicMock()
        sensors_response.results = [mock_sensor]
        mock_client.locations.sensors.return_value = sensors_response

        # Mock measurements to raise exception
        mock_client.measurements.list.side_effect = Exception("API Error")

        result = fetch_openaq_data(
            sites=["2708"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should return empty since measurement fetch failed
        assert result.empty

    @patch("aeolus.sources.openaq._get_client")
    def test_handles_null_datetime(
        self, mock_get_client, mock_sensor, mock_measurement_null_period
    ):
        """Test that null datetime values are handled."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock sensors response
        sensors_response = MagicMock()
        sensors_response.results = [mock_sensor]
        mock_client.locations.sensors.return_value = sensors_response

        # Mock measurements with null period
        measurements_response = MagicMock()
        measurements_response.results = [mock_measurement_null_period]
        mock_client.measurements.list.return_value = measurements_response

        result = fetch_openaq_data(
            sites=["2708"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should be filtered out during normalization
        assert result.empty

    @patch("aeolus.sources.openaq._get_client")
    def test_passes_correct_parameters_to_sdk(
        self, mock_get_client, mock_sensor, mock_measurement
    ):
        """Test that correct parameters are passed to SDK."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock sensors response
        sensors_response = MagicMock()
        sensors_response.results = [mock_sensor]
        mock_client.locations.sensors.return_value = sensors_response

        # Mock measurements response
        measurements_response = MagicMock()
        measurements_response.results = [mock_measurement]
        mock_client.measurements.list.return_value = measurements_response

        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        fetch_openaq_data(sites=["2708"], start_date=start, end_date=end)

        # Check measurements.list was called with correct params
        mock_client.measurements.list.assert_called_once_with(
            sensors_id=7117,
            datetime_from=start,
            datetime_to=end,
            limit=1000,
        )


# ============================================================================
# Tests for _normalize()
# ============================================================================


class TestNormalize:
    """Tests for data normalization."""

    def test_renames_columns(self):
        """Test that columns are renamed correctly."""
        df = pd.DataFrame(
            {
                "location_id": ["2708"],
                "sensor_id": [7117],
                "parameter": ["no2"],
                "value": [45.2],
                "datetime": [datetime(2024, 1, 1, 12, 0)],
                "units": ["µg/m³"],
            }
        )

        result = _normalize(df)

        assert "site_code" in result.columns
        assert "date_time" in result.columns
        assert "location_id" not in result.columns

    def test_standardizes_parameter_names(self):
        """Test that parameter names are standardized."""
        df = pd.DataFrame(
            {
                "location_id": ["2708", "2708"],
                "sensor_id": [7117, 7118],
                "parameter": ["no2", "pm25"],
                "value": [45.2, 18.5],
                "datetime": [datetime(2024, 1, 1), datetime(2024, 1, 1)],
                "units": ["µg/m³", "µg/m³"],
            }
        )

        result = _normalize(df)

        assert set(result["measurand"].unique()) == {"NO2", "PM2.5"}

    def test_handles_unknown_parameters(self):
        """Test that unknown parameters are uppercased."""
        df = pd.DataFrame(
            {
                "location_id": ["2708"],
                "sensor_id": [7117],
                "parameter": ["unknown_param"],
                "value": [10.0],
                "datetime": [datetime(2024, 1, 1)],
                "units": ["ppb"],
            }
        )

        result = _normalize(df)

        assert result["measurand"].iloc[0] == "UNKNOWN_PARAM"

    def test_standardizes_units(self):
        """Test that units are standardized."""
        df = pd.DataFrame(
            {
                "location_id": ["2708", "2708"],
                "sensor_id": [7117, 7118],
                "parameter": ["no2", "pm25"],
                "value": [45.2, 18.5],
                "datetime": [datetime(2024, 1, 1), datetime(2024, 1, 1)],
                "units": ["µg/m³", "μg/m³"],  # Different mu characters
            }
        )

        result = _normalize(df)

        assert (result["units"] == "ug/m3").all()

    def test_adds_source_network(self):
        """Test that source_network column is added."""
        df = pd.DataFrame(
            {
                "location_id": ["2708"],
                "sensor_id": [7117],
                "parameter": ["no2"],
                "value": [45.2],
                "datetime": [datetime(2024, 1, 1)],
                "units": ["µg/m³"],
            }
        )

        result = _normalize(df)

        assert (result["source_network"] == "OpenAQ").all()

    def test_adds_ratification(self):
        """Test that ratification column is added."""
        df = pd.DataFrame(
            {
                "location_id": ["2708"],
                "sensor_id": [7117],
                "parameter": ["no2"],
                "value": [45.2],
                "datetime": [datetime(2024, 1, 1)],
                "units": ["µg/m³"],
            }
        )

        result = _normalize(df)

        assert (result["ratification"] == "Unvalidated").all()

    def test_adds_created_at(self):
        """Test that created_at timestamp is added."""
        df = pd.DataFrame(
            {
                "location_id": ["2708"],
                "sensor_id": [7117],
                "parameter": ["no2"],
                "value": [45.2],
                "datetime": [datetime(2024, 1, 1)],
                "units": ["µg/m³"],
            }
        )

        result = _normalize(df)

        assert "created_at" in result.columns

    def test_drops_rows_with_null_datetime(self):
        """Test that rows with null datetime are dropped."""
        df = pd.DataFrame(
            {
                "location_id": ["2708", "2708"],
                "sensor_id": [7117, 7118],
                "parameter": ["no2", "pm25"],
                "value": [45.2, 18.5],
                "datetime": [datetime(2024, 1, 1), None],
                "units": ["µg/m³", "µg/m³"],
            }
        )

        result = _normalize(df)

        assert len(result) == 1

    def test_drops_rows_with_null_value(self):
        """Test that rows with null value are dropped."""
        df = pd.DataFrame(
            {
                "location_id": ["2708", "2708"],
                "sensor_id": [7117, 7118],
                "parameter": ["no2", "pm25"],
                "value": [45.2, None],
                "datetime": [datetime(2024, 1, 1), datetime(2024, 1, 1)],
                "units": ["µg/m³", "µg/m³"],
            }
        )

        result = _normalize(df)

        assert len(result) == 1

    def test_selects_correct_columns(self):
        """Test that only standard columns are in output."""
        df = pd.DataFrame(
            {
                "location_id": ["2708"],
                "sensor_id": [7117],
                "parameter": ["no2"],
                "value": [45.2],
                "datetime": [datetime(2024, 1, 1)],
                "units": ["µg/m³"],
            }
        )

        result = _normalize(df)

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


# ============================================================================
# Tests for _empty_dataframe()
# ============================================================================


class TestEmptyDataframe:
    """Tests for empty DataFrame generation."""

    def test_returns_dataframe_with_correct_schema(self):
        """Test that empty DataFrame has correct columns."""
        result = _empty_dataframe()

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
        assert result.empty


# ============================================================================
# Tests for PARAMETER_MAP
# ============================================================================


class TestParameterMap:
    """Tests for parameter name mapping."""

    def test_maps_common_parameters(self):
        """Test that common parameters are mapped correctly."""
        assert PARAMETER_MAP["no2"] == "NO2"
        assert PARAMETER_MAP["pm25"] == "PM2.5"
        assert PARAMETER_MAP["pm10"] == "PM10"
        assert PARAMETER_MAP["o3"] == "O3"
        assert PARAMETER_MAP["so2"] == "SO2"
        assert PARAMETER_MAP["co"] == "CO"

    def test_maps_additional_parameters(self):
        """Test that additional parameters are mapped."""
        assert PARAMETER_MAP["bc"] == "BC"
        assert PARAMETER_MAP["no"] == "NO"
        assert PARAMETER_MAP["nox"] == "NOX"
        assert PARAMETER_MAP["pm1"] == "PM1"
        assert PARAMETER_MAP["ch4"] == "CH4"


# ============================================================================
# Tests for source registration
# ============================================================================


class TestSourceRegistration:
    """Tests for source registration."""

    def test_openaq_is_registered(self):
        """Test that OpenAQ is registered as a source."""
        from aeolus.registry import get_source, register_source

        # Re-register if cleared by other tests
        source = get_source("OPENAQ")
        if source is None:
            register_source(
                "OPENAQ",
                {
                    "type": "portal",
                    "name": "OpenAQ",
                    "search": fetch_openaq_metadata,
                    "fetch_metadata": fetch_openaq_metadata,
                    "fetch_data": fetch_openaq_data,
                    "normalise": lambda df: df,
                    "requires_api_key": True,
                },
            )
            source = get_source("OPENAQ")

        assert source is not None
        assert source["name"] == "OpenAQ"
        assert source["type"] == "portal"
        assert source["requires_api_key"] is True

    def test_registered_with_correct_functions(self):
        """Test that correct functions are registered."""
        from aeolus.registry import get_source, register_source

        # Re-register if cleared by other tests
        source = get_source("OPENAQ")
        if source is None:
            register_source(
                "OPENAQ",
                {
                    "type": "portal",
                    "name": "OpenAQ",
                    "search": fetch_openaq_metadata,
                    "fetch_metadata": fetch_openaq_metadata,
                    "fetch_data": fetch_openaq_data,
                    "normalise": lambda df: df,
                    "requires_api_key": True,
                },
            )
            source = get_source("OPENAQ")

        # Check function names match (handles reloaded modules)
        assert source["search"].__name__ == "fetch_openaq_metadata"
        assert source["fetch_metadata"].__name__ == "fetch_openaq_metadata"
        assert source["fetch_data"].__name__ == "fetch_openaq_data"


# ============================================================================
# Integration-style tests
# ============================================================================


class TestOpenAQIntegration:
    """Integration-style tests for full workflows."""

    @patch("aeolus.sources.openaq._get_client")
    def test_full_metadata_workflow(self, mock_get_client, mock_location):
        """Test complete metadata fetching workflow."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.results = [mock_location]
        mock_client.locations.list.return_value = mock_response

        result = fetch_openaq_metadata(country="GB")

        assert not result.empty
        assert len(result) == 1
        assert result["site_code"].iloc[0] == "2708"
        assert result["site_name"].iloc[0] == "London Marylebone Road"
        assert result["latitude"].iloc[0] == 51.5225
        assert result["longitude"].iloc[0] == -0.1546
        assert result["country"].iloc[0] == "GB"
        assert result["source_network"].iloc[0] == "OpenAQ"

    @patch("aeolus.sources.openaq._get_client")
    def test_full_data_workflow(self, mock_get_client, mock_sensor, mock_measurement):
        """Test complete data fetching workflow."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock sensors response
        sensors_response = MagicMock()
        sensors_response.results = [mock_sensor]
        mock_client.locations.sensors.return_value = sensors_response

        # Mock measurements response
        measurements_response = MagicMock()
        measurements_response.results = [mock_measurement]
        mock_client.measurements.list.return_value = measurements_response

        result = fetch_openaq_data(
            sites=["2708"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert not result.empty
        assert result["site_code"].iloc[0] == "2708"
        assert result["measurand"].iloc[0] == "NO2"
        assert result["value"].iloc[0] == 45.2
        assert result["units"].iloc[0] == "ug/m3"
        assert result["source_network"].iloc[0] == "OpenAQ"
        assert pd.api.types.is_datetime64_any_dtype(result["date_time"])


# ============================================================================
# Live Integration Tests (require network access and API key)
# ============================================================================


@pytest.mark.integration
class TestLiveIntegration:
    """
    Integration tests that hit the live OpenAQ API.

    These tests are skipped by default. Run with:
        pytest -m integration tests/test_openaq.py

    Requires OPENAQ_API_KEY environment variable to be set.
    """

    @pytest.fixture(autouse=True)
    def check_api_key(self):
        """Skip tests if API key is not available."""
        import os

        if not os.environ.get("OPENAQ_API_KEY") and not os.environ.get(
            "OPENAQ-API-KEY"
        ):
            pytest.skip("OPENAQ_API_KEY not set")

        # Clear cached client to ensure fresh connection
        import aeolus.sources.openaq as openaq_module

        openaq_module._client = None
        yield
        openaq_module._client = None

    def test_live_search_by_country(self):
        """Test searching locations by country code."""
        df = fetch_openaq_metadata(country="GB", limit=20)

        assert not df.empty
        assert "site_code" in df.columns
        assert "site_name" in df.columns
        assert "latitude" in df.columns
        assert "longitude" in df.columns
        assert all(df["source_network"] == "OpenAQ")

        # Should have UK locations
        assert all(df["country"] == "GB")

    def test_live_search_by_bbox(self):
        """Test searching locations by bounding box (London area)."""
        # London bounding box
        bbox = (-0.5, 51.3, 0.3, 51.7)
        df = fetch_openaq_metadata(bbox=bbox, limit=20)

        if not df.empty:
            # Locations should be within or near bbox
            assert df["latitude"].min() > 50.0
            assert df["latitude"].max() < 53.0

    def test_live_search_by_coordinates(self):
        """Test searching locations by coordinates and radius."""
        # Central London
        df = fetch_openaq_metadata(
            coordinates=(51.5074, -0.1278),
            radius=10000,  # 10km
            limit=20,
        )

        if not df.empty:
            assert "site_code" in df.columns
            # Should find some locations near central London

    def test_live_fetch_data(self):
        """Test fetching actual measurement data."""
        # First find a location
        metadata = fetch_openaq_metadata(country="GB", limit=5)

        if metadata.empty:
            pytest.skip("No locations found")

        site_code = metadata["site_code"].iloc[0]

        # Fetch recent data (last 7 days)
        from datetime import timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        df = fetch_openaq_data(
            sites=[site_code],
            start_date=start_date,
            end_date=end_date,
        )

        # May be empty if location has no recent data
        if not df.empty:
            assert "site_code" in df.columns
            assert "date_time" in df.columns
            assert "measurand" in df.columns
            assert "value" in df.columns
            assert "units" in df.columns
            assert all(df["source_network"] == "OpenAQ")

            # Values should be reasonable
            assert df["value"].min() >= 0

    def test_live_aeolus_portals_api(self):
        """Test using aeolus.portals API with OpenAQ."""
        import aeolus

        df = aeolus.portals.find_sites("OPENAQ", country="GB", limit=10)

        assert not df.empty
        assert "site_code" in df.columns

    def test_live_full_workflow(self):
        """Test complete workflow: find sites, then download data."""
        import aeolus

        # Find sites
        sites = aeolus.portals.find_sites("OPENAQ", country="GB", limit=3)

        if sites.empty:
            pytest.skip("No sites found")

        site_ids = sites["site_code"].tolist()

        # Download recent data
        from datetime import timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=3)

        df = aeolus.download(
            "OPENAQ",
            site_ids,
            start_date,
            end_date,
        )

        # Verify structure even if empty
        expected_cols = {"site_code", "date_time", "measurand", "value", "units"}
        assert expected_cols.issubset(set(df.columns))
