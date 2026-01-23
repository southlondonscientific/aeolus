"""
Tests for OpenAQ data normalization pipeline.

Tests the transformation of raw OpenAQ API responses into
the standardized Aeolus schema.
"""

import pandas as pd
import pytest

from aeolus.sources.openaq import (
    PARAMETER_MAP,
    create_openaq_normalizer,
)

# ============================================================================
# Test Data - Raw OpenAQ API Response Format
# ============================================================================


@pytest.fixture
def raw_openaq_hourly_data():
    """
    Sample raw data from OpenAQ /sensors/{id}/hours endpoint.

    This mimics the structure we extract from the API after fetching
    measurements and adding location_id.
    """
    return pd.DataFrame(
        [
            {
                "locations_id": 2708,
                "value": 23.5,
                "parameter": {"id": 2, "name": "pm25", "units": "µg/m³"},
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
            },
            {
                "locations_id": 2708,
                "value": 24.1,
                "parameter": {"id": 2, "name": "pm25", "units": "µg/m³"},
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
            },
            {
                "locations_id": 2708,
                "value": 45.2,
                "parameter": {"id": 19, "name": "no2", "units": "µg/m³"},
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
            },
        ]
    )


@pytest.fixture
def raw_openaq_data_with_nulls():
    """Sample OpenAQ data with null values."""
    return pd.DataFrame(
        [
            {
                "locations_id": 2708,
                "value": None,  # Null value
                "parameter": {"id": 2, "name": "pm25", "units": "µg/m³"},
                "period": {
                    "datetimeTo": {"utc": "2024-01-01T01:00:00Z"},
                },
            },
            {
                "locations_id": 2708,
                "value": 24.1,
                "parameter": {"id": 2, "name": "pm25", "units": "µg/m³"},
                "period": {
                    "datetimeTo": {"utc": "2024-01-01T02:00:00Z"},
                },
            },
        ]
    )


@pytest.fixture
def raw_openaq_unknown_parameter():
    """Sample OpenAQ data with unknown parameter."""
    return pd.DataFrame(
        [
            {
                "locations_id": 2708,
                "value": 12.5,
                "parameter": {"id": 999, "name": "xyz", "units": "units"},
                "period": {
                    "datetimeTo": {"utc": "2024-01-01T01:00:00Z"},
                },
            },
        ]
    )


# ============================================================================
# Tests for Parameter Mapping
# ============================================================================


def test_parameter_map_has_standard_pollutants():
    """Test that PARAMETER_MAP includes standard air quality pollutants."""
    assert "no2" in PARAMETER_MAP
    assert "pm25" in PARAMETER_MAP
    assert "pm10" in PARAMETER_MAP
    assert "o3" in PARAMETER_MAP
    assert "so2" in PARAMETER_MAP
    assert "co" in PARAMETER_MAP


def test_parameter_map_uses_standard_names():
    """Test that parameter names are standardized."""
    assert PARAMETER_MAP["no2"] == "NO2"
    assert PARAMETER_MAP["pm25"] == "PM2.5"
    assert PARAMETER_MAP["pm10"] == "PM10"
    assert PARAMETER_MAP["o3"] == "O3"


def test_parameter_map_handles_edge_cases():
    """Test parameter mapping for less common pollutants."""
    assert PARAMETER_MAP["bc"] == "BC"  # Black carbon
    assert PARAMETER_MAP["nox"] == "NOX"
    assert PARAMETER_MAP["ch4"] == "CH4"  # Methane


# ============================================================================
# Tests for Normalization Pipeline
# ============================================================================


def test_normalizer_creates_callable():
    """Test that create_openaq_normalizer returns a callable function."""
    normalizer = create_openaq_normalizer()
    assert callable(normalizer)


def test_normalizer_converts_to_standard_schema(raw_openaq_hourly_data):
    """Test that normalizer produces standard Aeolus schema."""
    normalizer = create_openaq_normalizer()
    result = normalizer(raw_openaq_hourly_data)

    # Check required columns
    required_columns = [
        "site_code",
        "date_time",
        "measurand",
        "value",
        "units",
        "source_network",
        "ratification",
        "created_at",
    ]
    for col in required_columns:
        assert col in result.columns, f"Missing required column: {col}"


def test_normalizer_extracts_site_code(raw_openaq_hourly_data):
    """Test that location_id is converted to site_code as string."""
    normalizer = create_openaq_normalizer()
    result = normalizer(raw_openaq_hourly_data)

    assert "site_code" in result.columns
    assert result["site_code"].dtype == object  # String type
    assert result["site_code"].iloc[0] == "2708"


def test_normalizer_extracts_timestamp(raw_openaq_hourly_data):
    """Test that timestamp is extracted from period.datetimeTo.utc."""
    normalizer = create_openaq_normalizer()
    result = normalizer(raw_openaq_hourly_data)

    assert "date_time" in result.columns
    assert pd.api.types.is_datetime64_any_dtype(result["date_time"])

    # Check first timestamp (may be timezone-aware or naive)
    expected = pd.Timestamp("2024-01-01 01:00:00")
    actual = result["date_time"].iloc[0]
    # Compare without timezone info
    assert actual.tz_localize(None) == expected if actual.tz else actual == expected


def test_normalizer_standardizes_parameter_names(raw_openaq_hourly_data):
    """Test that parameter names are standardized using PARAMETER_MAP."""
    normalizer = create_openaq_normalizer()
    result = normalizer(raw_openaq_hourly_data)

    assert "measurand" in result.columns
    assert "PM2.5" in result["measurand"].values
    assert "NO2" in result["measurand"].values
    # Original lowercase names should not appear
    assert "pm25" not in result["measurand"].values
    assert "no2" not in result["measurand"].values


def test_normalizer_extracts_units(raw_openaq_hourly_data):
    """Test that units are extracted from parameter.units."""
    normalizer = create_openaq_normalizer()
    result = normalizer(raw_openaq_hourly_data)

    assert "units" in result.columns
    # µg/m³ should be converted to ug/m3
    assert "ug/m3" in result["units"].values


def test_normalizer_converts_units_format(raw_openaq_hourly_data):
    """Test that Unicode units are converted to ASCII."""
    normalizer = create_openaq_normalizer()
    result = normalizer(raw_openaq_hourly_data)

    # Should not contain Unicode µ character
    for unit in result["units"].unique():
        assert "µ" not in unit
        assert "μ" not in unit


def test_normalizer_adds_source_network(raw_openaq_hourly_data):
    """Test that source_network column is added."""
    normalizer = create_openaq_normalizer()
    result = normalizer(raw_openaq_hourly_data)

    assert "source_network" in result.columns
    assert all(result["source_network"] == "OpenAQ")


def test_normalizer_adds_ratification(raw_openaq_hourly_data):
    """Test that ratification column is added."""
    normalizer = create_openaq_normalizer()
    result = normalizer(raw_openaq_hourly_data)

    assert "ratification" in result.columns
    # OpenAQ hourly data is typically unvalidated
    assert all(result["ratification"] == "Unvalidated")


def test_normalizer_adds_created_at(raw_openaq_hourly_data):
    """Test that created_at timestamp is added."""
    normalizer = create_openaq_normalizer()
    result = normalizer(raw_openaq_hourly_data)

    assert "created_at" in result.columns
    # Should be a timestamp
    assert pd.api.types.is_datetime64_any_dtype(result["created_at"])


def test_normalizer_preserves_values(raw_openaq_hourly_data):
    """Test that measurement values are preserved."""
    normalizer = create_openaq_normalizer()
    result = normalizer(raw_openaq_hourly_data)

    assert "value" in result.columns
    # Check that original values are present
    assert 23.5 in result["value"].values
    assert 24.1 in result["value"].values
    assert 45.2 in result["value"].values


def test_normalizer_removes_complex_columns(raw_openaq_hourly_data):
    """Test that complex nested columns (period, parameter) are removed."""
    normalizer = create_openaq_normalizer()
    result = normalizer(raw_openaq_hourly_data)

    # These nested objects should not be in final result
    assert "period" not in result.columns
    assert "parameter" not in result.columns
    assert "locations_id" not in result.columns  # Converted to site_code


# ============================================================================
# Tests for Edge Cases
# ============================================================================


def test_normalizer_handles_empty_dataframe():
    """Test that normalizer handles empty DataFrames gracefully."""
    empty_df = pd.DataFrame(columns=["locations_id", "value", "parameter", "period"])

    normalizer = create_openaq_normalizer()
    result = normalizer(empty_df)

    # Should return empty DataFrame with correct schema
    assert len(result) == 0
    assert "site_code" in result.columns
    assert "date_time" in result.columns
    assert "measurand" in result.columns


def test_normalizer_handles_null_values(raw_openaq_data_with_nulls):
    """Test that normalizer handles null values correctly."""
    normalizer = create_openaq_normalizer()
    result = normalizer(raw_openaq_data_with_nulls)

    # Null values should be dropped
    assert len(result) == 1  # Only the non-null row remains
    assert result["value"].iloc[0] == 24.1


def test_normalizer_handles_unknown_parameters(raw_openaq_unknown_parameter):
    """Test that unknown parameters are uppercased as fallback."""
    normalizer = create_openaq_normalizer()
    result = normalizer(raw_openaq_unknown_parameter)

    # Unknown parameter should be converted to uppercase
    assert result["measurand"].iloc[0] == "XYZ"


def test_normalizer_handles_missing_period_fields():
    """Test that missing period fields are handled gracefully."""
    df = pd.DataFrame(
        [
            {
                "locations_id": 2708,
                "value": 23.5,
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "period": {},  # Empty period
            }
        ]
    )

    normalizer = create_openaq_normalizer()
    result = normalizer(df)

    # Should handle missing timestamp - will be NaT
    assert "date_time" in result.columns
    # Row with NaT should be dropped
    assert len(result) == 0


def test_normalizer_handles_malformed_parameter():
    """Test that malformed parameter dict is handled."""
    df = pd.DataFrame(
        [
            {
                "locations_id": 2708,
                "value": 23.5,
                "parameter": "not_a_dict",  # String instead of dict
                "period": {"datetimeTo": {"utc": "2024-01-01T01:00:00Z"}},
            }
        ]
    )

    normalizer = create_openaq_normalizer()
    result = normalizer(df)

    # Should handle gracefully
    assert "measurand" in result.columns


# ============================================================================
# Integration Tests
# ============================================================================


def test_normalizer_produces_mergeable_output():
    """Test that normalized data can be merged with other sources."""
    # Simulate OpenAQ data
    openaq_data = pd.DataFrame(
        [
            {
                "locations_id": 2708,
                "value": 23.5,
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "period": {"datetimeTo": {"utc": "2024-01-01T01:00:00Z"}},
            }
        ]
    )

    # Simulate AURN data (already normalized)
    aurn_data = pd.DataFrame(
        [
            {
                "site_code": "MY1",
                "date_time": pd.Timestamp("2024-01-01 01:00:00"),
                "measurand": "PM2.5",
                "value": 25.0,
                "units": "ug/m3",
                "source_network": "AURN",
                "ratification": "Validated",
                "created_at": pd.Timestamp.now(),
            }
        ]
    )

    # Normalize OpenAQ
    normalizer = create_openaq_normalizer()
    openaq_normalized = normalizer(openaq_data)

    # Merge both sources
    combined = pd.concat([aurn_data, openaq_normalized], ignore_index=True)

    # Check that schemas match
    assert len(combined) == 2
    assert set(combined["source_network"].unique()) == {"AURN", "OpenAQ"}
    assert all(combined.columns == aurn_data.columns)


def test_normalizer_consistent_across_multiple_calls(raw_openaq_hourly_data):
    """Test that normalizer produces consistent results."""
    normalizer = create_openaq_normalizer()

    result1 = normalizer(raw_openaq_hourly_data.copy())
    result2 = normalizer(raw_openaq_hourly_data.copy())

    # Results should be identical (except created_at timestamp)
    assert len(result1) == len(result2)
    assert list(result1.columns) == list(result2.columns)
    assert result1["site_code"].equals(result2["site_code"])
    assert result1["measurand"].equals(result2["measurand"])
    assert result1["value"].equals(result2["value"])


def test_normalizer_handles_multiple_locations():
    """Test normalizer with data from multiple locations."""
    df = pd.DataFrame(
        [
            {
                "locations_id": 2708,
                "value": 23.5,
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "period": {"datetimeTo": {"utc": "2024-01-01T01:00:00Z"}},
            },
            {
                "locations_id": 3272,
                "value": 45.2,
                "parameter": {"name": "no2", "units": "µg/m³"},
                "period": {"datetimeTo": {"utc": "2024-01-01T01:00:00Z"}},
            },
        ]
    )

    normalizer = create_openaq_normalizer()
    result = normalizer(df)

    assert len(result) == 2
    assert set(result["site_code"].unique()) == {"2708", "3272"}


def test_normalizer_handles_multiple_parameters():
    """Test normalizer with multiple parameters from same location."""
    df = pd.DataFrame(
        [
            {
                "locations_id": 2708,
                "value": 23.5,
                "parameter": {"name": "pm25", "units": "µg/m³"},
                "period": {"datetimeTo": {"utc": "2024-01-01T01:00:00Z"}},
            },
            {
                "locations_id": 2708,
                "value": 45.2,
                "parameter": {"name": "no2", "units": "µg/m³"},
                "period": {"datetimeTo": {"utc": "2024-01-01T01:00:00Z"}},
            },
            {
                "locations_id": 2708,
                "value": 38.1,
                "parameter": {"name": "o3", "units": "µg/m³"},
                "period": {"datetimeTo": {"utc": "2024-01-01T01:00:00Z"}},
            },
        ]
    )

    normalizer = create_openaq_normalizer()
    result = normalizer(df)

    assert len(result) == 3
    assert set(result["measurand"].unique()) == {"PM2.5", "NO2", "O3"}
    assert all(result["site_code"] == "2708")
