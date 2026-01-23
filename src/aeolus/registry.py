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
Data source registry for Aeolus.

This module provides a simple registry system for managing data sources.
Each source is registered as a SourceSpec (a bundle of functions) and can
be retrieved by name.

The registry is just a dictionary - no magic, no complexity. Sources register
themselves when their modules are imported.

Example:
    >>> from aeolus.registry import register_source, get_source
    >>>
    >>> # Register a source
    >>> register_source("MY_SOURCE", {
    ...     "name": "My Source",
    ...     "fetch_metadata": my_metadata_func,
    ...     "fetch_data": my_data_func,
    ...     "normalise": my_normalise_func,
    ...     "requires_api_key": False
    ... })
    >>>
    >>> # Retrieve and use it
    >>> source = get_source("MY_SOURCE")
    >>> df = source["fetch_metadata"]()
"""

from typing import Dict

from .types import SourceSpec

# The global registry - just a dictionary mapping names to SourceSpecs
_SOURCES: Dict[str, SourceSpec] = {}

# Export for submodules to access
SOURCES = _SOURCES


def register_source(name: str, spec: SourceSpec) -> None:
    """
    Register a data source in the global registry.

    Sources are identified by name (case-insensitive). If a source with the
    same name already exists, it will be replaced with a warning.

    Args:
        name: Unique identifier for the source (e.g., "AURN", "Breathe London")
        spec: SourceSpec containing the source's functions and metadata

    Example:
        >>> register_source("AURN", {
        ...     "name": "AURN",
        ...     "fetch_metadata": fetch_aurn_metadata,
        ...     "fetch_data": fetch_aurn_data,
        ...     "normalise": normalise_regulatory_data,
        ...     "requires_api_key": False
        ... })
    """
    import warnings

    normalized_name = name.upper()

    if normalized_name in _SOURCES:
        warnings.warn(
            f"Source '{normalized_name}' is already registered and will be replaced",
            UserWarning,
            stacklevel=2,
        )

    _SOURCES[normalized_name] = spec


def unregister_source(name: str) -> bool:
    """
    Remove a source from the registry.

    Args:
        name: Name of the source to remove (case-insensitive)

    Returns:
        bool: True if source was removed, False if it wasn't registered

    Example:
        >>> unregister_source("AURN")
        True
    """
    normalized_name = name.upper()

    if normalized_name in _SOURCES:
        del _SOURCES[normalized_name]
        return True
    return False


def get_source(name: str) -> SourceSpec | None:
    """
    Retrieve a registered source by name.

    Args:
        name: Name of the source (case-insensitive)

    Returns:
        SourceSpec | None: The source specification, or None if not found

    Example:
        >>> source = get_source("AURN")
        >>> if source:
        ...     df = source["fetch_metadata"]()
    """
    normalized_name = name.upper()
    return _SOURCES.get(normalized_name)


def list_sources() -> list[str]:
    """
    Get a list of all registered source names.

    Returns:
        list[str]: List of registered source names (uppercase)

    Example:
        >>> sources = list_sources()
        >>> print(sources)
        ['AURN', 'SAQN', 'BREATHE_LONDON']
    """
    return sorted(_SOURCES.keys())


def source_exists(name: str) -> bool:
    """
    Check if a source is registered.

    Args:
        name: Name of the source (case-insensitive)

    Returns:
        bool: True if source is registered, False otherwise

    Example:
        >>> if source_exists("AURN"):
        ...     print("AURN is available")
    """
    normalized_name = name.upper()
    return normalized_name in _SOURCES


def get_source_info(name: str) -> dict[str, str | bool] | None:
    """
    Get basic information about a registered source.

    Args:
        name: Name of the source (case-insensitive)

    Returns:
        dict | None: Dictionary with 'name' and 'requires_api_key' keys,
                     or None if source not found

    Example:
        >>> info = get_source_info("BREATHE_LONDON")
        >>> if info and info['requires_api_key']:
        ...     print("This source requires an API key")
    """
    source = get_source(name)
    if source is None:
        return None

    return {"name": source["name"], "requires_api_key": source["requires_api_key"]}


def clear_registry() -> None:
    """
    Clear all registered sources from the registry.

    This is primarily useful for testing. In normal use, you shouldn't
    need to call this function.

    Warning:
        This will remove ALL registered sources, including built-in ones.
    """
    global _SOURCES
    _SOURCES.clear()
