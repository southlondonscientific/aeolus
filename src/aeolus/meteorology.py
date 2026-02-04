"""
Meteorological data retrieval from Open-Meteo API.

.. deprecated:: 0.3.0
    This module is deprecated and will be removed in v0.4.0.
    Consider using the Open-Meteo Python SDK directly for meteorological data:
    https://pypi.org/project/openmeteo-requests/
"""

import warnings
from collections.abc import Iterable
from datetime import datetime, timedelta

import pandas as pd
import requests

# Deprecation warning shown on module import
warnings.warn(
    "aeolus.meteorology is deprecated and will be removed in v0.4.0. "
    "Consider using the Open-Meteo Python SDK directly for meteorological data.",
    DeprecationWarning,
    stacklevel=2,
)


def get_meteo_data_for_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Uses the get_meteo_data function to retrieve meteorological data for each row
    in a standard Aeolus dataframe.
    """
    pass


def get_meteo_data(
    lat: float | Iterable,
    lon: float | Iterable,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> pd.DataFrame:
    """
    Function to retrieve meteorological data from Open-Meteo API.
    Takes latitude, longitude, start_date, and end_date as parameters. Iterables
    of latitude and longitude can be provided but must be of the same length.
    """

    if len(lat) != len(lon):
        raise ValueError("Latitude and longitude must be of the same length.")

    if start_date is None:
        start_date = datetime.now() - timedelta(days=1)
    if end_date is None:
        end_date = datetime.now()

    start_date = datetime.strftime(start_date, "%Y-%m-%d")
    end_date = datetime.strftime(end_date, "%Y-%m-%d")

    meteo_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,cloud_cover,precipitation&start_date={start_date}&end_date={end_date}"

    weather = requests.get(meteo_url).json()
    weather = pd.DataFrame(weather["hourly"])
    weather["date_time"] = pd.to_datetime(weather["time"])
    return weather
