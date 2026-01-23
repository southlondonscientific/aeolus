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
Tests for networks and portals API modules.

These tests verify the new networks/portals architecture introduced in 0.2.0.
"""

from datetime import datetime

import pandas as pd
import pytest

from aeolus.networks import api as networks_api
from aeolus.portals import api as portals_api
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
def mock_network_metadata():
    """Mock network metadata function."""

    def fetch_metadata(**filters):
        return pd.DataFrame(
            {
                "site_code": ["SITE1", "SITE2", "SITE3"],
                "site_name": ["Site One", "Site Two", "Site Three"],
                "latitude": [51.5, 51.6, 51.7],
                "longitude": [-0.1, -0.2, -0.3],
                "source_network": ["TEST_NETWORK"] * 3,
            }
        )

    return fetch_metadata


@pytest.fixture
def mock_network_data():
    """Mock network data function."""

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
def mock_portal_search():
    """Mock portal search function."""

    def search(**filters):
        if not filters:
            raise ValueError("Filters required")

        return pd.DataFrame(
            {
                "location_id": ["LOC1", "LOC2", "LOC3"],
                "location_name": ["Location One", "Location Two", "Location Three"],
                "latitude": [51.5, 51.6, 51.7],
                "longitude": [-0.1, -0.2, -0.3],
                "source_network": ["TEST_PORTAL"] * 3,
            }
        )

    return search


@pytest.fixture
def mock_portal_data():
    """Mock portal data function."""

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


# ============================================================================
# Networks API Tests
# ============================================================================


def test_networks_get_metadata_success(mock_network_metadata):
    """Test successful metadata retrieval from network."""
    register_source(
        "TEST_NETWORK",
        {
            "type": "network",
            "name": "Test Network",
            "fetch_metadata": mock_network_metadata,
            "fetch_data": lambda *args: pd.DataFrame(),
            "requires_api_key": False,
        },
    )

    result = networks_api.get_metadata("TEST_NETWORK")

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 3
    assert "site_code" in result.columns
    assert "SITE1" in result["site_code"].values


def test_networks_get_metadata_with_filters(mock_network_metadata):
    """Test metadata retrieval with filters."""
    register_source(
        "TEST_NETWORK",
        {
            "type": "network",
            "name": "Test Network",
            "fetch_metadata": mock_network_metadata,
            "fetch_data": lambda *args: pd.DataFrame(),
            "requires_api_key": False,
        },
    )

    # Should pass filters through to fetcher
    result = networks_api.get_metadata("TEST_NETWORK", some_filter="value")

    assert isinstance(result, pd.DataFrame)


def test_networks_get_metadata_unknown_source():
    """Test that unknown network raises ValueError."""
    with pytest.raises(ValueError, match="Unknown network"):
        networks_api.get_metadata("NONEXISTENT")


def test_networks_get_metadata_portal_type(mock_portal_search):
    """Test that portal raises error when called as network."""
    register_source(
        "TEST_PORTAL",
        {
            "type": "portal",
            "name": "Test Portal",
            "search": mock_portal_search,
            "fetch_data": lambda *args: pd.DataFrame(),
            "requires_api_key": False,
        },
    )

    with pytest.raises(ValueError, match="portal, not a network"):
        networks_api.get_metadata("TEST_PORTAL")


def test_networks_download_success(mock_network_data):
    """Test successful data download from network."""
    register_source(
        "TEST_NETWORK",
        {
            "type": "network",
            "name": "Test Network",
            "fetch_metadata": lambda: pd.DataFrame(),
            "fetch_data": mock_network_data,
            "requires_api_key": False,
        },
    )

    result = networks_api.download(
        "TEST_NETWORK",
        ["SITE1", "SITE2"],
        datetime(2024, 1, 1),
        datetime(2024, 1, 31),
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert "SITE1" in result["site_code"].values
    assert "SITE2" in result["site_code"].values


def test_networks_download_unknown_source():
    """Test that unknown network raises ValueError."""
    with pytest.raises(ValueError, match="Unknown network"):
        networks_api.download(
            "NONEXISTENT", ["SITE1"], datetime(2024, 1, 1), datetime(2024, 1, 31)
        )


def test_networks_download_portal_type(mock_portal_data):
    """Test that portal raises error when called as network."""
    register_source(
        "TEST_PORTAL",
        {
            "type": "portal",
            "name": "Test Portal",
            "search": lambda **k: pd.DataFrame(),
            "fetch_data": mock_portal_data,
            "requires_api_key": False,
        },
    )

    with pytest.raises(ValueError, match="portal, not a network"):
        networks_api.download(
            "TEST_PORTAL", ["LOC1"], datetime(2024, 1, 1), datetime(2024, 1, 31)
        )


def test_networks_list_networks():
    """Test listing all networks."""
    register_source(
        "NET1",
        {
            "type": "network",
            "name": "Network 1",
            "fetch_metadata": lambda: pd.DataFrame(),
            "fetch_data": lambda *args: pd.DataFrame(),
            "requires_api_key": False,
        },
    )
    register_source(
        "NET2",
        {
            "type": "network",
            "name": "Network 2",
            "fetch_metadata": lambda: pd.DataFrame(),
            "fetch_data": lambda *args: pd.DataFrame(),
            "requires_api_key": False,
        },
    )
    register_source(
        "PORTAL1",
        {
            "type": "portal",
            "name": "Portal 1",
            "search": lambda **k: pd.DataFrame(),
            "fetch_data": lambda *args: pd.DataFrame(),
            "requires_api_key": False,
        },
    )

    result = networks_api.list_networks()

    assert "NET1" in result
    assert "NET2" in result
    assert "PORTAL1" not in result


# ============================================================================
# Portals API Tests
# ============================================================================


def test_portals_find_sites_success(mock_portal_search):
    """Test successful location search in portal."""
    register_source(
        "TEST_PORTAL",
        {
            "type": "portal",
            "name": "Test Portal",
            "search": mock_portal_search,
            "fetch_data": lambda *args: pd.DataFrame(),
            "requires_api_key": False,
        },
    )

    result = portals_api.find_sites("TEST_PORTAL", country="GB")

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 3
    assert "location_id" in result.columns


def test_portals_find_sites_unknown_source():
    """Test that unknown portal raises ValueError."""
    with pytest.raises(ValueError, match="Unknown portal"):
        portals_api.find_sites("NONEXISTENT", country="GB")


def test_portals_find_sites_network_type(mock_network_metadata):
    """Test that network raises error when called as portal."""
    register_source(
        "TEST_NETWORK",
        {
            "type": "network",
            "name": "Test Network",
            "fetch_metadata": mock_network_metadata,
            "fetch_data": lambda *args: pd.DataFrame(),
            "requires_api_key": False,
        },
    )

    with pytest.raises(ValueError, match="network, not a portal"):
        portals_api.find_sites("TEST_NETWORK", country="GB")


def test_portals_find_sites_requires_filters(mock_portal_search):
    """Test that portals require search filters."""
    register_source(
        "TEST_PORTAL",
        {
            "type": "portal",
            "name": "Test Portal",
            "search": mock_portal_search,
            "fetch_data": lambda *args: pd.DataFrame(),
            "requires_api_key": False,
        },
    )

    with pytest.raises(ValueError, match="requires search filters"):
        portals_api.find_sites("TEST_PORTAL")


def test_portals_download_success(mock_portal_data):
    """Test successful data download from portal."""
    register_source(
        "TEST_PORTAL",
        {
            "type": "portal",
            "name": "Test Portal",
            "search": lambda **k: pd.DataFrame(),
            "fetch_data": mock_portal_data,
            "requires_api_key": False,
        },
    )

    result = portals_api.download(
        "TEST_PORTAL",
        ["LOC1", "LOC2"],
        datetime(2024, 1, 1),
        datetime(2024, 1, 31),
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert "LOC1" in result["site_code"].values


def test_portals_download_unknown_source():
    """Test that unknown portal raises ValueError."""
    with pytest.raises(ValueError, match="Unknown portal"):
        portals_api.download(
            "NONEXISTENT", ["LOC1"], datetime(2024, 1, 1), datetime(2024, 1, 31)
        )


def test_portals_download_network_type(mock_network_data):
    """Test that network raises error when called as portal."""
    register_source(
        "TEST_NETWORK",
        {
            "type": "network",
            "name": "Test Network",
            "fetch_metadata": lambda: pd.DataFrame(),
            "fetch_data": mock_network_data,
            "requires_api_key": False,
        },
    )

    with pytest.raises(ValueError, match="network, not a portal"):
        portals_api.download(
            "TEST_NETWORK", ["SITE1"], datetime(2024, 1, 1), datetime(2024, 1, 31)
        )


def test_portals_list_portals():
    """Test listing all portals."""
    register_source(
        "PORTAL1",
        {
            "type": "portal",
            "name": "Portal 1",
            "search": lambda **k: pd.DataFrame(),
            "fetch_data": lambda *args: pd.DataFrame(),
            "requires_api_key": False,
        },
    )
    register_source(
        "PORTAL2",
        {
            "type": "portal",
            "name": "Portal 2",
            "search": lambda **k: pd.DataFrame(),
            "fetch_data": lambda *args: pd.DataFrame(),
            "requires_api_key": False,
        },
    )
    register_source(
        "NET1",
        {
            "type": "network",
            "name": "Network 1",
            "fetch_metadata": lambda: pd.DataFrame(),
            "fetch_data": lambda *args: pd.DataFrame(),
            "requires_api_key": False,
        },
    )

    result = portals_api.list_portals()

    assert "PORTAL1" in result
    assert "PORTAL2" in result
    assert "NET1" not in result


# ============================================================================
# Source Type Detection Tests
# ============================================================================


def test_source_without_type_defaults_to_network(
    mock_network_metadata, mock_network_data
):
    """Test that sources without type field default to network for backward compatibility."""
    register_source(
        "LEGACY",
        {
            # No "type" field - should default to "network"
            "name": "Legacy Source",
            "fetch_metadata": mock_network_metadata,
            "fetch_data": mock_network_data,
            "requires_api_key": False,
        },
    )

    # Should work as network
    result = networks_api.get_metadata("LEGACY")
    assert isinstance(result, pd.DataFrame)

    result = networks_api.download(
        "LEGACY", ["SITE1"], datetime(2024, 1, 1), datetime(2024, 1, 31)
    )
    assert isinstance(result, pd.DataFrame)


def test_portal_uses_search_function(mock_portal_search, mock_portal_data):
    """Test that portals correctly use search function."""
    register_source(
        "TEST_PORTAL",
        {
            "type": "portal",
            "name": "Test Portal",
            "search": mock_portal_search,
            "fetch_data": mock_portal_data,
            "requires_api_key": False,
        },
    )

    # Search function should be called with filters
    result = portals_api.find_sites("TEST_PORTAL", country="GB")
    assert len(result) == 3


def test_portal_with_fetch_metadata_fallback(mock_portal_search, mock_portal_data):
    """Test that portals can use fetch_metadata as fallback for search."""
    register_source(
        "TEST_PORTAL",
        {
            "type": "portal",
            "name": "Test Portal",
            "fetch_metadata": mock_portal_search,  # No explicit "search" field
            "fetch_data": mock_portal_data,
            "requires_api_key": False,
        },
    )

    # Should still work
    result = portals_api.find_sites("TEST_PORTAL", country="GB")
    assert len(result) == 3


# ============================================================================
# Integration Tests
# ============================================================================


def test_mixed_source_types_in_registry(
    mock_network_metadata, mock_network_data, mock_portal_search, mock_portal_data
):
    """Test that networks and portals can coexist in registry."""
    register_source(
        "NETWORK",
        {
            "type": "network",
            "name": "Test Network",
            "fetch_metadata": mock_network_metadata,
            "fetch_data": mock_network_data,
            "requires_api_key": False,
        },
    )
    register_source(
        "PORTAL",
        {
            "type": "portal",
            "name": "Test Portal",
            "search": mock_portal_search,
            "fetch_data": mock_portal_data,
            "requires_api_key": False,
        },
    )

    # Both should work independently
    network_sites = networks_api.get_metadata("NETWORK")
    portal_sites = portals_api.find_sites("PORTAL", country="GB")

    assert len(network_sites) == 3
    assert len(portal_sites) == 3

    # List functions should separate them
    networks = networks_api.list_networks()
    portals = portals_api.list_portals()

    assert "NETWORK" in networks
    assert "NETWORK" not in portals
    assert "PORTAL" in portals
    assert "PORTAL" not in networks
