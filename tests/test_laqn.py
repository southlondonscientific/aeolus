# Tests for the LAQN (London Air Quality Network) data source.

from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
import pytest

from aeolus.sources.laqn import (
    API_BASE,
    fetch_laqn_data,
    fetch_laqn_erg_data,
    fetch_laqn_metadata,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_sites_response():
    """Mock response from the LAQN ERG sites endpoint (metadata path)."""
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
def mock_laqn_rdata_df():
    """A LAQN openair-style RData frame: lowercase columns, FINE for PM2.5,
    no separate `code` column (`site` holds the site code)."""
    # 2024-01-01 00:00:00 UTC = 1704067200 (seconds since epoch)
    base = 1704067200.0
    return pd.DataFrame({
        "date": [base, base + 3600, base + 7200],
        "no": [17.2, 15.9, 14.0],
        "nox": [30.1, 28.5, 25.0],
        "no2": [13.4, 12.8, 11.2],
        "o3": [19.6, 21.2, 24.5],
        "pm10": [22.1, 23.0, 20.5],
        "pm10_raw": [21.0, 22.0, 19.0],  # extra column, should be dropped
        "FINE": [12.3, 13.0, 11.5],      # PM2.5 in LAQN openair feeds
        "co": [0.3, 0.25, 0.2],
        "CO2": [462.0, 470.0, 455.0],    # extra column, should be dropped
        "site": ["MY1", "MY1", "MY1"],
    })


# ============================================================================
# Metadata tests (ERG API path)
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
    def test_location_type_populated(self, mock_get, mock_sites_response):
        """location_type should be populated from @SiteType."""
        mock_get.return_value = mock_sites_response
        result = fetch_laqn_metadata()
        assert "location_type" in result.columns
        my1 = result[result["site_code"] == "MY1"]
        kc1 = result[result["site_code"] == "KC1"]
        assert my1["location_type"].iloc[0] == "Kerbside"
        assert kc1["location_type"].iloc[0] == "Urban Background"

    @patch("aeolus.sources.laqn._get_json")
    def test_returns_empty_on_none(self, mock_get):
        mock_get.return_value = None
        with pytest.warns(match="Failed to fetch LAQN metadata"):
            result = fetch_laqn_metadata()
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("aeolus.sources.laqn._get_json")
    def test_returns_empty_on_empty_sites(self, mock_get):
        mock_get.return_value = {"Sites": {"Site": []}}
        with pytest.warns(match="LAQN ERG API returned no sites"):
            result = fetch_laqn_metadata()
        assert result.empty


# ============================================================================
# Data tests (openair RData path)
# ============================================================================


class TestFetchData:
    """Tests for the data fetcher (RData feed via regulatory factory)."""

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_returns_standard_columns(self, mock_rdata, mock_laqn_rdata_df):
        mock_rdata.return_value = mock_laqn_rdata_df
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)

        from aeolus.types import DATA_COLUMNS
        for col in DATA_COLUMNS:
            assert col in result.columns

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_source_network_is_laqn(self, mock_rdata, mock_laqn_rdata_df):
        mock_rdata.return_value = mock_laqn_rdata_df
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        assert all(result["source_network"] == "LAQN")

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_fine_mapped_to_pm25(self, mock_rdata, mock_laqn_rdata_df):
        """LAQN's `FINE` column should appear as `PM2.5` in output."""
        mock_rdata.return_value = mock_laqn_rdata_df
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        assert "PM2.5" in result["measurand"].values
        # FINE shouldn't leak through as itself
        assert "FINE" not in result["measurand"].values

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_lowercase_columns_renamed_to_standard(self, mock_rdata, mock_laqn_rdata_df):
        """LAQN's lowercase `no`, `nox`, `no2`, `o3`, `pm10`, `co` should map
        to AURN-style names."""
        mock_rdata.return_value = mock_laqn_rdata_df
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        present = set(result["measurand"].unique())
        assert {"NO", "NO2", "NOXasNO2", "O3", "PM10", "CO", "PM2.5"}.issubset(present)

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_extra_columns_dropped(self, mock_rdata, mock_laqn_rdata_df):
        """Non-regulatory columns (`pm10_raw`, `CO2`) should not appear as
        measurands in the normalised output."""
        mock_rdata.return_value = mock_laqn_rdata_df
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        present = set(result["measurand"].unique())
        assert "pm10_raw" not in present
        assert "CO2" not in present

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_co_units_are_mg_m3(self, mock_rdata, mock_laqn_rdata_df):
        mock_rdata.return_value = mock_laqn_rdata_df
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        co = result[result["measurand"] == "CO"]
        assert not co.empty
        assert (co["units"] == "mg/m3").all()

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_non_co_units_are_ug_m3(self, mock_rdata, mock_laqn_rdata_df):
        mock_rdata.return_value = mock_laqn_rdata_df
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        non_co = result[result["measurand"] != "CO"]
        assert (non_co["units"] == "ug/m3").all()

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_timestamps_are_utc(self, mock_rdata, mock_laqn_rdata_df):
        mock_rdata.return_value = mock_laqn_rdata_df
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        result = fetch_laqn_data(["MY1"], start, end)
        assert result["date_time"].dt.tz is not None

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_url_uses_londonair_rdata(self, mock_rdata, mock_laqn_rdata_df):
        """LAQN data path must hit londonair.org.uk, not the ERG REST API."""
        mock_rdata.return_value = mock_laqn_rdata_df
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        fetch_laqn_data(["my1"], start, end)

        url = mock_rdata.call_args_list[0][0][0]
        assert url == "https://www.londonair.org.uk/r_data/MY1_2024.RData"

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_no_data_warns(self, mock_rdata):
        mock_rdata.return_value = None
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

    def test_api_base_unchanged(self):
        """Metadata path still uses ERG API."""
        assert "erg.ic.ac.uk" in API_BASE


# ============================================================================
# Data tests (live ERG REST path — LAQN-ERG source)
# ============================================================================


@pytest.fixture
def mock_erg_data_response():
    """Mock response from the ERG `Data/Site/.../Json` hourly-data endpoint.

    Mirrors the real shape: a flat list under AirQualityData.Data, each row
    carrying @SpeciesCode / @MeasurementDateGMT / @Value. Empty-value rows
    and unmapped species are present so the fetcher's filtering is exercised.
    """
    return {
        "AirQualityData": {
            "Data": [
                {"@SpeciesCode": "NO2", "@MeasurementDateGMT": "2026-05-25 03:00:00", "@Value": "23.5"},
                {"@SpeciesCode": "NO2", "@MeasurementDateGMT": "2026-05-25 04:00:00", "@Value": "25.1"},
                {"@SpeciesCode": "FINE", "@MeasurementDateGMT": "2026-05-25 04:00:00", "@Value": "12.3"},
                {"@SpeciesCode": "CO", "@MeasurementDateGMT": "2026-05-25 04:00:00", "@Value": "0.3"},
                {"@SpeciesCode": "NO2", "@MeasurementDateGMT": "2026-05-25 05:00:00", "@Value": ""},
                {"@SpeciesCode": "XYZ", "@MeasurementDateGMT": "2026-05-25 04:00:00", "@Value": "9.9"},
            ]
        }
    }


class TestFetchERGData:
    """Tests for the live ERG REST data fetcher (LAQN-ERG source).

    The RData feed (the default `LAQN` source) lags real time by a day or
    more, which makes it unusable for live polling. The ERG REST endpoint
    returns hourly data within a few hours of real time. This fetcher is the
    live counterpart, mirroring the AURN-SOS-live / AURN-RData-backfill split.
    """

    @patch("aeolus.sources.laqn._get_json")
    def test_returns_standard_columns(self, mock_get, mock_erg_data_response):
        mock_get.return_value = mock_erg_data_response
        start = datetime(2026, 5, 25, tzinfo=timezone.utc)
        end = datetime(2026, 5, 26, tzinfo=timezone.utc)

        result = fetch_laqn_erg_data(["MY1"], start, end)

        from aeolus.types import DATA_COLUMNS
        for col in DATA_COLUMNS:
            assert col in result.columns

    @patch("aeolus.sources.laqn._get_json")
    def test_source_network_is_laqn(self, mock_get, mock_erg_data_response):
        mock_get.return_value = mock_erg_data_response
        start = datetime(2026, 5, 25, tzinfo=timezone.utc)
        end = datetime(2026, 5, 26, tzinfo=timezone.utc)
        result = fetch_laqn_erg_data(["MY1"], start, end)
        assert all(result["source_network"] == "LAQN")

    @patch("aeolus.sources.laqn._get_json")
    def test_fine_mapped_to_pm25(self, mock_get, mock_erg_data_response):
        mock_get.return_value = mock_erg_data_response
        start = datetime(2026, 5, 25, tzinfo=timezone.utc)
        end = datetime(2026, 5, 26, tzinfo=timezone.utc)
        result = fetch_laqn_erg_data(["MY1"], start, end)
        assert "PM2.5" in result["measurand"].values
        assert "FINE" not in result["measurand"].values

    @patch("aeolus.sources.laqn._get_json")
    def test_co_units_are_mg_m3(self, mock_get, mock_erg_data_response):
        mock_get.return_value = mock_erg_data_response
        start = datetime(2026, 5, 25, tzinfo=timezone.utc)
        end = datetime(2026, 5, 26, tzinfo=timezone.utc)
        result = fetch_laqn_erg_data(["MY1"], start, end)
        co = result[result["measurand"] == "CO"]
        assert not co.empty
        assert (co["units"] == "mg/m3").all()

    @patch("aeolus.sources.laqn._get_json")
    def test_non_co_units_are_ug_m3(self, mock_get, mock_erg_data_response):
        mock_get.return_value = mock_erg_data_response
        start = datetime(2026, 5, 25, tzinfo=timezone.utc)
        end = datetime(2026, 5, 26, tzinfo=timezone.utc)
        result = fetch_laqn_erg_data(["MY1"], start, end)
        non_co = result[result["measurand"] != "CO"]
        assert (non_co["units"] == "ug/m3").all()

    @patch("aeolus.sources.laqn._get_json")
    def test_timestamps_are_utc(self, mock_get, mock_erg_data_response):
        mock_get.return_value = mock_erg_data_response
        start = datetime(2026, 5, 25, tzinfo=timezone.utc)
        end = datetime(2026, 5, 26, tzinfo=timezone.utc)
        result = fetch_laqn_erg_data(["MY1"], start, end)
        assert result["date_time"].dt.tz is not None

    @patch("aeolus.sources.laqn._get_json")
    def test_empty_values_dropped(self, mock_get, mock_erg_data_response):
        """The NO2 05:00 row has an empty @Value and must not survive."""
        mock_get.return_value = mock_erg_data_response
        start = datetime(2026, 5, 25, tzinfo=timezone.utc)
        end = datetime(2026, 5, 26, tzinfo=timezone.utc)
        result = fetch_laqn_erg_data(["MY1"], start, end)
        # 4 valid rows: NO2 03:00, NO2 04:00, FINE 04:00, CO 04:00
        # (empty NO2 05:00 dropped; XYZ unmapped dropped)
        assert len(result) == 4
        assert result["value"].notna().all()

    @patch("aeolus.sources.laqn._get_json")
    def test_unmapped_species_dropped(self, mock_get, mock_erg_data_response):
        mock_get.return_value = mock_erg_data_response
        start = datetime(2026, 5, 25, tzinfo=timezone.utc)
        end = datetime(2026, 5, 26, tzinfo=timezone.utc)
        result = fetch_laqn_erg_data(["MY1"], start, end)
        assert "XYZ" not in result["measurand"].values

    @patch("aeolus.sources.laqn._get_json")
    def test_uses_erg_data_endpoint(self, mock_get, mock_erg_data_response):
        """Live path must hit the ERG REST Data/Site endpoint, not RData."""
        mock_get.return_value = mock_erg_data_response
        start = datetime(2026, 5, 25, tzinfo=timezone.utc)
        end = datetime(2026, 5, 26, tzinfo=timezone.utc)
        fetch_laqn_erg_data(["MY1"], start, end)
        called_path = mock_get.call_args_list[0][0][0]
        assert "Data/Site/SiteCode=MY1" in called_path

    @patch("aeolus.sources.laqn._get_json")
    def test_site_codes_uppercased(self, mock_get, mock_erg_data_response):
        mock_get.return_value = mock_erg_data_response
        start = datetime(2026, 5, 25, tzinfo=timezone.utc)
        end = datetime(2026, 5, 26, tzinfo=timezone.utc)
        fetch_laqn_erg_data(["my1"], start, end)
        called_path = mock_get.call_args_list[0][0][0]
        assert "SiteCode=MY1" in called_path

    @patch("aeolus.sources.laqn._get_json")
    def test_no_data_warns(self, mock_get):
        mock_get.return_value = {"AirQualityData": {"Data": []}}
        start = datetime(2026, 5, 25, tzinfo=timezone.utc)
        end = datetime(2026, 5, 26, tzinfo=timezone.utc)
        with pytest.warns(match="No data retrieved for LAQN"):
            result = fetch_laqn_erg_data(["X"], start, end)
        assert result.empty


class TestERGRegistration:
    """The live ERG source is registered as a non-primary LAQN-ERG source,
    leaving the default LAQN (RData) source untouched."""

    def test_laqn_erg_registered(self):
        from aeolus.registry import get_source
        source = get_source("LAQN-ERG")
        assert source is not None
        assert source["type"] == "network"
        assert source["requires_api_key"] is False
        # Non-primary so it never displaces the fast RData feed as the
        # default backend for bulk/backfill use.
        assert source.get("primary") is False

    def test_laqn_default_still_registered(self):
        """Adding the ERG source must not disturb the default LAQN source."""
        from aeolus.registry import get_source
        assert get_source("LAQN") is not None
