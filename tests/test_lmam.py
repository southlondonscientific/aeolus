# Tests for the LMAM (Locally-Managed Automatic Monitoring) data source.

from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
import pytest

import aeolus.sources.lmam as lmam_module
from aeolus.sources.lmam import (
    DATA_PROVIDER_CODES,
    _normalise_lmam_metadata,
    fetch_lmam_data,
    fetch_lmam_metadata,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_pcode_cache():
    """Each test gets a fresh pcode cache so ordering doesn't matter."""
    lmam_module._pcode_cache = None
    yield
    lmam_module._pcode_cache = None


@pytest.fixture
def mock_lmam_metadata_df():
    """Mock raw LMAM metadata as returned from the openair RData feed.

    Mirrors the real (site, parameter, instrument-period) row structure:
    one site can have several rows per parameter for different measurement
    periods. Includes one site whose pcode has no published data files
    (``london``) — should be filtered out at normalisation time.
    """
    return pd.DataFrame({
        "site_id":   ["AD1", "AD1", "AD1", "AD1", "ZY3", "ZY3", "MY1"],
        "site_name": ["Adur"] * 4 + ["Kent A"] * 2 + ["Marylebone Rd"],
        "location_type": ["Urban Traffic"] * 4 + ["Urban Background"] * 2 + ["Kerbside"],
        "latitude":  [50.832] * 4 + [51.27] * 2 + [51.52],
        "longitude": [-0.277] * 4 + [0.5] * 2 + [-0.15],
        "parameter": ["NO2", "NO2", "PM10", "PM2.5", "NO2", "O3", "NO2"],
        "Parameter_name": ["x"] * 7,
        "start_date": ["2014-04-28"] * 7,
        "end_date":   ["ongoing"] * 7,
        "zone":       ["South East"] * 4 + ["South East"] * 2 + ["London"],
        "agglomeration": ["Brighton"] * 4 + ["Medway"] * 2 + ["Greater London"],
        "provider":   ["Sussex AQ Network"] * 4
                    + ["Kent and Medway"] * 2
                    + ["Londonair"],
        "pcode":      ["sussex"] * 4 + ["kent"] * 2 + ["london"],
    })


@pytest.fixture
def mock_lmam_site_rdata_df():
    """Mock per-site, per-year RData frame — schema identical to AURN
    (the LMAM data files use the same openair conventions)."""
    base = 1704067200.0  # 2024-01-01 UTC
    return pd.DataFrame({
        "date":     [base, base + 3600, base + 7200],
        "NO":       [27.4, 6.7, 12.1],
        "NO2":      [8.6, 4.3, 5.5],
        "NOXasNO2": [50.0, 14.5, 24.0],
        "PM2.5":    [6.0, 3.0, 4.5],
        "site":     ["Adur"] * 3,
        "code":     ["AD1"] * 3,
    })


# ============================================================================
# Metadata normalisation
# ============================================================================


class TestMetadataNormalisation:
    """The raw LMAM metadata has one row per (site, parameter,
    instrument-period). The normaliser must collapse these into one row
    per site with a `measurands` list, and filter out provider codes
    whose data files do not exist on the server."""

    def test_collapses_to_one_row_per_site(self, mock_lmam_metadata_df):
        result = _normalise_lmam_metadata(mock_lmam_metadata_df)
        # 1 LMAM site (AD1) + 1 LMAM site (ZY3); MY1 (london) is filtered out.
        assert len(result) == 2
        assert set(result["site_code"]) == {"AD1", "ZY3"}

    def test_measurands_aggregated_and_deduped(self, mock_lmam_metadata_df):
        result = _normalise_lmam_metadata(mock_lmam_metadata_df)
        ad1 = result[result["site_code"] == "AD1"].iloc[0]
        assert set(ad1["measurands"].split(",")) == {"NO2", "PM10", "PM2.5"}

    def test_filters_out_unsupported_pcodes(self, mock_lmam_metadata_df):
        """`london` has no per-site RData files on the LMAM server; sites
        with that pcode must not appear in the metadata output."""
        result = _normalise_lmam_metadata(mock_lmam_metadata_df)
        assert "MY1" not in result["site_code"].values

    def test_only_supported_pcodes_in_output(self, mock_lmam_metadata_df):
        result = _normalise_lmam_metadata(mock_lmam_metadata_df)
        assert set(result["pcode"]).issubset(DATA_PROVIDER_CODES)

    def test_source_network_is_lmam(self, mock_lmam_metadata_df):
        result = _normalise_lmam_metadata(mock_lmam_metadata_df)
        assert (result["source_network"] == "LMAM").all()

    def test_drops_sites_with_missing_coordinates(self):
        df = pd.DataFrame({
            "site_id": ["A", "B"],
            "site_name": ["A site", "B site"],
            "location_type": ["x", "y"],
            "latitude": [50.0, None],
            "longitude": [-0.5, -0.6],
            "parameter": ["NO2", "NO2"],
            "Parameter_name": ["x", "y"],
            "start_date": ["2020-01-01", "2020-01-01"],
            "end_date": ["ongoing", "ongoing"],
            "zone": ["x", "y"],
            "agglomeration": ["x", "y"],
            "provider": ["Sussex", "Sussex"],
            "pcode": ["sussex", "sussex"],
        })
        result = _normalise_lmam_metadata(df)
        assert len(result) == 1
        assert result["site_code"].iloc[0] == "A"


# ============================================================================
# Metadata fetch
# ============================================================================


class TestFetchMetadata:
    @patch("aeolus.sources.lmam.fetch_rdata")
    def test_warns_on_fetch_failure(self, mock_fetch):
        mock_fetch.return_value = None
        with pytest.warns(match="Failed to fetch LMAM metadata"):
            result = fetch_lmam_metadata()
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("aeolus.sources.lmam.fetch_rdata")
    def test_warns_on_no_usable_sites(self, mock_fetch):
        # Empty (well-formed) frame — no sites at all.
        mock_fetch.return_value = pd.DataFrame(columns=[
            "site_id", "site_name", "location_type", "latitude", "longitude",
            "parameter", "Parameter_name", "start_date", "end_date",
            "zone", "agglomeration", "provider", "pcode",
        ])
        with pytest.warns(match="no usable sites"):
            result = fetch_lmam_metadata()
        assert result.empty

    @patch("aeolus.sources.lmam.fetch_rdata")
    def test_populates_pcode_cache(self, mock_fetch, mock_lmam_metadata_df):
        mock_fetch.return_value = mock_lmam_metadata_df
        fetch_lmam_metadata()
        assert lmam_module._pcode_cache == {"AD1": "sussex", "ZY3": "kent"}


# ============================================================================
# Data fetch — URL construction with pcode subfolder
# ============================================================================


class TestFetchData:

    @patch("aeolus.sources.regulatory.fetch_rdata")
    @patch("aeolus.sources.lmam.fetch_rdata")
    def test_url_includes_pcode_subfolder(
        self, mock_meta_fetch, mock_data_fetch,
        mock_lmam_metadata_df, mock_lmam_site_rdata_df,
    ):
        """LMAM URLs must look like
        ``LMAM/R_data/{pcode}/{SITE}_{YEAR}.RData``."""
        mock_meta_fetch.return_value = mock_lmam_metadata_df
        mock_data_fetch.return_value = mock_lmam_site_rdata_df

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        fetch_lmam_data(["AD1"], start, end)

        urls_called = [c.args[0] for c in mock_data_fetch.call_args_list]
        assert urls_called == [
            "https://uk-air.defra.gov.uk/openair/LMAM/R_data/sussex/AD1_2024.RData"
        ]

    @patch("aeolus.sources.regulatory.fetch_rdata")
    @patch("aeolus.sources.lmam.fetch_rdata")
    def test_uses_correct_pcode_per_site(
        self, mock_meta_fetch, mock_data_fetch,
        mock_lmam_metadata_df, mock_lmam_site_rdata_df,
    ):
        """Different sites should resolve to different pcode subfolders."""
        mock_meta_fetch.return_value = mock_lmam_metadata_df
        mock_data_fetch.return_value = mock_lmam_site_rdata_df

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        fetch_lmam_data(["AD1", "ZY3"], start, end)

        urls_called = [c.args[0] for c in mock_data_fetch.call_args_list]
        assert any("/sussex/AD1_2024.RData" in u for u in urls_called)
        assert any("/kent/ZY3_2024.RData" in u for u in urls_called)

    @patch("aeolus.sources.regulatory.fetch_rdata")
    @patch("aeolus.sources.lmam.fetch_rdata")
    def test_unknown_site_warns_and_skips(
        self, mock_meta_fetch, mock_data_fetch,
        mock_lmam_metadata_df,
    ):
        """A site not present in metadata must be skipped with a warning,
        not silently 404."""
        mock_meta_fetch.return_value = mock_lmam_metadata_df
        mock_data_fetch.return_value = None

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        with pytest.warns(match="not found in metadata"):
            fetch_lmam_data(["UNKNOWN_SITE"], start, end)

        # Data fetch should never have been attempted for the unknown site.
        urls_called = [c.args[0] for c in mock_data_fetch.call_args_list]
        assert not any("UNKNOWN_SITE" in u for u in urls_called)

    @patch("aeolus.sources.regulatory.fetch_rdata")
    @patch("aeolus.sources.lmam.fetch_rdata")
    def test_returns_standard_data_columns(
        self, mock_meta_fetch, mock_data_fetch,
        mock_lmam_metadata_df, mock_lmam_site_rdata_df,
    ):
        mock_meta_fetch.return_value = mock_lmam_metadata_df
        mock_data_fetch.return_value = mock_lmam_site_rdata_df

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        result = fetch_lmam_data(["AD1"], start, end)

        from aeolus.types import DATA_COLUMNS
        for col in DATA_COLUMNS:
            assert col in result.columns
        assert (result["source_network"] == "LMAM").all()


# ============================================================================
# Source registration
# ============================================================================


class TestRegistration:
    def test_lmam_registered(self):
        from aeolus.registry import get_source
        source = get_source("LMAM")
        assert source is not None
        assert source["type"] == "network"
        assert source["requires_api_key"] is False
