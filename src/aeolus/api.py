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
Public API for Aeolus.

This module provides the top-level convenience functions for downloading
air quality data. It intelligently routes requests to the appropriate
submodules (networks or portals) based on source type.

For more control, use submodules directly:
    - aeolus.networks for discrete monitoring networks
    - aeolus.portals for global data portals

Basic usage:
    >>> import aeolus
    >>>
    >>> # See what's available
    >>> sources = aeolus.list_sources()
    >>>
    >>> # Single source download
    >>> data = aeolus.download("AURN", ["MY1"], start_date, end_date)
    >>>
    >>> # Multiple sources with explicit mapping
    >>> data = aeolus.download(
    ...     {
    ...         "AURN": ["MY1", "MY2"],
    ...         "OpenAQ": ["2178"]
    ...     },
    ...     start_date=start_date,
    ...     end_date=end_date
    ... )
"""

import warnings
from datetime import datetime
from typing import Any

import pandas as pd

# Import sources to trigger registration
from . import sources as _sources
from .registry import get_source, source_exists
from .registry import list_sources as _list_sources
from .types import DATA_COLUMNS as _STANDARD_COLUMNS
from .types import METADATA_COLUMNS as _METADATA_COLUMNS
from .types import empty_metadata_frame as _empty_metadata_frame


def list_sources() -> list[str]:
    """
    List all available data sources (networks and portals).

    Returns:
        list[str]: List of registered source names

    Example:
        >>> sources = aeolus.list_sources()
        >>> print(sources)
        ['AURN', 'SAQN', 'BREATHE_LONDON', 'OPENAQ', ...]
    """
    return _list_sources()


def download(
    sources: str | dict[str, list[str]],
    sites: list[str] | None = None,
    start_date: datetime = None,
    end_date: datetime = None,
    combine: bool = True,
) -> pd.DataFrame | dict[str, pd.DataFrame]:
    """
    Download air quality data with smart routing to networks/portals.

    This is the main convenience function for downloading data. It automatically
    routes requests to the appropriate submodule (networks or portals) based on
    source type.

    Single Source (Simple):
        Pass source name and site list:
        >>> data = aeolus.download("AURN", ["MY1", "MY2"], start, end)
        >>> data = aeolus.download("OpenAQ", ["2178"], start, end)

    Multiple Sources (Explicit Mapping):
        Pass dict mapping source names to their site lists:
        >>> data = aeolus.download(
        ...     {
        ...         "AURN": ["MY1", "MY2"],
        ...         "OpenAQ": ["2178", "2179"]
        ...     },
        ...     start_date=start,
        ...     end_date=end
        ... )

    Args:
        sources: Single source name OR dict of {source: [sites]}
        sites: Site IDs (only when sources is a string)
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)
        combine: If True, combine into single DataFrame (default True)

    Returns:
        DataFrame (if combine=True) or dict of DataFrames (if combine=False)

    Raises:
        ValueError: If sources/sites format is invalid or source not found
        TypeError: If sources is not str or dict

    Note:
        For fine control, use submodules directly:
        >>> aurn = aeolus.networks.download("AURN", ["MY1"], start, end)
        >>> openaq = aeolus.portals.download("OpenAQ", ["2178"], start, end)

    Examples:
        >>> from datetime import datetime
        >>>
        >>> # Single network
        >>> data = aeolus.download(
        ...     "AURN",
        ...     ["MY1", "MY2"],
        ...     datetime(2024, 1, 1),
        ...     datetime(2024, 1, 31)
        ... )
        >>>
        >>> # Single portal
        >>> data = aeolus.download(
        ...     "OpenAQ",
        ...     ["2178"],
        ...     datetime(2024, 1, 1),
        ...     datetime(2024, 1, 31)
        ... )
        >>>
        >>> # Multiple sources with explicit mapping
        >>> data = aeolus.download(
        ...     {
        ...         "AURN": ["MY1"],
        ...         "OpenAQ": ["2178"],
        ...         "BREATHE_LONDON": ["BL0001"]
        ...     },
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31)
        ... )
        >>>
        >>> # Get separate DataFrames per source
        >>> data_by_source = aeolus.download(
        ...     {"AURN": ["MY1"], "OpenAQ": ["2178"]},
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31),
        ...     combine=False
        ... )
    """
    # Validate required parameters
    if start_date is None or end_date is None:
        raise ValueError("start_date and end_date are required")

    # Case 1: Single source (string) - simple case
    if isinstance(sources, str):
        if sites is None:
            raise ValueError(
                "sites parameter required when sources is a string.\n\n"
                "Usage:\n"
                "  aeolus.download('AURN', ['MY1', 'MY2'], start_date, end_date)"
            )

        # Route to appropriate submodule
        source_spec = get_source(sources)
        if not source_spec:
            available = ", ".join(list_sources())
            raise ValueError(
                f"Unknown source: {sources}\nAvailable sources: {available}"
            )

        source_type = source_spec.get("type", "network")

        if source_type == "network":
            from .networks import download as network_download

            return network_download(sources, sites, start_date, end_date)
        elif source_type == "portal":
            from .portals import download as portal_download

            return portal_download(sources, sites, start_date, end_date)
        else:
            raise ValueError(f"Unknown source type: {source_type}")

    # Case 2: Multiple sources (dict) - explicit mapping
    elif isinstance(sources, dict):
        if sites is not None:
            raise ValueError(
                "When sources is a dict, sites are specified within the dict.\n"
                "Do not pass sites parameter separately.\n\n"
                "Example:\n"
                "  aeolus.download(\n"
                "      {'AURN': ['MY1'], 'OpenAQ': ['2178']},\n"
                "      start_date=start,\n"
                "      end_date=end\n"
                "  )"
            )

        all_data = {}

        for source_name, source_sites in sources.items():
            source_spec = get_source(source_name)
            if not source_spec:
                import warnings

                warnings.warn(f"Unknown source '{source_name}', skipping", UserWarning)
                continue

            source_type = source_spec.get("type", "network")

            try:
                if source_type == "network":
                    from .networks import download as network_download

                    data = network_download(
                        source_name, source_sites, start_date, end_date
                    )
                elif source_type == "portal":
                    from .portals import download as portal_download

                    data = portal_download(
                        source_name, source_sites, start_date, end_date
                    )
                else:
                    raise ValueError(f"Unknown source type: {source_type}")

                all_data[source_name] = data

            except Exception as e:
                import warnings

                warnings.warn(
                    f"Failed to download from {source_name}: {e}", UserWarning
                )
                all_data[source_name] = pd.DataFrame(columns=_STANDARD_COLUMNS)

        # Combine results
        if combine:
            non_empty = [df for df in all_data.values() if not df.empty]
            if non_empty:
                return pd.concat(non_empty, ignore_index=True)
            else:
                return pd.DataFrame(columns=_STANDARD_COLUMNS)
        else:
            return all_data

    # Case 3: List of sources (old multi-source pattern) - reject with helpful error
    elif isinstance(sources, list):
        raise ValueError(
            "Multiple sources require explicit site mapping.\n\n"
            "Use dict format:\n"
            "  aeolus.download({\n"
            "      'AURN': ['MY1', 'MY2'],\n"
            "      'OpenAQ': ['2178', '2179']\n"
            "  }, start_date, end_date)\n\n"
            "Or call submodules separately:\n"
            "  aurn = aeolus.networks.download('AURN', ['MY1'], start, end)\n"
            "  openaq = aeolus.portals.download('OpenAQ', ['2178'], start, end)\n"
            "  combined = pd.concat([aurn, openaq])"
        )

    else:
        raise TypeError(
            f"sources must be str or dict, got {type(sources).__name__}\n\n"
            "Valid formats:\n"
            "  - String: aeolus.download('AURN', ['MY1'], start, end)\n"
            "  - Dict: aeolus.download({'AURN': ['MY1']}, start_date=start, end_date=end)"
        )


def get_source_info(source: str) -> dict[str, Any]:
    """
    Get information about a data source.

    Args:
        source: Name of the data source

    Returns:
        dict: Dictionary with source information:
            - name: Display name of the source
            - type: "network" or "portal"
            - requires_api_key: Whether an API key is needed

    Raises:
        ValueError: If source is not registered

    Example:
        >>> info = aeolus.get_source_info("AURN")
        >>> print(info)
        {'name': 'AURN', 'type': 'network', 'requires_api_key': False}
        >>>
        >>> info = aeolus.get_source_info("OpenAQ")
        >>> print(info)
        {'name': 'OpenAQ', 'type': 'portal', 'requires_api_key': True}
    """
    source_obj = get_source(source)
    if source_obj is None:
        available = ", ".join(list_sources())
        raise ValueError(f"Source '{source}' not found. Available sources: {available}")

    return {
        "name": source_obj["name"],
        "type": source_obj.get("type", "network"),
        "requires_api_key": source_obj["requires_api_key"],
    }


# Convenience function aliases for backward compatibility
def fetch(
    sources: str | dict[str, list[str]],
    sites: list[str] | None = None,
    start_date: datetime = None,
    end_date: datetime = None,
    **kwargs,
) -> pd.DataFrame:
    """
    Alias for download(). Download air quality data.

    Args:
        sources: Source name(s) to download from
        sites: List of site codes (when sources is a string)
        start_date: Start of date range
        end_date: End of date range
        **kwargs: Additional arguments passed to download()

    Returns:
        pd.DataFrame: Air quality data

    Example:
        >>> data = aeolus.fetch(
        ...     "AURN",
        ...     ["MY1"],
        ...     datetime(2024, 1, 1),
        ...     datetime(2024, 1, 31)
        ... )
    """
    return download(sources, sites, start_date, end_date, **kwargs)


# ============================================================================
# find_sites() — Unified Site Discovery
# ============================================================================

# Networks whose fetch_metadata accepts a ``bbox`` keyword argument.
_BBOX_AWARE_NETWORKS = {"SENSOR_COMMUNITY", "AIRNOW"}


def _fetch_network_sites(
    name: str, spec: dict, search_bbox: tuple | None, filters: dict
) -> pd.DataFrame:
    """Fetch site metadata from a network source."""
    kwargs = dict(filters)
    if search_bbox is not None and name in _BBOX_AWARE_NETWORKS:
        kwargs["bbox"] = search_bbox
    try:
        return spec["fetch_metadata"](**kwargs)
    except TypeError:
        # Source's fetch_metadata doesn't accept these kwargs — call bare.
        return spec["fetch_metadata"]()


def _fetch_portal_sites(
    name: str, spec: dict, search_bbox: tuple | None, filters: dict
) -> pd.DataFrame:
    """Fetch site metadata from a portal source."""
    kwargs = dict(filters)
    if search_bbox is not None:
        kwargs["bbox"] = search_bbox
    if not kwargs:
        warnings.warn(
            f"Skipping {name}: portal source requires spatial or keyword filters",
            UserWarning,
        )
        return _empty_metadata_frame()
    fetch_fn = spec.get("fetch_metadata") or spec.get("search")
    return fetch_fn(**kwargs)


def find_sites(
    source: str | list[str] | None = None,
    near: tuple[float, float] | None = None,
    radius_km: float = 50.0,
    bbox: tuple[float, float, float, float] | None = None,
    include_all: bool = False,
    **filters: Any,
) -> pd.DataFrame:
    """
    Find air quality monitoring sites across one or more data sources.

    This is the main convenience function for discovering sites.  It unifies
    network and portal sources behind a single call and supports optional
    spatial filtering.

    Source selection:
        - ``source="AURN"`` — single source
        - ``source=["AURN", "SAQN"]`` — multiple named sources
        - ``source=None`` (default) — free sources only (no API key required)
        - ``source=None, include_all=True`` — all sources; warns on failures

    Spatial filtering:
        - ``near=(lat, lon)`` + ``radius_km`` — circular search.
          Adds ``distance_km`` column, sorted nearest-first.
        - ``bbox=(min_lon, min_lat, max_lon, max_lat)`` — rectangular filter.
        - Mutually exclusive (``ValueError`` if both).
        - No spatial args — return all sites for the selected source(s).

    Args:
        source: Source name(s).  ``None`` defaults to free sources.
        near: ``(latitude, longitude)`` for circular search.
        radius_km: Radius in km when *near* is used (default 50).
        bbox: ``(min_lon, min_lat, max_lon, max_lat)`` rectangular filter.
        include_all: When *source* is ``None``, include sources that require
            an API key and warn on failures.
        **filters: Source-specific keyword filters (e.g. ``country``,
            ``sensor_type``, ``location_type``).

    Returns:
        DataFrame with core columns
        ``[site_code, site_name, latitude, longitude, source_network]``
        plus ``distance_km`` when *near* is used, plus any source-specific
        extras.  Output feeds directly into ``aeolus.download()``.

    Raises:
        ValueError: If *near* and *bbox* are both provided, or if an
            unknown source is requested.

    Examples:
        >>> import aeolus
        >>> # All free-source sites near central London
        >>> sites = aeolus.find_sites(near=(51.5074, -0.1278), radius_km=20)
        >>> # AURN sites only
        >>> sites = aeolus.find_sites("AURN")
        >>> # Multiple sources with bbox
        >>> sites = aeolus.find_sites(
        ...     ["AURN", "SAQN"],
        ...     bbox=(-0.5, 51.3, 0.3, 51.7),
        ... )
    """
    # --- validate inputs ---
    if near is not None and bbox is not None:
        raise ValueError(
            "near and bbox are mutually exclusive. "
            "Use near=(lat, lon) for circular search or "
            "bbox=(min_lon, min_lat, max_lon, max_lat) for rectangular."
        )

    # --- determine source list ---
    if source is not None:
        if isinstance(source, str):
            source_names = [source.upper()]
        else:
            source_names = [s.upper() for s in source]
        for name in source_names:
            if not source_exists(name):
                available = ", ".join(_list_sources())
                raise ValueError(
                    f"Unknown source: {name}\nAvailable sources: {available}"
                )
    else:
        source_names = []
        for name in _list_sources():
            spec = get_source(name)
            if include_all or not spec["requires_api_key"]:
                source_names.append(name)

    # --- compute search bbox from near if needed ---
    search_bbox: tuple | None = None
    if near is not None:
        from .geo import near_to_bbox

        search_bbox = near_to_bbox(near[0], near[1], radius_km)
    elif bbox is not None:
        search_bbox = bbox

    # --- fetch from each source ---
    results: list[pd.DataFrame] = []
    for name in source_names:
        spec = get_source(name)
        source_type = spec.get("type", "network")
        try:
            if source_type == "portal":
                df = _fetch_portal_sites(name, spec, search_bbox, filters)
            else:
                df = _fetch_network_sites(name, spec, search_bbox, filters)
            if df is not None and not df.empty:
                results.append(df)
        except Exception as e:
            warnings.warn(
                f"Failed to fetch sites from {name}: {e}",
                UserWarning,
            )

    if not results:
        return _empty_metadata_frame()

    combined = pd.concat(results, ignore_index=True)

    # --- spatial post-filtering ---
    if near is not None:
        from .geo import haversine_distance

        lat, lon = near
        has_coords = combined["latitude"].notna() & combined["longitude"].notna()
        combined = combined[has_coords].copy()
        combined["distance_km"] = combined.apply(
            lambda row: haversine_distance(lat, lon, row["latitude"], row["longitude"]),
            axis=1,
        )
        combined = combined[combined["distance_km"] <= radius_km]
        combined = combined.sort_values("distance_km").reset_index(drop=True)
    elif bbox is not None:
        min_lon, min_lat, max_lon, max_lat = bbox
        has_coords = combined["latitude"].notna() & combined["longitude"].notna()
        mask = (
            has_coords
            & combined["latitude"].between(min_lat, max_lat)
            & combined["longitude"].between(min_lon, max_lon)
        )
        combined = combined[mask].reset_index(drop=True)

    # --- order columns: core -> distance_km -> extras ---
    core = list(_METADATA_COLUMNS)
    if "distance_km" in combined.columns:
        ordered = core + ["distance_km"]
    else:
        ordered = list(core)
    extras = [c for c in combined.columns if c not in ordered]
    combined = combined[ordered + extras]

    return combined
