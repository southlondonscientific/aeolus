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

import re
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

# Import sources to trigger registration
from . import sources as _sources  # noqa: F401
from .registry import get_source, source_exists
from .registry import list_sources as _list_sources
from .types import DATA_COLUMNS as _STANDARD_COLUMNS
from .types import METADATA_COLUMNS as _METADATA_COLUMNS
from .types import empty_metadata_frame as _empty_metadata_frame


_LAST_RE = re.compile(
    r"^(\d+)\s*"
    r"(min|mins|minute|minutes|h|hr|hrs|hour|hours"
    r"|d|day|days|w|week|weeks|m|month|months|y|year|years)$",
    re.I,
)

_LAST_UNITS = {
    "min": "minutes", "mins": "minutes", "minute": "minutes", "minutes": "minutes",
    "h": "hours", "hr": "hours", "hrs": "hours", "hour": "hours", "hours": "hours",
    "d": "days", "day": "days", "days": "days",
    "w": "weeks", "week": "weeks", "weeks": "weeks",
    "m": "months", "month": "months", "months": "months",
    "y": "years", "year": "years", "years": "years",
}


def _parse_last(last: str) -> tuple[datetime, datetime]:
    """Parse a ``last="30d"`` shorthand into (start_date, end_date).

    Supported units: min/minute/minutes, h/hr/hrs/hour/hours,
    d/day/days, w/week/weeks, m/month/months, y/year/years.
    ``end_date`` is always now (UTC). ``start_date`` is ``end_date - duration``.
    """
    match = _LAST_RE.match(last.strip())
    if not match:
        raise ValueError(
            f"Invalid last value: {last!r}. "
            "Expected format like '6h', '30d', '2w', '6m', '1y'."
        )
    n = int(match.group(1))
    unit = _LAST_UNITS[match.group(2).lower()]

    end = datetime.now(tz=timezone.utc)

    if unit == "minutes":
        start = end - timedelta(minutes=n)
    elif unit == "hours":
        start = end - timedelta(hours=n)
    elif unit == "days":
        start = end - timedelta(days=n)
    elif unit == "weeks":
        start = end - timedelta(weeks=n)
    elif unit == "months":
        total_months = end.year * 12 + end.month - n
        y, m = divmod(total_months - 1, 12)
        m += 1
        day = min(end.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
                            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
        start = end.replace(year=y, month=m, day=day)
    elif unit == "years":
        start = end.replace(year=end.year - n)
    else:
        raise ValueError(f"Unsupported unit: {unit}")

    return start, end


def _fetch_single_source(
    source_name: str, source_sites: list[str], start_date: datetime, end_date: datetime
) -> pd.DataFrame:
    """Fetch data from a single source, using cache if enabled."""
    from . import cache as _cache

    # Check cache
    if _cache.is_enabled():
        # Cache per (source, sorted-site-list, dates)
        cache_site_key = ",".join(sorted(source_sites))
        cached = _cache.get(source_name, cache_site_key, start_date, end_date)
        if cached is not None:
            return cached

    # Fetch from network
    source_spec = get_source(source_name)
    source_type = source_spec.get("type", "network")

    if source_type == "network":
        from .networks import download as network_download
        data = network_download(source_name, source_sites, start_date, end_date)
    elif source_type == "portal":
        from .portals import download as portal_download
        data = portal_download(source_name, source_sites, start_date, end_date)
    else:
        raise ValueError(f"Unknown source type: {source_type}")

    # Store in cache
    if _cache.is_enabled():
        _cache.put(source_name, cache_site_key, start_date, end_date, data)

    return data


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
    sources: str | dict[str, list[str]],
    sites: list[str] | None = None,
    start_date: datetime = None,
    end_date: datetime = None,
    last: str | None = None,
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
    # Handle last= shorthand
    if last is not None:
        if start_date is not None or end_date is not None:
            raise ValueError(
                "Cannot use 'last' together with 'start_date'/'end_date'. "
                "Use one or the other."
            )
        start_date, end_date = _parse_last(last)

    # Validate required parameters
    if start_date is None or end_date is None:
        raise ValueError("start_date and end_date are required (or use last='6h', last='30d', etc.)")

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

        return _fetch_single_source(sources, sites, start_date, end_date)

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
                warnings.warn(f"Unknown source '{source_name}', skipping", UserWarning)
                continue

            try:
                data = _fetch_single_source(
                    source_name, source_sites, start_date, end_date
                )
                all_data[source_name] = data

            except Exception as e:
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
    last: str | None = None,
    **kwargs,
) -> pd.DataFrame:
    """
    Alias for download(). Download air quality data.

    Args:
        sources: Source name(s) to download from
        sites: List of site codes (when sources is a string)
        start_date: Start of date range
        end_date: End of date range
        last: Date range shorthand (e.g. "6h", "30d", "6m")
        **kwargs: Additional arguments passed to download()

    Returns:
        pd.DataFrame: Air quality data

    Example:
        >>> data = aeolus.fetch("AURN", ["MY1"], last="30d")
    """
    return download(sources, sites, start_date, end_date, last=last, **kwargs)


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


# ============================================================================
# get_current() — Near-Real-Time Data via SOS
# ============================================================================

_SOS_BACKENDS = {
    "AURN": "AURN-SOS",
    "SAQN": "SAQN-SOS",
    "WAQN": "WAQN-SOS",
    "NI": "NI-SOS",
    "AQE": "AQE-SOS",
}


def get_current(
    source: str,
    sites: list[str],
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
        DataFrame with the standard 8-column schema, containing only
        the most recent reading per site+measurand.

    Raises:
        ValueError: If the source is not recognised.

    Example:
        >>> latest = aeolus.get_current("AURN", sites=["MY1", "KC1"])
        >>> print(latest[["site_code", "date_time", "measurand", "value"]])
    """
    source_upper = source.upper()

    # Route to SOS backend if available
    backend = _SOS_BACKENDS.get(source_upper, source_upper)

    spec = get_source(backend)
    if spec is None:
        available = ", ".join(list_sources(include_all=True))
        raise ValueError(
            f"Unknown source: {source}\nAvailable sources: {available}"
        )

    # Use fetch_latest if available, otherwise fall back to fetch_data
    # with a short window
    fetch_latest = spec.get("fetch_latest")
    if fetch_latest is not None:
        return fetch_latest(sites)

    # Fallback: fetch last 4 hours and keep the latest reading
    from datetime import timedelta

    now = datetime.now(tz=__import__("datetime").timezone.utc)
    start = now - timedelta(hours=4)

    from .networks import download as network_download

    df = network_download(backend, sites, start, now)
    if df.empty:
        return df

    # Keep only the most recent reading per site + measurand
    idx = df.groupby(["site_code", "measurand"])["date_time"].idxmax()
    return df.loc[idx].reset_index(drop=True)


# ============================================================================
# summarize() — Quick Data Overview
# ============================================================================


def summarize(data: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize a downloaded air quality dataset.

    Provides a quick overview of the data: sites, pollutants, date range,
    record counts, and data completeness per site+pollutant combination.

    Args:
        data: DataFrame from ``aeolus.download()`` with the standard
              8-column schema.

    Returns:
        DataFrame with one row per site+pollutant, columns:
        ``site_code``, ``source_network``, ``measurand``, ``start``,
        ``end``, ``records``, ``valid``, ``data_capture``.

    Example:
        >>> data = aeolus.download("AURN", ["MY1", "KC1"], start, end)
        >>> aeolus.summarize(data)
    """
    if data.empty:
        return pd.DataFrame(
            columns=[
                "site_code", "source_network", "measurand",
                "start", "end", "records", "valid", "data_capture",
            ]
        )

    df = data.copy()
    df["date_time"] = pd.to_datetime(df["date_time"])

    rows = []
    for (site, network, measurand), g in df.groupby(
        ["site_code", "source_network", "measurand"], observed=True
    ):
        dt = g["date_time"]
        total = len(g)
        valid = g["value"].notna().sum()
        start = dt.min()
        end = dt.max()
        # Expected hourly observations between start and end
        span_hours = max(1, (end - start).total_seconds() / 3600)
        dc = valid / span_hours

        rows.append({
            "site_code": site,
            "source_network": network,
            "measurand": measurand,
            "start": start,
            "end": end,
            "records": total,
            "valid": int(valid),
            "data_capture": round(min(dc, 1.0), 3),
        })

    return pd.DataFrame(rows)
