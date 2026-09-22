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

import inspect
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import pandas as pd

# Import sources to trigger registration
from . import sources as _sources  # noqa: F401
from ._dates import parse_last as _parse_last
from ._dates import resolve_dates as _resolve_dates
from .registry import (
    get_source,
    source_exists,
    unknown_source_message as _unknown_source_message,
)
from .registry import list_sources as _list_sources
from .types import AeolusDataWarning, AeolusExperimentalWarning
from .schema import DATA_COLUMNS as _STANDARD_COLUMNS
from .schema import finalise_data_frame
from .schema import METADATA_COLUMNS as _METADATA_COLUMNS
from .schema import empty_public_metadata_frame, finalise_metadata_frame, with_network_column


_warned_experimental: set[str] = set()


def _warn_if_experimental(source_name: str, spec: dict) -> None:
    """Warn, once per process per source, that an experimental source is in use."""
    if spec.get("status", "stable") != "experimental":
        return
    name = source_name.upper()
    if name in _warned_experimental:
        return
    _warned_experimental.add(name)
    warnings.warn(
        f"{name} support is experimental: {spec.get('status_note') or 'see the source documentation'} "
        f"Details: aeolus.get_source_info({name!r}).",
        AeolusExperimentalWarning,
        stacklevel=4,
    )


def _as_utc(dt: datetime) -> pd.Timestamp:
    """Timestamp of *dt* in UTC; naive datetimes are UTC by library convention."""
    ts = pd.Timestamp(dt)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def _with_requested_range(data: pd.DataFrame, requested_range: tuple) -> pd.DataFrame:
    """Record what was asked for, so ``summarise`` can measure data capture
    against it: sources drop missing values, so the frame alone cannot say
    whether an analyser was silent for most of the period.

    Stored as ISO 8601 strings: pandas serialises ``attrs`` to JSON when
    writing Parquet, so anything else here would break ``to_parquet()``."""
    start, end = requested_range
    data.attrs["aeolus_requested_range"] = [start.isoformat(), end.isoformat()]
    return data


def _fetch_single_source(
    source_name: str,
    source_sites: list[str],
    start_date: datetime | None,
    end_date: datetime | None,
    last: str | None = None,
) -> pd.DataFrame:
    """Dispatch a single-source download to the appropriate submodule.

    Caching is applied inside each submodule's ``download`` so direct
    submodule calls also benefit from the cache.
    """
    source_spec = get_source(source_name)
    source_type = source_spec.get("type", "network")
    _warn_if_experimental(source_name, source_spec)

    if source_type == "network":
        from .networks import download as network_download
        return network_download(source_name, source_sites, start_date, end_date, last)
    if source_type == "portal":
        from .portals import download as portal_download
        return portal_download(source_name, source_sites, start_date, end_date, last)
    raise ValueError(f"Unknown source type: {source_type}")


def list_sources(include_all: bool = False) -> list[str]:
    """
    List available data sources (networks and portals).

    By default, only *primary* sources are listed.  Pass
    ``include_all=True`` to include alternative backends such as the
    SOS variants of UK regulatory networks.

    Args:
        include_all: If True, include non-primary sources.

    Returns:
        list[str]: List of registered source names

    Example:
        >>> sources = aeolus.list_sources()
        >>> print(sources)
        ['AURN', 'SAQN', 'BREATHE_LONDON', 'OPENAQ', ...]
    """
    return _list_sources(include_all=include_all)


def download(
    sources: str | dict[str, list[str]] | None = None,
    sites: list[str] | None = None,
    start_date: datetime = None,
    end_date: datetime = None,
    last: str | None = None,
    combine: bool = True,
    network: str | None = None,
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

    Date Range Shorthand:
        Use ``last`` instead of explicit dates:
        >>> data = aeolus.download("AURN", ["MY1"], last="30d")
        >>> data = aeolus.download("AURN", ["MY1"], last="6m")

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
        last: Date range shorthand, e.g. "6h", "30d", "2w", "6m", "1y".
              Also accepts minutes ("90min") and hours ("24hours").
              Mutually exclusive with start_date/end_date.
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
        >>> # Date range shorthand
        >>> data = aeolus.download("AURN", ["MY1"], last="30d")
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
    # ``network=`` is an alias for the first argument (v0.5.0); choosing a
    # backend for a network is the v0.6.0 routing engine.
    if network is not None:
        if sources is not None:
            raise TypeError("pass either `network=` or `sources`, not both")
        sources = network

    # Resolve last= shorthand and validate that we have a date range.
    # The submodules re-resolve ``last`` themselves so the cache can key on
    # the shorthand; resolving here validates the arguments up front.
    start_date, end_date = _resolve_dates(start_date, end_date, last)
    requested_range = (_as_utc(start_date), _as_utc(end_date))
    if last is not None:
        start_date = end_date = None

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
            raise ValueError(_unknown_source_message(sources))

        return _with_requested_range(
            _fetch_single_source(sources, sites, start_date, end_date, last),
            requested_range,
        )

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
                warnings.warn(
                    f"Unknown source '{source_name}', skipping", AeolusDataWarning
                )
                continue

            try:
                data = _fetch_single_source(
                    source_name, source_sites, start_date, end_date, last
                )
                all_data[source_name] = data

            except Exception as e:
                warnings.warn(
                    f"Failed to download from {source_name}: {e}", AeolusDataWarning
                )
                all_data[source_name] = pd.DataFrame(columns=_STANDARD_COLUMNS)

        # Combine results
        if combine:
            non_empty = [df for df in all_data.values() if not df.empty]
            if non_empty:
                return _with_requested_range(
                    pd.concat(non_empty, ignore_index=True), requested_range
                )
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
            - status: "stable" or "experimental"
            - status_note: Why a source is experimental (None when stable)

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
        raise ValueError(_unknown_source_message(source))

    return {
        "name": source_obj["name"],
        "type": source_obj.get("type", "network"),
        "requires_api_key": source_obj["requires_api_key"],
        "status": source_obj.get("status", "stable"),
        "status_note": source_obj.get("status_note"),
    }


# Convenience function aliases for backward compatibility
def fetch(
    sources: str | dict[str, list[str]] | None = None,
    sites: list[str] | None = None,
    start_date: datetime = None,
    end_date: datetime = None,
    last: str | None = None,
    **kwargs: Any,
) -> pd.DataFrame | dict[str, pd.DataFrame]:
    """
    Alias for download(). Download air quality data.

    Args:
        sources: Source name(s) to download from
        sites: List of site codes (when sources is a string)
        start_date: Start of date range
        end_date: End of date range
        last: Date range shorthand (e.g. "6h", "30d", "6m")
        **kwargs: Additional arguments passed to download(), including
            ``combine``: when False with a dict of sources, returns a
            ``dict[source_name, DataFrame]`` instead of a single frame.

    Returns:
        DataFrame, or ``dict[str, pd.DataFrame]`` when ``combine=False``
        is passed for a multi-source dict input.

    Example:
        >>> data = aeolus.fetch("AURN", ["MY1"], last="30d")
    """
    return download(sources, sites, start_date, end_date, last=last, **kwargs)


# ============================================================================
# find_sites() — Unified Site Discovery
# ============================================================================


def _accepted_kwargs(fn: Callable, kwargs: dict) -> dict:
    """The subset of ``kwargs`` that ``fn``'s signature can take.

    Fetchers differ: some take ``**filters``, some a fixed ``bbox=``, some
    nothing. A keyword one of them does not know (``include_closed`` is only
    meaningful to the AURN family) must not cost another its ``bbox``.
    """
    try:
        params = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return dict(kwargs)
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params):
        return dict(kwargs)
    names = {p.name for p in params if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)}
    return {k: v for k, v in kwargs.items() if k in names}


def _fetch_network_sites(
    name: str, spec: dict, search_bbox: tuple | None, filters: dict
) -> pd.DataFrame:
    """Fetch site metadata from a network source."""
    kwargs = dict(filters)
    if search_bbox is not None and spec.get("bbox_aware"):
        kwargs["bbox"] = search_bbox
    fetch = spec["fetch_metadata"]
    return fetch(**_accepted_kwargs(fetch, kwargs))


def _fetch_portal_sites(
    name: str, spec: dict, search_bbox: tuple | None, filters: dict
) -> pd.DataFrame:
    """Fetch site metadata from a portal source.

    Portals are unbounded — they reject discovery calls without at least
    one filter or a spatial constraint. Raise here so the caller can
    decide whether to surface the failure (single explicit source) or
    warn-and-continue (iterating all sources). This matches
    :func:`aeolus.portals.find_sites` so the same call is consistent
    across the public API and the submodule.
    """
    kwargs = {k: v for k, v in filters.items() if k != "include_closed"}  # AURN-family only; never a portal filter
    if search_bbox is not None:
        kwargs["bbox"] = search_bbox
    if not kwargs:
        raise ValueError(
            f"{name} is a portal and requires search filters or a spatial "
            f"constraint (near=, bbox=).\n\n"
            f"Examples:\n"
            f"  aeolus.find_sites('{name}', country='GB')\n"
            f"  aeolus.find_sites('{name}', near=(51.5, -0.1), radius_km=20)"
        )
    fetch_fn = spec.get("fetch_metadata") or spec.get("search")
    return fetch_fn(**kwargs)


def find_sites(
    source: str | list[str] | None = None,
    near: tuple[float, float] | None = None,
    radius_km: float = 50.0,
    bbox: tuple[float, float, float, float] | None = None,
    measurand: str | list[str] | None = None,
    include_all: bool = False,
    network: str | list[str] | None = None,
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
        measurand: Filter to sites that measure this pollutant (or any of
            the given list).  Sites with a populated ``measurands`` list
            are matched against it.  Sites whose ``measurands`` is
            ``None`` are matched against their source's
            ``default_measurands`` (declared in the SourceSpec) when set,
            and excluded otherwise — this preserves the "old/decommissioned
            site" semantics for networks that populate measurands per-site.
        include_all: When *source* is ``None``, include sources that require
            an API key and warn on failures.
        **filters: Source-specific keyword filters (e.g. ``country``,
            ``sensor_type``, ``location_type``).

    Returns:
        DataFrame with core columns
        ``[site_code, site_name, latitude, longitude, network, country,
        instrument_class, provider, backend, measurands, source_network]``
        (``aeolus.schema.METADATA_COLUMNS``; the last is a deprecated mirror)
        plus ``distance_km`` when *near* is used, plus any source-specific
        extras.  ``measurands`` is a ``list[str]`` of
        pollutant names or ``None`` when unknown.  Output feeds directly
        into ``aeolus.download()``.

    Raises:
        ValueError: If *near* and *bbox* are both provided, or if an
            unknown source is requested.

    Examples:
        >>> import aeolus
        >>> # All free-source sites near central London
        >>> sites = aeolus.find_sites(near=(51.5074, -0.1278), radius_km=20)
        >>> # AURN sites only
        >>> sites = aeolus.find_sites("AURN")
        >>> # NO2 monitors near Birmingham
        >>> sites = aeolus.find_sites(
        ...     "AURN", near=(52.48, -1.89), radius_km=20, measurand="NO2",
        ... )
        >>> # Multiple sources with bbox
        >>> sites = aeolus.find_sites(
        ...     ["AURN", "SAQN"],
        ...     bbox=(-0.5, 51.3, 0.3, 51.7),
        ... )
    """
    if network is not None:
        if source is not None:
            raise TypeError("pass either `network=` or `source`, not both")
        source = network

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
                raise ValueError(_unknown_source_message(name))
    else:
        source_names = []
        for name in _list_sources(include_all=include_all):
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
    # The top-level find_sites is the graceful wrapper: it always returns
    # a DataFrame and warn-and-continues on per-source failures (missing
    # API key, missing filters, etc.). Callers who want loud failures
    # use aeolus.networks.get_metadata / aeolus.portals.find_sites
    # directly — those raise.
    results: list[pd.DataFrame] = []
    for name in source_names:
        spec = get_source(name)
        source_type = spec.get("type", "network")
        _warn_if_experimental(name, spec)
        try:
            if source_type == "portal":
                df = _fetch_portal_sites(name, spec, search_bbox, filters)
            else:
                df = _fetch_network_sites(name, spec, search_bbox, filters)
            if df is not None and not df.empty:
                results.append(finalise_metadata_frame(df, name))
        except Exception as e:
            warnings.warn(
                f"Failed to fetch sites from {name}: {e}",
                AeolusDataWarning,
            )

    if not results:
        return empty_public_metadata_frame()

    combined = pd.concat(results, ignore_index=True)

    # Guarantee the core metadata schema: a source that omits a column
    # (e.g. no per-site measurands) degrades to None/NaN rather than
    # raising a KeyError below.
    from .schema import public_metadata_columns

    for col in public_metadata_columns():
        if col not in combined.columns:
            combined[col] = None

    # --- spatial post-filtering ---
    # Ensure lat/lon are numeric (some sources may return strings)
    combined["latitude"] = pd.to_numeric(combined["latitude"], errors="coerce")
    combined["longitude"] = pd.to_numeric(combined["longitude"], errors="coerce")

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

    # --- measurand filtering ---
    if measurand is not None:
        if isinstance(measurand, str):
            wanted = {measurand}
        else:
            wanted = set(measurand)

        # Cache the per-source default_measurands lookup once.
        source_defaults: dict[str, set[str]] = {}
        for src_name in combined["network"].unique():
            spec = get_source(src_name)
            defaults = (spec or {}).get("default_measurands")
            if defaults:
                source_defaults[src_name] = set(defaults)

        def _matches(m, network) -> bool:
            if isinstance(m, (list, tuple, set)):
                return bool(wanted & set(m))
            # measurands is None / NaN / unknown — fall back to the
            # source-declared defaults if any. This catches sources whose
            # metadata feeds don't expose per-site measurands.
            defaults = source_defaults.get(network)
            if defaults is None:
                return False
            return bool(wanted & defaults)

        # Built without DataFrame.apply(axis=1): on a zero-row frame that
        # returns an empty DataFrame and the boolean index strips every column.
        mask = pd.Series(
            [
                _matches(m, n)
                for m, n in zip(
                    combined["measurands"], combined["network"], strict=True
                )
            ],
            index=combined.index,
            dtype=bool,
        )
        combined = combined[mask].reset_index(drop=True)

    # --- order columns: core -> distance_km -> extras ---
    core = [c for c in _METADATA_COLUMNS if c in combined.columns]
    if "distance_km" in combined.columns:
        ordered = core + ["distance_km"]
    else:
        ordered = list(core)
    extras = [c for c in combined.columns if c not in ordered]
    combined = combined[ordered + extras]

    return combined


# ============================================================================
# get_current() — Near-Real-Time Data via SOS
# ============================================================================


def get_current(
    source: str | None = None,
    sites: list[str] | None = None,
    network: str | None = None,
) -> pd.DataFrame:
    """
    Get the most recent readings for the given sites.

    For UK regulatory networks (AURN, SAQN, WAQN, NI, AQE), this
    automatically routes to the SOS backend which provides near-real-time
    data via the UK-AIR Sensor Observation Service.

    Args:
        source: Source name (e.g. ``"AURN"``).  Automatically routes to
            the SOS backend if one exists, or accepts the SOS name
            directly (e.g. ``"AURN-SOS"``).
        sites: List of site codes to fetch current data for.

    Returns:
        DataFrame with the public 13-column schema, containing only
        the most recent reading per site+measurand.

    Raises:
        ValueError: If the source is not recognised.

    Example:
        >>> latest = aeolus.get_current("AURN", sites=["MY1", "KC1"])
        >>> print(latest[["site_code", "date_time", "measurand", "value"]])
    """
    if network is not None:
        if source is not None:
            raise TypeError("pass either `network=` or `source`, not both")
        source = network
    if source is None or sites is None:
        raise ValueError("get_current() needs a source (or network=) and a list of sites")
    source_upper = source.upper()

    # Route to SOS backend declared by the primary source, if any.
    primary_spec = get_source(source_upper)
    backend = (primary_spec or {}).get("sos_backend", source_upper)

    spec = get_source(backend)
    if spec is None:
        raise ValueError(_unknown_source_message(source))

    # Use fetch_latest if available, otherwise fall back to fetch_data
    # with a short window
    fetch_latest = spec.get("fetch_latest")
    if fetch_latest is not None:
        return finalise_data_frame(fetch_latest(sites), backend)

    # Fallback: fetch last 4 hours and keep the latest reading.
    # Bypass the cache here — "current" data must always be live.
    from datetime import timedelta

    now = datetime.now(tz=timezone.utc)
    start = now - timedelta(hours=4)

    fetch_data = spec.get("fetch_data")
    if fetch_data is None:
        raise ValueError(f"Source {backend} has no fetch_data implementation")
    df = fetch_data(sites, start, now)
    if df.empty:
        return finalise_data_frame(df, backend)

    # Keep only the most recent *valid* reading per site + measurand. Drop
    # NaN-value rows first: near-real-time feeds often publish the newest hour
    # with a timestamp but a NaN (unratified) value, which would otherwise mask
    # an older genuine measurement. A group whose values are all NaN yields no
    # row. (Also sidesteps idxmax on an all-NaT group for the dropped rows.)
    valid = df[df["value"].notna()]
    if valid.empty:
        return finalise_data_frame(valid.reset_index(drop=True), backend)
    idx = valid.groupby(["site_code", "measurand"])["date_time"].idxmax()
    return finalise_data_frame(valid.loc[idx].reset_index(drop=True), backend)


# ============================================================================
# summarise() — Quick Data Overview
# ============================================================================


def summarise(data: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize a downloaded air quality dataset.

    Provides a quick overview of the data: sites, pollutants, date range,
    record counts, and data completeness per site+pollutant combination.

    Args:
        data: DataFrame from ``aeolus.download()`` (the public schema;
              pre-0.5 frames are accepted).

    Returns:
        DataFrame with one row per site+pollutant, columns:
        ``site_code``, ``network``, ``measurand``, ``start``,
        ``end``, ``records``, ``valid``, ``data_capture``.

    Example:
        >>> data = aeolus.download("AURN", ["MY1", "KC1"], start, end)
        >>> aeolus.summarise(data)
    """
    from . import options

    mirror = ["source_network"] if options.legacy_columns else []
    columns = ["site_code", "network", *mirror, "measurand", "start", "end", "records", "valid", "data_capture"]
    if data.empty:
        return pd.DataFrame(columns=columns)

    df = with_network_column(data.copy())
    df["date_time"] = pd.to_datetime(df["date_time"])
    requested = data.attrs.get("aeolus_requested_range")

    rows = []
    for (site, network, measurand), g in df.groupby(
        ["site_code", "network", "measurand"], observed=True
    ):
        dt = g["date_time"]
        total = len(g)
        valid = g["value"].notna().sum()
        start = dt.min()
        end = dt.max()
        # Infer reporting frequency from median gap between consecutive readings,
        # falling back to hourly if there's only one record.
        if total >= 2:
            gaps = dt.sort_values().diff().dropna()
            median_gap = gaps.median().total_seconds() / 3600  # hours
            freq_hours = max(median_gap, 1 / 60)  # floor at 1 minute
        else:
            freq_hours = 1.0
        if requested is not None:
            # Measure against the requested range (capped at now): the frame
            # only spans first-to-last *valid* reading.
            req_start, req_end = (_as_utc(pd.Timestamp(t)) for t in requested)
            req_end = min(req_end, pd.Timestamp.now(tz="UTC"))
            span_hours = max((req_end - req_start).total_seconds() / 3600, 0)
            expected = max(span_hours / freq_hours, 1)
        else:
            span_hours = (end - start).total_seconds() / 3600
            expected = (span_hours / freq_hours) + 1 if span_hours > 0 else 1
        dc = min(valid / expected, 1.0)

        rows.append({
            "site_code": site,
            "network": network,
            "source_network": network,
            "measurand": measurand,
            "start": start,
            "end": end,
            "records": total,
            "valid": int(valid),
            "data_capture": round(dc, 3),
        })

    return pd.DataFrame(rows)[columns]
