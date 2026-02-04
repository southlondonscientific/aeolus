"""
Tests for PurpleAir data source.

Tests the API calls, metadata fetching, data fetching, and normalization
pipeline with mocked responses.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from aeolus.sources.purpleair import (
    DEFAULT_HISTORY_FIELDS,
    METADATA_FIELDS,
    PARAMETER_MAP,
    PM_ABSOLUTE_AGREEMENT_THRESHOLD,
    PM_LOW_CONCENTRATION_THRESHOLD,
    PM_LOWER_DETECTION_LIMIT,
    PM_RELATIVE_AGREEMENT_THRESHOLD,
    PM_UPPER_SATURATION_LIMIT,
    _apply_pm_bounds_check,
    _calculate_channel_value,
    _calculate_channel_value_simple,
    _calculate_pm_channel_value,
    _create_metadata_normalizer,
    _get_purpleair_client,
    _parse_historic_response,
    create_purpleair_normalizer,
    fetch_purpleair_data,
    fetch_purpleair_metadata,
)

# ============================================================================
# Fixtures for Mock API Responses
# ============================================================================


@pytest.fixture
def mock_sensors_response():
    """Mock response from request_multiple_sensors_data."""
    return {
        "fields": [
            "sensor_index",
            "name",
            "latitude",
            "longitude",
            "altitude",
            "location_type",
            "last_seen",
            "date_created",
            "private",
            "model",
            "hardware",
        ],
        "data": [
            [
                131075,  # sensor_index
                "London Sensor 1",
                51.5074,
                -0.1278,
                100,
                0,  # outdoor
                1704067200,  # 2024-01-01 00:00:00 UTC
                1609459200,  # 2021-01-01 00:00:00 UTC
                0,  # public
                "PA-II",
                "2.0",
            ],
            [
                131076,
                "London Sensor 2",
                51.5080,
                -0.1290,
                105,
                1,  # indoor
                1704153600,  # 2024-01-02 00:00:00 UTC
                1609545600,  # 2021-01-02 00:00:00 UTC
                0,
                "PA-II",
                "2.0",
            ],
        ],
    }


@pytest.fixture
def mock_single_sensor_response():
    """Mock response for a single sensor."""
    return {
        "fields": [
            "sensor_index",
            "name",
            "latitude",
            "longitude",
            "altitude",
            "location_type",
            "last_seen",
            "date_created",
            "private",
            "model",
            "hardware",
        ],
        "data": [
            [
                131075,
                "London Sensor 1",
                51.5074,
                -0.1278,
                100,
                0,
                1704067200,
                1609459200,
                0,
                "PA-II",
                "2.0",
            ],
        ],
    }


@pytest.fixture
def mock_historic_response():
    """Mock response from request_sensor_historic_data."""
    return {
        "fields": [
            "time_stamp",
            "pm2.5_atm_a",
            "pm2.5_atm_b",
            "pm10.0_atm_a",
            "pm10.0_atm_b",
            "pm1.0_atm_a",
            "pm1.0_atm_b",
            "humidity_a",
            "humidity_b",
            "temperature_a",
            "temperature_b",
        ],
        "data": [
            # 2024-01-01 00:00:00 UTC - both channels valid, good agreement
            [1704067200, 12.5, 12.8, 18.2, 18.5, 8.1, 8.3, 65.0, 65.2, 68.0, 68.2],
            # 2024-01-01 01:00:00 UTC - both channels valid, good agreement
            [1704070800, 14.2, 14.5, 20.1, 20.3, 9.5, 9.7, 62.0, 62.1, 70.0, 70.1],
            # 2024-01-01 02:00:00 UTC - channel B missing
            [1704074400, 16.8, None, 22.5, None, 11.2, None, 58.0, None, 72.0, None],
        ],
    }


@pytest.fixture
def mock_historic_response_with_disagreement():
    """Mock response with channel disagreement (>10 µg/m³ at low concentration)."""
    return {
        "fields": [
            "time_stamp",
            "pm2.5_atm_a",
            "pm2.5_atm_b",
            "pm10.0_atm_a",
            "pm10.0_atm_b",
            "pm1.0_atm_a",
            "pm1.0_atm_b",
            "humidity_a",
            "humidity_b",
            "temperature_a",
            "temperature_b",
        ],
        "data": [
            # Channels disagree by more than 10 µg/m³ (absolute threshold for low conc)
            # 5 and 20 differ by 15 µg/m³, avg = 12.5 (< 100, so absolute threshold applies)
            [1704067200, 5.0, 20.0, 18.0, 18.5, 8.0, 8.2, 65.0, 65.2, 68.0, 68.2],
        ],
    }


@pytest.fixture
def mock_historic_response_high_concentration():
    """Mock response with high concentration data (>100 µg/m³)."""
    return {
        "fields": [
            "time_stamp",
            "pm2.5_atm_a",
            "pm2.5_atm_b",
            "pm10.0_atm_a",
            "pm10.0_atm_b",
            "pm1.0_atm_a",
            "pm1.0_atm_b",
            "humidity_a",
            "humidity_b",
            "temperature_a",
            "temperature_b",
        ],
        "data": [
            # High concentration, good agreement (within 10%)
            # 200 and 210 differ by 5%, avg = 205
            [
                1704067200,
                200.0,
                210.0,
                250.0,
                260.0,
                150.0,
                155.0,
                65.0,
                65.2,
                68.0,
                68.2,
            ],
            # High concentration, poor agreement (>10%)
            # 200 and 280 differ by 33%, avg = 240
            [
                1704070800,
                200.0,
                280.0,
                250.0,
                350.0,
                150.0,
                210.0,
                65.0,
                65.2,
                68.0,
                68.2,
            ],
        ],
    }


@pytest.fixture
def mock_historic_response_edge_cases():
    """Mock response with edge cases: below detection, saturation."""
    return {
        "fields": [
            "time_stamp",
            "pm2.5_atm_a",
            "pm2.5_atm_b",
            "pm10.0_atm_a",
            "pm10.0_atm_b",
            "pm1.0_atm_a",
            "pm1.0_atm_b",
            "humidity_a",
            "humidity_b",
            "temperature_a",
            "temperature_b",
        ],
        "data": [
            # Below detection limit (< 0.3 µg/m³)
            [1704067200, 0.1, 0.2, 0.1, 0.1, 0.05, 0.05, 65.0, 65.2, 68.0, 68.2],
            # Sensor saturation (> 1000 µg/m³)
            [
                1704070800,
                1200.0,
                1150.0,
                1300.0,
                1250.0,
                1100.0,
                1050.0,
                65.0,
                65.2,
                68.0,
                68.2,
            ],
        ],
    }


@pytest.fixture
def mock_empty_response():
    """Mock empty response."""
    return {"fields": [], "data": []}


# ============================================================================
# Tests for _get_purpleair_client()
# ============================================================================


class TestGetPurpleairClient:
    """Tests for the API client getter."""

    def test_raises_without_api_key(self, monkeypatch):
        """Test that missing API key raises ValueError."""
        monkeypatch.delenv("PURPLEAIR_API_KEY", raising=False)

        with pytest.raises(ValueError, match="PurpleAir API key required"):
            _get_purpleair_client()

    def test_error_message_includes_setup_instructions(self, monkeypatch):
        """Test that error message includes instructions for getting API key."""
        monkeypatch.delenv("PURPLEAIR_API_KEY", raising=False)

        with pytest.raises(ValueError, match="PURPLEAIR_API_KEY"):
            _get_purpleair_client()

        with pytest.raises(ValueError, match="develop.purpleair.com"):
            _get_purpleair_client()

    def test_returns_client_with_api_key(self, monkeypatch):
        """Test that client is created with API key."""
        monkeypatch.setenv("PURPLEAIR_API_KEY", "test_key_123")

        with patch("purpleair_api.PurpleAirAPI.PurpleAirReadAPI") as mock_cls:
            client = _get_purpleair_client()
            mock_cls.assert_called_once_with("test_key_123")


# ============================================================================
# Tests for fetch_purpleair_metadata()
# ============================================================================


class TestFetchPurpleairMetadata:
    """Tests for metadata fetching."""

    def test_returns_empty_without_api_key(self, monkeypatch):
        """Test that missing API key returns empty DataFrame."""
        monkeypatch.delenv("PURPLEAIR_API_KEY", raising=False)

        result = fetch_purpleair_metadata()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_fetches_sensors(self, mock_get_client, mock_sensors_response):
        """Test fetching sensors."""
        mock_client = MagicMock()
        mock_client.request_multiple_sensors_data.return_value = mock_sensors_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_metadata()

        assert len(result) == 2
        assert "site_code" in result.columns
        assert "site_name" in result.columns
        assert "latitude" in result.columns
        assert "longitude" in result.columns
        assert "source_network" in result.columns

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_normalizes_column_names(self, mock_get_client, mock_sensors_response):
        """Test that column names are normalized to standard schema."""
        mock_client = MagicMock()
        mock_client.request_multiple_sensors_data.return_value = mock_sensors_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_metadata()

        assert "site_code" in result.columns
        assert "site_name" in result.columns
        assert result["site_code"].iloc[0] == "131075"

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_adds_source_network(self, mock_get_client, mock_sensors_response):
        """Test that source_network column is added."""
        mock_client = MagicMock()
        mock_client.request_multiple_sensors_data.return_value = mock_sensors_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_metadata()

        assert (result["source_network"] == "PurpleAir").all()

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_converts_location_type(self, mock_get_client, mock_sensors_response):
        """Test that location_type is converted from int to string."""
        mock_client = MagicMock()
        mock_client.request_multiple_sensors_data.return_value = mock_sensors_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_metadata()

        assert result["location_type"].iloc[0] == "outdoor"
        assert result["location_type"].iloc[1] == "indoor"

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_converts_timestamps(self, mock_get_client, mock_sensors_response):
        """Test that timestamps are converted to datetime."""
        mock_client = MagicMock()
        mock_client.request_multiple_sensors_data.return_value = mock_sensors_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_metadata()

        assert pd.api.types.is_datetime64_any_dtype(result["last_seen"])
        assert pd.api.types.is_datetime64_any_dtype(result["date_created"])

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_passes_bounding_box_filters(
        self, mock_get_client, mock_single_sensor_response
    ):
        """Test that bounding box filters are passed to API."""
        mock_client = MagicMock()
        mock_client.request_multiple_sensors_data.return_value = (
            mock_single_sensor_response
        )
        mock_get_client.return_value = mock_client

        fetch_purpleair_metadata(nwlat=51.7, nwlng=-0.5, selat=51.3, selng=0.3)

        call_kwargs = mock_client.request_multiple_sensors_data.call_args[1]
        assert call_kwargs["nwlat"] == 51.7
        assert call_kwargs["nwlng"] == -0.5
        assert call_kwargs["selat"] == 51.3
        assert call_kwargs["selng"] == 0.3

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_passes_location_type_filter(
        self, mock_get_client, mock_single_sensor_response
    ):
        """Test that location_type filter is passed to API."""
        mock_client = MagicMock()
        mock_client.request_multiple_sensors_data.return_value = (
            mock_single_sensor_response
        )
        mock_get_client.return_value = mock_client

        fetch_purpleair_metadata(location_type=0)

        call_kwargs = mock_client.request_multiple_sensors_data.call_args[1]
        assert call_kwargs["location_type"] == 0

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_passes_show_only_filter(
        self, mock_get_client, mock_single_sensor_response
    ):
        """Test that show_only filter is passed to API."""
        mock_client = MagicMock()
        mock_client.request_multiple_sensors_data.return_value = (
            mock_single_sensor_response
        )
        mock_get_client.return_value = mock_client

        fetch_purpleair_metadata(show_only="131075,131076")

        call_kwargs = mock_client.request_multiple_sensors_data.call_args[1]
        assert call_kwargs["show_only"] == "131075,131076"

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_returns_empty_on_no_results(self, mock_get_client, mock_empty_response):
        """Test that empty response returns empty DataFrame."""
        mock_client = MagicMock()
        mock_client.request_multiple_sensors_data.return_value = mock_empty_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_metadata()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_returns_empty_on_api_error(self, mock_get_client):
        """Test that API errors return empty DataFrame with warning."""
        mock_client = MagicMock()
        mock_client.request_multiple_sensors_data.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_metadata()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ============================================================================
# Tests for fetch_purpleair_data()
# ============================================================================


class TestFetchPurpleairData:
    """Tests for data fetching."""

    def test_returns_empty_without_api_key(self, monkeypatch):
        """Test that missing API key returns empty DataFrame."""
        monkeypatch.delenv("PURPLEAIR_API_KEY", raising=False)

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert isinstance(result, pd.DataFrame)
        assert result.empty
        assert "site_code" in result.columns

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_fetches_single_site(self, mock_get_client, mock_historic_response):
        """Test fetching data for a single site."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = mock_historic_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert not result.empty
        assert "site_code" in result.columns
        assert "date_time" in result.columns
        assert "measurand" in result.columns
        assert "value" in result.columns

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_calls_api_with_correct_params(
        self, mock_get_client, mock_historic_response
    ):
        """Test that API is called with correct parameters."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = mock_historic_response
        mock_get_client.return_value = mock_client

        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)

        fetch_purpleair_data(sites=["131075"], start_date=start, end_date=end)

        mock_client.request_sensor_historic_data.assert_called_once()
        call_kwargs = mock_client.request_sensor_historic_data.call_args[1]
        assert call_kwargs["sensor_index"] == 131075
        assert call_kwargs["start_timestamp"] == int(start.timestamp())
        assert call_kwargs["end_timestamp"] == int(end.timestamp())
        assert call_kwargs["average"] == 60  # Hourly

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_fetches_multiple_sites(self, mock_get_client, mock_historic_response):
        """Test fetching data for multiple sites."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = mock_historic_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075", "131076"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert mock_client.request_sensor_historic_data.call_count == 2
        assert not result.empty

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_continues_on_single_site_failure(
        self, mock_get_client, mock_historic_response
    ):
        """Test that failure for one site doesn't stop other sites."""
        mock_client = MagicMock()
        # First site fails, second succeeds
        mock_client.request_sensor_historic_data.side_effect = [
            Exception("API Error"),
            mock_historic_response,
        ]
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075", "131076"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert not result.empty

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_returns_empty_on_all_failures(self, mock_get_client):
        """Test that empty DataFrame returned when all sites fail."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert result.empty
        assert "site_code" in result.columns

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_normalizes_output_schema(self, mock_get_client, mock_historic_response):
        """Test that output has normalized schema."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = mock_historic_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075"],
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

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_adds_source_network(self, mock_get_client, mock_historic_response):
        """Test that source_network is added."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = mock_historic_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert (result["source_network"] == "PurpleAir").all()

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_raw_parameter_returns_wide_format(
        self, mock_get_client, mock_historic_response
    ):
        """Test that raw=True returns wide format data."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = mock_historic_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
            raw=True,
        )

        # Should have wide format columns
        assert "pm2.5_atm_a" in result.columns
        assert "pm2.5_atm_b" in result.columns
        assert "sensor_index" in result.columns
        assert "time_stamp" in result.columns
        # Should NOT have normalized columns
        assert "site_code" not in result.columns
        assert "measurand" not in result.columns

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_raw_parameter_preserves_channel_data(
        self, mock_get_client, mock_historic_response
    ):
        """Test that raw=True preserves individual channel values."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = mock_historic_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
            raw=True,
        )

        # Check first row values match mock data
        assert result["pm2.5_atm_a"].iloc[0] == 12.5
        assert result["pm2.5_atm_b"].iloc[0] == 12.8

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_include_flagged_false_filters_bad_data(
        self, mock_get_client, mock_historic_response_with_disagreement
    ):
        """Test that include_flagged=False filters out flagged data."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = (
            mock_historic_response_with_disagreement
        )
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
            include_flagged=False,
        )

        # PM2.5 has channel disagreement, so should be filtered out
        pm25_rows = result[result["measurand"] == "PM2.5"]
        assert len(pm25_rows) == 0 or (pm25_rows["ratification"] == "Validated").all()

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_include_flagged_true_keeps_all_data(
        self, mock_get_client, mock_historic_response_with_disagreement
    ):
        """Test that include_flagged=True (default) keeps flagged data."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = (
            mock_historic_response_with_disagreement
        )
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
            include_flagged=True,
        )

        # Should have channel disagreement flag
        assert "Channel Disagreement" in result["ratification"].values

    def test_returns_empty_raw_without_api_key(self, monkeypatch):
        """Test that missing API key returns empty raw DataFrame."""
        monkeypatch.delenv("PURPLEAIR_API_KEY", raising=False)

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
            raw=True,
        )

        assert isinstance(result, pd.DataFrame)
        assert result.empty
        assert "sensor_index" in result.columns
        assert "pm2.5_atm_a" in result.columns


# ============================================================================
# Tests for QA/QC edge cases in normalization
# ============================================================================


class TestQAQCEdgeCases:
    """Tests for QA/QC edge cases in full normalization pipeline."""

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_below_detection_limit_flagged(
        self, mock_get_client, mock_historic_response_edge_cases
    ):
        """Test that below detection limit values are flagged."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = (
            mock_historic_response_edge_cases
        )
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        # First row has below detection values
        below_detection = result[result["ratification"] == "Below Detection Limit"]
        assert len(below_detection) > 0

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_saturation_flagged(
        self, mock_get_client, mock_historic_response_edge_cases
    ):
        """Test that saturation values are flagged."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = (
            mock_historic_response_edge_cases
        )
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        # Second row has saturation values
        saturation = result[result["ratification"] == "Sensor Saturation"]
        assert len(saturation) > 0

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_high_concentration_relative_threshold(
        self, mock_get_client, mock_historic_response_high_concentration
    ):
        """Test that high concentration uses relative threshold."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = (
            mock_historic_response_high_concentration
        )
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        pm25_results = result[result["measurand"] == "PM2.5"]

        # First row: good agreement (5% diff) should be Validated
        # Second row: poor agreement (33% diff) should be Channel Disagreement
        ratifications = pm25_results["ratification"].tolist()
        assert "Validated" in ratifications
        assert "Channel Disagreement" in ratifications


# ============================================================================
# Tests for _calculate_pm_channel_value() - Literature-based QA/QC
# ============================================================================


class TestCalculatePmChannelValue:
    """Tests for PM dual channel value calculation with literature-based QA/QC."""

    # --- Low concentration tests (absolute threshold: ±10 µg/m³) ---

    def test_low_conc_good_agreement(self):
        """Test low concentration with good agreement (diff < 10 µg/m³)."""
        # 8.0 and 9.5 differ by 1.5 µg/m³, avg = 8.75 (< 100)
        value, status = _calculate_pm_channel_value(8.0, 9.5)

        assert value == pytest.approx(8.75, rel=0.01)
        assert status == "Validated"

    def test_low_conc_poor_agreement(self):
        """Test low concentration with poor agreement (diff > 10 µg/m³)."""
        # 5.0 and 18.0 differ by 13 µg/m³, avg = 11.5 (< 100)
        value, status = _calculate_pm_channel_value(5.0, 18.0)

        assert value == pytest.approx(11.5, rel=0.01)
        assert status == "Channel Disagreement"

    def test_low_conc_at_threshold_boundary(self):
        """Test at exactly 10 µg/m³ absolute threshold."""
        # 10 and 20 differ by exactly 10 µg/m³, avg = 15
        value, status = _calculate_pm_channel_value(10.0, 20.0)

        assert value == pytest.approx(15.0, rel=0.01)
        assert status == "Validated"

    def test_low_conc_just_over_threshold(self):
        """Test just over the 10 µg/m³ threshold."""
        # 10 and 21 differ by 11 µg/m³, avg = 15.5
        value, status = _calculate_pm_channel_value(10.0, 21.0)

        assert value == pytest.approx(15.5, rel=0.01)
        assert status == "Channel Disagreement"

    # --- High concentration tests (relative threshold: ±10%) ---

    def test_high_conc_good_agreement(self):
        """Test high concentration with good agreement (diff < 10%)."""
        # 200 and 210 differ by 5%, avg = 205 (> 100)
        value, status = _calculate_pm_channel_value(200.0, 210.0)

        assert value == pytest.approx(205.0, rel=0.01)
        assert status == "Validated"

    def test_high_conc_poor_agreement(self):
        """Test high concentration with poor agreement (diff > 10%)."""
        # 200 and 280 differ by 33%, avg = 240 (> 100)
        value, status = _calculate_pm_channel_value(200.0, 280.0)

        assert value == pytest.approx(240.0, rel=0.01)
        assert status == "Channel Disagreement"

    def test_high_conc_at_threshold_boundary(self):
        """Test at exactly 10% relative threshold."""
        # For avg = 200, 10% = 20. So 190 and 210 should pass.
        value, status = _calculate_pm_channel_value(190.0, 210.0)

        assert value == pytest.approx(200.0, rel=0.01)
        assert status == "Validated"

    def test_high_conc_just_over_threshold(self):
        """Test just over the 10% relative threshold."""
        # For avg = 200, 10% = 20. 188 and 212 differ by 24, which is 12%.
        value, status = _calculate_pm_channel_value(188.0, 212.0)

        assert value == pytest.approx(200.0, rel=0.01)
        assert status == "Channel Disagreement"

    # --- Bounds tests ---

    def test_below_detection_limit(self):
        """Test values below detection limit (< 0.3 µg/m³)."""
        value, status = _calculate_pm_channel_value(0.1, 0.2)

        assert value == pytest.approx(0.15, rel=0.01)
        assert status == "Below Detection Limit"

    def test_sensor_saturation(self):
        """Test values above saturation limit (> 1000 µg/m³)."""
        value, status = _calculate_pm_channel_value(1200.0, 1150.0)

        assert value == pytest.approx(1175.0, rel=0.01)
        assert status == "Sensor Saturation"

    def test_at_detection_limit_boundary(self):
        """Test at exactly the detection limit."""
        value, status = _calculate_pm_channel_value(0.3, 0.3)

        assert value == pytest.approx(0.3, rel=0.01)
        assert status == "Validated"

    def test_at_saturation_boundary(self):
        """Test at exactly the saturation limit."""
        value, status = _calculate_pm_channel_value(1000.0, 1000.0)

        assert value == pytest.approx(1000.0, rel=0.01)
        assert status == "Validated"

    # --- Single channel tests ---

    def test_only_channel_a_valid(self):
        """Test using channel A when B is None."""
        value, status = _calculate_pm_channel_value(12.5, None)

        assert value == 12.5
        assert status == "Single Channel (A)"

    def test_only_channel_b_valid(self):
        """Test using channel B when A is None."""
        value, status = _calculate_pm_channel_value(None, 12.5)

        assert value == 12.5
        assert status == "Single Channel (B)"

    def test_single_channel_below_detection(self):
        """Test single channel below detection limit."""
        value, status = _calculate_pm_channel_value(0.1, None)

        assert value == 0.1
        assert status == "Below Detection Limit"

    def test_single_channel_saturation(self):
        """Test single channel above saturation."""
        value, status = _calculate_pm_channel_value(None, 1500.0)

        assert value == 1500.0
        assert status == "Sensor Saturation"

    # --- Invalid data tests ---

    def test_both_channels_none(self):
        """Test returning None when both channels invalid."""
        value, status = _calculate_pm_channel_value(None, None)

        assert value is None
        assert status == "Invalid"

    def test_handles_nan_values(self):
        """Test handling NaN values."""
        import numpy as np

        value, status = _calculate_pm_channel_value(12.5, np.nan)

        assert value == 12.5
        assert status == "Single Channel (A)"

    # --- Concentration boundary tests ---

    def test_at_low_high_concentration_boundary(self):
        """Test at exactly 100 µg/m³ boundary (uses relative threshold)."""
        # At avg = 100, 10% = 10 µg/m³, same as absolute. Test just above.
        # 99 and 101 average to 100, diff = 2 = 2%, should pass
        value, status = _calculate_pm_channel_value(99.0, 101.0)

        assert value == pytest.approx(100.0, rel=0.01)
        assert status == "Validated"


class TestCalculateChannelValueSimple:
    """Tests for simple channel averaging without PM-specific QA/QC."""

    def test_both_channels_valid(self):
        """Test averaging when both channels valid."""
        value, status = _calculate_channel_value_simple(65.0, 65.2)

        assert value == pytest.approx(65.1, rel=0.01)
        assert status == "Unvalidated"

    def test_only_channel_a_valid(self):
        """Test using channel A when B is None."""
        value, status = _calculate_channel_value_simple(65.0, None)

        assert value == 65.0
        assert status == "Single Channel (A)"

    def test_only_channel_b_valid(self):
        """Test using channel B when A is None."""
        value, status = _calculate_channel_value_simple(None, 65.0)

        assert value == 65.0
        assert status == "Single Channel (B)"

    def test_both_channels_none(self):
        """Test returning None when both channels invalid."""
        value, status = _calculate_channel_value_simple(None, None)

        assert value is None
        assert status == "Invalid"


class TestApplyPmBoundsCheck:
    """Tests for PM bounds checking helper."""

    def test_normal_value(self):
        """Test value within normal bounds."""
        value, status = _apply_pm_bounds_check(50.0, "Test Flag")

        assert value == 50.0
        assert status == "Test Flag"

    def test_below_detection(self):
        """Test value below detection limit."""
        value, status = _apply_pm_bounds_check(0.1, "Test Flag")

        assert value == 0.1
        assert status == "Below Detection Limit"

    def test_above_saturation(self):
        """Test value above saturation limit."""
        value, status = _apply_pm_bounds_check(1500.0, "Test Flag")

        assert value == 1500.0
        assert status == "Sensor Saturation"


# Legacy function backward compatibility
class TestCalculateChannelValueLegacy:
    """Tests for legacy _calculate_channel_value function."""

    def test_calls_pm_function(self):
        """Test that legacy function works as expected."""
        # This just ensures backward compatibility
        value, status = _calculate_channel_value(12.5, 12.8)

        assert value == pytest.approx(12.65, rel=0.01)
        assert status == "Validated"


# ============================================================================
# Tests for _parse_historic_response()
# ============================================================================


class TestParseHistoricResponse:
    """Tests for parsing historic API responses."""

    def test_parses_response_correctly(self, mock_historic_response):
        """Test that response is parsed to DataFrame."""
        result = _parse_historic_response(mock_historic_response, "131075")

        assert not result.empty
        assert len(result) == 3
        assert "time_stamp" in result.columns
        assert "pm2.5_atm_a" in result.columns
        assert "sensor_index" in result.columns

    def test_adds_sensor_index(self, mock_historic_response):
        """Test that sensor index is added to all rows."""
        result = _parse_historic_response(mock_historic_response, "131075")

        assert (result["sensor_index"] == "131075").all()

    def test_handles_empty_response(self, mock_empty_response):
        """Test handling empty response."""
        result = _parse_historic_response(mock_empty_response, "131075")

        assert result.empty

    def test_handles_missing_data_key(self):
        """Test handling response without data key."""
        result = _parse_historic_response({"fields": ["time_stamp"]}, "131075")

        assert result.empty


# ============================================================================
# Tests for create_purpleair_normalizer()
# ============================================================================


class TestPurpleairNormalizer:
    """Tests for the data normalization pipeline."""

    def test_converts_to_long_format(self, mock_historic_response):
        """Test conversion from wide to long format."""
        normalizer = create_purpleair_normalizer()

        # First parse the response
        df = _parse_historic_response(mock_historic_response, "131075")
        result = normalizer(df)

        # Should have multiple rows per timestamp (one per measurand)
        assert len(result) > len(mock_historic_response["data"])
        assert "measurand" in result.columns
        assert set(result["measurand"].unique()) == {
            "PM2.5",
            "PM10",
            "PM1",
            "Humidity",
            "Temperature",
        }

    def test_parses_timestamps(self, mock_historic_response):
        """Test that timestamps are parsed to datetime."""
        normalizer = create_purpleair_normalizer()

        df = _parse_historic_response(mock_historic_response, "131075")
        result = normalizer(df)

        assert pd.api.types.is_datetime64_any_dtype(result["date_time"])

    def test_converts_temperature_to_celsius(self, mock_historic_response):
        """Test that temperature is converted from Fahrenheit to Celsius."""
        normalizer = create_purpleair_normalizer()

        df = _parse_historic_response(mock_historic_response, "131075")
        result = normalizer(df)

        temp_rows = result[result["measurand"] == "Temperature"]
        assert (temp_rows["units"] == "C").all()
        # 68°F = 20°C
        first_temp = temp_rows["value"].iloc[0]
        assert first_temp == pytest.approx(20.0, abs=0.5)

    def test_adds_ratification_status(self, mock_historic_response):
        """Test that ratification status is added."""
        normalizer = create_purpleair_normalizer()

        df = _parse_historic_response(mock_historic_response, "131075")
        result = normalizer(df)

        assert "ratification" in result.columns
        # First row has both channels valid with good agreement
        pm25_first = result[
            (result["measurand"] == "PM2.5") & (result["date_time"].dt.hour == 0)
        ]
        assert pm25_first["ratification"].iloc[0] == "Validated"

    def test_flags_single_channel_data(self, mock_historic_response):
        """Test that single channel data is flagged."""
        normalizer = create_purpleair_normalizer()

        df = _parse_historic_response(mock_historic_response, "131075")
        result = normalizer(df)

        # Third row has only channel A
        pm25_third = result[
            (result["measurand"] == "PM2.5") & (result["date_time"].dt.hour == 2)
        ]
        assert pm25_third["ratification"].iloc[0] == "Single Channel (A)"

    def test_flags_channel_disagreement(self, mock_historic_response_with_disagreement):
        """Test that channel disagreement is flagged."""
        normalizer = create_purpleair_normalizer()

        df = _parse_historic_response(
            mock_historic_response_with_disagreement, "131075"
        )
        result = normalizer(df)

        pm25_row = result[result["measurand"] == "PM2.5"]
        assert pm25_row["ratification"].iloc[0] == "Channel Disagreement"

    def test_adds_source_network(self, mock_historic_response):
        """Test that source_network column is added."""
        normalizer = create_purpleair_normalizer()

        df = _parse_historic_response(mock_historic_response, "131075")
        result = normalizer(df)

        assert (result["source_network"] == "PurpleAir").all()

    def test_adds_created_at(self, mock_historic_response):
        """Test that created_at timestamp is added."""
        normalizer = create_purpleair_normalizer()

        df = _parse_historic_response(mock_historic_response, "131075")
        result = normalizer(df)

        assert "created_at" in result.columns

    def test_selects_correct_columns(self, mock_historic_response):
        """Test that only standard columns are in output."""
        normalizer = create_purpleair_normalizer()

        df = _parse_historic_response(mock_historic_response, "131075")
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

    def test_correct_units_for_pm(self, mock_historic_response):
        """Test that PM measurements have correct units."""
        normalizer = create_purpleair_normalizer()

        df = _parse_historic_response(mock_historic_response, "131075")
        result = normalizer(df)

        pm_rows = result[result["measurand"].isin(["PM1", "PM2.5", "PM10"])]
        assert (pm_rows["units"] == "ug/m3").all()

    def test_correct_units_for_humidity(self, mock_historic_response):
        """Test that humidity has correct units."""
        normalizer = create_purpleair_normalizer()

        df = _parse_historic_response(mock_historic_response, "131075")
        result = normalizer(df)

        humidity_rows = result[result["measurand"] == "Humidity"]
        assert (humidity_rows["units"] == "%").all()


# ============================================================================
# Tests for _create_metadata_normalizer()
# ============================================================================


class TestMetadataNormalizer:
    """Tests for metadata normalization."""

    def test_converts_sensor_index_to_site_code(self):
        """Test that sensor_index is converted to site_code."""
        normalizer = _create_metadata_normalizer()

        df = pd.DataFrame(
            {
                "sensor_index": [131075],
                "name": ["Test Sensor"],
                "latitude": [51.5],
                "longitude": [-0.1],
                "location_type": [0],
            }
        )

        result = normalizer(df)

        assert result["site_code"].iloc[0] == "131075"

    def test_converts_location_type(self):
        """Test that location_type int is converted to string."""
        normalizer = _create_metadata_normalizer()

        df = pd.DataFrame(
            {
                "sensor_index": [131075, 131076],
                "name": ["Outdoor", "Indoor"],
                "latitude": [51.5, 51.5],
                "longitude": [-0.1, -0.1],
                "location_type": [0, 1],
            }
        )

        result = normalizer(df)

        assert result["location_type"].iloc[0] == "outdoor"
        assert result["location_type"].iloc[1] == "indoor"

    def test_adds_source_network(self):
        """Test that source_network is added."""
        normalizer = _create_metadata_normalizer()

        df = pd.DataFrame(
            {
                "sensor_index": [131075],
                "name": ["Test"],
                "latitude": [51.5],
                "longitude": [-0.1],
            }
        )

        result = normalizer(df)

        assert (result["source_network"] == "PurpleAir").all()


# ============================================================================
# Tests for PARAMETER_MAP
# ============================================================================


class TestParameterMap:
    """Tests for parameter name mapping."""

    def test_maps_pm_fields(self):
        """Test that PM fields are mapped correctly."""
        assert PARAMETER_MAP["pm2.5_atm"] == "PM2.5"
        assert PARAMETER_MAP["pm10.0_atm"] == "PM10"
        assert PARAMETER_MAP["pm1.0_atm"] == "PM1"

    def test_maps_environmental_fields(self):
        """Test that environmental fields are mapped."""
        assert PARAMETER_MAP["humidity"] == "Humidity"
        assert PARAMETER_MAP["temperature"] == "Temperature"
        assert PARAMETER_MAP["pressure"] == "Pressure"


# ============================================================================
# Tests for source registration
# ============================================================================


class TestSourceRegistration:
    """Tests for source registration."""

    def test_purpleair_is_registered(self):
        """Test that PurpleAir is registered as a source."""
        from aeolus.registry import _SOURCES, get_source, register_source

        # Re-register if cleared by other tests
        if "PURPLEAIR" not in _SOURCES:
            register_source(
                "PURPLEAIR",
                {
                    "type": "portal",
                    "name": "PurpleAir",
                    "fetch_metadata": fetch_purpleair_metadata,
                    "fetch_data": fetch_purpleair_data,
                    "normalise": create_purpleair_normalizer(),
                    "requires_api_key": True,
                },
            )

        source = get_source("PURPLEAIR")

        assert source is not None
        assert source["name"] == "PurpleAir"
        assert source["type"] == "portal"
        assert source["requires_api_key"] is True

    def test_registered_with_correct_functions(self):
        """Test that correct functions are registered."""
        from aeolus.registry import _SOURCES, get_source, register_source

        # Re-register if cleared by other tests
        if "PURPLEAIR" not in _SOURCES:
            register_source(
                "PURPLEAIR",
                {
                    "type": "portal",
                    "name": "PurpleAir",
                    "fetch_metadata": fetch_purpleair_metadata,
                    "fetch_data": fetch_purpleair_data,
                    "normalise": create_purpleair_normalizer(),
                    "requires_api_key": True,
                },
            )

        source = get_source("PURPLEAIR")

        # Check function names match (handles reloaded modules)
        assert source["fetch_metadata"].__name__ == "fetch_purpleair_metadata"
        assert source["fetch_data"].__name__ == "fetch_purpleair_data"


# ============================================================================
# Integration-style tests
# ============================================================================


class TestPurpleairIntegration:
    """Integration-style tests for full workflows."""

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_full_metadata_workflow(self, mock_get_client, mock_sensors_response):
        """Test complete metadata fetching workflow."""
        mock_client = MagicMock()
        mock_client.request_multiple_sensors_data.return_value = mock_sensors_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_metadata()

        # Verify complete schema
        assert not result.empty
        assert len(result) == 2
        assert result["site_code"].tolist() == ["131075", "131076"]
        assert (result["source_network"] == "PurpleAir").all()
        assert result["latitude"].dtype == float or "float" in str(
            result["latitude"].dtype
        )

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_full_data_workflow(self, mock_get_client, mock_historic_response):
        """Test complete data fetching workflow."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = mock_historic_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        # Verify complete schema and data
        assert not result.empty
        assert set(result["measurand"].unique()) == {
            "PM2.5",
            "PM10",
            "PM1",
            "Humidity",
            "Temperature",
        }
        assert (result["source_network"] == "PurpleAir").all()
        assert pd.api.types.is_datetime64_any_dtype(result["date_time"])

    @patch("aeolus.sources.purpleair._get_purpleair_client")
    def test_data_quality_flags_preserved(
        self, mock_get_client, mock_historic_response
    ):
        """Test that data quality flags are correctly assigned."""
        mock_client = MagicMock()
        mock_client.request_sensor_historic_data.return_value = mock_historic_response
        mock_get_client.return_value = mock_client

        result = fetch_purpleair_data(
            sites=["131075"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        # Check that we have different ratification statuses
        ratifications = result["ratification"].unique()
        assert "Validated" in ratifications
        assert "Single Channel (A)" in ratifications


# ============================================================================
# Live Integration Tests (require network access and API key)
# ============================================================================


@pytest.mark.integration
class TestLiveIntegration:
    """
    Integration tests that hit the live PurpleAir API.

    These tests are skipped by default. Run with:
        pytest -m integration tests/test_purpleair.py

    Requires PURPLEAIR_API_KEY environment variable to be set.
    """

    @pytest.fixture(autouse=True)
    def check_api_key(self):
        """Skip tests if API key is not available."""
        import os

        if not os.environ.get("PURPLEAIR_API_KEY"):
            pytest.skip("PURPLEAIR_API_KEY not set")

        # Clear cached client
        import aeolus.sources.purpleair as purpleair_module

        purpleair_module._client = None
        yield
        purpleair_module._client = None

    def test_live_fetch_metadata_by_location(self):
        """Test fetching sensors near a location (London)."""
        df = fetch_purpleair_metadata(
            nwlat=51.6,
            nwlng=-0.3,
            selat=51.4,
            selng=0.1,
        )

        # May be empty in some areas
        if not df.empty:
            assert "site_code" in df.columns
            assert "site_name" in df.columns
            assert "latitude" in df.columns
            assert "longitude" in df.columns
            assert all(df["source_network"] == "PurpleAir")

            # Should be in London area
            assert df["latitude"].min() > 51.0
            assert df["latitude"].max() < 52.0

    def test_live_fetch_metadata_outdoor_only(self):
        """Test fetching only outdoor sensors."""
        df = fetch_purpleair_metadata(
            nwlat=52.0,
            nwlng=-2.0,
            selat=51.0,
            selng=0.0,
            location_type=0,  # outdoor only
        )

        # Verify outdoor sensors (location_type=0)
        if not df.empty and "location_type" in df.columns:
            assert (df["location_type"] == 0).all()

    def test_live_fetch_historical_data(self):
        """Test fetching historical data."""
        # First find a sensor
        metadata = fetch_purpleair_metadata(
            nwlat=51.6,
            nwlng=-0.3,
            selat=51.4,
            selng=0.1,
        )

        if metadata.empty:
            pytest.skip("No sensors found in area")

        sensor_id = metadata["site_code"].iloc[0]

        # Fetch data from a week ago (to ensure data availability)
        from datetime import timedelta

        end_date = datetime.now() - timedelta(days=7)
        start_date = end_date - timedelta(days=1)

        df = fetch_purpleair_data(
            sites=[sensor_id],
            start_date=start_date,
            end_date=end_date,
        )

        # May be empty if sensor wasn't active
        if not df.empty:
            assert "site_code" in df.columns
            assert "date_time" in df.columns
            assert "measurand" in df.columns
            assert "value" in df.columns
            assert "ratification" in df.columns
            assert all(df["source_network"] == "PurpleAir")

            # Should have PM data
            measurands = df["measurand"].unique()
            assert any(m in measurands for m in ["PM2.5", "PM10", "PM1"])

            # Values should be reasonable for PM (most < 500)
            pm_data = df[df["measurand"].isin(["PM2.5", "PM10", "PM1"])]
            if not pm_data.empty:
                assert pm_data["value"].min() >= 0
                assert pm_data["value"].quantile(0.95) < 500

    def test_live_fetch_multiple_sensors(self):
        """Test fetching data for multiple sensors."""
        # Find a few sensors
        metadata = fetch_purpleair_metadata(
            nwlat=51.6,
            nwlng=-0.3,
            selat=51.4,
            selng=0.1,
        )

        if len(metadata) < 2:
            pytest.skip("Not enough sensors found")

        sensor_ids = metadata["site_code"].head(2).tolist()

        from datetime import timedelta

        end_date = datetime.now() - timedelta(days=7)
        start_date = end_date - timedelta(hours=12)

        df = fetch_purpleair_data(
            sites=sensor_ids,
            start_date=start_date,
            end_date=end_date,
        )

        if not df.empty:
            # Should have data from multiple sensors
            assert len(df["site_code"].unique()) >= 1

    def test_live_aeolus_portals_api(self):
        """Test using aeolus.portals API with PurpleAir."""
        import aeolus

        df = aeolus.portals.find_sites(
            "PURPLEAIR",
            nwlat=51.6,
            nwlng=-0.3,
            selat=51.4,
            selng=0.1,
        )

        if not df.empty:
            assert "site_code" in df.columns
            assert "latitude" in df.columns

    def test_live_full_workflow(self):
        """Test complete workflow: find sites, then download data."""
        import aeolus

        # Find sites
        sites = aeolus.portals.find_sites(
            "PURPLEAIR",
            nwlat=51.6,
            nwlng=-0.3,
            selat=51.4,
            selng=0.1,
        )

        if sites.empty:
            pytest.skip("No sites found")

        site_ids = sites["site_code"].head(2).tolist()

        # Download data
        from datetime import timedelta

        end_date = datetime.now() - timedelta(days=7)
        start_date = end_date - timedelta(hours=6)

        df = aeolus.download(
            "PURPLEAIR",
            site_ids,
            start_date,
            end_date,
        )

        # Verify structure even if empty
        expected_cols = {"site_code", "date_time", "measurand", "value", "units"}
        assert expected_cols.issubset(set(df.columns))
