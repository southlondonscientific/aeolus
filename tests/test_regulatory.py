"""
Tests for UK Regulatory Network data sources (AURN, SAQN, etc.).

Tests the RData fetching, metadata and data normalisation, and factory
functions with mocked HTTP responses.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import responses

# Import sources package to ensure all sources are registered
import aeolus.sources  # noqa: F401
from aeolus.sources.regulatory import (
    DATA_BASE_URLS,
    METADATA_URLS,
    REGULATORY_MEASURANDS,
    fetch_rdata,
    make_data_fetcher,
    make_metadata_fetcher,
    normalise_regulatory_data,
    normalise_regulatory_metadata,
)

# ============================================================================
# Fixtures for Mock Data
# ============================================================================


@pytest.fixture
def mock_metadata_df():
    """Mock metadata DataFrame as would be returned from RData."""
    return pd.DataFrame(
        {
            "site_id": ["MY1", "KC1", "ED1"],
            "site_name": [
                "London Marylebone Road",
                "London N. Kensington",
                "Edinburgh St Leonards",
            ],
            "latitude": [51.5225, 51.5210, 55.9456],
            "longitude": [-0.1547, -0.2133, -3.1824],
            "site_type": ["Urban Traffic", "Urban Background", "Urban Background"],
            "local_authority": ["Westminster", "RBKC", "Edinburgh"],
            "start_date": ["1997-01-01", "1996-01-01", "2000-01-01"],
            "end_date": [None, None, None],
            "parameter": ["O3, NO2, PM2.5", "O3, NO2, PM10", "NO2, PM2.5"],
            "Parameter_name": ["Ozone, etc", "Ozone, etc", "NO2, etc"],
        }
    )


@pytest.fixture
def mock_data_df():
    """Mock data DataFrame as would be returned from RData."""
    return pd.DataFrame(
        {
            "site": ["London Marylebone Road"] * 6,
            "code": ["MY1"] * 6,
            "date": [
                datetime(2024, 1, 1, 0, 0),
                datetime(2024, 1, 1, 1, 0),
                datetime(2024, 1, 1, 2, 0),
                datetime(2024, 1, 1, 0, 0),
                datetime(2024, 1, 1, 1, 0),
                datetime(2024, 1, 1, 2, 0),
            ],
            "NO2": [45.2, 42.8, 38.5, 45.2, 42.8, 38.5],
            "O3": [25.1, 28.3, 32.0, 25.1, 28.3, 32.0],
            "PM2.5": [12.5, 14.2, 11.8, 12.5, 14.2, 11.8],
        }
    )


@pytest.fixture
def mock_data_df_multiple_sites():
    """Mock data DataFrame with multiple sites."""
    return pd.DataFrame(
        {
            "site": [
                "London Marylebone Road",
                "London Marylebone Road",
                "London N. Kensington",
                "London N. Kensington",
            ],
            "code": ["MY1", "MY1", "KC1", "KC1"],
            "date": [
                datetime(2024, 1, 1, 0, 0),
                datetime(2024, 1, 1, 1, 0),
                datetime(2024, 1, 1, 0, 0),
                datetime(2024, 1, 1, 1, 0),
            ],
            "NO2": [45.2, 42.8, 22.1, 20.5],
            "PM10": [28.5, 30.2, 18.3, 17.8],
        }
    )


@pytest.fixture
def mock_empty_df():
    """Mock empty DataFrame."""
    return pd.DataFrame()


# ============================================================================
# Tests for fetch_rdata()
# ============================================================================


class TestFetchRdata:
    """Tests for the low-level RData fetcher."""

    @responses.activate
    def test_fetch_rdata_connection_error(self):
        """Should return None on connection error (after retries)."""
        from requests.exceptions import ConnectionError

        responses.add(
            responses.GET,
            "https://example.com/test.RData",
            body=ConnectionError("Connection refused"),
        )

        # The retry decorator will retry, then give up and raise
        # But the function catches RequestException and returns None
        result = fetch_rdata("https://example.com/test.RData")
        assert result is None

    @responses.activate
    def test_fetch_rdata_http_error(self):
        """Should return None on HTTP error."""
        responses.add(
            responses.GET,
            "https://example.com/test.RData",
            status=404,
        )

        result = fetch_rdata("https://example.com/test.RData")
        assert result is None

    @responses.activate
    def test_fetch_rdata_invalid_content(self):
        """Should return None on invalid RData content."""
        responses.add(
            responses.GET,
            "https://example.com/test.RData",
            body=b"not valid rdata content",
            status=200,
        )

        result = fetch_rdata("https://example.com/test.RData")
        assert result is None


# ============================================================================
# Tests for normalise_regulatory_metadata()
# ============================================================================


class TestNormaliseRegulatoryMetadata:
    """Tests for metadata normalisation."""

    def test_normalise_metadata_renames_columns(self, mock_metadata_df):
        """Should rename site_id to site_code and local_authority to owner."""
        normaliser = normalise_regulatory_metadata("AURN")
        result = normaliser(mock_metadata_df)

        assert "site_code" in result.columns
        assert "owner" in result.columns
        assert "site_id" not in result.columns
        assert "local_authority" not in result.columns

    def test_normalise_metadata_drops_columns(self, mock_metadata_df):
        """Should drop parameter and Parameter_name columns."""
        normaliser = normalise_regulatory_metadata("AURN")
        result = normaliser(mock_metadata_df)

        assert "parameter" not in result.columns
        assert "Parameter_name" not in result.columns

    def test_normalise_metadata_adds_source_network(self, mock_metadata_df):
        """Should add source_network column with network name."""
        normaliser = normalise_regulatory_metadata("AURN")
        result = normaliser(mock_metadata_df)

        assert "source_network" in result.columns
        assert all(result["source_network"] == "AURN")

    def test_normalise_metadata_preserves_other_columns(self, mock_metadata_df):
        """Should preserve site_name, latitude, longitude, etc."""
        normaliser = normalise_regulatory_metadata("AURN")
        result = normaliser(mock_metadata_df)

        assert "site_name" in result.columns
        assert "latitude" in result.columns
        assert "longitude" in result.columns
        assert "site_type" in result.columns

    def test_normalise_metadata_different_networks(self, mock_metadata_df):
        """Should correctly tag different networks."""
        for network in ["AURN", "SAQN", "NI", "WAQN", "AQE"]:
            normaliser = normalise_regulatory_metadata(network)
            result = normaliser(mock_metadata_df)
            assert all(result["source_network"] == network)


# ============================================================================
# Tests for normalise_regulatory_data()
# ============================================================================


class TestNormaliseRegulatoryData:
    """Tests for data normalisation."""

    def test_normalise_data_melts_measurands(self, mock_data_df):
        """Should melt measurand columns into rows."""
        normaliser = normalise_regulatory_data("AURN")
        result = normaliser(mock_data_df)

        # Should have measurand and value columns
        assert "measurand" in result.columns
        assert "value" in result.columns

        # Should not have individual measurand columns
        assert "NO2" not in result.columns
        assert "O3" not in result.columns
        assert "PM2.5" not in result.columns

        # Should have all three measurands in the data
        measurands = result["measurand"].unique()
        assert "NO2" in measurands
        assert "O3" in measurands
        assert "PM2.5" in measurands

    def test_normalise_data_renames_columns(self, mock_data_df):
        """Should rename site, code, date columns."""
        normaliser = normalise_regulatory_data("AURN")
        result = normaliser(mock_data_df)

        assert "site_name" in result.columns
        assert "site_code" in result.columns
        assert "date_time" in result.columns
        assert "site" not in result.columns
        assert "code" not in result.columns
        assert "date" not in result.columns

    def test_normalise_data_adds_metadata_columns(self, mock_data_df):
        """Should add source_network, ratification, units, created_at."""
        normaliser = normalise_regulatory_data("AURN")
        result = normaliser(mock_data_df)

        assert "source_network" in result.columns
        assert "ratification" in result.columns
        assert "units" in result.columns
        assert "created_at" in result.columns

        assert all(result["source_network"] == "AURN")
        assert all(result["units"] == "ug/m3")

    def test_normalise_data_empty_dataframe(self, mock_empty_df):
        """Should handle empty DataFrame gracefully."""
        normaliser = normalise_regulatory_data("AURN")
        result = normaliser(mock_empty_df)

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_normalise_data_no_measurands(self):
        """Should return empty DataFrame if no measurands found."""
        df = pd.DataFrame(
            {
                "site": ["Test Site"],
                "code": ["TS1"],
                "date": [datetime(2024, 1, 1)],
                "unknown_column": [100],
            }
        )

        normaliser = normalise_regulatory_data("AURN")
        result = normaliser(df)

        assert result.empty

    def test_normalise_data_different_networks(self, mock_data_df):
        """Should correctly tag different networks."""
        for network in ["AURN", "SAQN", "NI", "WAQN", "AQE"]:
            normaliser = normalise_regulatory_data(network)
            result = normaliser(mock_data_df)
            assert all(result["source_network"] == network)

    def test_normalise_data_categorises_columns(self, mock_data_df):
        """Should categorise appropriate columns."""
        normaliser = normalise_regulatory_data("AURN")
        result = normaliser(mock_data_df)

        # Check that categorical columns are categorical dtype
        assert result["site_code"].dtype.name == "category"
        assert result["measurand"].dtype.name == "category"
        assert result["source_network"].dtype.name == "category"


# ============================================================================
# Tests for make_metadata_fetcher()
# ============================================================================


class TestMakeMetadataFetcher:
    """Tests for metadata fetcher factory."""

    def test_make_metadata_fetcher_returns_callable(self):
        """Should return a callable function."""
        fetcher = make_metadata_fetcher("aurn")
        assert callable(fetcher)

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_metadata_fetcher_calls_correct_url(self, mock_fetch, mock_metadata_df):
        """Should fetch from correct URL for each network."""
        mock_fetch.return_value = mock_metadata_df

        for network in ["aurn", "saqn", "ni", "waqn", "aqe", "local"]:
            fetcher = make_metadata_fetcher(network)
            fetcher()

            expected_url = METADATA_URLS[network]
            mock_fetch.assert_called_with(expected_url)

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_metadata_fetcher_normalises_result(self, mock_fetch, mock_metadata_df):
        """Should normalise the fetched data."""
        mock_fetch.return_value = mock_metadata_df

        fetcher = make_metadata_fetcher("aurn")
        result = fetcher()

        # Should have normalised column names
        assert "site_code" in result.columns
        assert "source_network" in result.columns
        assert all(result["source_network"] == "AURN")

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_metadata_fetcher_handles_none(self, mock_fetch):
        """Should return empty DataFrame if fetch returns None."""
        mock_fetch.return_value = None

        fetcher = make_metadata_fetcher("aurn")
        result = fetcher()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ============================================================================
# Tests for make_data_fetcher()
# ============================================================================


class TestMakeDataFetcher:
    """Tests for data fetcher factory."""

    def test_make_data_fetcher_returns_callable(self):
        """Should return a callable function."""
        fetcher = make_data_fetcher("aurn")
        assert callable(fetcher)

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_data_fetcher_constructs_correct_urls(self, mock_fetch, mock_data_df):
        """Should construct correct URLs for site and year."""
        mock_fetch.return_value = mock_data_df

        fetcher = make_data_fetcher("aurn")
        fetcher(
            sites=["MY1"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        expected_url = f"{DATA_BASE_URLS['aurn']}MY1_2024.RData"
        mock_fetch.assert_called_with(expected_url)

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_data_fetcher_fetches_multiple_years(self, mock_fetch, mock_data_df):
        """Should fetch data for each year in range."""
        mock_fetch.return_value = mock_data_df

        fetcher = make_data_fetcher("aurn")
        fetcher(
            sites=["MY1"],
            start_date=datetime(2022, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        # Should have called for 2022, 2023, 2024
        assert mock_fetch.call_count == 3

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_data_fetcher_fetches_multiple_sites(self, mock_fetch, mock_data_df):
        """Should fetch data for each site."""
        mock_fetch.return_value = mock_data_df

        fetcher = make_data_fetcher("aurn")
        fetcher(
            sites=["MY1", "KC1"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        # Should have called for both sites
        assert mock_fetch.call_count == 2

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_data_fetcher_normalises_result(self, mock_fetch, mock_data_df):
        """Should normalise the fetched data."""
        mock_fetch.return_value = mock_data_df

        fetcher = make_data_fetcher("aurn")
        result = fetcher(
            sites=["MY1"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        # Should have normalised structure
        assert "site_code" in result.columns
        assert "measurand" in result.columns
        assert "value" in result.columns
        assert "source_network" in result.columns

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_data_fetcher_filters_date_range(self, mock_fetch, mock_data_df):
        """Should filter results to requested date range."""
        mock_fetch.return_value = mock_data_df

        fetcher = make_data_fetcher("aurn")
        result = fetcher(
            sites=["MY1"],
            start_date=datetime(2024, 1, 1, 0, 0),
            end_date=datetime(2024, 1, 1, 1, 0),
        )

        # Should only include data within range
        if not result.empty:
            assert result["date_time"].min() >= datetime(2024, 1, 1, 0, 0)
            assert result["date_time"].max() <= datetime(2024, 1, 1, 1, 0)

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_data_fetcher_handles_all_none(self, mock_fetch):
        """Should return empty DataFrame if all fetches return None."""
        mock_fetch.return_value = None

        fetcher = make_data_fetcher("aurn")
        result = fetcher(
            sites=["MY1"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_data_fetcher_uppercase_site_codes(self, mock_fetch, mock_data_df):
        """Should uppercase site codes in URL."""
        mock_fetch.return_value = mock_data_df

        fetcher = make_data_fetcher("aurn")
        fetcher(
            sites=["my1"],  # lowercase
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        expected_url = f"{DATA_BASE_URLS['aurn']}MY1_2024.RData"
        mock_fetch.assert_called_with(expected_url)


# ============================================================================
# Tests for Source Registration
# ============================================================================


class TestSourceRegistration:
    """Tests for source registration."""

    def test_aurn_registered(self):
        """AURN should be registered as a source."""
        from aeolus.registry import get_source

        source = get_source("AURN")
        assert source is not None
        assert source["type"] == "network"
        assert source["name"] == "AURN"
        assert source["requires_api_key"] is False
        assert callable(source["fetch_metadata"])
        assert callable(source["fetch_data"])

    def test_saqn_registered(self):
        """SAQN should be registered as a source."""
        from aeolus.registry import get_source

        source = get_source("SAQN")
        assert source is not None
        assert source["type"] == "network"

    def test_ni_registered(self):
        """NI should be registered as a source."""
        from aeolus.registry import get_source

        source = get_source("NI")
        assert source is not None
        assert source["type"] == "network"

    def test_waqn_registered(self):
        """WAQN should be registered as a source."""
        from aeolus.registry import get_source

        source = get_source("WAQN")
        assert source is not None
        assert source["type"] == "network"

    def test_aqe_registered(self):
        """AQE should be registered as a source."""
        from aeolus.registry import get_source

        source = get_source("AQE")
        assert source is not None
        assert source["type"] == "network"

    def test_local_registered(self):
        """LOCAL should be registered as a source."""
        from aeolus.registry import get_source

        source = get_source("LOCAL")
        assert source is not None
        assert source["type"] == "network"

    def test_lmam_registered(self):
        """LMAM should be registered as a source."""
        from aeolus.registry import get_source

        source = get_source("LMAM")
        assert source is not None
        assert source["type"] == "network"


# ============================================================================
# Tests for Configuration Constants
# ============================================================================


class TestConfiguration:
    """Tests for configuration constants."""

    def test_metadata_urls_all_networks(self):
        """Should have metadata URLs for all networks."""
        expected_networks = [
            "aurn",
            "saqn",
            "saqd",
            "ni",
            "waqn",
            "aqe",
            "local",
            "lmam",
        ]
        for network in expected_networks:
            assert network in METADATA_URLS
            assert METADATA_URLS[network].endswith(".RData")

    def test_data_base_urls_all_networks(self):
        """Should have data base URLs for all networks."""
        expected_networks = [
            "aurn",
            "saqn",
            "saqd",
            "ni",
            "waqn",
            "aqe",
            "local",
            "lmam",
        ]
        for network in expected_networks:
            assert network in DATA_BASE_URLS
            assert DATA_BASE_URLS[network].endswith("/")

    def test_regulatory_measurands_includes_common(self):
        """Should include common pollutants."""
        common = ["O3", "NO", "NO2", "SO2", "CO", "PM10", "PM2.5"]
        for pollutant in common:
            assert pollutant in REGULATORY_MEASURANDS


# ============================================================================
# Integration Tests with aeolus.download()
# ============================================================================


class TestIntegrationWithAeolus:
    """Tests for integration with main aeolus API."""

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_download_via_aeolus(self, mock_fetch, mock_data_df):
        """Should work with aeolus.download()."""
        import aeolus

        mock_fetch.return_value = mock_data_df

        result = aeolus.download(
            sources="AURN",
            sites=["MY1"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert isinstance(result, pd.DataFrame)
        if not result.empty:
            assert "site_code" in result.columns
            assert "source_network" in result.columns

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_networks_get_metadata(self, mock_fetch, mock_metadata_df):
        """Should work with aeolus.networks.get_metadata()."""
        import aeolus

        mock_fetch.return_value = mock_metadata_df

        result = aeolus.networks.get_metadata("AURN")

        assert isinstance(result, pd.DataFrame)
        if not result.empty:
            assert "site_code" in result.columns
            assert "source_network" in result.columns

    def test_list_networks_includes_regulatory(self):
        """Regulatory networks should appear in list_networks()."""
        import aeolus

        networks = aeolus.networks.list_networks()

        assert "AURN" in networks
        assert "SAQN" in networks
        assert "NI" in networks
        assert "WAQN" in networks
        assert "AQE" in networks
