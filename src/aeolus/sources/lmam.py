# Aeolus: download and standardise air quality data
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
LMAM — Locally-Managed Automatic Monitoring.

DEFRA's umbrella feed for automatic air quality stations operated by local
authorities and regional networks outside the national strategy (AURN, SAQN,
WAQN, NI, AQE). At time of writing this covers six active provider networks:

- ``sussex``    — Sussex Air Quality Network         (~53 sites)
- ``kent``      — Kent and Medway Air Quality        (~44 sites)
- ``aqdm``      — UK Air Quality (Defra-managed)     (~59 sites)
- ``nlincs``    — Air Quality in North Lincolnshire  (~28 sites)
- ``leicester`` — Leicester Council AQ Network       (~7 sites)
- ``hants``     — Hampshire Air Quality Network      (~6 sites)

Pollutants measured: NO, NO2, NOXasNO2, O3, SO2, CO, PM10, PM2.5 (subset
varies by site — see the ``measurands`` metadata column).

The metadata feed at ``LMAM/R_data/LMAM_metadata.RData`` also references
``london`` (LAQN, already covered as a separate source), ``aqengland``
(Hertfordshire/Bedfordshire) and ``essex`` provider codes, but per-site
RData files do not currently exist for those — they are filtered out at
metadata time so ``find_sites("LMAM")`` only returns sites whose data
endpoints are reachable.

Per-site data URL pattern:
    ``https://uk-air.defra.gov.uk/openair/LMAM/R_data/{pcode}/{SITE}_{YEAR}.RData``

The ``{pcode}/`` subfolder is looked up from the metadata frame; the data
fetcher caches this mapping after the first call.

API: ``https://uk-air.defra.gov.uk/openair/LMAM/R_data/``
Background: ``https://uk-air.defra.gov.uk/networks/network-info?view=nondefraaqmon``
"""

import warnings

import pandas as pd

from ..registry import register_source
from ..transforms import (
    add_column,
    compose,
    rename_columns,
    reset_index,
    select_columns,
)
from ..types import (
    METADATA_COLUMNS,
    AeolusDataWarning,
    empty_metadata_frame,
)
from .regulatory import (
    METADATA_URLS,
    fetch_rdata,
    make_data_fetcher,
    normalise_regulatory_data,
)

# ============================================================================
# CONSTANTS
# ============================================================================

# Provider codes whose data files exist on the LMAM server. Other pcodes
# present in the metadata (london, aqengland, essex) currently 404 at the
# data path; ``london`` sites are reached via the dedicated LAQN source.
DATA_PROVIDER_CODES = frozenset({
    "sussex", "kent", "aqdm", "nlincs", "leicester", "hants",
})


# ============================================================================
# METADATA
# ============================================================================


def _normalise_lmam_metadata(raw: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the (site, parameter) row structure into one row per site
    with measurands as a comma-separated list, then conform to the standard
    metadata schema.
    """
    if raw.empty:
        return empty_metadata_frame()

    # The metadata file has one row per (site, parameter, instrument-period).
    # Collapse to one row per site, deduplicating parameters across rows.
    # Some early rows have NaN coords — keep them out so find_sites works.
    raw = raw.dropna(subset=["latitude", "longitude"])

    grouped = (
        raw.groupby("site_id", as_index=False)
        .agg({
            "site_name": "first",
            "location_type": "first",
            "latitude": "first",
            "longitude": "first",
            "provider": "first",
            "pcode": "first",
            "parameter": lambda s: ",".join(sorted(set(s.dropna()))),
        })
        .rename(columns={"parameter": "measurands"})
    )

    # Drop sites whose pcode has no data files on the server.
    grouped = grouped[grouped["pcode"].isin(DATA_PROVIDER_CODES)]

    if grouped.empty:
        return empty_metadata_frame()

    return compose(
        rename_columns({
            "site_id": "site_code",
            "provider": "owner",
        }),
        add_column("source_network", "LMAM"),
        select_columns(*METADATA_COLUMNS, "location_type", "pcode"),
        reset_index(),
    )(grouped)


# Lazy site→pcode cache, populated on first metadata or data fetch.
_pcode_cache: dict[str, str] | None = None


def _populate_pcode_cache(meta_df: pd.DataFrame) -> None:
    """Build the site_code → pcode lookup from a raw or normalised metadata
    frame. Subsequent calls reuse the cache.

    On any unexpected shape (missing ``pcode`` column, missing site-code
    column) leave the cache as ``None`` so the next call retries the
    metadata fetch rather than latching to an empty dict that would
    silently break every subsequent data fetch.
    """
    global _pcode_cache
    if "pcode" not in meta_df.columns:
        return
    if "site_id" in meta_df.columns:
        codes = meta_df["site_id"]
    elif "site_code" in meta_df.columns:
        codes = meta_df["site_code"]
    else:
        return
    pcodes = meta_df["pcode"]
    _pcode_cache = {
        str(c).upper(): str(p)
        for c, p in zip(codes, pcodes)
        if isinstance(p, str) and p in DATA_PROVIDER_CODES
    }


def fetch_lmam_metadata(**filters) -> pd.DataFrame:
    """Fetch metadata for LMAM monitoring sites.

    Returns a DataFrame with the standard metadata schema plus
    ``location_type`` and ``pcode`` columns. Only sites belonging to a
    provider network whose data files exist on the LMAM server are
    returned (see ``DATA_PROVIDER_CODES``).
    """
    raw = fetch_rdata(METADATA_URLS["lmam"])
    if raw is None:
        warnings.warn(
            "Failed to fetch LMAM metadata",
            AeolusDataWarning,
            stacklevel=2,
        )
        return empty_metadata_frame()

    normalised = _normalise_lmam_metadata(raw)
    if normalised.empty:
        warnings.warn(
            "LMAM metadata feed returned no usable sites",
            AeolusDataWarning,
            stacklevel=2,
        )
    _populate_pcode_cache(normalised)
    return normalised


# ============================================================================
# DATA
# ============================================================================


def _site_path(site_code: str) -> str | None:
    """Return ``{pcode}/`` for a site, fetching metadata if not yet cached.

    Returns ``None`` if the site is unknown or belongs to a provider whose
    data files are not published; the data fetcher will then skip it with
    a warning.
    """
    global _pcode_cache
    if _pcode_cache is None:
        # Trigger metadata fetch to populate the cache.
        fetch_lmam_metadata()
    pcode = (_pcode_cache or {}).get(site_code.upper())
    return f"{pcode}/" if pcode else None


fetch_lmam_data = make_data_fetcher("lmam", site_path=_site_path)


# ============================================================================
# SOURCE REGISTRATION
# ============================================================================

register_source("LMAM", {
    "type": "network",
    "name": "Locally-Managed Automatic Monitoring",
    "fetch_metadata": fetch_lmam_metadata,
    "fetch_data": fetch_lmam_data,
    "normalise": normalise_regulatory_data("LMAM"),
    "requires_api_key": False,
})
