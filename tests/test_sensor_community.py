"""
Tests for Sensor.Community data source.

Tests the API calls, metadata fetching, data fetching, rate limiting,
and normalization with mocked responses.
"""

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from aeolus.registry import _SOURCES
from aeolus.sources.sensor_community import (
    ARCHIVE_BASE,
    DATA_API_BASE,
    DEFAULT_RATE_LIMIT_PERIOD,
    DEFAULT_RATE_LIMIT_REQUESTS,
    DEFAULT_REQUEST_DELAY,
    SENSOR_TYPE_MAP,
    UNITS_MAP,
    USER_AGENT,
    VALUE_NAME_MAP,
    RateLimiter,
    _apply_rate_limit,
    _empty_dataframe,
    _fetch_sensor_archive,
    _get_sensor_types_for_sites,
    _make_request,
    _normalize_sensor_data,
    fetch_sensor_community_data,
    fetch_sensor_community_metadata,
    fetch_sensor_community_realtime,
    set_rate_limiting,
)

# ============================================================================
# Ensure source is registered for tests
# ============================================================================


@pytest.fixture(autouse=True)
def ensure_source_registered():
    """Ensure Sensor.Community source is registered before tests."""
    from aeolus.registry import register_source
    from aeolus.sources import sensor_community as sc_module  # noqa: F401

    if "SENSOR_COMMUNITY" not in _SOURCES:
        register_source(
            "SENSOR_COMMUNITY",
            {
                "type": "network",
                "name": "Sensor.Community",
                "fetch_metadata": fetch_sensor_community_metadata,
                "fetch_data": fetch_sensor_community_data,
                "requires_api_key": False,
            },
        )
    yield


@pytest.fixture(autouse=True)
def clear_sensor_type_cache():
    """Clear the sensor type cache before each test."""
    from aeolus.sources import sensor_community

    sensor_community._sensor_type_cache.clear()
    yield
    sensor_community._sensor_type_cache.clear()


# ============================================================================
# Fixtures for Mock API Responses
# ============================================================================


@pytest.fixture
def mock_realtime_response():
    """Mock response from the real-time API endpoint."""
    return [
        {
            "sensor": {"id": 12345, "sensor_type": {"id": 14, "name": "SDS011"}},
            "location": {
                "id": 6789,
                "latitude": "51.5074",
                "longitude": "-0.1278",
                "country": "GB",
                "indoor": 0,
            },
            "timestamp": "2024-01-15T12:00:00",
            "sensordatavalues": [
                {"id": 1, "value": "25.5", "value_type": "P2"},  # PM2.5
                {"id": 2, "value": "35.2", "value_type": "P1"},  # PM10
            ],
        },
        {
            "sensor": {"id": 12346, "sensor_type": {"id": 14, "name": "SDS011"}},
            "location": {
                "id": 6790,
                "latitude": "52.52",
                "longitude": "13.405",
                "country": "DE",
                "indoor": 1,
            },
            "timestamp": "2024-01-15T12:00:00",
            "sensordatavalues": [
                {"id": 3, "value": "18.3", "value_type": "P2"},
                {"id": 4, "value": "28.7", "value_type": "P1"},
            ],
        },
    ]


@pytest.fixture
def mock_bme280_response():
    """Mock response for BME280 temperature/humidity sensors."""
    return [
        {
            "sensor": {"id": 54321, "sensor_type": {"id": 17, "name": "BME280"}},
            "location": {
                "id": 9876,
                "latitude": "48.8566",
                "longitude": "2.3522",
                "country": "FR",
                "indoor": 0,
            },
            "timestamp": "2024-01-15T12:00:00",
            "sensordatavalues": [
                {"id": 5, "value": "15.5", "value_type": "temperature"},
                {"id": 6, "value": "65.2", "value_type": "humidity"},
                {"id": 7, "value": "101325", "value_type": "pressure"},
            ],
        },
    ]


@pytest.fixture
def mock_sensor_archive_csv():
    """Mock CSV content from the per-sensor archive."""
    return """sensor_id;sensor_type;location;lat;lon;timestamp;P1;P2
12345;SDS011;GB;51.5074;-0.1278;2024-01-15T10:00:00;32.5;22.3
12345;SDS011;GB;51.5074;-0.1278;2024-01-15T11:00:00;30.1;20.5
"""


@pytest.fixture
def mock_bme280_archive_csv():
    """Mock CSV content for BME280 sensors from the archive."""
    return """sensor_id;sensor_type;location;lat;lon;timestamp;temperature;humidity;pressure
54321;BME280;FR;48.8566;2.3522;2024-01-15T10:00:00;15.5;65.2;101325
54321;BME280;FR;48.8566;2.3522;2024-01-15T11:00:00;16.0;63.8;101300
"""


# ============================================================================
# Constants Tests
# ============================================================================


class TestConstants:
    """Test module constants."""

    def test_api_base_urls(self):
        """Test API base URLs are correct."""
        assert DATA_API_BASE == "https://data.sensor.community"
        assert ARCHIVE_BASE == "https://archive.sensor.community"

    def test_user_agent_format(self):
        """Test User-Agent header is properly formatted."""
        assert "aeolus" in USER_AGENT.lower()
        assert "http" in USER_AGENT

    def test_sensor_type_map_has_common_sensors(self):
        """Test sensor type map includes common sensor types."""
        assert "SDS011" in SENSOR_TYPE_MAP
        assert "BME280" in SENSOR_TYPE_MAP
        assert "PMS5003" in SENSOR_TYPE_MAP
        assert "DHT22" in SENSOR_TYPE_MAP

    def test_sensor_type_map_measurands(self):
        """Test sensor types map to correct measurands."""
        assert "PM2.5" in SENSOR_TYPE_MAP["SDS011"]
        assert "PM10" in SENSOR_TYPE_MAP["SDS011"]
        assert "Temperature" in SENSOR_TYPE_MAP["BME280"]
        assert "Humidity" in SENSOR_TYPE_MAP["BME280"]
        assert "Pressure" in SENSOR_TYPE_MAP["BME280"]

    def test_value_name_map(self):
        """Test value name mapping is correct."""
        assert VALUE_NAME_MAP["P1"] == "PM10"
        assert VALUE_NAME_MAP["P2"] == "PM2.5"
        assert VALUE_NAME_MAP["temperature"] == "Temperature"
        assert VALUE_NAME_MAP["humidity"] == "Humidity"

    def test_units_map(self):
        """Test units mapping is correct."""
        assert UNITS_MAP["PM2.5"] == "ug/m3"
        assert UNITS_MAP["PM10"] == "ug/m3"
        assert UNITS_MAP["Temperature"] == "C"
        assert UNITS_MAP["Humidity"] == "%"
        assert UNITS_MAP["Pressure"] == "Pa"


# ============================================================================
# Rate Limiter Tests
# ============================================================================


class TestRateLimiter:
    """Test the rate limiter class."""

    def test_rate_limiter_init(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(max_requests=5, period=30.0, min_delay=0.5)
        assert limiter.max_requests == 5
        assert limiter.period == 30.0
        assert limiter.min_delay == 0.5
        assert limiter.request_times == []

    def test_rate_limiter_default_values(self):
        """Test rate limiter default values."""
        limiter = RateLimiter()
        assert limiter.max_requests == DEFAULT_RATE_LIMIT_REQUESTS
        assert limiter.period == DEFAULT_RATE_LIMIT_PERIOD
        assert limiter.min_delay == DEFAULT_REQUEST_DELAY

    def test_rate_limiter_records_requests(self):
        """Test that rate limiter records request times."""
        limiter = RateLimiter(max_requests=10, period=60.0, min_delay=0.0)

        initial_count = len(limiter.request_times)
        limiter.wait_if_needed()

        assert len(limiter.request_times) == initial_count + 1

    def test_rate_limiter_enforces_min_delay(self):
        """Test that rate limiter enforces minimum delay between requests."""
        limiter = RateLimiter(max_requests=100, period=60.0, min_delay=0.1)

        start = time.time()
        limiter.wait_if_needed()
        limiter.wait_if_needed()
        elapsed = time.time() - start

        assert elapsed >= 0.1

    def test_rate_limiter_cleans_old_requests(self):
        """Test that rate limiter cleans up old request times."""
        limiter = RateLimiter(max_requests=10, period=0.1, min_delay=0.0)

        limiter.request_times = [time.time() - 1.0]

        limiter.wait_if_needed()

        assert len(limiter.request_times) == 1


class TestSetRateLimiting:
    """Test the set_rate_limiting function."""

    def test_disable_rate_limiting(self):
        """Test disabling rate limiting."""
        from aeolus.sources import sensor_community

        original = sensor_community._rate_limiter
        try:
            set_rate_limiting(enabled=False)
            assert sensor_community._rate_limiter is None
        finally:
            sensor_community._rate_limiter = original

    def test_enable_rate_limiting(self):
        """Test enabling rate limiting with custom values."""
        from aeolus.sources import sensor_community

        original = sensor_community._rate_limiter
        try:
            set_rate_limiting(enabled=True, max_requests=5, period=30.0, min_delay=2.0)
            assert sensor_community._rate_limiter is not None
            assert sensor_community._rate_limiter.max_requests == 5
            assert sensor_community._rate_limiter.period == 30.0
            assert sensor_community._rate_limiter.min_delay == 2.0
        finally:
            sensor_community._rate_limiter = original

    def test_re_enable_with_defaults(self):
        """Test re-enabling rate limiting with defaults."""
        from aeolus.sources import sensor_community

        original = sensor_community._rate_limiter
        try:
            set_rate_limiting(enabled=False)
            set_rate_limiting(enabled=True)
            assert sensor_community._rate_limiter is not None
            assert (
                sensor_community._rate_limiter.max_requests
                == DEFAULT_RATE_LIMIT_REQUESTS
            )
        finally:
            sensor_community._rate_limiter = original


# ============================================================================
# HTTP Client Tests
# ============================================================================


class TestMakeRequest:
    """Test the _make_request function."""

    @patch("aeolus.sources.sensor_community.requests.get")
    @patch("aeolus.sources.sensor_community._apply_rate_limit")
    def test_make_request_success(self, mock_rate_limit, mock_get):
        """Test successful request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = _make_request("https://example.com/test")

        assert result == mock_response
        mock_rate_limit.assert_called_once()
        mock_get.assert_called_once()

    @patch("aeolus.sources.sensor_community.requests.get")
    @patch("aeolus.sources.sensor_community._apply_rate_limit")
    def test_make_request_includes_user_agent(self, mock_rate_limit, mock_get):
        """Test that request includes User-Agent header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        _make_request("https://example.com/test")

        call_kwargs = mock_get.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["User-Agent"] == USER_AGENT

    @patch("aeolus.sources.sensor_community.requests.get")
    @patch("aeolus.sources.sensor_community._apply_rate_limit")
    def test_make_request_timeout(self, mock_rate_limit, mock_get):
        """Test request timeout handling."""
        import requests

        mock_get.side_effect = requests.exceptions.Timeout()

        result = _make_request("https://example.com/test")

        assert result is None

    @patch("aeolus.sources.sensor_community.requests.get")
    @patch("aeolus.sources.sensor_community._apply_rate_limit")
    def test_make_request_http_error(self, mock_rate_limit, mock_get):
        """Test HTTP error handling."""
        import requests

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        result = _make_request("https://example.com/test")

        assert result is None

    @patch("aeolus.sources.sensor_community.requests.get")
    @patch("aeolus.sources.sensor_community._apply_rate_limit")
    def test_make_request_404_silent(self, mock_rate_limit, mock_get):
        """Test that 404 errors don't warn (expected for missing sensors)."""
        import requests

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        result = _make_request("https://example.com/test")

        assert result is None


# ============================================================================
# Metadata Fetcher Tests
# ============================================================================


class TestFetchMetadata:
    """Test the fetch_sensor_community_metadata function."""

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_metadata_basic(self, mock_request, mock_realtime_response):
        """Test basic metadata fetching."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_realtime_response
        mock_request.return_value = mock_response

        df = fetch_sensor_community_metadata(sensor_type="SDS011", country="GB")

        assert not df.empty
        assert "site_code" in df.columns
        assert "latitude" in df.columns
        assert "longitude" in df.columns
        assert "sensor_type" in df.columns
        assert "source_network" in df.columns
        assert df["source_network"].iloc[0] == "Sensor.Community"

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_metadata_caches_sensor_types(
        self, mock_request, mock_realtime_response
    ):
        """Test that metadata fetching populates sensor type cache."""
        from aeolus.sources import sensor_community

        mock_response = MagicMock()
        mock_response.json.return_value = mock_realtime_response
        mock_request.return_value = mock_response

        fetch_sensor_community_metadata(sensor_type="SDS011")

        # Check cache was populated
        assert "12345" in sensor_community._sensor_type_cache
        assert sensor_community._sensor_type_cache["12345"] == "SDS011"

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_metadata_with_filters(self, mock_request, mock_realtime_response):
        """Test metadata fetching with various filters."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_realtime_response
        mock_request.return_value = mock_response

        fetch_sensor_community_metadata(
            sensor_type=["SDS011", "BME280"],
            country=["GB", "DE"],
        )

        call_url = mock_request.call_args[0][0]
        assert "type=SDS011,BME280" in call_url
        assert "country=GB,DE" in call_url

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_metadata_area_filter(self, mock_request, mock_realtime_response):
        """Test metadata fetching with area filter."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_realtime_response
        mock_request.return_value = mock_response

        fetch_sensor_community_metadata(area=(51.5, -0.1, 50))

        call_url = mock_request.call_args[0][0]
        assert "area=51.5,-0.1,50" in call_url

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_metadata_box_filter(self, mock_request, mock_realtime_response):
        """Test metadata fetching with bounding box filter."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_realtime_response
        mock_request.return_value = mock_response

        fetch_sensor_community_metadata(box=(51.0, -0.5, 52.0, 0.5))

        call_url = mock_request.call_args[0][0]
        assert "box=51.0,-0.5,52.0,0.5" in call_url

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_metadata_empty_response(self, mock_request):
        """Test handling of empty response."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_request.return_value = mock_response

        df = fetch_sensor_community_metadata(country="XX")

        assert df.empty

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_metadata_request_failure(self, mock_request):
        """Test handling of request failure."""
        mock_request.return_value = None

        df = fetch_sensor_community_metadata(country="GB")

        assert df.empty


# ============================================================================
# Real-time Data Fetcher Tests
# ============================================================================


class TestFetchRealtime:
    """Test the fetch_sensor_community_realtime function."""

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_realtime_basic(self, mock_request, mock_realtime_response):
        """Test basic real-time data fetching."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_realtime_response
        mock_request.return_value = mock_response

        df = fetch_sensor_community_realtime(sensor_type="SDS011", country="GB")

        assert not df.empty
        assert "site_code" in df.columns
        assert "date_time" in df.columns
        assert "measurand" in df.columns
        assert "value" in df.columns
        assert "units" in df.columns
        assert "source_network" in df.columns
        assert "ratification" in df.columns

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_realtime_pm_values(self, mock_request, mock_realtime_response):
        """Test that PM values are correctly parsed."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_realtime_response
        mock_request.return_value = mock_response

        df = fetch_sensor_community_realtime(sensor_type="SDS011")

        pm25 = df[df["measurand"] == "PM2.5"]
        pm10 = df[df["measurand"] == "PM10"]

        assert not pm25.empty
        assert not pm10.empty
        assert pm25["units"].iloc[0] == "ug/m3"
        assert pm10["units"].iloc[0] == "ug/m3"

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_realtime_bme280(self, mock_request, mock_bme280_response):
        """Test fetching BME280 temperature/humidity data."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_bme280_response
        mock_request.return_value = mock_response

        df = fetch_sensor_community_realtime(sensor_type="BME280")

        temp = df[df["measurand"] == "Temperature"]
        humidity = df[df["measurand"] == "Humidity"]
        pressure = df[df["measurand"] == "Pressure"]

        assert not temp.empty
        assert not humidity.empty
        assert not pressure.empty
        assert temp["units"].iloc[0] == "C"
        assert humidity["units"].iloc[0] == "%"
        assert pressure["units"].iloc[0] == "Pa"

    def test_fetch_realtime_invalid_averaging(self):
        """Test that invalid averaging period raises error."""
        with pytest.raises(ValueError, match="Invalid averaging"):
            fetch_sensor_community_realtime(averaging="invalid")

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_realtime_source_network(self, mock_request, mock_realtime_response):
        """Test that source_network is correctly set."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_realtime_response
        mock_request.return_value = mock_response

        df = fetch_sensor_community_realtime()

        assert all(df["source_network"] == "Sensor.Community")

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_realtime_ratification(self, mock_request, mock_realtime_response):
        """Test that ratification is set to Unvalidated."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_realtime_response
        mock_request.return_value = mock_response

        df = fetch_sensor_community_realtime()

        assert all(df["ratification"] == "Unvalidated")


# ============================================================================
# Sensor Type Lookup Tests
# ============================================================================


class TestGetSensorTypesForSites:
    """Test the _get_sensor_types_for_sites function."""

    def test_uses_cache_when_available(self):
        """Test that cached sensor types are used."""
        from aeolus.sources import sensor_community

        sensor_community._sensor_type_cache["12345"] = "SDS011"
        sensor_community._sensor_type_cache["12346"] = "BME280"

        result = _get_sensor_types_for_sites(["12345", "12346"])

        assert result["12345"] == "SDS011"
        assert result["12346"] == "BME280"

    @patch("aeolus.sources.sensor_community._make_request")
    def test_queries_api_for_missing(self, mock_request, mock_realtime_response):
        """Test that API is queried for sensors not in cache."""
        from aeolus.sources import sensor_community

        mock_response = MagicMock()
        mock_response.json.return_value = mock_realtime_response
        mock_request.return_value = mock_response

        # Only 12345 is in cache
        sensor_community._sensor_type_cache["12345"] = "SDS011"

        result = _get_sensor_types_for_sites(["12345", "12346"])

        assert result["12345"] == "SDS011"
        # 12346 should be looked up from API response
        assert "12346" in result


# ============================================================================
# Historical Data Fetcher Tests
# ============================================================================


class TestFetchData:
    """Test the fetch_sensor_community_data function."""

    def test_fetch_data_empty_sites_returns_empty(self):
        """Test that empty sites list returns empty DataFrame."""
        df = fetch_sensor_community_data(
            sites=[],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        assert df.empty

    @patch("aeolus.sources.sensor_community._fetch_sensor_archive")
    @patch("aeolus.sources.sensor_community._get_sensor_types_for_sites")
    def test_fetch_data_calls_archive_per_sensor(self, mock_get_types, mock_archive):
        """Test that archive is fetched for each sensor."""
        mock_get_types.return_value = {"12345": "SDS011", "12346": "SDS011"}
        mock_archive.return_value = _empty_dataframe()

        fetch_sensor_community_data(
            sites=["12345", "12346"],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        # Should call archive for each sensor
        assert mock_archive.call_count == 2

    @patch("aeolus.sources.sensor_community._fetch_sensor_archive")
    @patch("aeolus.sources.sensor_community._get_sensor_types_for_sites")
    def test_fetch_data_standard_interface(self, mock_get_types, mock_archive):
        """Test that fetch_data matches the standard interface (sites, start, end)."""
        mock_get_types.return_value = {"12345": "SDS011"}
        mock_archive.return_value = pd.DataFrame(
            {
                "site_code": ["12345"],
                "date_time": [datetime(2024, 1, 15, 10, 0)],
                "measurand": ["PM2.5"],
                "value": [22.3],
                "units": ["ug/m3"],
                "source_network": ["Sensor.Community"],
                "ratification": ["Unvalidated"],
                "created_at": [datetime.now()],
            }
        )

        df = fetch_sensor_community_data(
            sites=["12345"],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 15),
        )

        assert not df.empty
        assert "site_code" in df.columns
        assert df["site_code"].iloc[0] == "12345"

    @patch("aeolus.sources.sensor_community._fetch_sensor_archive")
    @patch("aeolus.sources.sensor_community._get_sensor_types_for_sites")
    def test_fetch_data_multiple_days(self, mock_get_types, mock_archive):
        """Test fetching data across multiple days."""
        mock_get_types.return_value = {"12345": "SDS011"}
        mock_archive.return_value = _empty_dataframe()

        fetch_sensor_community_data(
            sites=["12345"],
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 17),
        )

        # Should call archive for each day (3 days)
        assert mock_archive.call_count == 3


class TestFetchSensorArchive:
    """Test the _fetch_sensor_archive function."""

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_sensor_archive_url_format(self, mock_request):
        """Test that per-sensor archive URL is correctly formatted."""
        mock_response = MagicMock()
        mock_response.text = ""
        mock_request.return_value = mock_response

        _fetch_sensor_archive(datetime(2024, 1, 15), "SDS011", "12345")

        expected_url = f"{ARCHIVE_BASE}/2024-01-15/2024-01-15_sds011_sensor_12345.csv"
        mock_request.assert_called_once_with(expected_url, timeout=60)

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_sensor_archive_parses_csv(
        self, mock_request, mock_sensor_archive_csv
    ):
        """Test that archive CSV is correctly parsed."""
        mock_response = MagicMock()
        mock_response.text = mock_sensor_archive_csv
        mock_request.return_value = mock_response

        df = _fetch_sensor_archive(datetime(2024, 1, 15), "SDS011", "12345")

        assert not df.empty
        assert "site_code" in df.columns
        assert "measurand" in df.columns
        assert "value" in df.columns

    @patch("aeolus.sources.sensor_community._make_request")
    def test_fetch_sensor_archive_request_failure(self, mock_request):
        """Test handling of request failure (e.g., sensor doesn't exist)."""
        mock_request.return_value = None

        df = _fetch_sensor_archive(datetime(2024, 1, 15), "SDS011", "99999")

        assert df.empty


class TestNormalizeSensorData:
    """Test the _normalize_sensor_data function."""

    def test_normalize_sds011_data(self):
        """Test normalization of SDS011 PM data."""
        df = pd.DataFrame(
            {
                "sensor_id": [12345, 12345],
                "timestamp": ["2024-01-15T10:00:00", "2024-01-15T11:00:00"],
                "P1": [32.5, 30.1],
                "P2": [22.3, 20.5],
            }
        )

        result = _normalize_sensor_data(df, "SDS011", "12345")

        assert "site_code" in result.columns
        assert "measurand" in result.columns
        assert set(result["measurand"].unique()) == {"PM10", "PM2.5"}
        assert all(result["source_network"] == "Sensor.Community")
        assert all(result["ratification"] == "Unvalidated")
        assert all(result["site_code"] == "12345")

    def test_normalize_bme280_data(self):
        """Test normalization of BME280 environmental data."""
        df = pd.DataFrame(
            {
                "sensor_id": [54321],
                "timestamp": ["2024-01-15T10:00:00"],
                "temperature": [15.5],
                "humidity": [65.2],
                "pressure": [101325],
            }
        )

        result = _normalize_sensor_data(df, "BME280", "54321")

        measurands = set(result["measurand"].unique())
        assert "Temperature" in measurands
        assert "Humidity" in measurands
        assert "Pressure" in measurands

    def test_normalize_handles_missing_values(self):
        """Test that missing values are handled correctly."""
        df = pd.DataFrame(
            {
                "sensor_id": [12345],
                "timestamp": ["2024-01-15T10:00:00"],
                "P1": [None],
                "P2": [22.3],
            }
        )

        result = _normalize_sensor_data(df, "SDS011", "12345")

        assert len(result) == 1
        assert result["measurand"].iloc[0] == "PM2.5"


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
        """Test that SENSOR_COMMUNITY source is registered."""
        assert "SENSOR_COMMUNITY" in _SOURCES

    def test_source_has_required_fields(self):
        """Test that source has all required fields."""
        source = _SOURCES["SENSOR_COMMUNITY"]

        assert "type" in source
        assert "name" in source
        assert "fetch_metadata" in source
        assert "fetch_data" in source

    def test_source_type_is_network(self):
        """Test that source type is 'network'."""
        source = _SOURCES["SENSOR_COMMUNITY"]
        assert source["type"] == "network"

    def test_source_does_not_require_api_key(self):
        """Test that source does not require API key."""
        source = _SOURCES["SENSOR_COMMUNITY"]
        assert source.get("requires_api_key", False) is False


# ============================================================================
# Integration with aeolus.download Tests
# ============================================================================


class TestAeolusDownloadIntegration:
    """Test integration with the main aeolus.download function."""

    @patch("aeolus.sources.sensor_community._fetch_sensor_archive")
    @patch("aeolus.sources.sensor_community._get_sensor_types_for_sites")
    def test_download_via_aeolus_api(self, mock_get_types, mock_archive):
        """Test that aeolus.download works with SENSOR_COMMUNITY."""
        import aeolus

        mock_get_types.return_value = {"12345": "SDS011"}
        mock_archive.return_value = pd.DataFrame(
            {
                "site_code": ["12345"],
                "date_time": [datetime(2024, 1, 15, 10, 0)],
                "measurand": ["PM2.5"],
                "value": [22.3],
                "units": ["ug/m3"],
                "source_network": ["Sensor.Community"],
                "ratification": ["Unvalidated"],
                "created_at": [datetime.now()],
            }
        )

        df = aeolus.download(
            "SENSOR_COMMUNITY",
            ["12345"],
            datetime(2024, 1, 15),
            datetime(2024, 1, 15),
        )

        assert not df.empty
        assert df["source_network"].iloc[0] == "Sensor.Community"

    @patch("aeolus.sources.sensor_community._fetch_sensor_archive")
    @patch("aeolus.sources.sensor_community._get_sensor_types_for_sites")
    def test_download_via_networks_api(self, mock_get_types, mock_archive):
        """Test that aeolus.networks.download works with SENSOR_COMMUNITY."""
        import aeolus.networks

        mock_get_types.return_value = {"12345": "SDS011"}
        mock_archive.return_value = pd.DataFrame(
            {
                "site_code": ["12345"],
                "date_time": [datetime(2024, 1, 15, 10, 0)],
                "measurand": ["PM2.5"],
                "value": [22.3],
                "units": ["ug/m3"],
                "source_network": ["Sensor.Community"],
                "ratification": ["Unvalidated"],
                "created_at": [datetime.now()],
            }
        )

        df = aeolus.networks.download(
            "SENSOR_COMMUNITY",
            ["12345"],
            datetime(2024, 1, 15),
            datetime(2024, 1, 15),
        )

        assert not df.empty
