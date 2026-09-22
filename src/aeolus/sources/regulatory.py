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
UK Regulatory Network Data Sources.

This module provides data fetchers for UK regulatory air quality networks
that publish data through the OpenAir project (Ricardo). Supported networks:

- AURN (Automatic Urban and Rural Network)
- SAQN (Scottish Air Quality Network)
- SAQD (Scottish Air Quality Database — alias for SAQN)
- NI (Northern Ireland Air Quality Network)
- WAQN (Wales Air Quality Network)
- AQE (Air Quality England)

All networks follow the same data format (RData files from OpenAir), so they
share common fetching and normalisation functions via factory functions.

Authentication: None required — all endpoints are open.

Primary API endpoints (per-network RData files):

- AURN: https://uk-air.defra.gov.uk/openair/R_data/
- SAQN/SAQD: https://www.scottishairquality.scot/openair/R_data/
- NI: https://www.airqualityni.co.uk/openair/R_data/
- WAQN: https://airquality.gov.wales/sites/default/files/openair/R_data/
- AQE: https://airqualityengland.co.uk/assets/openair/R_data/
- LAQN: https://www.londonair.org.uk/r_data/  (data only — metadata via ERG API)
- LMAM: https://uk-air.defra.gov.uk/openair/LMAM/R_data/  (per-pcode subfolder)

Per-site data URL pattern: ``{base}{SITE}_{YEAR}.RData`` (LMAM inserts a
``{pcode}/`` subfolder — see ``lmam.py``).

Known quirks:

- AQE has ~2000 sites in its metadata but many are closed; active sites
  have recent RData files, closed sites return 404.
- Some sites report CO values in mg/m3 (the original openair convention);
  we label these correctly via per-measurand units mapping.
- ``SAQD`` is a historical alias for ``SAQN`` — same endpoint, kept for
  backwards compatibility.
"""

import os
import struct
import json
import threading
import time
import warnings
from datetime import date, datetime, timedelta, timezone
from logging import warning
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

import numpy as np
import pandas as pd
import rdata
import requests

# Suppress harmless rdata warnings about POSIXct/POSIXt conversion
# These occur when parsing R datetime objects but don't affect functionality
warnings.filterwarnings(
    "ignore",
    message="Missing constructor for R class",
    category=UserWarning,
    module="rdata.conversion._conversion",
)

from ..decorators import retry_on_network_error
from ..registry import register_source
from ..schema import legacy_mirror
from ..transforms import (
    add_column,
    add_measurands_column,
    categorise_columns,
    compose,
    convert_timestamps,
    drop_columns,
    filter_rows,
    melt_measurands,
    rename_columns,
    reset_index,
    select_columns,
)
from ..types import (
    ADAPTER_DATA_COLUMNS,
    AeolusDataWarning,
    DataFetcher,
    MetadataFetcher,
    Normaliser,
    empty_data_frame,
    empty_metadata_frame,
)


# ============================================================================
# CONSTANTS
# ============================================================================

# URLs for each network
METADATA_URLS = {
    "aurn": "https://uk-air.defra.gov.uk/openair/R_data/AURN_metadata.RData",
    "saqn": "https://www.scottishairquality.scot/openair/R_data/SCOT_metadata.RData",
    "saqd": "https://www.scottishairquality.scot/openair/R_data/SCOT_metadata.RData",
    "ni": "https://www.airqualityni.co.uk/openair/R_data/NI_metadata.RData",
    "waqn": "https://airquality.gov.wales/sites/default/files/openair/R_data/WAQ_metadata.RData",
    "aqe": "https://airqualityengland.co.uk/assets/openair/R_data/AQE_metadata.RData",
    "lmam": "https://uk-air.defra.gov.uk/openair/LMAM/R_data/LMAM_metadata.RData",
}

DATA_BASE_URLS = {
    "aurn": "https://uk-air.defra.gov.uk/openair/R_data/",
    "saqn": "https://www.scottishairquality.scot/openair/R_data/",
    "saqd": "https://www.scottishairquality.scot/openair/R_data/",
    "ni": "https://www.airqualityni.co.uk/openair/R_data/",
    "waqn": "https://airquality.gov.wales/sites/default/files/openair/R_data/",
    "aqe": "https://airqualityengland.co.uk/assets/openair/R_data/",
    "laqn": "https://www.londonair.org.uk/r_data/",
    "lmam": "https://uk-air.defra.gov.uk/openair/LMAM/R_data/",
}

# (ratified token, unratified token) in each network's own words. The openair
# metadata gives a `ratified_to` date per (site, parameter); rows on or before
# it are ratified. AURN's tokens follow openair's `<species>_qc`; the other
# UK networks publish "Ratified"/"Provisional" (and "Supplied", which the
# metadata cannot reveal, so it is never emitted here). LMAM and LAQN carry
# no ratification field and stay unwired.
RATIFICATION_TOKENS = {
    "aurn": ("verified", "unverified"),
    "saqn": ("Ratified", "Provisional"),
    "saqd": ("Ratified", "Provisional"),
    "waqn": ("Ratified", "Provisional"),
    "ni": ("Ratified", "Provisional"),
    "aqe": ("Ratified", "Provisional"),
}

# The metadata RData is read by find_sites (site list) and by the ratified_to
# join; one download serves both, remembered for AEOLUS_METADATA_TTL_S seconds
# (default a day) so a long-running process still sees new ratifications.
_METADATA_TTL_S = int(os.environ.get("AEOLUS_METADATA_TTL_S", "86400"))
_metadata_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_ratified_to_cache: dict[str, tuple[int, dict]] = {}


def reset_ratification_lookups() -> None:
    """Forget cached metadata and ratified_to lookups (tests and ops)."""
    _metadata_cache.clear()
    _ratified_to_cache.clear()


def _raw_metadata(network: str) -> pd.DataFrame | None:
    """The network's metadata RData, downloaded at most once per TTL.

    A failed download is not remembered, so the next call retries.
    """
    url = METADATA_URLS.get(network.lower())
    if url is None:
        return None
    hit = _metadata_cache.get(url)
    if hit is not None and time.time() - hit[0] < _METADATA_TTL_S:
        return hit[1]
    df = fetch_rdata(url)
    if df is not None:
        _metadata_cache[url] = (time.time(), df)
    return df


def _ratified_to_lookup(network: str) -> dict[tuple[str, str], date | None]:
    """``(site_code, measurand) -> last ratified date`` for *network*.

    ``None`` means the metadata says ``"Never"``. A pair whose value is
    anything else that is not an ISO date (blank, NA, "ongoing") is left out,
    so its rows get a null ``qa_code`` rather than a status the upstream never
    asserted. Empty, with a warning, if the metadata could not be read.
    """
    network = network.lower()
    df = _raw_metadata(network)
    if df is None or not {"site_id", "parameter", "ratified_to"} <= set(df.columns):
        if df is None:
            warnings.warn(
                f"{network.upper()}: ratification metadata unavailable; qa_code will be "
                "null for this download",
                AeolusDataWarning,
                stacklevel=4,
            )
        return {}
    cached = _ratified_to_cache.get(network)
    if cached is not None and cached[0] == id(df):
        return cached[1]
    lookup: dict[tuple[str, str], date | None] = {}
    for site, param, ratified in zip(df["site_id"], df["parameter"], df["ratified_to"], strict=True):
        if ratified is None or (not isinstance(ratified, str) and pd.isna(ratified)):
            continue
        text = str(ratified).strip()
        key = (str(site).upper(), str(param))
        if text == "Never":
            lookup[key] = None
            continue
        try:
            lookup[key] = date.fromisoformat(text)
        except ValueError:
            continue
    _ratified_to_cache[network] = (id(df), lookup)
    return lookup


def _add_ratification_codes(df: pd.DataFrame, network: str) -> pd.DataFrame:
    """Add ``qa_code`` from the ratified_to join, vectorised.

    Rows whose (site, measurand) the metadata does not list get ``None``.
    """
    ratified_token, unratified_token = RATIFICATION_TOKENS[network.lower()]
    if df.empty:
        return df.assign(qa_code=pd.Series(dtype=object))
    lookup = _ratified_to_lookup(network)
    if not lookup:
        return df.assign(qa_code=pd.Series([None] * len(df), index=df.index, dtype=object))

    keys = pd.MultiIndex.from_arrays(
        [df["site_code"].astype(str).str.upper(), df["measurand"].astype(str)]
    )
    until = pd.Series(
        {k: (pd.Timestamp(v) if v is not None else pd.NaT) for k, v in lookup.items()},
        dtype="datetime64[ns]",
    )
    until.index = pd.MultiIndex.from_tuples(until.index)
    listed = keys.isin(until.index)
    mapped = until.reindex(keys).to_numpy()  # NaT for "Never" and for unlisted pairs
    day = df["date_time"].dt.tz_convert("UTC").dt.tz_localize(None).dt.floor("D").to_numpy()
    ratified = listed & (day <= mapped)  # a NaT comparison is False
    codes = np.where(~listed, None, np.where(ratified, ratified_token, unratified_token))
    return df.assign(qa_code=pd.Series(codes, index=df.index, dtype=object))


# LAQN openair files use lowercase column names and `FINE` for PM2.5; the
# `site` column contains the site code (no separate `code` column). Rename
# to AURN-style so the shared melt/normalise pipeline works unchanged.
LAQN_COLUMN_MAP = {
    "no": "NO",
    "no2": "NO2",
    "nox": "NOXasNO2",
    "o3": "O3",
    "so2": "SO2",
    "co": "CO",
    "pm10": "PM10",
    "FINE": "PM2.5",
}

# The londonair openair files store gases in volume units (ppb; CO in ppm),
# unlike every Defra-family file, which is already in mass units. They are an
# interchange format: openair's ``importImperial`` converts to mass on read,
# and the network itself publishes ug/m3 (its API, LAQN-ERG here, and its
# website). So this is the one place aeolus converts in an adapter rather than
# labelling faithfully — leaving these as ppb would make LAQN disagree with
# LAQN-ERG for the same site and hour.
#
# These are Defra's published 20 °C / 1013 mb factors, not openair's rounded
# 1.91 / 2.00 / 2.66. They are exact: for ratified years the converted file
# reproduces the AURN twin (MY1, KC1, BL0/CLL2) to 0.00 ug/m3 — verified
# 2005-2026, and pinned by TestLAQNUnitsAgainstAURNTwin. Keys are post-rename
# (AURN-style) column names. Particulates are already in ug/m3.
LAQN_VOLUME_TO_MASS = {
    "NO": 1.2474,
    "NO2": 1.9125,
    "NOXasNO2": 1.9125,  # NOx is expressed as NO2
    "O3": 1.9957,
    "SO2": 2.6609,
    "CO": 1.1642,  # ppm -> mg/m3
}

# Pollutants/measurands available in regulatory network data
REGULATORY_MEASURANDS = [
    "O3",
    "NO",
    "NO2",
    "NOXasNO2",
    "SO2",
    "CO",
    "PM10",
    "PM2.5",
    "ETHANE",
    "ETHENE",
    "ETHYNE",
    "PROPANE",
    "PROPENE",
    "iBUTANE",
    "nBUTANE",
    "1BUTENE",
    "t2BUTENE",
    "c2BUTENE",
    "iPENTANE",
    "nPENTANE",
    "13BDIENE",
    "t2PENTEN",
    "1PENTEN",
    "2MEPENT",
    "ISOPRENE",
    "nHEXANE",
    "nHEPTANE",
    "iOCTANE",
    "nOCTANE",
    "BENZENE",
    "TOLUENE",
    "ETHBENZ",
    "mpXYLENE",
    "oXYLENE",
    "123TMB",
    "124TMB",
    "135TMB",
]


# ============================================================================
# HTTP CLIENT
# ============================================================================


@retry_on_network_error
def _get_rdata_bytes(url: str) -> bytes:
    """GET raw RData bytes. Raises, so the retry decorator sees failures
    (connection errors, timeouts, 5xx); 4xx such as a 404 for a site-year
    that doesn't exist are raised once and not retried."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


# ----------------------------------------------------------------------------
# Per-host circuit-breaker
# ----------------------------------------------------------------------------
#
# A retried request to a dead host costs ~6 s of backoff before giving up —
# ~96 s if the host black-holes and each attempt runs to its 30 s timeout — and a bulk
# download asks for one file per site-year, so an outage at one RData host
# would stall for minutes while returning nothing. After
# ``AEOLUS_RDATA_BREAKER_FAILURES`` consecutive failed fetches to a host,
# further requests to *that host* fail fast for
# ``AEOLUS_RDATA_BREAKER_COOLDOWN_S`` seconds; the first call after the
# cooldown probes it again. A 4xx (no file for that site-year) proves the
# host is up and counts as a success. Mirrors the SOS breaker in ``sos.py``.


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


_RDATA_BREAKER_FAILURES = _env_int("AEOLUS_RDATA_BREAKER_FAILURES", 3)
_RDATA_BREAKER_COOLDOWN_S = _env_int("AEOLUS_RDATA_BREAKER_COOLDOWN_S", 60)

_rdata_breaker_lock = threading.Lock()
_rdata_failure_counts: dict[str, int] = {}
_rdata_opened_until: dict[str, datetime] = {}


def _rdata_breaker_is_open(host: str) -> bool:
    with _rdata_breaker_lock:
        opened_until = _rdata_opened_until.get(host)
        if opened_until is None:
            return False
        if datetime.now(tz=timezone.utc) >= opened_until:
            # Cooldown elapsed: half-open. This call probes the host; one more
            # failure reopens the breaker at once, a success closes it.
            del _rdata_opened_until[host]
            _rdata_failure_counts[host] = _RDATA_BREAKER_FAILURES - 1
            return False
        return True


def _record_rdata_success(host: str) -> None:
    with _rdata_breaker_lock:
        _rdata_failure_counts[host] = 0
        _rdata_opened_until.pop(host, None)


def _record_rdata_failure(host: str) -> None:
    with _rdata_breaker_lock:
        count = _rdata_failure_counts.get(host, 0) + 1
        _rdata_failure_counts[host] = count
        if count >= _RDATA_BREAKER_FAILURES and host not in _rdata_opened_until:
            _rdata_opened_until[host] = datetime.now(tz=timezone.utc) + timedelta(
                seconds=_RDATA_BREAKER_COOLDOWN_S
            )
            warning(
                f"{host} failed {count} consecutive fetches; skipping further "
                f"requests to it for {_RDATA_BREAKER_COOLDOWN_S}s"
            )


def reset_rdata_circuit() -> None:
    """Clear circuit-breaker state. Intended for tests and ops use."""
    with _rdata_breaker_lock:
        _rdata_failure_counts.clear()
        _rdata_opened_until.clear()


# Low-level fetcher - downloads and parses RData files
def fetch_rdata(url: str) -> pd.DataFrame | None:
    """
    Fetch and parse an RData file from a URL.

    Args:
        url: URL of the RData file

    Returns:
        pd.DataFrame | None: Parsed DataFrame, or None if fetch/parse fails

    Note:
        This is a low-level function. Use the higher-level fetch_* functions
        for specific networks instead.
    """
    host = urlsplit(url).netloc
    if _rdata_breaker_is_open(host):
        return None

    try:
        content = _get_rdata_bytes(url)
    except requests.exceptions.RequestException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status is not None and status < 500:
            _record_rdata_success(host)  # the host answered; this file is absent
        else:
            _record_rdata_failure(host)
        warning(f"Failed to fetch RData from {url}: {e}")
        return None
    _record_rdata_success(host)

    try:
        parsed = rdata.parser.parse_data(content)
        converted = rdata.conversion.convert(parsed)
        # RData returns a dict with one key - get the first (only) value
        data = converted[next(iter(converted))]
        return pd.DataFrame(data)
    except (ValueError, KeyError, TypeError, StopIteration, struct.error, RuntimeError) as e:
        warning(f"Failed to parse RData from {url}: {e}")
        return None


# SOS mapping cache (loaded once, shared across networks)
_sos_mapping: dict | None = None
_SOS_MAPPING_PATH = Path(__file__).parent / "_sos_mapping.json"


def _load_sos_mapping() -> dict:
    """Load the SOS station mapping, caching for reuse.

    On read errors (corrupt JSON, mid-rebuild file replacement) we return an
    empty dict locally but do NOT assign to ``_sos_mapping`` — the next call
    retries the load rather than latching to an empty cache for the process
    lifetime.
    """
    global _sos_mapping
    if _sos_mapping is not None:
        return _sos_mapping
    try:
        with open(_SOS_MAPPING_PATH) as f:
            _sos_mapping = json.load(f)
            return _sos_mapping
    except (FileNotFoundError, json.JSONDecodeError):
        warning("Could not load SOS mapping; measurands will be unavailable")
        return {}


# ============================================================================
# METADATA
# ============================================================================


# Metadata normalisation pipeline for regulatory networks
def normalise_regulatory_metadata(network_name: str) -> Normaliser:
    """
    Create a normalisation pipeline for regulatory network metadata.

    Args:
        network_name: Name of the network (e.g., "AURN", "SAQN")

    Returns:
        Normaliser: Function that normalises metadata DataFrame
    """
    sos_mapping = _load_sos_mapping()
    site_lookup = sos_mapping.get(network_name.lower(), {})

    return compose(
        drop_columns("parameter", "Parameter_name"),
        rename_columns(
            {
                "site_id": "site_code",
                "local_authority": "owner",
            }
        ),
        add_column("source_network", network_name.upper()),
        add_measurands_column(site_lookup),
        reset_index(),
    )


# ============================================================================
# DATA
# ============================================================================


# Data normalisation pipeline for regulatory networks
def normalise_regulatory_data(network_name: str) -> Normaliser:
    """
    Create a normalisation pipeline for regulatory network data.

    Args:
        network_name: Name of the network (e.g., "AURN", "SAQN")

    Returns:
        Normaliser: Function that normalises data DataFrame
    """

    def normalise(df: pd.DataFrame) -> pd.DataFrame:
        # Identify which measurands are present in this DataFrame
        measurands_present = [m for m in REGULATORY_MEASURANDS if m in df.columns]

        if not measurands_present:
            # No measurands found - return empty DataFrame with standard schema
            warning(f"No measurands found in DataFrame for {network_name}")
            return empty_data_frame()

        # Apply transformation pipeline
        return compose(
            melt_measurands(
                id_vars=["site", "code", "date"],
                measurands=measurands_present,
            ),
            # RData feeds are dense wide tables: hours with no reading melt to
            # value=NaN. Drop them (every other source drops NaN values) so they
            # don't dominate the output and skew downstream means/data-capture.
            filter_rows(lambda d: d["value"].notna()),
            rename_columns(
                {
                    "site": "site_name",
                    "code": "site_code",
                    "date": "date_time",
                }
            ),
            convert_timestamps("date_time", unit="s", utc=True),
            add_column("source_network", network_name.upper()),
            add_column("ratification", "None"),
            add_column(
                "units",
                lambda df: df["measurand"].map(
                    lambda m: "mg/m3" if m == "CO" else "ug/m3"
                ),
            ),
            add_column("created_at", lambda df: datetime.now(timezone.utc)),
            drop_columns("site_name"),
            select_columns(*ADAPTER_DATA_COLUMNS, require_all=True),
        )(df)

    return normalise


# Factory function for creating metadata fetchers
def make_metadata_fetcher(network_name: str) -> MetadataFetcher:
    """
    Create a metadata fetcher function for a specific regulatory network.

    Args:
        network_name: Name of the network (e.g., "aurn", "saqn")

    Returns:
        MetadataFetcher: Function that fetches and normalises metadata
    """

    def fetch_metadata() -> pd.DataFrame:
        df = _raw_metadata(network_name)

        if df is None:
            warnings.warn(
                f"Failed to fetch metadata for {network_name.upper()}",
                AeolusDataWarning,
                stacklevel=2,
            )
            return empty_metadata_frame()

        normaliser = normalise_regulatory_metadata(network_name)
        return normaliser(df)

    return fetch_metadata


# Factory function for creating data fetchers
def make_data_fetcher(
    network_name: str,
    column_map: dict[str, str] | None = None,
    site_path: Callable[[str], str | None] | None = None,
    value_factors: dict[str, float] | None = None,
) -> DataFetcher:
    """
    Create a data fetcher function for a specific regulatory network.

    Args:
        network_name: Name of the network (e.g., "aurn", "saqn")
        column_map: Optional mapping applied with ``DataFrame.rename`` to bring
            non-standard column names (e.g. lowercase LAQN columns, ``FINE``)
            into line with the AURN-style schema before melting.
        site_path: Optional callable mapping a site code to a URL fragment
            inserted between ``base_url`` and ``{SITE}_{YEAR}.RData`` (e.g.
            ``"sussex/"`` for LMAM). Returning ``None`` causes the site to be
            skipped with a warning. When ``None``, no fragment is inserted.

        value_factors: Optional per-column multipliers applied after
            ``column_map``, for files whose values are not in the units the
            shared pipeline labels them with (LAQN only — see
            ``LAQN_VOLUME_TO_MASS``).

    Returns:
        DataFetcher: Function that fetches and normalises data
    """

    def fetch_data(
        sites: list[str], start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        base_url = DATA_BASE_URLS[network_name.lower()]
        years = range(start_date.year, end_date.year + 1)

        from ..progress import track

        results = []
        for site in track(sites, f"Downloading {network_name.upper()}"):
            site_code = site.upper()

            if site_path is not None:
                prefix = site_path(site_code)
                if prefix is None:
                    warnings.warn(
                        f"{network_name.upper()}: site {site_code!r} not "
                        "found in metadata; skipping",
                        AeolusDataWarning,
                        stacklevel=2,
                    )
                    continue
            else:
                prefix = ""

            for year in years:
                url = f"{base_url}{prefix}{site_code}_{year}.RData"
                df = fetch_rdata(url)

                if df is not None and not df.empty:
                    if column_map:
                        df = df.rename(columns=column_map)
                    if value_factors:
                        for column, factor in value_factors.items():
                            if column in df.columns:
                                df[column] = pd.to_numeric(df[column], errors="coerce") * factor
                    # LAQN openair files have no separate `code` column —
                    # the `site` column contains the site code (not a
                    # human-readable name). Provide a `code` column so the
                    # shared melt pipeline works. Downstream `site` is
                    # renamed to `site_name` and dropped before output —
                    # LAQN data therefore has no `site_name` carrying a
                    # real name; consumers wanting a name must join on
                    # `site_code` against `find_sites("LAQN")` metadata.
                    if "code" not in df.columns and "site" in df.columns:
                        df = df.assign(code=df["site"])
                    results.append(df)

        if not results:
            warnings.warn(
                f"No data retrieved for {network_name.upper()} "
                f"(sites={sites}, years={list(years)})",
                AeolusDataWarning,
                stacklevel=2,
            )
            return empty_data_frame(qa=network_name.lower() in RATIFICATION_TOKENS)

        # Concatenate all results
        combined = pd.concat(results, ignore_index=True)

        # Normalise the combined data
        normaliser = normalise_regulatory_data(network_name)
        normalised = normaliser(combined)

        # Filter to the requested date range
        if not normalised.empty and "date_time" in normalised.columns:
            # Ensure start/end dates are tz-aware UTC to match the data
            sd = start_date if start_date.tzinfo else start_date.replace(tzinfo=timezone.utc)
            ed = end_date if end_date.tzinfo else end_date.replace(tzinfo=timezone.utc)
            mask = (normalised["date_time"] >= sd) & (
                normalised["date_time"] <= ed
            )
            normalised = normalised[mask]

        if network_name.lower() in RATIFICATION_TOKENS:
            normalised = _add_ratification_codes(normalised, network_name)
            # The adapter's legacy label must be the one the public frame shows
            normalised["ratification"] = legacy_mirror(network_name, normalised["qa_code"])

        return normalised

    return fetch_data


# ============================================================================
# SOURCE REGISTRATION
# ============================================================================


# Register AURN (the primary network)
register_source(
    "AURN",
    {
        "type": "network",
        "name": "AURN",
        "fetch_metadata": make_metadata_fetcher("aurn"),
        "fetch_data": make_data_fetcher("aurn"),
        "normalise": normalise_regulatory_data("AURN"),
        "requires_api_key": False,
        "sos_backend": "AURN-SOS",
    },
)

# Register SAQN (Scottish Air Quality Network)
register_source(
    "SAQN",
    {
        "type": "network",
        "name": "SAQN",
        "fetch_metadata": make_metadata_fetcher("saqn"),
        "fetch_data": make_data_fetcher("saqn"),
        "normalise": normalise_regulatory_data("SAQN"),
        "requires_api_key": False,
        "sos_backend": "SAQN-SOS",
    },
)

# Register SAQD (alias for SAQN)
# Marked non-primary so it stays out of default list_sources()/find_sites() —
# SAQD and SAQN share the same endpoint and data; SAQN is the documented name.
register_source(
    "SAQD",
    {
        "type": "network",
        "name": "SAQD",
        "fetch_metadata": make_metadata_fetcher("saqd"),
        "fetch_data": make_data_fetcher("saqd"),
        "normalise": normalise_regulatory_data("SAQD"),
        "requires_api_key": False,
        "primary": False,
    },
)

# Register NI (Northern Ireland)
register_source(
    "NI",
    {
        "type": "network",
        "name": "NI",
        "fetch_metadata": make_metadata_fetcher("ni"),
        "fetch_data": make_data_fetcher("ni"),
        "normalise": normalise_regulatory_data("NI"),
        "requires_api_key": False,
        "sos_backend": "NI-SOS",
    },
)

# Register WAQN (Wales Air Quality Network)
register_source(
    "WAQN",
    {
        "type": "network",
        "name": "WAQN",
        "fetch_metadata": make_metadata_fetcher("waqn"),
        "fetch_data": make_data_fetcher("waqn"),
        "normalise": normalise_regulatory_data("WAQN"),
        "requires_api_key": False,
        "sos_backend": "WAQN-SOS",
    },
)

# Register AQE (Air Quality England)
register_source(
    "AQE",
    {
        "type": "network",
        "name": "AQE",
        "fetch_metadata": make_metadata_fetcher("aqe"),
        "fetch_data": make_data_fetcher("aqe"),
        "normalise": normalise_regulatory_data("AQE"),
        "requires_api_key": False,
        "sos_backend": "AQE-SOS",
    },
)

