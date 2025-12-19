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
This module provides functions for downloading metadata and data files from
air quality networks and standardising them into a common pandas DataFrame format.
Currently, it supports downloading data from the following networks:
- AURN (DEFRA's Automatic Urban and Rural Network)
- SAQN (Scottish Air Quality Network)
- NI (Northern Ireland Air Quality Network)
- WAQN (Wales Air Quality Network)
- AQE (Air Quality England)
- Local (Local regulatory networks in England)
- Breathe London (requires API key set in environment variable BL_API_KEY)

Regulatory network metadata is provided as a pandas DataFrame with the columns:
    - site_id: str
    - source_network: str
    - location_type: str
    - latitude: float
    - longitude: float
    - parameter: str
    - Parameter_name: str
    - start_date: datetime
    - end_date: datetime
    - ratified_to: datetime
    - zone: str
    - agglomeration: str
    - local_authority: str

Air quality data is returned as a pandas DataFrame with the columns:
    - site_code: str
    - date_time: datetime
    - measurand: str
    - value: float
    - unit: str
    - source_network: str
    - ratification: str

Note that this means multiple data points can be returned for a single site
and time period depending on the measurand. This is because some sites may have
multiple sensors measuring different pollutants, and each sensor may have a
different measurement frequency.

TODO: Add support for downloading data from the following additional sources:
    - OpenAQ
    - AirGradient
"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from logging import warning
from pathlib import Path
from queue import Queue

import pandas as pd
import rdata
import requests
from requests.sessions import Request

# Base URLs for metadata
metadata_urls = {
    "aurn": "https://uk-air.defra.gov.uk/openair/R_data/AURN_metadata.RData",
    "saqn": "https://www.scottishairquality.scot/openair/R_data/SCOT_metadata.RData",
    "saqd": "https://www.scottishairquality.scot/openair/R_data/SCOT_metadata.RData",
    "ni": "https://www.airqualityni.co.uk/openair/R_data/NI_metadata.RData",
    "waqn": "https://airquality.gov.wales/sites/default/files/openair/R_data/WAQ_metadata.RData",
    "aqe": "https://airqualityengland.co.uk/assets/openair/R_data/AQE_metadata.RData",
    "local": "https://uk-air.defra.gov.uk/openair/LMAM/R_data/LMAM_metadata.RData",
    "lmam": "https://uk-air.defra.gov.uk/openair/LMAM/R_data/LMAM_metadata.RData",
    # "bl_list": "https://breathe-london-7x54d7qf.ew.gateway.dev/ListSensors",
}

# Base URLs for openair data
base_urls = {
    "aurn": "https://uk-air.defra.gov.uk/openair/R_data/",
    "saqn": "https://www.scottishairquality.scot/openair/R_data/",
    "saqd": "https://www.scottishairquality.scot/openair/R_data/",
    "ni": "https://www.airqualityni.co.uk/openair/R_data/",
    "waqn": "https://airquality.gov.wales/sites/default/files/openair/R_data/",
    "aqe": "https://airqualityengland.co.uk/assets/openair/R_data/",
    "local": "https://uk-air.defra.gov.uk/openair/LMAM/R_data/",
    "lmam": "https://uk-air.defra.gov.uk/openair/LMAM/R_data/",
}

BL_API_KEY = os.environ.get("BL_API_KEY")

# Pollutants returned by AURN and other regulatory networks where data is provided through Ricardo/Openair.
aurn_measurands = [
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


def get_network_metadata(network: str) -> pd.DataFrame:
    """
    Get metadata for a regulatory network (e.g. AURN, SAQN, WAQN).
    This function retrieves metadata from a predefined URL based on the network name,
    including site names, codes, coordinates, and other relevant information. Data is
    drawn from Rdata files provided by the Openair project.

    Args:
        network (str): The acronym of the regulatory network as a string. The
        following networks are supported: AURN, SAQN, WAQN, NI, AQE

    Returns:
        pd.DataFrame: Metadata for the specified regulatory network with the following columns:
            - site_code: Site code
            - site_name: Site name
            - latitude: Latitude
            - longitude: Longitude
            - owner: Owner/operator of the site
            - source_network: Source network

    NOTE: At present, this function only supports regulatory networks in the UK where
    data is provided by Ricardo through the Openair project. For Breathe London data, consult
    https://www.breathe-london.org.uk/data/.
    """
    network_url = metadata_urls[network.lower()]

    response = requests.get(network_url)
    response.raise_for_status()

    try:
        parsed = rdata.parser.parse_data(response.content)
    except Exception as e:
        raise ValueError("Failed to parse response data") from e

    try:
        converted = rdata.conversion.convert(parsed)
    except Exception as e:
        raise ValueError("Failed to convert parsed data") from e

    # converted is a dict with one key:value pair, this gets the first value
    converted = converted[next(iter(converted))]

    # Now let's convert the data into a pandas DataFrame
    df = pd.DataFrame(converted)

    # And clean up the DataFrame
    df = df.drop(columns=["parameter", "Parameter_name"])
    df = df.drop_duplicates()
    df = df.reset_index(drop=True)

    # Now we can normalise the DataFrame into the format our database expects
    df = df.rename(
        columns={
            "site_id": "site_code",
            "local_authority": "owner",
        }
    )
    df["source_network"] = network.upper()
    return df


def multiple_download_regulatory_data(
    sites: list | str, years: list | int, networks: list | str
) -> pd.DataFrame():
    """
    Download data for multiple regulatory network sites and years.

    Args:
        site (str): The code of the regulatory network site as a string.
        year (int): The year of the data as an integer.
        network (str): The acronym of the regulatory network as a string. The
        following networks are supported: AURN, SAQN, WAQN, NI, AQE, and local networks.

    Returns:
        pd.DataFrame: Data for the specified regulatory network site and year.

    """
    if type(sites) == str:
        sites = [sites]
    if type(years) == int:
        years = [years]
    if type(networks) == str:
        networks = [networks]

    all_to_download = []

    for network in networks:
        for site in sites:
            for year in years:
                all_to_download.append((site, year, network))

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(download_regulatory_data, *zip(*all_to_download)))

    return pd.concat(results, ignore_index=True)


def download_regulatory_data(
    site: str, year: int, network: str, threaded: bool = False, queue: Queue = None
) -> pd.DataFrame:
    """
    Download data for a regulatory network site and year.
    This function retrieves data from a predefined URL based on the network name,
    site code, and year. Data is drawn from Rdata files provided by the Openair project
    and Ricardo. To download data for multiple sites and years, use the
    multiple_download_regulatory_data function.

    Args:
        site (str): The code of the regulatory network site as a string.
        year (int): The year of the data as an integer.
        network (str): The acronym of the regulatory network as a string. The
        following networks are supported: AURN, SAQN, WAQN, NI, AQE, and local networks.

    Returns:
        pd.DataFrame: Data for the specified regulatory network site and year.

    """
    try:
        url_base = base_urls[network.lower()]
    except KeyError:
        raise ValueError(f"Unknown network: {network}")

    network_url = url_base + site.upper() + "_" + str(year) + ".RData"

    response = requests.get(network_url)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        warning(f"Failed to retrieve data for {site} in {year}: {e}")
        return None

    try:
        parsed = rdata.parser.parse_data(response.content)
    except Exception as e:
        raise ValueError("Failed to parse response data") from e
    try:
        converted = rdata.conversion.convert(parsed)
    except Exception as e:
        raise ValueError("Failed to convert response data") from e
    site_key = site.upper() + "_" + str(year)
    try:
        this_data = converted[site_key]
        df_hourly = pd.DataFrame(this_data)
    except KeyError as e:
        raise ValueError(f"Site key not found: {site_key}")

    # print(df_hourly)
    # print(df_hourly.columns)

    this_measurands = [x for x in aurn_measurands if x in df_hourly.columns]

    df_hourly = pd.melt(
        df_hourly,
        id_vars=["site", "code", "date"],
        value_vars=this_measurands,
        var_name="measurand",
    )

    df_hourly["source_network"] = network.upper()
    df_hourly["ratification"] = "None"
    df_hourly["units"] = "ug/m3"
    columns = {
        "site": "site_code",
        "date": "date_time",
    }

    df = df_hourly.rename(columns=columns)

    df["created_at"] = datetime.now()
    # dates are given as seconds since epoch (UNIX timestamps) so
    # we need to convert them to datetime objects
    df["date_time"] = pd.to_datetime(df["date_time"], unit="s")
    if threaded:
        queue.put(df)
    else:
        return df


def download_breathe_london_data(
    site=None,
    borough=None,
    start_time=None,
    end_time=None,
    species=None,
    sponsor=None,
    facility=None,
    latitude=None,
    longitude=None,
    radius_km=None,
) -> pd.DataFrame:
    """
    Download air quality data from Breathe London API.

    Parameters:
        site (str): Site code.
        borough (str): Borough name.
        start_time (str): Start time in ISO format.
        end_time (str): End time in ISO format.
        species (str): Species code.
        sponsor (str): Sponsor name.
        facility (str): Facility name.
        latitude (float): Latitude.
        longitude (float): Longitude.
        radius_km (float): Radius in kilometers.

    Returns:
        pd.DataFrame: Air quality data.
    """
    params = {
        "SiteCode": site,
        "Borough": borough,
        "startTime": start_time,
        "endTime": end_time,
        "Species": species,
        "Sponsor": sponsor,
        "Facility": facility,
        "Latitude": latitude,
        "Longitude": longitude,
        "RadiusKM": radius_km,
    }
    headers = {"X-API-KEY": BL_API_KEY}
    req_url = "https://breathe-london-7x54d7qf.ew.gateway.dev/SensorData"
    r = requests.get(req_url, params=params, headers=headers)
    r_df = pd.DataFrame(r.json())

    r_df = normalise_breathe_london_data(r_df)
    return r_df


def normalise_breathe_london_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise Breathe London data into a consistent
    """
    columns = {
        "SiteCode": "site_code",
        "DateTime": "date_time",
        "RatificationStatus": "ratification",
        "Units": "units",
        "Species": "measurand",
        "ScaledValue": "value",
    }

    source_network = "Breathe London"
    df = df.rename(columns=columns)
    df["source_network"] = source_network
    df["created_at"] = datetime.now()
    df["date_time"] = pd.to_datetime(df["date_time"])

    df = df.drop(columns=["Source", "SensorContract", "Duration"])

    # Replace "nan" with -999 - bad practice but will do for now
    df = df.fillna(value=-999)

    return df


if __name__ == "__main__":
    pass
