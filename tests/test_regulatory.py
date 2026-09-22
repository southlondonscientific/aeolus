"""
Tests for UK Regulatory Network data sources (AURN, SAQN, etc.).

Tests the RData fetching, metadata and data normalisation, and factory
functions with mocked HTTP responses.
"""

from datetime import datetime, timezone
from unittest.mock import patch

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

    def test_normalise_data_drops_nan_values(self):
        """Dense RData wide tables melt empty hours to value=NaN; those rows
        must be dropped, not emitted — otherwise they dominate the output and
        inflate downstream data-capture / skew means."""
        raw = pd.DataFrame(
            {
                "site": ["London Marylebone Road", "London Marylebone Road"],
                "code": ["MY1", "MY1"],
                "date": [datetime(2024, 1, 1, 0, 0), datetime(2024, 1, 1, 1, 0)],
                "NO2": [45.2, float("nan")],  # second hour missing NO2
                "O3": [float("nan"), 28.3],   # first hour missing O3
            }
        )
        result = normalise_regulatory_data("AURN")(raw)
        assert result["value"].notna().all()
        assert len(result) == 2
        assert set(zip(result["measurand"], result["value"])) == {
            ("NO2", 45.2),
            ("O3", 28.3),
        }

    def test_normalise_data_renames_columns(self, mock_data_df):
        """Should rename site, code, date columns."""
        normaliser = normalise_regulatory_data("AURN")
        result = normaliser(mock_data_df)

        assert "site_code" in result.columns
        assert "date_time" in result.columns
        assert "site" not in result.columns
        assert "code" not in result.columns
        assert "date" not in result.columns
        # site_name is dropped (not in standard data schema)
        assert "site_name" not in result.columns

    def test_normalise_data_adds_metadata_columns(self, mock_data_df):
        """Should add source_network, ratification, units, created_at."""
        normaliser = normalise_regulatory_data("AURN")
        result = normaliser(mock_data_df)

        assert "source_network" in result.columns
        assert "ratification" in result.columns
        assert "units" in result.columns
        assert "created_at" in result.columns

        assert all(result["source_network"] == "AURN")
        # Non-CO measurands should be ug/m3
        assert all(result["units"] == "ug/m3")

    def test_normalise_data_co_units_are_mg_m3(self):
        """CO should be labelled mg/m3, not ug/m3."""
        df = pd.DataFrame(
            {
                "site": ["Site A"] * 2,
                "code": ["S1"] * 2,
                "date": [datetime(2024, 1, 1, 0, 0)] * 2,
                "NO2": [30.0, 30.0],
                "CO": [0.3, 0.3],
            }
        )
        normaliser = normalise_regulatory_data("AURN")
        result = normaliser(df)

        co = result[result["measurand"] == "CO"]
        no2 = result[result["measurand"] == "NO2"]
        assert all(co["units"] == "mg/m3")
        assert all(no2["units"] == "ug/m3")

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

    def test_normalise_data_standard_schema(self, mock_data_df):
        """Should produce the strict 8-column schema in ADAPTER_DATA_COLUMNS order."""
        from aeolus.types import ADAPTER_DATA_COLUMNS

        result = normalise_regulatory_data("AURN")(mock_data_df)
        assert list(result.columns) == ADAPTER_DATA_COLUMNS

    def test_make_metadata_fetcher_returns_callable(self):
        """Should return a callable function."""
        fetcher = make_metadata_fetcher("aurn")
        assert callable(fetcher)

    @patch("aeolus.sources.regulatory.fetch_rdata")
    def test_metadata_fetcher_calls_correct_url(self, mock_fetch, mock_metadata_df):
        """Should fetch from correct URL for each network."""
        mock_fetch.return_value = mock_metadata_df

        for network in ["aurn", "saqn", "ni", "waqn", "aqe"]:
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
        """Should return empty METADATA-schema DataFrame if fetch returns None.

        Must be the metadata schema (6 cols) not the data schema (8 cols) —
        otherwise multi-source find_sites() concat produces a mixed frame.
        """
        from aeolus.types import METADATA_COLUMNS

        mock_fetch.return_value = None

        fetcher = make_metadata_fetcher("aurn")
        result = fetcher()

        assert isinstance(result, pd.DataFrame)
        assert result.empty
        assert list(result.columns) == METADATA_COLUMNS


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
        mock_fetch.assert_any_call(expected_url)  # the metadata is fetched too

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

        # 2022, 2023, 2024 — plus one metadata fetch for the ratified_to join
        assert mock_fetch.call_count == 4

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

        # both sites, plus one metadata fetch for the ratified_to join
        assert mock_fetch.call_count == 3

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
            assert result["date_time"].min() >= datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
            assert result["date_time"].max() <= datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc)

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
        mock_fetch.assert_any_call(expected_url)  # the metadata is fetched too


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



# ============================================================================
# Tests for SOS-mapping cache invalidation
# ============================================================================


class TestLoadSosMappingCache:
    """The ``_sos_mapping`` module global must NOT latch to ``{}`` on a
    transient read error. Otherwise once the file is briefly unreadable
    (e.g. mid-rebuild) the process serves empty measurand lookups for the
    rest of its lifetime.
    """

    def test_cache_not_latched_on_missing_file(self, tmp_path, monkeypatch):
        from aeolus.sources import regulatory

        monkeypatch.setattr(regulatory, "_sos_mapping", None)
        missing = tmp_path / "nonexistent.json"
        monkeypatch.setattr(regulatory, "_SOS_MAPPING_PATH", missing)

        result1 = regulatory._load_sos_mapping()
        assert result1 == {}
        assert regulatory._sos_mapping is None, (
            "cache must remain None so next call retries the load"
        )

        # Simulate the file appearing (e.g. rebuild_sos_mapping completed).
        import json
        missing.write_text(json.dumps({"aurn": {"MY1": [{"ts_id": "100"}]}}))

        result2 = regulatory._load_sos_mapping()
        assert "aurn" in result2
        assert regulatory._sos_mapping is not None

    def test_cache_not_latched_on_corrupt_json(self, tmp_path, monkeypatch):
        from aeolus.sources import regulatory

        monkeypatch.setattr(regulatory, "_sos_mapping", None)
        bad = tmp_path / "_sos_mapping.json"
        bad.write_text("not valid json {{{")
        monkeypatch.setattr(regulatory, "_SOS_MAPPING_PATH", bad)

        result = regulatory._load_sos_mapping()
        assert result == {}
        assert regulatory._sos_mapping is None


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


# ============================================================================
# Live Integration Tests (require network access)
# ============================================================================


@pytest.mark.integration
class TestLiveIntegration:
    """
    Integration tests that hit the live UK regulatory data APIs.

    These tests are skipped by default. Run with:
        pytest -m integration tests/test_regulatory.py

    Note: These tests depend on external API availability and may be slow.
    The UK regulatory data is hosted on public servers and doesn't require API keys.
    """

    def test_live_aurn_metadata(self):
        """Test fetching live AURN metadata."""
        fetcher = make_metadata_fetcher("aurn")
        df = fetcher()

        assert not df.empty
        assert "site_code" in df.columns
        assert "site_name" in df.columns
        assert "latitude" in df.columns
        assert "longitude" in df.columns
        assert "source_network" in df.columns
        assert all(df["source_network"] == "AURN")

        # AURN should have many sites
        assert len(df) > 50

        # Coordinates should be in UK
        assert df["latitude"].min() > 49.0
        assert df["latitude"].max() < 61.0

    def test_live_saqn_metadata(self):
        """Test fetching live SAQN (Scotland) metadata."""
        fetcher = make_metadata_fetcher("saqn")
        df = fetcher()

        assert not df.empty
        assert "site_code" in df.columns
        assert all(df["source_network"] == "SAQN")

        # Scottish sites should be in northern UK
        assert df["latitude"].min() > 54.0

    def test_live_waqn_metadata(self):
        """Test fetching live WAQN (Wales) metadata."""
        fetcher = make_metadata_fetcher("waqn")
        df = fetcher()

        assert not df.empty
        assert "site_code" in df.columns
        assert all(df["source_network"] == "WAQN")

    def test_live_ni_metadata(self):
        """Test fetching live NI (Northern Ireland) metadata."""
        fetcher = make_metadata_fetcher("ni")
        df = fetcher()

        assert not df.empty
        assert "site_code" in df.columns
        assert all(df["source_network"] == "NI")

    def test_live_aurn_historical_data(self):
        """Test fetching historical AURN data."""
        fetcher = make_data_fetcher("aurn")

        # Fetch data for a well-known site (London Marylebone Road)
        # Use 2023 data which should be complete
        df = fetcher(
            sites=["MY1"],
            start_date=datetime(2023, 6, 1),
            end_date=datetime(2023, 6, 7),
        )

        assert not df.empty
        assert "site_code" in df.columns
        assert "date_time" in df.columns
        assert "measurand" in df.columns
        assert "value" in df.columns
        assert "units" in df.columns
        assert all(df["source_network"] == "AURN")

        # Should have multiple measurands
        measurands = df["measurand"].unique()
        assert len(measurands) >= 2

        # Values should be reasonable
        assert df["value"].min() >= 0
        assert df["value"].max() < 1000

    def test_live_aurn_multiple_sites(self):
        """Test fetching data for multiple AURN sites."""
        fetcher = make_data_fetcher("aurn")

        # MY1 = London Marylebone Road, KC1 = London N. Kensington
        df = fetcher(
            sites=["MY1", "KC1"],
            start_date=datetime(2023, 6, 1),
            end_date=datetime(2023, 6, 3),
        )

        assert not df.empty

        # Should have data from both sites
        sites = df["site_code"].unique()
        assert len(sites) == 2
        assert "MY1" in sites
        assert "KC1" in sites

    def test_live_aeolus_download_aurn(self):
        """Test the full aeolus.download() flow with AURN."""
        import aeolus

        df = aeolus.download(
            sources="AURN",
            sites=["MY1"],
            start_date=datetime(2023, 6, 1),
            end_date=datetime(2023, 6, 3),
        )

        assert not df.empty
        assert "site_code" in df.columns
        assert "measurand" in df.columns
        assert all(df["source_network"] == "AURN")

    def test_live_aeolus_networks_get_metadata(self):
        """Test aeolus.networks.get_metadata() with AURN."""
        import aeolus

        df = aeolus.networks.get_metadata("AURN")

        assert not df.empty
        assert "site_code" in df.columns
        assert "latitude" in df.columns
        assert "longitude" in df.columns

    def test_live_saqn_historical_data(self):
        """Test fetching historical SAQN data."""
        # First get a valid site code
        meta_fetcher = make_metadata_fetcher("saqn")
        metadata = meta_fetcher()

        if metadata.empty:
            pytest.skip("No SAQN metadata available")

        site_code = metadata["site_code"].iloc[0]

        fetcher = make_data_fetcher("saqn")
        df = fetcher(
            sites=[site_code],
            start_date=datetime(2023, 6, 1),
            end_date=datetime(2023, 6, 7),
        )

        # May be empty if site doesn't have data for this period
        if not df.empty:
            assert "site_code" in df.columns
            assert all(df["source_network"] == "SAQN")


# =========================================================================
# v0.5.0 QA wiring: ratified_to join
# =========================================================================

from datetime import date

from aeolus.sources import regulatory as reg


def _metadata_rdata(rows):
    """A metadata RData frame as fetch_rdata returns it."""
    return pd.DataFrame(rows, columns=["site_id", "site_name", "location_type", "latitude", "longitude",
                                       "parameter", "Parameter_name", "start_date", "end_date", "ratified_to",
                                       "zone", "agglomeration", "local_authority"])


def _data_rdata(hours, **values):
    base = pd.Timestamp("2024-01-01", tz="UTC")
    return pd.DataFrame({"date": [(base + pd.Timedelta(hours=h)).timestamp() for h in hours],
                         "site": "Marylebone Road", "code": "MY1", **values})


META = _metadata_rdata([
    ["MY1", "Marylebone Road", "Urban Traffic", 51.52, -0.15, "NO2", "Nitrogen dioxide", "1997-07-17", "ongoing", "2024-01-01", "", "", ""],
    ["MY1", "Marylebone Road", "Urban Traffic", 51.52, -0.15, "O3", "Ozone", "1997-07-17", "ongoing", "Never", "", "", ""],
])


class TestRatifiedToJoin:
    def _fetch(self, network, meta=META):
        def side_effect(url):
            return meta if url == reg.METADATA_URLS[network] else _data_rdata([0, 23, 24, 25], NO2=[1.0, 2.0, 3.0, 4.0], O3=[5.0] * 4, SO2=[6.0] * 4)
        with patch("aeolus.sources.regulatory.fetch_rdata", side_effect=side_effect):
            return reg.make_data_fetcher(network)(["MY1"], datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 3, tzinfo=timezone.utc))

    def test_rows_on_or_before_ratified_to_are_ratified(self):
        out = self._fetch("aurn")
        no2 = out[out["measurand"] == "NO2"].sort_values("date_time")
        assert no2["qa_code"].tolist() == ["verified", "verified", "unverified", "unverified"]

    def test_never_ratified_and_unknown_measurands(self):
        out = self._fetch("aurn")
        assert set(out.loc[out["measurand"] == "O3", "qa_code"]) == {"unverified"}   # "Never"
        assert out.loc[out["measurand"] == "SO2", "qa_code"].isna().all()           # not in metadata

    def test_other_uk_networks_use_their_own_tokens(self):
        out = self._fetch("aqe")
        no2 = out[out["measurand"] == "NO2"].sort_values("date_time")
        assert no2["qa_code"].tolist() == ["Ratified", "Ratified", "Provisional", "Provisional"]

    def test_wired_adapter_columns(self):
        from aeolus.types import ADAPTER_DATA_COLUMNS_QA

        assert list(self._fetch("aurn").columns) == ADAPTER_DATA_COLUMNS_QA

    def test_unwired_networks_have_no_qa_column(self):
        with patch("aeolus.sources.regulatory.fetch_rdata", return_value=_data_rdata([0, 1], NO2=[1.0, 2.0])):
            out = reg.make_data_fetcher("lmam")(["AD1"], datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 2, tzinfo=timezone.utc))
        assert "qa_code" not in out.columns

    def test_lookup_is_not_cached_when_metadata_is_unavailable(self):
        with patch("aeolus.sources.regulatory.fetch_rdata", return_value=None):
            assert reg._ratified_to_lookup("aurn") == {}
        with patch("aeolus.sources.regulatory.fetch_rdata", return_value=META):
            assert reg._ratified_to_lookup("aurn")[("MY1", "NO2")] == date(2024, 1, 1)
            assert reg._ratified_to_lookup("aurn")[("MY1", "O3")] is None

    def test_end_to_end_tier_and_mirror(self):
        import aeolus

        def side_effect(url):
            return META if url == reg.METADATA_URLS["aurn"] else _data_rdata([0, 25], NO2=[1.0, 2.0])
        with patch("aeolus.sources.regulatory.fetch_rdata", side_effect=side_effect):
            out = aeolus.download("AURN", ["MY1"], datetime(2024, 1, 1), datetime(2024, 1, 3)).sort_values("date_time")
        assert out["qa_tier"].tolist() == ["reference_full_qc", "reference_provisional"]
        assert out["ratification_stage"].tolist() == ["ratified", "unratified"]
        assert out["ratification"].tolist() == ["Ratified", "Provisional"]


class TestRatifiedToJoinReviewFixes:
    """PR #16 review: silent failures, non-date values, empties, the mirror, refresh."""

    def _run(self, network, meta_response, data_hours=(0, 25)):
        def side_effect(url):
            if url == reg.METADATA_URLS[network]:
                return meta_response
            return _data_rdata(list(data_hours), NO2=[1.0] * len(data_hours))
        with patch("aeolus.sources.regulatory.fetch_rdata", side_effect=side_effect):
            return reg.make_data_fetcher(network)(["MY1"], datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 3, tzinfo=timezone.utc))

    def test_metadata_unavailable_warns_and_yields_null_codes(self):
        from aeolus.types import AeolusDataWarning

        with pytest.warns(AeolusDataWarning, match="ratification"):
            out = self._run("aurn", None)
        assert out["qa_code"].isna().all()

    @pytest.mark.parametrize("value", [pd.NA, None, "", "ongoing", "not-a-date"])
    def test_non_date_ratified_to_is_unknown_not_never(self, value):
        meta = _metadata_rdata([["MY1", "Marylebone Road", "Urban Traffic", 51.52, -0.15, "NO2", "Nitrogen dioxide", "1997-07-17", "ongoing", value, "", "", ""]])
        out = self._run("aurn", meta)
        assert out["qa_code"].isna().all(), "only the literal 'Never' means never-ratified"

    def test_literal_never_is_unratified(self):
        out = self._run("aurn", META)
        assert set(out.loc[out["measurand"] == "NO2", "qa_code"]) <= {"verified", "unverified"}

    def test_empty_result_carries_the_qa_column(self):
        from aeolus.types import ADAPTER_DATA_COLUMNS_QA

        with patch("aeolus.sources.regulatory.fetch_rdata", return_value=None), pytest.warns(Warning):
            out = reg.make_data_fetcher("aurn")(["MY1"], datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 2, tzinfo=timezone.utc))
        assert out.empty and list(out.columns) == ADAPTER_DATA_COLUMNS_QA

    def test_adapter_mirror_equals_the_public_mirror(self):
        out = self._run("aurn", META).sort_values("date_time")
        assert out["ratification"].tolist() == ["Ratified", "Provisional"]

    def test_lookup_refreshes_after_ttl(self, monkeypatch):
        monkeypatch.setattr(reg, "_METADATA_TTL_S", 0)
        with patch("aeolus.sources.regulatory.fetch_rdata", return_value=META) as mock_fetch:
            reg._ratified_to_lookup("aurn")
            reg._ratified_to_lookup("aurn")
        assert mock_fetch.call_count == 2

    def test_find_sites_and_the_join_share_one_metadata_download(self):
        with patch("aeolus.sources.regulatory.fetch_rdata", return_value=META) as mock_fetch:
            reg.make_metadata_fetcher("aurn")()
            reg._ratified_to_lookup("aurn")
        assert mock_fetch.call_count == 1


class TestClosedSitesAreNotListed:
    """openair's importMeta(all=FALSE) lists only sites still open; so does find_sites()."""

    def _meta(self, end_dates):
        return pd.DataFrame({
            "site_id": ["MY1", "MY1", "ISL", "ISL", "WA2"],
            "site_name": ["Marylebone", "Marylebone", "Islington", "Islington", "Wandsworth"],
            "latitude": [51.5] * 5, "longitude": [-0.1] * 5,
            "site_type": ["Urban Traffic"] * 5, "local_authority": ["x"] * 5,
            "start_date": ["1997-01-01"] * 5, "end_date": end_dates,
            "parameter": ["NO2", "O3", "SO2", "NO2", "NO2"], "Parameter_name": ["n"] * 5,
        })

    def test_sites_whose_every_parameter_has_ended_are_dropped(self):
        from aeolus.sources.regulatory import normalise_regulatory_metadata

        out = normalise_regulatory_metadata("aurn")(self._meta(["ongoing", "2015-12-31", "1978-10-11", "1978-10-11", "2007-09-30"]))
        assert set(out["site_code"]) == {"MY1"}

    def test_blank_or_missing_end_dates_count_as_open(self):
        from aeolus.sources.regulatory import normalise_regulatory_metadata

        out = normalise_regulatory_metadata("aurn")(self._meta([None, None, "", float("nan"), "2007-09-30"]))
        assert set(out["site_code"]) == {"MY1", "ISL"}

    def test_a_future_end_date_is_still_open(self):
        from aeolus.sources.regulatory import normalise_regulatory_metadata

        out = normalise_regulatory_metadata("aurn")(self._meta(["ongoing", "ongoing", "2999-01-01", "2999-01-01", "2007-09-30"]))
        assert set(out["site_code"]) == {"MY1", "ISL"}

    def test_include_closed_keeps_everything(self):
        from aeolus.sources.regulatory import normalise_regulatory_metadata

        out = normalise_regulatory_metadata("aurn", include_closed=True)(self._meta(["ongoing", "ongoing", "1978-10-11", "1978-10-11", "2007-09-30"]))
        assert set(out["site_code"]) == {"MY1", "ISL", "WA2"}

    def test_one_row_per_site(self):
        """The openair metadata has one row per site-parameter; find_sites() wants one per site."""
        from aeolus.sources.regulatory import normalise_regulatory_metadata

        out = normalise_regulatory_metadata("aurn")(self._meta(["ongoing"] * 5))
        assert out["site_code"].tolist() == ["MY1", "ISL", "WA2"]

    def test_site_dates_are_aggregated_not_taken_from_the_first_row(self):
        """An open site whose first-listed parameter has ended must still read as open."""
        from aeolus.sources.regulatory import normalise_regulatory_metadata

        meta = self._meta(["2015-12-31", "ongoing", "1978-10-11", "1978-10-11", "ongoing"])
        meta["start_date"] = ["2000-01-01", "1997-01-01", "1976-07-09", "1976-07-09", "1996-04-01"]
        meta["ratified_to"] = ["2015-12-31", "2025-06-30", "1978-10-11", "1978-10-11", "2025-06-30"]
        out = normalise_regulatory_metadata("aurn")(meta).set_index("site_code")
        assert out.loc["MY1", "end_date"] == "ongoing" and out.loc["MY1", "start_date"] == "1997-01-01"
        assert out.loc["WA2", "end_date"] == "ongoing"
        assert "ratified_to" not in out.columns  # per parameter, meaningless per site

    def test_closed_site_keeps_its_last_end_date(self):
        from aeolus.sources.regulatory import normalise_regulatory_metadata

        out = normalise_regulatory_metadata("aurn", include_closed=True)(self._meta(["ongoing", "ongoing", "1978-08-01", "1978-10-11", "2007-09-30"])).set_index("site_code")
        assert out.loc["ISL", "end_date"] == "1978-10-11"

    def test_a_site_ending_today_is_still_open(self):
        from aeolus.sources.regulatory import normalise_regulatory_metadata

        today = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
        out = normalise_regulatory_metadata("aurn")(self._meta(["ongoing", "ongoing", today, today, "2007-09-30"]))
        assert set(out["site_code"]) == {"MY1", "ISL"}

    @pytest.mark.filterwarnings("error::UserWarning")
    def test_ongoing_first_does_not_provoke_a_pandas_format_warning(self):
        from aeolus.sources.regulatory import normalise_regulatory_metadata

        out = normalise_regulatory_metadata("aurn")(self._meta(["ongoing", "2015-12-31 00:00:00", "1978-10-11", "1978-10-11", "2007-09-30"]))
        assert set(out["site_code"]) == {"MY1"}

    def test_include_closed_is_reachable_through_get_metadata_and_find_sites(self):
        import aeolus
        from aeolus.sources import regulatory

        meta = self._meta(["ongoing", "ongoing", "1978-10-11", "1978-10-11", "2007-09-30"])
        with patch.object(regulatory, "_raw_metadata", return_value=meta):
            assert set(aeolus.networks.get_metadata("AURN")["site_code"]) == {"MY1"}
            assert set(aeolus.networks.get_metadata("AURN", include_closed=True)["site_code"]) == {"MY1", "ISL", "WA2"}
            assert set(aeolus.find_sites("AURN", include_closed=True)["site_code"]) == {"MY1", "ISL", "WA2"}
