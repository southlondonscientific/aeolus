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
London Air Quality Network (LAQN) Data Source.

This module provides metadata access and source registration for the LAQN,
London's main regulatory air quality monitoring network. The network is
managed by the Environmental Research Group (ERG) at Imperial College London
and provides hourly data from ~250 monitoring sites across Greater London.

Pollutants measured: CO, NO2, O3, PM10, PM2.5, SO2

Data is fetched from the openair RData feed at
``https://www.londonair.org.uk/r_data/<SITE>_<YEAR>.RData`` via the shared
``regulatory.make_data_fetcher`` factory — orders of magnitude faster than
the legacy ERG REST API path.

Metadata still comes from the ERG/London Air JSON API
(`https://api.erg.ic.ac.uk/AirQuality/`) because the openair convention's
``LAQN_metadata.RData`` URL does not exist; the related ``sites.RData`` file
is the broader Imperial superset (includes non-LAQN networks). The ERG API
also exposes richer site-type information (Kerbside/Roadside/etc.).
"""

import warnings

import pandas as pd
import requests

from ..decorators import retry_on_network_error
from ..registry import register_source
from ..transforms import (
    add_column,
    compose,
    reset_index,
    select_columns,
)
from ..types import (
    METADATA_COLUMNS,
    AeolusDataWarning,
    empty_metadata_frame,
)
from .regulatory import (
    LAQN_COLUMN_MAP,
    make_data_fetcher,
    normalise_regulatory_data,
)

# ============================================================================
# CONSTANTS
# ============================================================================

API_BASE = "https://api.erg.ic.ac.uk/AirQuality"


# ============================================================================
# HTTP CLIENT
# ============================================================================


@retry_on_network_error
def _get_json(path: str) -> dict | None:
    """GET a JSON response from the London Air API."""
    url = f"{API_BASE}/{path}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ============================================================================
# METADATA
# ============================================================================


def normalise_laqn_metadata():
    """Return a compose() pipeline that normalises LAQN site metadata."""
    return compose(
        add_column("source_network", "LAQN"),
        add_column("measurands", None),
        add_column(
            "latitude",
            lambda df: pd.to_numeric(df["latitude"], errors="coerce"),
        ),
        add_column(
            "longitude",
            lambda df: pd.to_numeric(df["longitude"], errors="coerce"),
        ),
        select_columns(*METADATA_COLUMNS, "location_type"),
        reset_index(),
    )


def fetch_laqn_metadata(**filters) -> pd.DataFrame:
    """Fetch metadata for all LAQN monitoring sites.

    Returns a DataFrame with the standard metadata schema. Only sites with
    valid coordinates are included. Closed sites are included (they have
    historical data).
    """
    data = _get_json("Information/MonitoringSites/GroupName=London/Json")
    if data is None:
        warnings.warn(
            "Failed to fetch LAQN metadata from ERG API",
            AeolusDataWarning,
            stacklevel=2,
        )
        return empty_metadata_frame()

    sites = data.get("Sites", {}).get("Site", [])
    if not sites:
        warnings.warn(
            "LAQN ERG API returned no sites",
            AeolusDataWarning,
            stacklevel=2,
        )
        return empty_metadata_frame()

    rows = []
    for s in sites:
        lat = s.get("@Latitude", "")
        lon = s.get("@Longitude", "")
        if not lat or not lon:
            continue
        rows.append({
            "site_code": s["@SiteCode"],
            "site_name": s.get("@SiteName", "").strip("- "),
            "latitude": lat,
            "longitude": lon,
            "location_type": s.get("@SiteType", "") or None,
        })

    if not rows:
        warnings.warn(
            "LAQN ERG API returned no sites with valid coordinates",
            AeolusDataWarning,
            stacklevel=2,
        )
        return empty_metadata_frame()

    raw = pd.DataFrame(rows)
    return normalise_laqn_metadata()(raw)


# ============================================================================
# SOURCE REGISTRATION
# ============================================================================

# Data path uses the openair RData feed (fast, ~1s/site/year).
fetch_laqn_data = make_data_fetcher("laqn", column_map=LAQN_COLUMN_MAP)

register_source("LAQN", {
    "type": "network",
    "name": "London Air Quality Network",
    "fetch_metadata": fetch_laqn_metadata,
    "fetch_data": fetch_laqn_data,
    "normalise": normalise_regulatory_data("LAQN"),
    "requires_api_key": False,
})
