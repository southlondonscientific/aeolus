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

This module provides data fetchers for the LAQN, London's main regulatory
air quality monitoring network. The network is managed by the Environmental
Research Group (ERG) at Imperial College London and provides hourly data
from ~250 monitoring sites across Greater London.

Pollutants measured: CO, NO2, O3, PM10, PM2.5, SO2

The data is accessed via the ERG/London Air JSON API. No API key is required.
Requests for long date ranges are chunked into monthly blocks to avoid timeouts.

API: https://api.erg.ic.ac.uk/AirQuality/
Data portal: https://www.londonair.org.uk/
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

API_BASE = "https://api.erg.ic.ac.uk/AirQuality"

# Maps API species codes to aeolus standard measurand names.
# The API returns "FINE" for PM2.5 in data responses, though the species
# list names it "PM25".
SPECIES_MAP = {
    "CO": "CO",
    "NO2": "NO2",
    "O3": "O3",
    "PM10": "PM10",
    "PM25": "PM2.5",
    "FINE": "PM2.5",
    "SO2": "SO2",
}

# The London Air API returns CO in mg/m3; all other species in ug/m3.
UNITS_MAP = {
    "CO": "mg/m3",
    "NO2": "ug/m3",
    "O3": "ug/m3",
    "PM10": "ug/m3",
    "PM25": "ug/m3",
    "FINE": "ug/m3",
    "SO2": "ug/m3",
}


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
        rename_columns({
            "site_code": "site_code",
            "site_name": "site_name",
        }),
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
        select_columns(*METADATA_COLUMNS),
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
        return empty_metadata_frame()

    sites = data.get("Sites", {}).get("Site", [])
    if not sites:
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
        })

    if not rows:
        return empty_metadata_frame()

    raw = pd.DataFrame(rows)
    return normalise_laqn_metadata()(raw)


# ============================================================================
# DATA
# ============================================================================


def _month_ranges(start: datetime, end: datetime):
    """Yield (start, end) pairs chunked by calendar month."""
    cursor = start.replace(day=1)
    while cursor <= end:
        chunk_start = max(cursor, start)
        # Advance to first day of next month
        if cursor.month == 12:
            next_month = cursor.replace(year=cursor.year + 1, month=1, day=1)
        else:
            next_month = cursor.replace(month=cursor.month + 1, day=1)
        chunk_end = min(next_month, end)
        yield chunk_start, chunk_end
        cursor = next_month


def _fetch_site_data(site_code: str, start: datetime, end: datetime) -> list[dict]:
    """Fetch data for one site, chunking by month to avoid API timeouts."""
    all_points = []
    for chunk_start, chunk_end in _month_ranges(start, end):
        start_str = chunk_start.strftime("%Y-%m-%d")
        end_str = chunk_end.strftime("%Y-%m-%d")
        path = (
            f"Data/Site/SiteCode={site_code}"
            f"/StartDate={start_str}/EndDate={end_str}/Json"
        )
        try:
            data = _get_json(path)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 400:
                logger.warning("LAQN API returned 400 for site %s — skipping", site_code)
                return []
            raise

        if data is None:
            continue

        points = data.get("AirQualityData", {}).get("Data", [])
        if points:
            all_points.extend(points)

    return all_points


def fetch_laqn_data(
    sites: list[str],
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    """Fetch hourly air quality data from the LAQN API.

    Args:
        sites: List of LAQN site codes (e.g. ["MY1", "KC1"])
        start_date: Start of date range
        end_date: End of date range

    Returns:
        DataFrame with the standard 8-column data schema.
    """
    dfs = []
    for site in track(sites, description="Downloading LAQN"):
        points = _fetch_site_data(site, start_date, end_date)
        if not points:
            continue

        raw = pd.DataFrame(points)

        # Filter out rows with empty or missing values
        raw = raw[raw["@Value"].astype(str).str.strip() != ""]

        if raw.empty:
            continue

        normaliser = compose(
            rename_columns({
                "@MeasurementDateGMT": "date_time",
                "@Value": "value",
                "@SpeciesCode": "measurand_raw",
            }),
            convert_timestamps("date_time", utc=True),
            add_column(
                "value",
                lambda df: pd.to_numeric(df["value"], errors="coerce"),
            ),
            add_column(
                "measurand",
                lambda df: df["measurand_raw"].map(SPECIES_MAP),
            ),
            add_column("site_code", site),
            add_column(
                "units",
                lambda df: df["measurand_raw"].map(UNITS_MAP),
            ),
            add_column("source_network", "LAQN"),
            add_column("ratification", "None"),
            add_column("created_at", lambda df: datetime.now(timezone.utc)),
            select_columns(*DATA_COLUMNS),
            reset_index(),
        )

        normalised = normaliser(raw)

        # Drop rows where species wasn't in our map
        normalised = normalised.dropna(subset=["measurand"])

        if not normalised.empty:
            dfs.append(normalised)

    if not dfs:
        warnings.warn(
            f"No data retrieved for LAQN (sites={sites})",
            AeolusDataWarning,
            stacklevel=2,
        )
        return empty_data_frame()

    return pd.concat(dfs, ignore_index=True)


# ============================================================================
# SOURCE REGISTRATION
# ============================================================================

register_source("LAQN", {
    "type": "network",
    "name": "London Air Quality Network",
    "fetch_metadata": fetch_laqn_metadata,
    "fetch_data": fetch_laqn_data,
    "normalise": lambda df: df,
    "requires_api_key": False,
})
