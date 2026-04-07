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
Smart Dublin (Sonitus) Data Source.

This module provides data fetchers for Dublin City Council's Sonitus
air quality and noise monitoring network, accessed via the Smart Dublin
open data portal.

The network includes:
- National air quality monitors (reference-grade, managed with EPA Ireland)
- Local air quality monitors (indicative PM and gas sensors)
- Noise monitors (excluded from Aeolus — air quality only)

Pollutants measured: NO2, SO2, CO, NO, O3, PM1, PM2.5, PM10, TSP

The API uses public credentials published on the Smart Dublin data portal.
No user-specific API key is required.

Implementation notes:
    All endpoints are POST-only. Auth credentials are passed in the JSON body
    (not HTTP Basic Auth). Start/end times are Unix timestamps as strings.
    The /data endpoint returns 15-minute resolution data with columns varying
    by monitor type (gas vs PM). Negative values can occur from uncalibrated
    sensors and are passed through as-is.

API: https://data.smartdublin.ie/sonitus-api/api/
Dataset: https://data.smartdublin.ie/dataset/sonitus
"""

import warnings
from datetime import datetime, timezone
from logging import getLogger

import pandas as pd
import requests

from ..decorators import retry_on_network_error
from ..progress import track
from ..registry import register_source
from ..transforms import (
    add_column,
    compose,
    convert_timestamps,
    rename_columns,
    reset_index,
    select_columns,
)
from ..types import (
    AeolusDataWarning,
    DATA_COLUMNS,
    METADATA_COLUMNS,
    empty_data_frame,
    empty_metadata_frame,
)

logger = getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

API_BASE = "https://data.smartdublin.ie/sonitus-api/api"

_AUTH_BODY = {
    "username": "dublincityapi",
    "password": "Xpa5vAQ9ki",
}

COLUMN_TO_MEASURAND = {
    "no2": "NO2",
    "so2": "SO2",
    "co": "CO",
    "no": "NO",
    "o3": "O3",
    "pm1": "PM1",
    "pm2_5": "PM2.5",
    "pm10": "PM10",
    "tsp": "TSP",
}

MEASURAND_COLUMNS = set(COLUMN_TO_MEASURAND.keys())

_AQ_LABEL_PREFIXES = ("National Air", "Local Air", "Former Local Air", "Gas ")


# ============================================================================
# HTTP CLIENT
# ============================================================================


@retry_on_network_error
def _call_sonitus_api(endpoint, extra_body=None):
    """POST to a Sonitus API endpoint with auth credentials."""
    url = f"{API_BASE}/{endpoint}"
    body = {**_AUTH_BODY}
    if extra_body:
        body.update(extra_body)
    resp = requests.post(url, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _is_air_quality_monitor(monitor):
    """Return True if the monitor is an air quality (not noise) station."""
    label = monitor.get("label", "")
    serial = monitor.get("serial_number", "")
    return (
        any(label.startswith(prefix) for prefix in _AQ_LABEL_PREFIXES)
        or serial.startswith("DCC-AQ")
        or serial.startswith("DM30-")
        or serial.startswith("0110-")
        or serial.startswith("15")
        or serial.startswith("0325")
    )


def _has_coordinates(monitor):
    """Return True if the monitor has non-empty latitude and longitude."""
    lat = monitor.get("latitude", "")
    lon = monitor.get("longitude", "")
    return bool(lat) and bool(lon)


# ============================================================================
# METADATA NORMALISER
# ============================================================================


def normalise_sonitus_metadata():
    """Return a compose() pipeline that normalises Sonitus metadata."""
    return compose(
        rename_columns({
            "serial_number": "site_code",
            "location": "site_name",
        }),
        add_column("source_network", "SONITUS"),
        add_column("measurands", None),
        add_column(
            "latitude",
            lambda df: pd.to_numeric(df["latitude"], errors="coerce"),
        ),
        add_column(
            "longitude",
            lambda df: pd.to_numeric(df["longitude"], errors="coerce"),
        ),
        select_columns(*METADATA_COLUMNS),
        reset_index(),
    )


# ============================================================================
# METADATA FETCHER
# ============================================================================


def fetch_sonitus_metadata(**filters):
    """Fetch metadata for all Sonitus air quality monitors.

    Returns a DataFrame with the standard metadata schema. Noise monitors
    and monitors without coordinates are excluded.
    """
    monitors = _call_sonitus_api("monitors")
    if monitors is None:
        return empty_metadata_frame()

    aq_monitors = [
        m for m in monitors
        if _is_air_quality_monitor(m) and _has_coordinates(m)
    ]

    if not aq_monitors:
        return empty_metadata_frame()

    raw = pd.DataFrame(aq_monitors)
    normaliser = normalise_sonitus_metadata()
    return normaliser(raw)


# ============================================================================
# DATA NORMALISATION
# ============================================================================


def normalise_sonitus_data(site_code: str) -> callable:
    """Build a normaliser for Sonitus data from a specific monitor."""
    def _normalise(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return empty_data_frame()

        present = [c for c in df.columns if c in MEASURAND_COLUMNS]
        if not present:
            return empty_data_frame()

        melted = df.melt(
            id_vars=["datetime"],
            value_vars=present,
            var_name="measurand_raw",
            value_name="value",
        )

        normaliser = compose(
            add_column("site_code", site_code),
            rename_columns({"datetime": "date_time"}),
            convert_timestamps("date_time", utc=True),
            add_column(
                "measurand",
                lambda df: df["measurand_raw"].map(COLUMN_TO_MEASURAND),
            ),
            add_column("units", "ug/m3"),
            add_column("source_network", "SONITUS"),
            add_column("ratification", "Unvalidated"),
            add_column("created_at", lambda df: datetime.now(timezone.utc)),
            select_columns(*DATA_COLUMNS),
            reset_index(),
        )
        return normaliser(melted)

    return _normalise


# ============================================================================
# DATA FETCHER
# ============================================================================


def _datetime_to_unix(dt: datetime) -> str:
    return str(int(dt.timestamp()))


def fetch_sonitus_data(
    sites: list[str],
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    start_unix = _datetime_to_unix(start_date)
    end_unix = _datetime_to_unix(end_date)

    dfs = []
    for site in track(sites, description="Fetching Sonitus data"):
        result = _call_sonitus_api(
            "data",
            extra_body={
                "monitor": site,
                "start": start_unix,
                "end": end_unix,
            },
        )

        if result is None or not result:
            warnings.warn(
                f"No data returned for Sonitus monitor {site}",
                AeolusDataWarning,
                stacklevel=2,
            )
            continue

        raw = pd.DataFrame(result)
        normaliser = normalise_sonitus_data(site)
        normalised = normaliser(raw)
        if not normalised.empty:
            dfs.append(normalised)

    if not dfs:
        return empty_data_frame()

    return pd.concat(dfs, ignore_index=True)
