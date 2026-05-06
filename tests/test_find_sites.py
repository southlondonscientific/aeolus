"""Tests for find_sites() unified site discovery.

Follows the test_api.py pattern: register mock sources, reset registry
after each test.
"""

import importlib

import pandas as pd
import pytest

from aeolus import api
from aeolus.registry import clear_registry, register_source
from aeolus.types import METADATA_COLUMNS


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_registry():
    """Clear registry before and after each test, then restore sources."""
    clear_registry()
    yield
    clear_registry()
    from aeolus.sources import (
        airnow,
        airqo,
        breathe_london,
        eea,
        laqn,
        openaq,
        purpleair,
        regulatory,
        sensor_community,
        sonitus,
        sos,
    )

    for module in [
        airnow,
        airqo,
        breathe_london,
        eea,
        laqn,
        openaq,
        purpleair,
        regulatory,
        sensor_community,
        sonitus,
        sos,
    ]:
        importlib.reload(module)


def _make_metadata(rows, source_network="TEST", measurands=None):
    """Helper to build a metadata DataFrame."""
    records = []
    for code, name, lat, lon in rows:
        records.append(
            {
                "site_code": code,
                "site_name": name,
                "latitude": lat,
                "longitude": lon,
                "source_network": source_network,
                "measurands": measurands,
            }
        )
    return pd.DataFrame(records)


# --- London-area sites for spatial tests ---
# Site A: Westminster (51.50, -0.13)
# Site B: Greenwich  (51.48, 0.00)
# Site C: Heathrow   (51.47, -0.45)  ~25 km from Westminster
# Site D: Brighton    (50.82, -0.14)  ~75 km from Westminster

LONDON_SITES = [
    ("WM1", "Westminster", 51.50, -0.13),
    ("GR1", "Greenwich", 51.48, 0.00),
    ("LH1", "Heathrow", 51.47, -0.45),
    ("BR1", "Brighton", 50.82, -0.14),
]


@pytest.fixture
def register_free_network():
    """Register a free network source with London-area sites."""
    register_source(
        "FREE_NET",
        {
            "type": "network",
            "name": "Free Network",
            "fetch_metadata": lambda **kw: _make_metadata(LONDON_SITES, "FREE_NET"),
            "fetch_data": lambda sites, s, e: pd.DataFrame(),
            "normalise": lambda df: df,
            "requires_api_key": False,
        },
    )


@pytest.fixture
def register_paid_network():
    """Register a paid network source with a couple of sites."""
    sites = [
        ("PN1", "Paid Site 1", 51.51, -0.12),
        ("PN2", "Paid Site 2", 51.52, -0.11),
    ]
    register_source(
        "PAID_NET",
        {
            "type": "network",
            "name": "Paid Network",
            "fetch_metadata": lambda **kw: _make_metadata(sites, "PAID_NET"),
            "fetch_data": lambda sites, s, e: pd.DataFrame(),
            "normalise": lambda df: df,
            "requires_api_key": True,
        },
    )


@pytest.fixture
def register_test_portal():
    """Register a portal source that requires bbox/filters."""
    portal_sites = [
        ("PO1", "Portal Site 1", 51.49, -0.10),
        ("PO2", "Portal Site 2", 51.53, -0.08),
    ]

    def portal_search(**filters):
        return _make_metadata(portal_sites, "TEST_PORTAL")

    register_source(
        "TEST_PORTAL",
        {
            "type": "portal",
            "name": "Test Portal",
            "fetch_metadata": portal_search,
            "fetch_data": lambda sites, s, e: pd.DataFrame(),
            "normalise": lambda df: df,
            "requires_api_key": True,
        },
    )


@pytest.fixture
def register_all(register_free_network, register_paid_network, register_test_portal):
    """Register free network, paid network, and portal."""
    pass


# ============================================================================
# Basic source selection
# ============================================================================


def test_single_network(register_free_network):
    """Single network source returns its sites."""
    result = api.find_sites("FREE_NET")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 4
    assert list(result.columns[: len(METADATA_COLUMNS)]) == METADATA_COLUMNS


def test_single_portal_with_bbox(register_test_portal):
    """Single portal source with bbox returns its sites."""
    result = api.find_sites(
        "TEST_PORTAL", bbox=(-0.5, 51.0, 0.5, 52.0)
    )
    assert len(result) == 2
    assert result["source_network"].iloc[0] == "TEST_PORTAL"


def test_multiple_sources(register_free_network, register_paid_network):
    """Multiple sources returns combined results."""
    result = api.find_sites(["FREE_NET", "PAID_NET"])
    assert len(result) == 6  # 4 + 2
    assert set(result["source_network"]) == {"FREE_NET", "PAID_NET"}


# ============================================================================
# Spatial filtering — near
# ============================================================================


def test_near_adds_distance_column(register_free_network):
    """near=(lat, lon) adds a distance_km column."""
    result = api.find_sites("FREE_NET", near=(51.50, -0.13), radius_km=100)
    assert "distance_km" in result.columns


def test_near_sorted_by_distance(register_free_network):
    """Results are sorted nearest-first when near is used."""
    result = api.find_sites("FREE_NET", near=(51.50, -0.13), radius_km=100)
    distances = result["distance_km"].tolist()
    assert distances == sorted(distances)


def test_near_filters_by_radius(register_free_network):
    """Sites beyond radius_km are excluded."""
    # Westminster at (51.50, -0.13); Brighton at ~75 km, Heathrow at ~25 km
    result = api.find_sites("FREE_NET", near=(51.50, -0.13), radius_km=30)
    codes = result["site_code"].tolist()
    assert "WM1" in codes  # ~0 km
    assert "GR1" in codes  # ~10 km
    assert "LH1" in codes  # ~25 km
    assert "BR1" not in codes  # ~75 km — excluded


def test_near_zero_radius(register_free_network):
    """radius_km=0 returns only exact matches (practically nothing)."""
    result = api.find_sites("FREE_NET", near=(51.50, -0.13), radius_km=0)
    # Only the point itself (or very close) should match
    assert len(result) <= 1


# ============================================================================
# Spatial filtering — bbox
# ============================================================================


def test_bbox_filters_rectangle(register_free_network):
    """bbox filters sites to the given rectangle."""
    # Box that includes Westminster and Greenwich but not Heathrow or Brighton
    result = api.find_sites(
        "FREE_NET", bbox=(-0.15, 51.47, 0.05, 51.51)
    )
    codes = result["site_code"].tolist()
    assert "WM1" in codes
    assert "GR1" in codes
    assert "LH1" not in codes
    assert "BR1" not in codes


def test_bbox_no_distance_column(register_free_network):
    """bbox mode should NOT add a distance_km column."""
    result = api.find_sites("FREE_NET", bbox=(-1, 50, 1, 53))
    assert "distance_km" not in result.columns


# ============================================================================
# Mutual exclusion
# ============================================================================


def test_near_and_bbox_raises(register_free_network):
    """near + bbox at the same time raises ValueError."""
    with pytest.raises(ValueError, match="mutually exclusive"):
        api.find_sites(
            "FREE_NET",
            near=(51.5, -0.1),
            bbox=(-1, 50, 1, 53),
        )


# ============================================================================
# Source selection defaults
# ============================================================================


def test_default_queries_free_sources_only(register_all):
    """source=None queries only free (no-API-key) sources."""
    result = api.find_sites()
    assert set(result["source_network"]) == {"FREE_NET"}


def test_include_all_queries_all_sources(register_free_network, register_paid_network):
    """include_all=True includes API-key sources."""
    result = api.find_sites(include_all=True)
    assert "FREE_NET" in set(result["source_network"])
    assert "PAID_NET" in set(result["source_network"])


def test_include_all_warns_on_failure(register_free_network):
    """include_all=True warns and continues when a source fails."""

    def failing_metadata(**kw):
        raise RuntimeError("API key invalid")

    register_source(
        "FAILING_NET",
        {
            "type": "network",
            "name": "Failing Network",
            "fetch_metadata": failing_metadata,
            "fetch_data": lambda sites, s, e: pd.DataFrame(),
            "normalise": lambda df: df,
            "requires_api_key": True,
        },
    )

    with pytest.warns(UserWarning, match="Failed to fetch sites from FAILING_NET"):
        result = api.find_sites(include_all=True)

    # Should still have results from FREE_NET
    assert len(result) == 4
    assert set(result["source_network"]) == {"FREE_NET"}


# ============================================================================
# Error cases
# ============================================================================


def test_unknown_source_raises():
    """Unknown source name raises ValueError."""
    with pytest.raises(ValueError, match="Unknown source: NOPE"):
        api.find_sites("NOPE")


def test_portal_without_filters_skipped(register_test_portal):
    """Portal source with no spatial/keyword filters is skipped with warning."""
    with pytest.warns(UserWarning, match="Skipping TEST_PORTAL"):
        result = api.find_sites("TEST_PORTAL")

    assert result.empty
    assert list(result.columns) == METADATA_COLUMNS


# ============================================================================
# Empty results
# ============================================================================


def test_empty_results_schema(register_free_network):
    """Empty results (all filtered out) return schema-correct DataFrame."""
    result = api.find_sites(
        "FREE_NET", bbox=(100, 100, 101, 101)  # Nowhere near London
    )
    assert result.empty
    assert list(result.columns[: len(METADATA_COLUMNS)]) == METADATA_COLUMNS


def test_no_sources_returns_empty():
    """No registered sources returns empty metadata frame."""
    result = api.find_sites()
    assert result.empty
    assert list(result.columns) == METADATA_COLUMNS


# ============================================================================
# Column ordering
# ============================================================================


def test_core_columns_first(register_free_network):
    """Core metadata columns are always the first five."""
    result = api.find_sites("FREE_NET")
    assert list(result.columns[: len(METADATA_COLUMNS)]) == METADATA_COLUMNS


def test_distance_column_after_core(register_free_network):
    """distance_km appears right after the core columns when near is used."""
    result = api.find_sites("FREE_NET", near=(51.50, -0.13), radius_km=100)
    assert list(result.columns[: len(METADATA_COLUMNS)]) == METADATA_COLUMNS
    assert result.columns[len(METADATA_COLUMNS)] == "distance_km"


# ============================================================================
# Edge cases
# ============================================================================


def test_sites_with_nan_coords_excluded_by_near():
    """Sites with NaN lat/lon are excluded from near results."""
    sites_with_nan = [
        ("OK1", "Has Coords", 51.50, -0.13),
        ("BAD", "No Coords", None, None),
    ]
    register_source(
        "NAN_NET",
        {
            "type": "network",
            "name": "NaN Network",
            "fetch_metadata": lambda **kw: _make_metadata(
                sites_with_nan, "NAN_NET"
            ),
            "fetch_data": lambda sites, s, e: pd.DataFrame(),
            "normalise": lambda df: df,
            "requires_api_key": False,
        },
    )
    result = api.find_sites("NAN_NET", near=(51.50, -0.13), radius_km=50)
    assert "BAD" not in result["site_code"].tolist()
    assert "OK1" in result["site_code"].tolist()


def test_case_insensitive_source(register_free_network):
    """Source name lookup is case-insensitive."""
    result = api.find_sites("free_net")
    assert len(result) == 4


# ============================================================================
# Primary flag
# ============================================================================


def test_non_primary_excluded_from_default(register_free_network):
    """Sources with primary=False are excluded from find_sites() default."""
    non_primary_sites = [
        ("NP1", "Non-Primary Site", 51.50, -0.13),
    ]
    register_source(
        "NON_PRIMARY_NET",
        {
            "type": "network",
            "name": "Non-Primary",
            "primary": False,
            "fetch_metadata": lambda **kw: _make_metadata(
                non_primary_sites, "NON_PRIMARY_NET"
            ),
            "fetch_data": lambda sites, s, e: pd.DataFrame(),
            "normalise": lambda df: df,
            "requires_api_key": False,
        },
    )

    result = api.find_sites()
    assert "FREE_NET" in set(result["source_network"])
    assert "NON_PRIMARY_NET" not in set(result["source_network"])


def test_non_primary_included_when_explicit(register_free_network):
    """Non-primary sources can still be queried explicitly by name."""
    non_primary_sites = [
        ("NP1", "Non-Primary Site", 51.50, -0.13),
    ]
    register_source(
        "NON_PRIMARY_NET",
        {
            "type": "network",
            "name": "Non-Primary",
            "primary": False,
            "fetch_metadata": lambda **kw: _make_metadata(
                non_primary_sites, "NON_PRIMARY_NET"
            ),
            "fetch_data": lambda sites, s, e: pd.DataFrame(),
            "normalise": lambda df: df,
            "requires_api_key": False,
        },
    )

    result = api.find_sites("NON_PRIMARY_NET")
    assert len(result) == 1
    assert result["source_network"].iloc[0] == "NON_PRIMARY_NET"


# ============================================================================
# Missing metadata columns
# ============================================================================


def test_source_missing_site_name_column():
    """Sources that don't return site_name should not crash find_sites()."""
    # Sensor.Community bbox queries may omit site_name
    no_name_records = pd.DataFrame(
        [
            {"site_code": "SC1", "latitude": 51.50, "longitude": -0.13, "source_network": "NO_NAME_NET"},
            {"site_code": "SC2", "latitude": 51.51, "longitude": -0.12, "source_network": "NO_NAME_NET"},
        ]
    )
    register_source(
        "NO_NAME_NET",
        {
            "type": "network",
            "name": "No Name Network",
            "fetch_metadata": lambda **kw: no_name_records.copy(),
            "fetch_data": lambda sites, s, e: pd.DataFrame(),
            "normalise": lambda df: df,
            "requires_api_key": False,
        },
    )

    result = api.find_sites("NO_NAME_NET")
    assert len(result) == 2
    assert "site_code" in result.columns
    assert "source_network" in result.columns


# ============================================================================
# Measurand filtering
# ============================================================================


@pytest.fixture
def register_measurand_network():
    """Register a network with known measurands per site."""
    rows = [
        ("A1", "Site A", 51.50, -0.13),
        ("B1", "Site B", 51.48, 0.00),
        ("C1", "Site C", 51.47, -0.45),
    ]

    def _meta(**kw):
        df = _make_metadata(rows, "MEAS_NET")
        df["measurands"] = [
            ["NO2", "O3", "PM2.5"],
            ["NO2", "PM10"],
            None,  # unknown
        ]
        return df

    register_source(
        "MEAS_NET",
        {
            "type": "network",
            "name": "Measurand Network",
            "fetch_metadata": _meta,
            "fetch_data": lambda sites, s, e: pd.DataFrame(),
            "normalise": lambda df: df,
            "requires_api_key": False,
        },
    )


def test_measurand_filter_single(register_measurand_network):
    """Filtering by a single measurand returns matching sites."""
    result = api.find_sites("MEAS_NET", measurand="O3")
    assert len(result) == 1
    assert result["site_code"].iloc[0] == "A1"


def test_measurand_filter_multiple_matches(register_measurand_network):
    """Filtering by a shared measurand returns all matching sites."""
    result = api.find_sites("MEAS_NET", measurand="NO2")
    assert len(result) == 2
    assert set(result["site_code"]) == {"A1", "B1"}


def test_measurand_filter_list(register_measurand_network):
    """Filtering by a list of measurands uses any-match semantics."""
    result = api.find_sites("MEAS_NET", measurand=["PM10", "O3"])
    assert len(result) == 2
    assert set(result["site_code"]) == {"A1", "B1"}


def test_measurand_filter_excludes_unknown(register_measurand_network):
    """Sites with measurands=None are excluded by measurand filter."""
    result = api.find_sites("MEAS_NET", measurand="NO2")
    assert "C1" not in set(result["site_code"])


def test_measurand_filter_no_match(register_measurand_network):
    """Filtering by a measurand no site has returns empty."""
    result = api.find_sites("MEAS_NET", measurand="SO2")
    assert len(result) == 0
    assert "measurands" in result.columns


def test_measurands_column_present(register_free_network):
    """Metadata always includes a measurands column."""
    result = api.find_sites("FREE_NET")
    assert "measurands" in result.columns


@pytest.fixture
def register_default_measurands_network():
    """Register a network that declares default_measurands and reports None per site."""
    rows = [
        ("D1", "Site D", 51.50, -0.13),
        ("D2", "Site D2", 51.48, 0.00),
    ]

    def _meta(**kw):
        df = _make_metadata(rows, "DEFAULT_NET")
        df["measurands"] = [None, None]
        return df

    register_source(
        "DEFAULT_NET",
        {
            "type": "network",
            "name": "Default Measurands Network",
            "fetch_metadata": _meta,
            "fetch_data": lambda sites, s, e: pd.DataFrame(),
            "normalise": lambda df: df,
            "requires_api_key": False,
            "default_measurands": ["NO2", "PM2.5"],
        },
    )


def test_measurand_filter_uses_source_defaults(register_default_measurands_network):
    """Sites with measurands=None are matched against source default_measurands."""
    result = api.find_sites("DEFAULT_NET", measurand="NO2")
    assert len(result) == 2
    assert set(result["site_code"]) == {"D1", "D2"}


def test_measurand_filter_default_no_match(register_default_measurands_network):
    """source default_measurands not matching the wanted measurand still excludes."""
    result = api.find_sites("DEFAULT_NET", measurand="SO2")
    assert len(result) == 0


def test_measurand_filter_default_does_not_override_populated(
    register_measurand_network,
):
    """Sources without default_measurands keep the strict 'exclude None' behaviour."""
    result = api.find_sites("MEAS_NET", measurand="NO2")
    # C1 has measurands=None and MEAS_NET has no default_measurands → excluded.
    assert "C1" not in set(result["site_code"])
