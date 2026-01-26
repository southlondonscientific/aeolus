# Aeolus: download UK and standardise air quality data
# Copyright (C) 2025 Ruaraidh Dobson, South London Scientific

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Tests for the main public API (api.py).

These tests verify the top-level download() function with its smart routing
and various input patterns.
"""

from datetime import datetime

import pandas as pd
import pytest

from aeolus import api
from aeolus.registry import clear_registry, register_source

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_registry():
    """Clear registry before and after each test."""
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def mock_network_fetcher():
    """Mock data fetcher for network sources."""

    def fetch_data(sites, start_date, end_date):
        data = []
        for site in sites:
            data.append(
                {
                    "site_code": site,
                    "date_time": start_date,
                    "measurand": "NO2",
                    "value": 42.0,
                    "units": "ug/m3",
                    "source_network": "TEST_NETWORK",
                    "ratification": "Validated",
                    "created_at": datetime.now(),
                }
            )
        return pd.DataFrame(data)

    return fetch_data


@pytest.fixture
def mock_portal_fetcher():
    """Mock data fetcher for portal sources."""

    def fetch_data(location_ids, start_date, end_date):
        data = []
        for loc_id in location_ids:
            data.append(
                {
                    "site_code": loc_id,
                    "date_time": start_date,
                    "measurand": "PM2.5",
                    "value": 15.0,
                    "units": "ug/m3",
                    "source_network": "TEST_PORTAL",
                    "ratification": "Unvalidated",
                    "created_at": datetime.now(),
                }
            )
        return pd.DataFrame(data)

    return fetch_data


@pytest.fixture
def register_test_network(mock_network_fetcher):
    """Register a test network source."""
    register_source(
        "TEST_NETWORK",
        {
            "type": "network",
            "name": "Test Network",
            "fetch_data": mock_network_fetcher,
            "fetch_metadata": lambda **kw: pd.DataFrame(),
            "requires_api_key": False,
        },
    )


@pytest.fixture
def register_test_portal(mock_portal_fetcher):
    """Register a test portal source."""
    register_source(
        "TEST_PORTAL",
        {
            "type": "portal",
            "name": "Test Portal",
            "fetch_data": mock_portal_fetcher,
            "search": lambda **kw: pd.DataFrame(),
            "requires_api_key": True,
        },
    )


@pytest.fixture
def register_both_sources(register_test_network, register_test_portal):
    """Register both test network and portal."""
    pass


@pytest.fixture
def test_dates():
    """Common test date range."""
    return {
        "start_date": datetime(2024, 1, 1),
        "end_date": datetime(2024, 1, 31),
    }


# ============================================================================
# list_sources() Tests
# ============================================================================


def test_list_sources_empty_registry():
    """Test list_sources returns empty list when no sources registered."""
    result = api.list_sources()
    assert isinstance(result, list)
    assert len(result) == 0


def test_list_sources_with_registered_sources(register_both_sources):
    """Test list_sources returns all registered sources."""
    result = api.list_sources()
    assert isinstance(result, list)
    assert "TEST_NETWORK" in result
    assert "TEST_PORTAL" in result
    assert len(result) == 2


# ============================================================================
# download() - Single Source Tests
# ============================================================================


def test_download_single_network_success(register_test_network, test_dates):
    """Test successful download from a single network."""
    result = api.download(
        "TEST_NETWORK",
        ["SITE1", "SITE2"],
        start_date=test_dates["start_date"],
        end_date=test_dates["end_date"],
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert "site_code" in result.columns
    assert "measurand" in result.columns
    assert result["site_code"].tolist() == ["SITE1", "SITE2"]
    assert all(result["measurand"] == "NO2")


def test_download_single_portal_success(register_test_portal, test_dates):
    """Test successful download from a single portal."""
    result = api.download(
        "TEST_PORTAL",
        ["LOC1", "LOC2"],
        start_date=test_dates["start_date"],
        end_date=test_dates["end_date"],
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert "site_code" in result.columns
    assert result["site_code"].tolist() == ["LOC1", "LOC2"]
    assert all(result["measurand"] == "PM2.5")


def test_download_single_source_missing_sites(register_test_network, test_dates):
    """Test download with string source but missing sites parameter."""
    with pytest.raises(ValueError, match="sites parameter required"):
        api.download(
            "TEST_NETWORK",
            start_date=test_dates["start_date"],
            end_date=test_dates["end_date"],
        )


def test_download_single_source_missing_dates(register_test_network):
    """Test download with missing start_date or end_date."""
    with pytest.raises(ValueError, match="start_date and end_date are required"):
        api.download("TEST_NETWORK", ["SITE1"])

    with pytest.raises(ValueError, match="start_date and end_date are required"):
        api.download("TEST_NETWORK", ["SITE1"], start_date=datetime(2024, 1, 1))

    with pytest.raises(ValueError, match="start_date and end_date are required"):
        api.download("TEST_NETWORK", ["SITE1"], end_date=datetime(2024, 1, 31))


def test_download_unknown_source(test_dates):
    """Test download with unknown source name."""
    with pytest.raises(ValueError, match="Unknown source: UNKNOWN"):
        api.download(
            "UNKNOWN",
            ["SITE1"],
            start_date=test_dates["start_date"],
            end_date=test_dates["end_date"],
        )


# ============================================================================
# download() - Multiple Sources Tests
# ============================================================================


def test_download_multiple_sources_dict_success(register_both_sources, test_dates):
    """Test successful download from multiple sources using dict."""
    result = api.download(
        {
            "TEST_NETWORK": ["SITE1", "SITE2"],
            "TEST_PORTAL": ["LOC1"],
        },
        start_date=test_dates["start_date"],
        end_date=test_dates["end_date"],
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 3  # 2 from network + 1 from portal
    assert "site_code" in result.columns
    assert set(result["site_code"]) == {"SITE1", "SITE2", "LOC1"}


def test_download_multiple_sources_dict_no_combine(register_both_sources, test_dates):
    """Test multiple sources download with combine=False returns dict."""
    result = api.download(
        {
            "TEST_NETWORK": ["SITE1"],
            "TEST_PORTAL": ["LOC1"],
        },
        start_date=test_dates["start_date"],
        end_date=test_dates["end_date"],
        combine=False,
    )

    assert isinstance(result, dict)
    assert "TEST_NETWORK" in result
    assert "TEST_PORTAL" in result
    assert isinstance(result["TEST_NETWORK"], pd.DataFrame)
    assert isinstance(result["TEST_PORTAL"], pd.DataFrame)
    assert len(result["TEST_NETWORK"]) == 1
    assert len(result["TEST_PORTAL"]) == 1


def test_download_multiple_sources_dict_with_sites_param_fails(
    register_both_sources, test_dates
):
    """Test that passing sites param with dict raises helpful error."""
    with pytest.raises(ValueError, match="When sources is a dict, sites are specified"):
        api.download(
            {"TEST_NETWORK": ["SITE1"]},
            sites=["SITE2"],  # This should fail
            start_date=test_dates["start_date"],
            end_date=test_dates["end_date"],
        )


def test_download_multiple_sources_with_unknown_source(
    register_test_network, test_dates
):
    """Test multiple sources download skips unknown sources with warning."""
    with pytest.warns(UserWarning, match="Unknown source 'UNKNOWN', skipping"):
        result = api.download(
            {
                "TEST_NETWORK": ["SITE1"],
                "UNKNOWN": ["SITE2"],
            },
            start_date=test_dates["start_date"],
            end_date=test_dates["end_date"],
        )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1  # Only TEST_NETWORK should succeed
    assert result["site_code"].iloc[0] == "SITE1"


def test_download_multiple_sources_all_fail_returns_empty(test_dates):
    """Test that when all sources fail, empty DataFrame is returned."""
    result = api.download(
        {
            "UNKNOWN1": ["SITE1"],
            "UNKNOWN2": ["SITE2"],
        },
        start_date=test_dates["start_date"],
        end_date=test_dates["end_date"],
    )

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_download_multiple_sources_handles_partial_failures(
    register_test_network, test_dates
):
    """Test that partial failures are handled gracefully."""

    # Register a source that will fail
    def failing_fetcher(sites, start_date, end_date):
        raise RuntimeError("Simulated failure")

    register_source(
        "FAILING_SOURCE",
        {
            "type": "network",
            "name": "Failing Source",
            "fetch_data": failing_fetcher,
            "fetch_metadata": lambda **kw: pd.DataFrame(),
            "requires_api_key": False,
        },
    )

    with pytest.warns(UserWarning, match="Failed to download from FAILING_SOURCE"):
        result = api.download(
            {
                "TEST_NETWORK": ["SITE1"],
                "FAILING_SOURCE": ["SITE2"],
            },
            start_date=test_dates["start_date"],
            end_date=test_dates["end_date"],
        )

    # Should still get data from TEST_NETWORK
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result["site_code"].iloc[0] == "SITE1"


def test_download_multiple_sources_no_combine_includes_empty_dfs(
    register_test_network, test_dates
):
    """Test that combine=False includes empty DataFrames for failed sources."""

    def failing_fetcher(sites, start_date, end_date):
        raise RuntimeError("Simulated failure")

    register_source(
        "FAILING_SOURCE",
        {
            "type": "network",
            "name": "Failing Source",
            "fetch_data": failing_fetcher,
            "fetch_metadata": lambda **kw: pd.DataFrame(),
            "requires_api_key": False,
        },
    )

    with pytest.warns(UserWarning):
        result = api.download(
            {
                "TEST_NETWORK": ["SITE1"],
                "FAILING_SOURCE": ["SITE2"],
            },
            start_date=test_dates["start_date"],
            end_date=test_dates["end_date"],
            combine=False,
        )

    assert isinstance(result, dict)
    assert "TEST_NETWORK" in result
    assert "FAILING_SOURCE" in result
    assert not result["TEST_NETWORK"].empty
    assert result["FAILING_SOURCE"].empty


# ============================================================================
# download() - Error Cases
# ============================================================================


def test_download_list_of_sources_raises_helpful_error(test_dates):
    """Test that list of sources raises helpful error (old API pattern)."""
    with pytest.raises(
        ValueError, match="Multiple sources require explicit site mapping"
    ):
        api.download(
            ["SOURCE1", "SOURCE2"],  # List not supported
            start_date=test_dates["start_date"],
            end_date=test_dates["end_date"],
        )


def test_download_invalid_type_raises_type_error(test_dates):
    """Test that invalid sources type raises TypeError."""
    with pytest.raises(TypeError, match="sources must be str or dict"):
        api.download(
            12345,  # Invalid type
            start_date=test_dates["start_date"],
            end_date=test_dates["end_date"],
        )


def test_download_unknown_source_type_raises_error(test_dates):
    """Test that source with unknown type raises error."""
    register_source(
        "WEIRD_SOURCE",
        {
            "type": "weird_type",  # Invalid type
            "name": "Weird Source",
            "fetch_data": lambda *args: pd.DataFrame(),
            "requires_api_key": False,
        },
    )

    with pytest.raises(ValueError, match="Unknown source type: weird_type"):
        api.download(
            "WEIRD_SOURCE",
            ["SITE1"],
            start_date=test_dates["start_date"],
            end_date=test_dates["end_date"],
        )


# ============================================================================
# get_source_info() Tests
# ============================================================================


def test_get_source_info_network(register_test_network):
    """Test get_source_info for a network source."""
    info = api.get_source_info("TEST_NETWORK")

    assert isinstance(info, dict)
    assert info["name"] == "Test Network"
    assert info["type"] == "network"
    assert info["requires_api_key"] is False


def test_get_source_info_portal(register_test_portal):
    """Test get_source_info for a portal source."""
    info = api.get_source_info("TEST_PORTAL")

    assert isinstance(info, dict)
    assert info["name"] == "Test Portal"
    assert info["type"] == "portal"
    assert info["requires_api_key"] is True


def test_get_source_info_unknown_source():
    """Test get_source_info with unknown source raises ValueError."""
    with pytest.raises(ValueError, match="Source 'UNKNOWN' not found"):
        api.get_source_info("UNKNOWN")


def test_get_source_info_lists_available_sources(register_test_network):
    """Test that error message lists available sources."""
    with pytest.raises(ValueError, match="Available sources"):
        api.get_source_info("UNKNOWN")


# ============================================================================
# fetch() Alias Tests
# ============================================================================


def test_fetch_alias_works(register_test_network, test_dates):
    """Test that fetch() alias works identically to download()."""
    result = api.fetch(
        "TEST_NETWORK",
        ["SITE1"],
        start_date=test_dates["start_date"],
        end_date=test_dates["end_date"],
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result["site_code"].iloc[0] == "SITE1"


def test_fetch_alias_accepts_kwargs(register_test_network, test_dates):
    """Test that fetch() accepts and passes through kwargs."""
    result = api.fetch(
        "TEST_NETWORK",
        ["SITE1"],
        start_date=test_dates["start_date"],
        end_date=test_dates["end_date"],
        combine=True,
    )

    assert isinstance(result, pd.DataFrame)


# ============================================================================
# Integration Tests
# ============================================================================


def test_download_empty_sites_list(register_test_network, test_dates):
    """Test download with empty sites list returns empty DataFrame."""
    result = api.download(
        "TEST_NETWORK",
        [],
        start_date=test_dates["start_date"],
        end_date=test_dates["end_date"],
    )

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_download_single_site(register_test_network, test_dates):
    """Test download with single site in list."""
    result = api.download(
        "TEST_NETWORK",
        ["SITE1"],
        start_date=test_dates["start_date"],
        end_date=test_dates["end_date"],
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result["site_code"].iloc[0] == "SITE1"


def test_download_multiple_sources_empty_all_combined(test_dates):
    """Test that combining multiple empty DataFrames returns empty DataFrame."""
    result = api.download(
        {
            "UNKNOWN1": ["SITE1"],
            "UNKNOWN2": ["SITE2"],
        },
        start_date=test_dates["start_date"],
        end_date=test_dates["end_date"],
        combine=True,
    )

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_download_preserves_data_types(register_test_network, test_dates):
    """Test that download preserves expected data types."""
    result = api.download(
        "TEST_NETWORK",
        ["SITE1"],
        start_date=test_dates["start_date"],
        end_date=test_dates["end_date"],
    )

    assert isinstance(result["site_code"].iloc[0], str)
    assert isinstance(result["value"].iloc[0], float)
    assert isinstance(result["measurand"].iloc[0], str)


def test_download_date_range_validation(register_test_network):
    """Test that dates are passed through correctly."""
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 31)

    result = api.download("TEST_NETWORK", ["SITE1"], start_date=start, end_date=end)

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    # The mock fetcher sets date_time to start_date
    assert result["date_time"].iloc[0] == start
