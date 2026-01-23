"""
Tests for OpenAQ API fetcher functions.

Tests the low-level API calls, pagination, sensor fetching, and
data retrieval with mocked HTTP responses.
"""

from datetime import datetime

import pytest
import responses

from aeolus.sources.openaq import (
    OPENAQ_API_BASE,
    _call_openaq_api,
    _get_sensors_for_location,
    _paginate_openaq,
    fetch_openaq_data,
)

# ============================================================================
# Fixtures for Mock API Responses
# ============================================================================


@pytest.fixture
def mock_sensors_response():
    """Mock response from /locations/{id}/sensors endpoint."""
    return {
        "meta": {
            "name": "openaq-api",
            "page": 1,
            "limit": 100,
            "found": 3,
        },
        "results": [
            {
                "id": 7117,
                "name": "PM2.5",
                "parameter": {
                    "id": 2,
                    "name": "pm25",
                    "units": "µg/m³",
                    "displayName": "PM2.5",
                },
            },
            {
                "id": 7118,
                "name": "NO2",
                "parameter": {
                    "id": 19,
                    "name": "no2",
                    "units": "µg/m³",
                    "displayName": "NO₂",
                },
            },
            {
                "id": 7119,
                "name": "O3",
                "parameter": {
                    "id": 5,
                    "name": "o3",
                    "units": "µg/m³",
                    "displayName": "O₃",
                },
            },
        ],
    }


@pytest.fixture
def mock_measurements_response():
    """Mock response from /sensors/{id}/hours endpoint."""
    return {
        "meta": {
            "name": "openaq-api",
            "page": 1,
            "limit": 100,
            "found": 3,
        },
        "results": [
            {
                "value": 23.5,
                "period": {
                    "label": "hour",
                    "interval": "1h",
                    "datetimeFrom": {
                        "utc": "2024-01-01T00:00:00Z",
                        "local": "2024-01-01T00:00:00+00:00",
                    },
                    "datetimeTo": {
                        "utc": "2024-01-01T01:00:00Z",
                        "local": "2024-01-01T01:00:00+00:00",
                    },
                },
                "flagInfo": {"hasFlags": False},
            },
            {
                "value": 24.1,
                "period": {
                    "label": "hour",
                    "interval": "1h",
                    "datetimeFrom": {
                        "utc": "2024-01-01T01:00:00Z",
                        "local": "2024-01-01T01:00:00+00:00",
                    },
                    "datetimeTo": {
                        "utc": "2024-01-01T02:00:00Z",
                        "local": "2024-01-01T02:00:00+00:00",
                    },
                },
                "flagInfo": {"hasFlags": False},
            },
            {
                "value": 22.8,
                "period": {
                    "label": "hour",
                    "interval": "1h",
                    "datetimeFrom": {
                        "utc": "2024-01-01T02:00:00Z",
                        "local": "2024-01-01T02:00:00+00:00",
                    },
                    "datetimeTo": {
                        "utc": "2024-01-01T03:00:00Z",
                        "local": "2024-01-01T03:00:00+00:00",
                    },
                },
                "flagInfo": {"hasFlags": False},
            },
        ],
    }


@pytest.fixture
def mock_empty_response():
    """Mock empty response (no data available)."""
    return {
        "meta": {
            "name": "openaq-api",
            "page": 1,
            "limit": 100,
            "found": 0,
        },
        "results": [],
    }


@pytest.fixture
def mock_paginated_response_page1():
    """Mock first page of paginated response."""
    return {
        "meta": {
            "name": "openaq-api",
            "page": 1,
            "limit": 2,
            "found": 5,
        },
        "results": [
            {"value": 1.0, "period": {"datetimeTo": {"utc": "2024-01-01T01:00:00Z"}}},
            {"value": 2.0, "period": {"datetimeTo": {"utc": "2024-01-01T02:00:00Z"}}},
        ],
    }


@pytest.fixture
def mock_paginated_response_page2():
    """Mock second page of paginated response."""
    return {
        "meta": {
            "name": "openaq-api",
            "page": 2,
            "limit": 2,
            "found": 5,
        },
        "results": [
            {"value": 3.0, "period": {"datetimeTo": {"utc": "2024-01-01T03:00:00Z"}}},
            {"value": 4.0, "period": {"datetimeTo": {"utc": "2024-01-01T04:00:00Z"}}},
        ],
    }


@pytest.fixture
def mock_paginated_response_page3():
    """Mock third (last) page of paginated response."""
    return {
        "meta": {
            "name": "openaq-api",
            "page": 3,
            "limit": 2,
            "found": 5,
        },
        "results": [
            {"value": 5.0, "period": {"datetimeTo": {"utc": "2024-01-01T05:00:00Z"}}},
        ],
    }


# ============================================================================
# Tests for _call_openaq_api()
# ============================================================================


@responses.activate
def test_call_openaq_api_success(mock_sensors_response, monkeypatch):
    """Test successful API call."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    # Mock the HTTP response
    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/locations/2708/sensors",
        json=mock_sensors_response,
        status=200,
    )

    result = _call_openaq_api("locations/2708/sensors", {})

    assert result == mock_sensors_response
    assert len(responses.calls) == 1
    assert "X-API-Key" in responses.calls[0].request.headers


@responses.activate
def test_call_openaq_api_includes_api_key(monkeypatch):
    """Test that API key is included in request headers."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/test",
        json={"results": []},
        status=200,
    )

    _call_openaq_api("test", {})

    assert responses.calls[0].request.headers["X-API-Key"] == "test_key_123"


def test_call_openaq_api_raises_without_api_key(monkeypatch):
    """Test that missing API key raises ValueError."""
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OpenAQ API key required"):
        _call_openaq_api("test", {})


@responses.activate
def test_call_openaq_api_handles_404(monkeypatch):
    """Test that 404 responses are handled gracefully."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/locations/999999/sensors",
        status=404,
    )

    result = _call_openaq_api("locations/999999/sensors", {})

    # Should return empty results structure
    assert result["results"] == []
    assert result["meta"]["found"] == 0


@responses.activate
def test_call_openaq_api_handles_rate_limit(monkeypatch):
    """Test that 429 rate limit responses raise appropriate error."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/test",
        status=429,
    )

    import requests

    with pytest.raises(requests.HTTPError, match="rate limit"):
        _call_openaq_api("test", {})


@responses.activate
def test_call_openaq_api_includes_query_params(monkeypatch):
    """Test that query parameters are passed correctly."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/test",
        json={"results": []},
        status=200,
    )

    params = {"page": 2, "limit": 50, "date_from": "2024-01-01"}
    _call_openaq_api("test", params)

    # Check query string
    request = responses.calls[0].request
    assert "page=2" in request.url
    assert "limit=50" in request.url
    assert "date_from=2024-01-01" in request.url


# ============================================================================
# Tests for _get_sensors_for_location()
# ============================================================================


@responses.activate
def test_get_sensors_for_location_success(mock_sensors_response, monkeypatch):
    """Test fetching sensors for a location."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/locations/2708/sensors",
        json=mock_sensors_response,
        status=200,
    )

    sensors = _get_sensors_for_location(2708)

    assert len(sensors) == 3
    assert sensors[0]["id"] == 7117
    assert sensors[0]["parameter"]["name"] == "pm25"


@responses.activate
def test_get_sensors_for_location_empty_result(mock_empty_response, monkeypatch):
    """Test fetching sensors when none are available."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/locations/9999/sensors",
        json=mock_empty_response,
        status=200,
    )

    sensors = _get_sensors_for_location(9999)

    assert sensors == []


@responses.activate
def test_get_sensors_for_location_handles_errors(monkeypatch):
    """Test that sensor fetching handles API errors gracefully."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/locations/2708/sensors",
        status=500,
    )

    sensors = _get_sensors_for_location(2708)

    # Should return empty list on error
    assert sensors == []


# ============================================================================
# Tests for _paginate_openaq()
# ============================================================================


@responses.activate
def test_paginate_openaq_single_page(mock_measurements_response, monkeypatch):
    """Test pagination with single page of results."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/sensors/7117/hours",
        json=mock_measurements_response,
        status=200,
    )

    results = list(_paginate_openaq("sensors/7117/hours", {}))

    assert len(results) == 3
    assert results[0]["value"] == 23.5


@responses.activate
def test_paginate_openaq_multiple_pages(
    mock_paginated_response_page1,
    mock_paginated_response_page2,
    mock_paginated_response_page3,
    monkeypatch,
):
    """Test pagination across multiple pages."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    # Mock three pages of results with match parameters
    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/test",
        json=mock_paginated_response_page1,
        status=200,
        match=[responses.matchers.query_param_matcher({"page": "1", "limit": "100"})],
    )
    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/test",
        json=mock_paginated_response_page2,
        status=200,
        match=[responses.matchers.query_param_matcher({"page": "2", "limit": "100"})],
    )
    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/test",
        json=mock_paginated_response_page3,
        status=200,
        match=[responses.matchers.query_param_matcher({"page": "3", "limit": "100"})],
    )

    results = list(_paginate_openaq("test", {}))

    # Should fetch all pages
    assert len(results) == 5
    assert results[0]["value"] == 1.0
    assert results[4]["value"] == 5.0
    assert len(responses.calls) == 3


@responses.activate
def test_paginate_openaq_empty_results(mock_empty_response, monkeypatch):
    """Test pagination with no results."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/test",
        json=mock_empty_response,
        status=200,
    )

    results = list(_paginate_openaq("test", {}))

    assert results == []


@responses.activate
def test_paginate_openaq_stops_on_error(
    mock_paginated_response_page1,
    monkeypatch,
):
    """Test that pagination stops gracefully on error."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    # First page succeeds
    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/test",
        json=mock_paginated_response_page1,
        status=200,
    )
    # Second page fails
    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/test",
        status=500,
    )

    results = list(_paginate_openaq("test", {}))

    # Should return results from first page only
    assert len(results) == 2


@responses.activate
def test_paginate_openaq_handles_string_found(monkeypatch):
    """Test that pagination handles 'found' as string instead of int."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    response_with_string_found = {
        "meta": {"found": "1", "page": 1, "limit": 100},
        "results": [{"value": 1.0}],
    }

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/test",
        json=response_with_string_found,
        status=200,
    )

    results = list(_paginate_openaq("test", {}))

    # Should handle string conversion gracefully
    assert len(results) == 1


# ============================================================================
# Tests for fetch_openaq_data()
# ============================================================================


@responses.activate
def test_fetch_openaq_data_success(
    mock_sensors_response,
    mock_measurements_response,
    monkeypatch,
):
    """Test successful data fetching from OpenAQ."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    # Mock sensors endpoint
    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/locations/2708/sensors",
        json=mock_sensors_response,
        status=200,
    )

    # Mock measurements endpoint for each sensor
    for sensor_id in [7117, 7118, 7119]:
        responses.add(
            responses.GET,
            f"{OPENAQ_API_BASE}/sensors/{sensor_id}/hours",
            json=mock_measurements_response,
            status=200,
        )

    result = fetch_openaq_data(
        sites=["2708"],
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 2),
    )

    # Should fetch data from all 3 sensors
    assert not result.empty
    assert len(result) == 9  # 3 sensors × 3 measurements each
    assert "site_code" in result.columns
    assert "measurand" in result.columns
    assert result["site_code"].iloc[0] == "2708"


@responses.activate
def test_fetch_openaq_data_multiple_sites(
    mock_sensors_response,
    mock_measurements_response,
    monkeypatch,
):
    """Test fetching data from multiple locations."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    # Mock sensors for two locations
    for location_id in [2708, 3272]:
        responses.add(
            responses.GET,
            f"{OPENAQ_API_BASE}/locations/{location_id}/sensors",
            json=mock_sensors_response,
            status=200,
        )

    # Mock measurements for all sensors
    for _ in range(6):  # 2 locations × 3 sensors each
        responses.add(
            responses.GET,
            f"{OPENAQ_API_BASE}/sensors/7117/hours",
            json=mock_measurements_response,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{OPENAQ_API_BASE}/sensors/7118/hours",
            json=mock_measurements_response,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{OPENAQ_API_BASE}/sensors/7119/hours",
            json=mock_measurements_response,
            status=200,
        )

    result = fetch_openaq_data(
        sites=["2708", "3272"],
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 2),
    )

    assert not result.empty
    # Should have data from both locations
    assert set(result["site_code"].unique()) == {"2708", "3272"}


@responses.activate
def test_fetch_openaq_data_no_sensors(mock_empty_response, monkeypatch):
    """Test fetching data when location has no sensors."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/locations/9999/sensors",
        json=mock_empty_response,
        status=200,
    )

    result = fetch_openaq_data(
        sites=["9999"],
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 2),
    )

    # Should return empty DataFrame with correct schema
    assert result.empty
    assert "site_code" in result.columns
    assert "date_time" in result.columns


@responses.activate
def test_fetch_openaq_data_no_measurements(
    mock_sensors_response,
    mock_empty_response,
    monkeypatch,
):
    """Test fetching data when sensors have no measurements."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/locations/2708/sensors",
        json=mock_sensors_response,
        status=200,
    )

    # All sensors return empty results
    for _ in range(3):
        responses.add(
            responses.GET,
            f"{OPENAQ_API_BASE}/sensors/7117/hours",
            json=mock_empty_response,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{OPENAQ_API_BASE}/sensors/7118/hours",
            json=mock_empty_response,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{OPENAQ_API_BASE}/sensors/7119/hours",
            json=mock_empty_response,
            status=200,
        )

    result = fetch_openaq_data(
        sites=["2708"],
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 2),
    )

    assert result.empty


@responses.activate
def test_fetch_openaq_data_skips_null_values(mock_sensors_response, monkeypatch):
    """Test that null values are filtered out."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/locations/2708/sensors",
        json=mock_sensors_response,
        status=200,
    )

    # Response with null value
    measurements_with_null = {
        "meta": {"found": 2},
        "results": [
            {
                "value": None,
                "period": {"datetimeTo": {"utc": "2024-01-01T01:00:00Z"}},
            },
            {
                "value": 23.5,
                "period": {"datetimeTo": {"utc": "2024-01-01T02:00:00Z"}},
            },
        ],
    }

    for _ in range(3):
        responses.add(
            responses.GET,
            f"{OPENAQ_API_BASE}/sensors/7117/hours",
            json=measurements_with_null,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{OPENAQ_API_BASE}/sensors/7118/hours",
            json=measurements_with_null,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{OPENAQ_API_BASE}/sensors/7119/hours",
            json=measurements_with_null,
            status=200,
        )

    result = fetch_openaq_data(
        sites=["2708"],
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 2),
    )

    # Should only have non-null values
    assert len(result) == 3  # 3 sensors, 1 non-null measurement each
    assert result["value"].notna().all()


@responses.activate
def test_fetch_openaq_data_handles_sensor_fetch_error(monkeypatch):
    """Test that sensor fetch errors are handled gracefully."""
    monkeypatch.setenv("OPENAQ_API_KEY", "test_key_123")

    responses.add(
        responses.GET,
        f"{OPENAQ_API_BASE}/locations/2708/sensors",
        status=500,
    )

    result = fetch_openaq_data(
        sites=["2708"],
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 2),
    )

    # Should return empty DataFrame
    assert result.empty
