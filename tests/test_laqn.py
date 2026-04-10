# Tests for the LAQN (London Air Quality Network) data source.

from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
import pytest

from aeolus.sources.laqn import (
    API_BASE,
    SPECIES_MAP,
    _month_ranges,
    fetch_laqn_data,
    fetch_laqn_metadata,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_sites_response():
    """Mock response from the LAQN sites endpoint."""
    return {
        "Sites": {
            "Site": [
                {
                    "@SiteCode": "MY1",
                    "@SiteName": "Marylebone Road",
                    "@SiteType": "Kerbside",
                    "@Latitude": "51.522530",
                    "@Longitude": "-0.154611",
                    "@DateOpened": "1999-01-01 00:00:00",
                    "@DateClosed": "",
                    "@LocalAuthorityCode": "14",
                    "@LocalAuthorityName": "Westminster",
                    "@DataOwner": "TfL",
                    "@DataManager": "ERG",
                    "@SiteLink": "",
                },
                {
                    "@SiteCode": "KC1",
                    "@SiteName": "North Kensington",
                    "@SiteType": "Urban Background",
                    "@Latitude": "51.521050",
                    "@Longitude": "-0.213492",
                    "@DateOpened": "1996-01-01 00:00:00",
                    "@DateClosed": "",
                    "@LocalAuthorityCode": "15",
                    "@LocalAuthorityName": "RBKC",
                    "@DataOwner": "DEFRA",
                    "@DataManager": "ERG",
                    "@SiteLink": "",
                },
                {
                    "@SiteCode": "NOCOORDS",
                    "@SiteName": "No Coordinates Site",
                    "@SiteType": "Urban Background",
                    "@Latitude": "",
                    "@Longitude": "",
                    "@DateOpened": "2020-01-01 00:00:00",
                    "@DateClosed": "",
                    "@LocalAuthorityCode": "",
                    "@LocalAuthorityName": "",
                    "@DataOwner": "",
                    "@DataManager": "",
                    "@SiteLink": "",
                },
            ]
        }
    }


@pytest.fixture
def mock_data_response():
    """Mock response from the LAQN data endpoint."""
    return {
        "AirQualityData": {
            "@SiteCode": "MY1",
            "Data": [
                {
                    "@SpeciesCode": "NO2",
                    "@MeasurementDateGMT": "2024-01-01 00:00:00",
                    "@Value": "45.2",
                },
                {
                    "@SpeciesCode": "NO2",
                    "@MeasurementDateGMT": "2024-01-01 01:00:00",
                    "@Value": "38.7",
                },
                {
                    "@SpeciesCode": "PM10",
                    "@MeasurementDateGMT": "2024-01-01 00:00:00",
                    "@Value": "22.1",
                },
                {
                    "@SpeciesCode": "FINE",
                    "@MeasurementDateGMT": "2024-01-01 00:00:00",
                    "@Value": "12.3",
                },
                {
                    "@SpeciesCode": "CO",
                    "@MeasurementDateGMT": "2024-01-01 00:00:00",
                    "@Value": "0.3",
                },
                {
                    "@SpeciesCode": "NO2",
                    "@MeasurementDateGMT": "2024-01-01 02:00:00",
                    "@Value": "",
                },
            ],
        }
    }


# ============================================================================
# Tests for _month_ranges()
# ============================================================================


class TestMonthRanges:
    """Tests for the month chunking helper."""

    def test_single_month(self):
        start = datetime(2024, 3, 5)
        end = datetime(2024, 3, 20)
        ranges = list(_month_ranges(start, end))
        assert len(ranges) == 1
        assert ranges[0] == (start, end)

    def test_spans_two_months(self):
        start = datetime(2024, 1, 15)
        end = datetime(2024, 2, 10)
        ranges = list(_month_ranges(start, end))
        assert len(ranges) == 2
        assert ranges[0] == (datetime(2024, 1, 15), datetime(2024, 2, 1))
        assert ranges[1] == (datetime(2024, 2, 1), datetime(2024, 2, 10))

    def test_spans_year_boundary(self):
        start = datetime(2023, 12, 15)
        end = datetime(2024, 1, 10)
        ranges = list(_month_ranges(start, end))
        assert len(ranges) == 2
        assert ranges[0][0] == datetime(2023, 12, 15)
        assert ranges[1][1] == datetime(2024, 1, 10)

    def test_full_year(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        ranges = list(_month_ranges(start, end))
        assert len(ranges) == 12


# ============================================================================
# Tests for species mapping
# ============================================================================


class TestSpeciesMap:
    """Tests for the species code mapping."""

    def test_fine_maps_to_pm25(self):
        assert SPECIES_MAP["FINE"] == "PM2.5"

    def test_pm25_maps_to_pm25(self):
        assert SPECIES_MAP["PM25"] == "PM2.5"

    def test_standard_pollutants(self):
        assert SPECIES_MAP["NO2"] == "NO2"
        assert SPECIES_MAP["O3"] == "O3"
        assert SPECIES_MAP["CO"] == "CO"
        assert SPECIES_MAP["PM10"] == "PM10"
        assert SPECIES_MAP["SO2"] == "SO2"


# ============================================================================
# Tests for fetch_laqn_metadata()
# ============================================================================


class TestFetchMetadata:
    """Tests for the metadata fetcher."""

    @patch("aeolus.sources.laqn._get_json")
    def test_returns_standard_columns(self, mock_get, mock_sites_response):
        mock_get.return_value = mock_sites_response
        result = fetch_laqn_metadata()

        assert "site_code" in result.columns
        assert "site_name" in result.columns
        assert "latitude" in result.columns
        assert "longitude" in result.columns
        assert "source_network" in result.columns

    @patch("aeolus.sources.laqn._get_json")
    def test_source_network_is_laqn(self, mock_get, mock_sites_response):
        mock_get.return_value = mock_sites_response
        result = fetch_laqn_metadata()
        assert all(result["source_network"] == "LAQN")

    @patch("aeolus.sources.laqn._get_json")
    def test_excludes_sites_without_coordinates(self, mock_get, mock_sites_response):
        mock_get.return_value = mock_sites_response
        result = fetch_laqn_metadata()
        assert "NOCOORDS" not in result["site_code"].values
        assert len(result) == 2

    @patch("aeolus.sources.laqn._get_json")
    def test_coordinates_are_numeric(self, mock_get, mock_sites_response):
        mock_get.return_value = mock_sites_response
        result = fetch_laqn_metadata()
        assert result["latitude"].dtype == float
        assert result["longitude"].dtype == float

    @patch("aeolus.sources.laqn._get_json")
    def test_returns_empty_on_none(self, mock_get):
        mock_get.return_value = None
        result = fetch_laqn_metadata()
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("aeolus.sources.laqn._get_json")
    def test_returns_empty_on_empty_sites(self, mock_get):
        mock_get.return_value = {"Sites": {"Site": []}}
        result = fetch_laqn_metadata()
        assert result.empty


# ============================================================================
# Tests for fetch_laqn_data()
# ============================================================================


class TestFetchData:
    """Tests for the data fetcher."""

    @patch("aeolus.sources.laqn._get_json")
    def test_returns_standard_columns(self, mock_get, mock_data_response):
        mock_get.return_value = mock_data_response
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)

        from aeolus.types import DATA_COLUMNS
        for col in DATA_COLUMNS:
            assert col in result.columns

    @patch("aeolus.sources.laqn._get_json")
    def test_source_network_is_laqn(self, mock_get, mock_data_response):
        mock_get.return_value = mock_data_response
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        assert all(result["source_network"] == "LAQN")

    @patch("aeolus.sources.laqn._get_json")
    def test_fine_mapped_to_pm25(self, mock_get, mock_data_response):
        mock_get.return_value = mock_data_response
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        assert "PM2.5" in result["measurand"].values

    @patch("aeolus.sources.laqn._get_json")
    def test_empty_values_filtered(self, mock_get, mock_data_response):
        """Rows with empty @Value should be excluded."""
        mock_get.return_value = mock_data_response
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        # The mock has 6 data points but one has empty value
        assert len(result) == 5

    @patch("aeolus.sources.laqn._get_json")
    def test_values_are_numeric(self, mock_get, mock_data_response):
        mock_get.return_value = mock_data_response
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        assert result["value"].dtype == float

    @patch("aeolus.sources.laqn._get_json")
    def test_timestamps_are_utc(self, mock_get, mock_data_response):
        mock_get.return_value = mock_data_response
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        assert result["date_time"].dt.tz is not None

    @patch("aeolus.sources.laqn._get_json")
    def test_co_units_are_mg_m3(self, mock_get, mock_data_response):
        """CO should be labelled mg/m3, not ug/m3."""
        mock_get.return_value = mock_data_response
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        co = result[result["measurand"] == "CO"]
        assert len(co) == 1
        assert co["units"].iloc[0] == "mg/m3"

    @patch("aeolus.sources.laqn._get_json")
    def test_non_co_units_are_ug_m3(self, mock_get, mock_data_response):
        """Non-CO species should be labelled ug/m3."""
        mock_get.return_value = mock_data_response
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        non_co = result[result["measurand"] != "CO"]
        assert (non_co["units"] == "ug/m3").all()

    @patch("aeolus.sources.laqn._get_json")
    def test_no_data_warns(self, mock_get):
        mock_get.return_value = {"AirQualityData": {"@SiteCode": "X", "Data": []}}
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        with pytest.warns(match="No data retrieved for LAQN"):
            result = fetch_laqn_data(["X"], start, end)

        assert result.empty


# ============================================================================
# Tests for source registration
# ============================================================================


class TestRegistration:
    """Tests for LAQN source registration."""

    def test_laqn_registered(self):
        from aeolus.registry import get_source
        source = get_source("LAQN")
        assert source is not None
        assert source["type"] == "network"
        assert source["requires_api_key"] is False
