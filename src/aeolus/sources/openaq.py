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
OpenAQ data source using the official OpenAQ Python SDK.

OpenAQ <https://openaq.org/> is the leading global air quality data platform,
aggregating measurements from regulatory monitors and low-cost sensors across
100+ countries. This adapter wraps the official ``openaq`` Python SDK rather
than calling the REST API directly — this keeps aeolus aligned with upstream
SDK changes (rate-limit handling, validators, response models) and makes it
easy for users to drop down to the SDK for advanced queries.

If you use aeolus to access OpenAQ data, please cite OpenAQ and acknowledge
the original data providers (per location-level licence metadata). For very
large pulls or production use, consider supporting OpenAQ's open data work
via <https://openaq.org/donate/>.

SDK Documentation: https://python.openaq.org/
Data Platform: https://openaq.org/
"""

import logging
import os
import warnings
from datetime import datetime, timezone

import pandas as pd

from ..progress import track
from ..registry import register_source
from ..transforms import add_column, compose, select_columns
from ..types import AeolusDataWarning, empty_data_frame, empty_metadata_frame

logger = logging.getLogger(__name__)

# Parameter name standardization
# Maps OpenAQ parameter names to Aeolus standard names
PARAMETER_MAP = {
    "no2": "NO2",
    "pm25": "PM2.5",
    "pm10": "PM10",
    "o3": "O3",
    "so2": "SO2",
    "co": "CO",
    "bc": "BC",
    "no": "NO",
    "nox": "NOX",
    "pm1": "PM1",
    "ch4": "CH4",
}


# ============================================================================
# CLIENT MANAGEMENT
# ============================================================================


_client = None


def _get_client() -> "OpenAQ":
    """
    Get an OpenAQ client instance (reuses existing client).

    Supports both OPENAQ_API_KEY (Aeolus convention) and OPENAQ-API-KEY (SDK convention).

    Returns:
        OpenAQ: Configured client instance

    Raises:
        ValueError: If no API key is found
    """
    from openaq import OpenAQ

    global _client

    # Reuse existing client if available
    if _client is not None:
        return _client

    # Support both env var conventions
    api_key = os.getenv("OPENAQ_API_KEY") or os.getenv("OPENAQ-API-KEY")

    if not api_key:
        raise ValueError(
            "OpenAQ API key required. Set OPENAQ_API_KEY environment variable. "
            "Get a free key at: https://openaq.org/"
        )

    _client = OpenAQ(api_key=api_key, auto_wait=True)
    return _client


# ============================================================================
# METADATA FETCHER (Search)
# ============================================================================


# SDK enforces 1 <= limit <= 1000 per request, so this is the most efficient
# page size for any auto-pagination loop.
_OPENAQ_MAX_PAGE_SIZE = 1000

# Safety cap on auto-pagination — hitting this means the user almost certainly
# wants a narrower filter rather than 50 000+ rows of metadata. We warn rather
# than silently truncate.
_OPENAQ_MAX_AUTO_PAGES = 50


def fetch_openaq_metadata(**filters) -> pd.DataFrame:
    """
    Search for monitoring locations on OpenAQ.

    By default this auto-paginates through the SDK to return *all* matching
    locations (not just the first page). Pass ``limit=N`` to cap the total
    number of results returned.

    Args:
        **filters: Search filters
            - country: ISO 3166-alpha-2 country code (e.g., "GB", "US", "KR")
              — mapped to the SDK's ``iso`` parameter. Aliases ``iso=`` and
              ``countries=`` are also accepted; passing more than one of the
              three raises ``ValueError`` rather than silently picking one.
            - bbox: Bounding box tuple ``(min_lon, min_lat, max_lon, max_lat)``.
            - coordinates: ``(latitude, longitude)`` for radius search.
            - radius: Search radius in metres (1–25 000); use with coordinates.
            - monitor: ``True`` for reference-grade regulatory monitors only,
              ``False`` for low-cost air sensors only. Omit for both.
            - limit: Optional positive total cap on results. When omitted,
              every matching location is returned (auto-paginated, capped at
              ~50 000 by ``_OPENAQ_MAX_AUTO_PAGES``). Must be ``>= 1`` —
              the SDK enforces ``1 <= limit <= 1000`` per request.

    Returns:
        pd.DataFrame: Location metadata with columns:
            - site_code: OpenAQ location ID (use for download)
            - site_name: Human-readable name
            - latitude / longitude: Coordinates (None if missing)
            - country: ISO country code
            - measurands: Sorted list of available pollutants
            - source_network: Always "OPENAQ"

    Examples:
        >>> # All Korean stations (~760, mostly the national reference network)
        >>> locations = fetch_openaq_metadata(country="KR")
        >>> # First 50 only
        >>> locations = fetch_openaq_metadata(country="KR", limit=50)
        >>> # Reference monitors only in a London bbox
        >>> locations = fetch_openaq_metadata(
        ...     bbox=(-0.5, 51.3, 0.3, 51.7), monitor=True,
        ... )
    """
    if not filters:
        raise ValueError(
            "OpenAQ requires search filters. Examples:\n"
            "  fetch_openaq_metadata(country='GB')\n"
            "  fetch_openaq_metadata(bbox=(-0.5, 51.3, 0.3, 51.7))"
        )

    client = _get_client()

    # Map Aeolus filter names to SDK parameter names
    sdk_params = {}

    # Accept several common spellings for the country filter so callers
    # going through ``find_sites(countries=...)`` (aeolus convention) and
    # those who know the OpenAQ SDK's ``iso=`` directly both work. If more
    # than one is supplied we'd have to guess which one the caller meant —
    # raise instead so typos surface.
    country_aliases = [
        alias for alias in ("iso", "country", "countries")
        if filters.get(alias) is not None
    ]
    if len(country_aliases) > 1:
        raise ValueError(
            f"OpenAQ: pass only one of iso=, country=, countries= "
            f"(got {', '.join(country_aliases)})"
        )
    if country_aliases:
        sdk_params["iso"] = filters[country_aliases[0]]

    if "bbox" in filters:
        # SDK requires tuple, but accept list for convenience
        bbox = filters["bbox"]
        sdk_params["bbox"] = tuple(bbox) if isinstance(bbox, list) else bbox

    if "coordinates" in filters:
        sdk_params["coordinates"] = filters["coordinates"]

    if "radius" in filters:
        sdk_params["radius"] = filters["radius"]

    if "monitor" in filters:
        sdk_params["monitor"] = filters["monitor"]

    user_limit = filters.get("limit")
    if user_limit is not None and user_limit < 1:
        raise ValueError(
            f"OpenAQ: limit must be a positive integer (got {user_limit!r})"
        )
    page_size = (
        min(_OPENAQ_MAX_PAGE_SIZE, user_limit)
        if user_limit is not None
        else _OPENAQ_MAX_PAGE_SIZE
    )

    # Auto-paginate. The OpenAQ SDK enforces page<=1000 results so this is
    # the most efficient walk; ``auto_wait=True`` on the client handles
    # rate-limit backoff for us. ``track`` shows a progress bar past the
    # first page when tqdm is installed (silent fallback otherwise) so big
    # country pulls don't look like a hang.
    locations: list = []
    for page in track(
        range(1, _OPENAQ_MAX_AUTO_PAGES + 1),
        "Fetching OpenAQ locations",
    ):
        response = client.locations.list(
            **sdk_params, limit=page_size, page=page
        )
        page_results = response.results or []
        if not page_results:
            break
        locations.extend(page_results)
        if user_limit is not None and len(locations) >= user_limit:
            locations = locations[:user_limit]
            break
        if len(page_results) < page_size:
            break  # last page
    else:
        warnings.warn(
            f"OpenAQ pagination hit the {_OPENAQ_MAX_AUTO_PAGES}-page safety "
            f"cap ({len(locations)} locations); narrow your filters or pass "
            "an explicit limit=N to suppress this warning",
            AeolusDataWarning,
            stacklevel=2,
        )

    if not locations:
        return empty_metadata_frame()

    records = []
    for loc in locations:
        # Get parameter names from sensors
        measurands = []
        if hasattr(loc, "sensors") and loc.sensors:
            measurands = sorted(
                {s.parameter.name for s in loc.sensors if s.parameter}
            )

        records.append(
            {
                "site_code": str(loc.id),
                "site_name": loc.name,
                "latitude": loc.coordinates.latitude if loc.coordinates else None,
                "longitude": loc.coordinates.longitude if loc.coordinates else None,
                "country": loc.country.code if loc.country else None,
                "measurands": measurands or None,
                "source_network": "OPENAQ",
            }
        )

    return pd.DataFrame(records)


# ============================================================================
# DATA FETCHER
# ============================================================================


def fetch_openaq_data(
    sites: list[str], start_date: datetime, end_date: datetime
) -> pd.DataFrame:
    """
    Fetch air quality data from OpenAQ.

    Args:
        sites: List of OpenAQ location IDs as strings
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        pd.DataFrame: Air quality data with standardised schema

    Example:
        >>> data = fetch_openaq_data(
        ...     sites=["2178"],
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 1, 31)
        ... )
    """
    from openaq.shared.exceptions import OpenAQError

    client = _get_client()
    all_measurements = []

    for location_id in sites:
        location_id_int = int(location_id)
        logger.info(f"Fetching data for OpenAQ location {location_id}...")

        # Step 1: Get sensors for this location
        try:
            sensors_response = client.locations.sensors(location_id_int)
            sensors = sensors_response.results if sensors_response.results else []
        except (OpenAQError, KeyError, ValueError, AttributeError) as e:
            logger.warning(f"Failed to get sensors for location {location_id}: {e}")
            continue

        if not sensors:
            logger.warning(f"No sensors found for location {location_id}")
            continue

        logger.info(f"Found {len(sensors)} sensors for location {location_id}")

        # Step 2: Fetch measurements for each sensor
        for sensor in sensors:
            sensor_id = sensor.id
            param_name = sensor.parameter.name if sensor.parameter else "unknown"

            logger.debug(f"Fetching data for sensor {sensor_id} ({param_name})")

            try:
                # Paginate through all results (API returns max 1000 per page)
                page = 1
                sensor_total = 0
                while True:
                    measurements = client.measurements.list(
                        sensors_id=sensor_id,
                        data="measurements",
                        datetime_from=start_date,
                        datetime_to=end_date,
                        limit=1000,
                        page=page,
                    )

                    if not measurements.results:
                        break

                    for m in measurements.results:
                        all_measurements.append(
                            {
                                "location_id": location_id,
                                "sensor_id": sensor_id,
                                "parameter": param_name,
                                "value": m.value,
                                "datetime": m.period.datetime_to.utc
                                if m.period and m.period.datetime_to
                                else None,
                                "units": sensor.parameter.units
                                if sensor.parameter
                                else "",
                            }
                        )

                    sensor_total += len(measurements.results)

                    # If we got fewer than the limit, we've reached the end
                    if len(measurements.results) < 1000:
                        break
                    page += 1

                if sensor_total > 0:
                    logger.debug(
                        f"Sensor {sensor_id}: fetched {sensor_total} measurements"
                    )

            except (OpenAQError, KeyError, ValueError, AttributeError) as e:
                logger.warning(f"Failed to fetch data for sensor {sensor_id}: {e}")
                continue

    if not all_measurements:
        warnings.warn(
            "No measurements found for any location",
            AeolusDataWarning,
            stacklevel=2,
        )
        return empty_data_frame()

    # Convert to DataFrame and normalise
    df = pd.DataFrame(all_measurements)
    logger.info(f"Total measurements collected: {len(df)}")

    return _normalise(df)


# ============================================================================
# NORMALIZATION
# ============================================================================


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize OpenAQ data to Aeolus standard schema."""

    # Rename columns
    df = df.rename(
        columns={
            "location_id": "site_code",
            "datetime": "date_time",
        }
    )

    # Standardize parameter names
    df["measurand"] = df["parameter"].str.lower().map(PARAMETER_MAP)
    mask = df["measurand"].isna()
    df.loc[mask, "measurand"] = df.loc[mask, "parameter"].str.upper()

    # Convert datetime
    df["date_time"] = pd.to_datetime(df["date_time"], utc=True, errors="coerce")

    # Standardize units
    unit_map = {"µg/m³": "ug/m3", "μg/m³": "ug/m3"}
    df["units"] = df["units"].replace(unit_map)

    # Add standard columns
    df["source_network"] = "OPENAQ"
    df["ratification"] = "Unvalidated"
    df["created_at"] = datetime.now(timezone.utc)

    # Drop rows with missing essential data
    df = df.dropna(subset=["date_time", "value", "measurand"])

    # Select final columns
    return df[
        [
            "site_code",
            "date_time",
            "measurand",
            "value",
            "units",
            "source_network",
            "ratification",
            "created_at",
        ]
    ]


# ============================================================================
# SOURCE REGISTRATION
# ============================================================================

register_source(
    "OPENAQ",
    {
        "type": "portal",
        "name": "OpenAQ",
        "search": fetch_openaq_metadata,
        "fetch_metadata": fetch_openaq_metadata,
        "fetch_data": fetch_openaq_data,
        "normalise": lambda df: df,  # Normalization happens in fetch_openaq_data
        "requires_api_key": True,
    },
)
