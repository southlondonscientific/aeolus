"""
Tests for registry.py - source registration and retrieval.

The registry is the core of Aeolus's extensibility, so these tests
ensure it works correctly.
"""

import pytest

from aeolus.registry import (
    _SOURCES,
    get_source,
    list_sources,
    register_source,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def clean_registry():
    """
    Clean the registry before and after each test.

    This ensures tests don't interfere with each other.
    """
    # Save original state
    original_sources = _SOURCES.copy()

    # Clear for test
    _SOURCES.clear()

    yield

    # Restore original state
    _SOURCES.clear()
    _SOURCES.update(original_sources)


@pytest.fixture
def sample_source_spec():
    """Return a valid source specification."""
    return {
        "name": "TestSource",
        "fetch_metadata": lambda: None,
        "fetch_data": lambda sites, start, end: None,
        "normalise": lambda df: df,
        "requires_api_key": False,
    }


@pytest.fixture
def minimal_source_spec():
    """Return a minimal source specification with only required fields."""
    return {
        "name": "MinimalSource",
        "fetch_data": lambda sites, start, end: None,
    }


# ============================================================================
# Tests for register_source()
# ============================================================================


def test_register_source_adds_to_registry(sample_source_spec):
    """Test that register_source adds a source to the registry."""
    register_source("TEST", sample_source_spec)

    assert "TEST" in _SOURCES
    assert _SOURCES["TEST"] == sample_source_spec


def test_register_source_converts_key_to_uppercase(sample_source_spec):
    """Test that source keys are automatically converted to uppercase."""
    register_source("test", sample_source_spec)

    assert "TEST" in _SOURCES
    assert "test" not in _SOURCES


def test_register_source_with_minimal_spec(minimal_source_spec):
    """Test registering a source with minimal required fields."""
    register_source("MINIMAL", minimal_source_spec)

    assert "MINIMAL" in _SOURCES
    assert _SOURCES["MINIMAL"]["name"] == "MinimalSource"


def test_register_source_overwrites_existing():
    """Test that registering a source twice overwrites the first registration."""
    spec1 = {"name": "First", "fetch_data": lambda s, st, e: None}
    spec2 = {"name": "Second", "fetch_data": lambda s, st, e: None}

    register_source("TEST", spec1)
    assert _SOURCES["TEST"]["name"] == "First"

    register_source("TEST", spec2)
    assert _SOURCES["TEST"]["name"] == "Second"


def test_register_source_allows_multiple_sources(sample_source_spec):
    """Test that multiple sources can be registered."""
    spec1 = {**sample_source_spec, "name": "Source1"}
    spec2 = {**sample_source_spec, "name": "Source2"}
    spec3 = {**sample_source_spec, "name": "Source3"}

    register_source("SOURCE1", spec1)
    register_source("SOURCE2", spec2)
    register_source("SOURCE3", spec3)

    assert len(_SOURCES) == 3
    assert "SOURCE1" in _SOURCES
    assert "SOURCE2" in _SOURCES
    assert "SOURCE3" in _SOURCES


def test_register_source_with_api_key_requirement():
    """Test registering a source that requires an API key."""
    spec = {
        "name": "APISource",
        "fetch_data": lambda s, st, e: None,
        "requires_api_key": True,
    }

    register_source("APISOURCE", spec)

    assert _SOURCES["APISOURCE"]["requires_api_key"] is True


def test_register_source_with_custom_normalizer():
    """Test registering a source with a custom normalizer."""

    def custom_normalizer(df):
        return df.assign(custom_col="test")

    spec = {
        "name": "CustomSource",
        "fetch_data": lambda s, st, e: None,
        "normalise": custom_normalizer,
    }

    register_source("CUSTOM", spec)

    assert _SOURCES["CUSTOM"]["normalise"] == custom_normalizer


# ============================================================================
# Tests for get_source()
# ============================================================================


def test_get_source_retrieves_registered_source(sample_source_spec):
    """Test that get_source retrieves a registered source."""
    register_source("TEST", sample_source_spec)

    result = get_source("TEST")

    assert result == sample_source_spec


def test_get_source_is_case_insensitive(sample_source_spec):
    """Test that get_source works with any case."""
    register_source("TEST", sample_source_spec)

    assert get_source("test") == sample_source_spec
    assert get_source("Test") == sample_source_spec
    assert get_source("TEST") == sample_source_spec
    assert get_source("TeSt") == sample_source_spec


def test_get_source_returns_none_for_unknown_source():
    """Test that get_source returns None for unknown sources."""
    result = get_source("NONEXISTENT")
    assert result is None


def test_get_source_returns_none_with_available_sources(sample_source_spec):
    """Test that get_source returns None when source not found."""
    register_source("AURN", sample_source_spec)
    register_source("SAQN", sample_source_spec)

    result = get_source("INVALID")

    # Returns None, user can check list_sources() for available
    assert result is None
    available = list_sources()
    assert "AURN" in available
    assert "SAQN" in available


def test_get_source_with_empty_registry():
    """Test get_source behavior when registry is empty."""
    # Registry is already clean from fixture

    result = get_source("TEST")
    assert result is None


# ============================================================================
# Tests for list_sources()
# ============================================================================


def test_list_sources_returns_empty_list_when_no_sources():
    """Test that list_sources returns empty list for empty registry."""
    result = list_sources()

    assert result == []


def test_list_sources_returns_registered_sources(sample_source_spec):
    """Test that list_sources returns all registered source names."""
    register_source("AURN", sample_source_spec)
    register_source("SAQN", sample_source_spec)
    register_source("OPENAQ", sample_source_spec)

    result = list_sources()

    assert len(result) == 3
    assert "AURN" in result
    assert "SAQN" in result
    assert "OPENAQ" in result


def test_list_sources_returns_list_type(sample_source_spec):
    """Test that list_sources returns a list (not dict_keys or other)."""
    register_source("TEST", sample_source_spec)

    result = list_sources()

    assert isinstance(result, list)


def test_list_sources_returns_uppercase_keys(sample_source_spec):
    """Test that list_sources returns uppercase keys even if registered lowercase."""
    register_source("test", sample_source_spec)

    result = list_sources()

    assert "TEST" in result
    assert "test" not in result


def test_list_sources_is_sorted(sample_source_spec):
    """Test that list_sources returns sources in sorted order."""
    # Register in random order
    register_source("ZEBRA", sample_source_spec)
    register_source("ALPHA", sample_source_spec)
    register_source("MIKE", sample_source_spec)

    result = list_sources()

    assert result == sorted(result)
    assert result == ["ALPHA", "MIKE", "ZEBRA"]


# ============================================================================
# Integration Tests
# ============================================================================


def test_register_and_retrieve_complete_source():
    """Test registering and retrieving a complete source specification."""
    spec = {
        "name": "CompleteSource",
        "fetch_metadata": lambda: "metadata",
        "fetch_data": lambda s, st, e: "data",
        "normalise": lambda df: df,
        "requires_api_key": True,
        "custom_field": "custom_value",
    }

    register_source("COMPLETE", spec)
    retrieved = get_source("COMPLETE")

    assert retrieved["name"] == "CompleteSource"
    assert retrieved["fetch_metadata"]() == "metadata"
    assert retrieved["fetch_data"](None, None, None) == "data"
    assert retrieved["requires_api_key"] is True
    assert retrieved["custom_field"] == "custom_value"


def test_multiple_sources_independent():
    """Test that multiple sources maintain independent specifications."""
    spec1 = {
        "name": "Source1",
        "fetch_data": lambda s, st, e: "data1",
        "requires_api_key": False,
    }
    spec2 = {
        "name": "Source2",
        "fetch_data": lambda s, st, e: "data2",
        "requires_api_key": True,
    }

    register_source("SOURCE1", spec1)
    register_source("SOURCE2", spec2)

    s1 = get_source("SOURCE1")
    s2 = get_source("SOURCE2")

    assert s1["name"] == "Source1"
    assert s2["name"] == "Source2"
    assert s1["requires_api_key"] is False
    assert s2["requires_api_key"] is True
    assert s1["fetch_data"](None, None, None) == "data1"
    assert s2["fetch_data"](None, None, None) == "data2"


def test_registry_workflow():
    """Test a complete workflow: register, list, get."""
    spec1 = {"name": "AURN", "fetch_data": lambda s, st, e: None}
    spec2 = {"name": "OpenAQ", "fetch_data": lambda s, st, e: None}

    # Initially empty
    assert list_sources() == []

    # Register first source
    register_source("AURN", spec1)
    assert list_sources() == ["AURN"]
    assert get_source("AURN")["name"] == "AURN"

    # Register second source
    register_source("OPENAQ", spec2)
    assert len(list_sources()) == 2
    assert "AURN" in list_sources()
    assert "OPENAQ" in list_sources()

    # Retrieve both
    aurn = get_source("AURN")
    openaq = get_source("openaq")  # Case insensitive

    assert aurn["name"] == "AURN"
    assert openaq["name"] == "OpenAQ"


# ============================================================================
# Edge Cases and Error Conditions
# ============================================================================


def test_register_source_with_none_spec():
    """Test that registering None as spec doesn't crash."""
    # This might not be prevented, but shouldn't crash
    register_source("TEST", None)

    assert "TEST" in _SOURCES
    assert _SOURCES["TEST"] is None


def test_register_source_with_empty_dict():
    """Test registering with an empty specification dict."""
    register_source("EMPTY", {})

    assert "EMPTY" in _SOURCES
    assert _SOURCES["EMPTY"] == {}


def test_get_source_with_whitespace():
    """Test get_source with whitespace in source name."""
    spec = {"name": "Test", "fetch_data": lambda s, st, e: None}
    register_source("TEST", spec)

    # Whitespace is not stripped - exact match required
    result = get_source("  TEST  ")

    # Returns None because whitespace doesn't match
    assert result is None

    # Without whitespace works
    result_clean = get_source("TEST")
    assert result_clean == spec


def test_register_source_with_special_characters():
    """Test registering sources with special characters in name."""
    spec = {"name": "Test-Source_123", "fetch_data": lambda s, st, e: None}

    # Should work with special characters
    register_source("TEST-SOURCE_123", spec)

    assert "TEST-SOURCE_123" in _SOURCES


def test_list_sources_does_not_expose_internal_dict():
    """Test that list_sources returns a copy, not a reference."""
    spec = {"name": "Test", "fetch_data": lambda s, st, e: None}
    register_source("TEST", spec)

    sources1 = list_sources()
    sources2 = list_sources()

    # Should be equal but not the same object
    assert sources1 == sources2
    assert sources1 is not sources2


def test_registry_persists_across_calls(sample_source_spec):
    """Test that registry maintains state between calls."""
    register_source("PERSISTENT", sample_source_spec)

    # Call list_sources multiple times
    assert "PERSISTENT" in list_sources()
    assert "PERSISTENT" in list_sources()
    assert "PERSISTENT" in list_sources()

    # Call get_source multiple times
    s1 = get_source("PERSISTENT")
    s2 = get_source("PERSISTENT")

    assert s1 == s2
