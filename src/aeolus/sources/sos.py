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
UK-AIR Sensor Observation Service (SOS) data source.

Provides near-real-time access to UK regulatory air quality data via the
UK-AIR SOS REST API. This covers the same physical stations as the RData
sources (AURN, SAQN, WAQN, NI, AQE) but supports temporal filtering —
you can request just the last hour instead of downloading year-long files.

SOS API base: https://uk-air.defra.gov.uk/sos-ukair/api/v1/

Station mapping uses coordinate matching: SOS stations are matched to
RData metadata sites by geographic proximity (<200m).
"""

import functools
import json
import logging
import re
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from ..decorators import retry_on_network_error
from ..geo import haversine_distance
from ..registry import register_source
from ..types import AeolusDataWarning, empty_data_frame

logger = logging.getLogger(__name__)

SOS_BASE_URL = "https://uk-air.defra.gov.uk/sos-ukair/api/v1"

# EIONET pollutant ID → Aeolus measurand name
EIONET_POLLUTANT_MAP = {
    1: "SO2",
    5: "PM10",
    7: "O3",
    8: "NO2",
    9: "NOXasNO2",
    10: "CO",
    38: "NO",
    6001: "PM2.5",
}

# Sentinel value used by SOS for missing data
_MISSING_SENTINEL = -99.0

# Networks that have SOS backends
_SOS_NETWORKS = ["aurn", "saqn", "waqn", "ni", "aqe"]


# ============================================================================
# Low-level API helpers
# ============================================================================


@retry_on_network_error
def _fetch_sos_json(endpoint: str, **params) -> dict | list:
    """GET a JSON response from the SOS API."""
    url = f"{SOS_BASE_URL}/{endpoint}"
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def _parse_eionet_id(label_or_uri: str) -> int | None:
    """Extract numeric EIONET pollutant ID from a URI or label string.

    Examples:
        >>> _parse_eionet_id("http://dd.eionet.europa.eu/vocabulary/aq/pollutant/8")
        8
        >>> _parse_eionet_id("8")
        8
    """
    match = re.search(r"(\d+)\s*$", label_or_uri.strip())
    if match:
        return int(match.group(1))
    return None


def _extract_site_name(station_label: str) -> str:
    """Extract site name from SOS station label.

    SOS labels look like "Camden Kerbside-Nitrogen dioxide (air)".
    We strip the pollutant suffix to get the site name.
    """
    # Remove common pollutant suffixes
    suffixes = [
        r"-Nitrogen dioxide \(air\)",
        r"-Nitrogen oxides \(air\)",
        r"-Ozone \(air\)",
        r"-Sulphur dioxide \(air\)",
        r"-Carbon monoxide \(air\)",
        r"-Particulate matter less than 10.*",
        r"-Particulate matter less than 2\.5.*",
        r"-PM10.*",
        r"-PM2\.5.*",
        r"-Arsenic.*",
        r"-Nickel.*",
        r"-.*\(air\)",
        r"-.*\(aerosol\)",
    ]
    name = station_label
    for suffix in suffixes:
        name = re.sub(suffix, "", name)
    return name.strip()


# ============================================================================
# Station mapping — coordinate matching
# ============================================================================


def _fetch_all_timeseries() -> list[dict]:
    """Fetch all expanded timeseries from SOS API.

    Paginates through the full set (typically ~500-1000 timeseries).
    """
    all_ts = []
    offset = 0
    limit = 100
    while True:
        batch = _fetch_sos_json(
            "timeseries", expanded="true", limit=limit, offset=offset
        )
        if not batch:
            break
        all_ts.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return all_ts


@functools.lru_cache(maxsize=1)
def _get_all_timeseries_cached() -> tuple:
    """Cached version — returns tuple for hashability."""
    return tuple(_fetch_all_timeseries())


def _build_station_mapping(
    network: str,
) -> dict[str, list[dict]]:
    """Map RData site codes to SOS timeseries IDs via coordinate matching.

    For each SOS timeseries, finds the nearest RData metadata site within
    200m. Groups timeseries by matched site_code.

    Args:
        network: Network name (e.g. "aurn", "saqn")

    Returns:
        Dict mapping site_code → list of dicts with keys:
            ts_id, measurand, uom
    """
    from .regulatory import make_metadata_fetcher

    # Fetch RData metadata for this network
    fetch_meta = make_metadata_fetcher(network)
    meta_df = fetch_meta()
    if meta_df.empty:
        return {}

    # Build a lookup of (lat, lon) → site_code from metadata
    meta_sites = []
    for _, row in meta_df.iterrows():
        if pd.notna(row.get("latitude")) and pd.notna(row.get("longitude")):
            meta_sites.append(
                (row["site_code"], float(row["latitude"]), float(row["longitude"]))
            )

    if not meta_sites:
        return {}

    # Fetch all SOS timeseries
    all_ts = list(_get_all_timeseries_cached())

    # Match each SOS timeseries to the nearest metadata site
    mapping: dict[str, list[dict]] = {}

    for ts in all_ts:
        station = ts.get("station", {})
        coords = station.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            continue

        # UK-AIR SOS returns [lat, lon, elevation] — not GeoJSON [lon, lat] order
        sos_lat, sos_lon = float(coords[0]), float(coords[1])

        # Parse pollutant from EIONET phenomenon
        phenomenon = (
            ts.get("parameters", {}).get("phenomenon", {}).get("id", "")
        )
        eionet_id = _parse_eionet_id(str(phenomenon))
        if eionet_id is None or eionet_id not in EIONET_POLLUTANT_MAP:
            continue

        measurand = EIONET_POLLUTANT_MAP[eionet_id]

        # Find nearest metadata site within 200m
        best_code = None
        best_dist = float("inf")
        for code, meta_lat, meta_lon in meta_sites:
            dist = haversine_distance(sos_lat, sos_lon, meta_lat, meta_lon)
            if dist < best_dist:
                best_dist = dist
                best_code = code

        if best_code is not None and best_dist <= 0.2:  # 200m threshold
            ts_info = {
                "ts_id": str(ts["id"]),
                "measurand": measurand,
                "uom": ts.get("uom", "ug.m-3").replace(".", "/"),
            }
            mapping.setdefault(best_code, []).append(ts_info)

    return mapping


# Per-network mapping caches
_network_mappings: dict[str, dict[str, list[dict]]] = {}

_MAPPING_FILE = Path(__file__).parent / "_sos_mapping.json"
_STALENESS_DAYS = 90


def _load_static_mapping() -> dict | None:
    """Load the static SOS mapping from the shipped JSON file.

    Returns the full mapping dict (with ``_generated`` key), or ``None``
    if the file is missing or corrupt.  Warns if the mapping is older
    than 90 days.
    """
    if not _MAPPING_FILE.exists():
        return None

    try:
        with open(_MAPPING_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load static SOS mapping: %s", e)
        return None

    # Check staleness
    generated = data.get("_generated")
    if generated:
        try:
            gen_dt = datetime.fromisoformat(generated)
            if gen_dt.tzinfo is None:
                gen_dt = gen_dt.replace(tzinfo=timezone.utc)
            age = datetime.now(tz=timezone.utc) - gen_dt
            if age.days > _STALENESS_DAYS:
                warnings.warn(
                    f"SOS station mapping is {age.days} days old "
                    f"(generated {generated}). Consider running "
                    f"rebuild_sos_mapping() to refresh it.",
                    AeolusDataWarning,
                    stacklevel=3,
                )
        except (ValueError, TypeError):
            pass

    return data


def _get_network_mapping(network: str) -> dict[str, list[dict]]:
    """Get the station mapping for a network.

    Tries the static JSON file first, then falls back to live
    coordinate matching via the SOS API.
    """
    if network in _network_mappings:
        return _network_mappings[network]

    # Try static mapping
    static = _load_static_mapping()
    if static is not None and network in static:
        _network_mappings[network] = static[network]
        return _network_mappings[network]

    # Fall back to live mapping
    _network_mappings[network] = _build_station_mapping(network)
    return _network_mappings[network]


def rebuild_sos_mapping() -> Path:
    """Rebuild the static SOS station mapping file.

    Fetches all SOS timeseries and matches them to RData metadata
    for each network.  Writes the result to ``_sos_mapping.json``
    in the package directory.

    This is a maintainer tool — call it periodically (e.g. in CI)
    to keep the mapping fresh.

    Returns:
        Path to the written mapping file.
    """
    mapping = {"_generated": datetime.now(tz=timezone.utc).isoformat()}

    for net in _SOS_NETWORKS:
        logger.info("Building SOS mapping for %s...", net.upper())
        mapping[net] = _build_station_mapping(net)

    with open(_MAPPING_FILE, "w") as f:
        json.dump(mapping, f, indent=2)

    logger.info("SOS mapping written to %s", _MAPPING_FILE)
    return _MAPPING_FILE


# ============================================================================
# Data fetchers
# ============================================================================


def make_sos_data_fetcher(network: str):
    """Create a data fetcher that retrieves data from the SOS API.

    Args:
        network: Network name (e.g. "aurn")

    Returns:
        DataFetcher function
    """

    def fetch_data(
        sites: list[str], start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        mapping = _get_network_mapping(network)

        # Ensure dates are tz-aware UTC
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        timespan = (
            f"{start_date.strftime('%Y-%m-%dT%H:%M:%SZ')}/"
            f"{end_date.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        )

        from ..progress import track

        results = []
        for site_code in track(sites, f"Fetching {network.upper()} SOS"):
            ts_list = mapping.get(site_code.upper())
            if not ts_list:
                logger.warning(
                    "No SOS timeseries found for site %s on %s",
                    site_code,
                    network.upper(),
                )
                continue

            for ts_info in ts_list:
                try:
                    data = _fetch_sos_json(
                        f"timeseries/{ts_info['ts_id']}/getData",
                        timespan=timespan,
                    )
                except requests.exceptions.RequestException as e:
                    logger.warning(
                        "Failed to fetch SOS data for %s/%s: %s",
                        site_code,
                        ts_info["measurand"],
                        e,
                    )
                    continue

                values = data.get("values", [])
                if not values:
                    continue

                for v in values:
                    val = v.get("value")
                    if val == _MISSING_SENTINEL:
                        continue
                    results.append(
                        {
                            "site_code": site_code.upper(),
                            "date_time": pd.Timestamp(
                                v["timestamp"], unit="ms", tz="UTC"
                            ),
                            "measurand": ts_info["measurand"],
                            "value": float(val),
                            "units": "ug/m3",
                            "source_network": network.upper(),
                            "ratification": "None",
                            "created_at": pd.Timestamp.now(tz="UTC"),
                        }
                    )

        if not results:
            return empty_data_frame()

        return pd.DataFrame(results)

    return fetch_data


def make_sos_latest_fetcher(network: str):
    """Create a fetcher that returns only the most recent reading per site+measurand.

    Fetches the last 4 hours of data and keeps the latest row.

    Args:
        network: Network name (e.g. "aurn")

    Returns:
        Function(sites: list[str]) -> pd.DataFrame
    """
    data_fetcher = make_sos_data_fetcher(network)

    def fetch_latest(sites: list[str]) -> pd.DataFrame:
        now = datetime.now(tz=timezone.utc)
        start = now - timedelta(hours=4)
        df = data_fetcher(sites, start, now)
        if df.empty:
            return df
        idx = df.groupby(["site_code", "measurand"])["date_time"].idxmax()
        return df.loc[idx].reset_index(drop=True)

    return fetch_latest


# ============================================================================
# Registration
# ============================================================================

def _register_sos_sources():
    """Register all SOS network variants."""
    from .regulatory import make_metadata_fetcher

    for net in _SOS_NETWORKS:
        register_source(
            f"{net.upper()}-SOS",
            {
                "type": "network",
                "name": f"{net.upper()} (SOS)",
                "primary": False,
                "fetch_metadata": make_metadata_fetcher(net),
                "fetch_data": make_sos_data_fetcher(net),
                "normalise": lambda df: df,
                "requires_api_key": False,
                "fetch_latest": make_sos_latest_fetcher(net),
            },
        )


_register_sos_sources()
