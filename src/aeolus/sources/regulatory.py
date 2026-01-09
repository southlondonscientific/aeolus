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
that provide data through the OpenAir project (Ricardo). Supported networks:
- AURN (Automatic Urban and Rural Network)
- SAQN (Scottish Air Quality Network)
- SAQD (Scottish Air Quality Database)
- NI (Northern Ireland Air Quality Network)
- WAQN (Wales Air Quality Network)
- AQE (Air Quality England)
- Local (Local Monitoring and Management networks)

All networks follow the same data format (RData files from OpenAir), so they
share common fetching and normalisation functions.
"""

from datetime import datetime
from logging import warning
from typing import Callable

import pandas as pd
import rdata
import requests

from ..registry import register_source
from ..transforms import (
    add_column,
    compose,
    convert_timestamps,
    drop_columns,
    melt_measurands,
    rename_columns,
    reset_index,
)
from ..types import DataFetcher, MetadataFetcher, Normaliser


# Configuration - URLs for each network
METADATA_URLS = {
    "aurn": "https://uk-air.defra.gov.uk/openair/R_data/AURN_metadata.RData",
    "saqn": "https://www.scottishairquality.scot/openair/R_data/SCOT_metadata.RData",
    "saqd": "https://www.scottishairquality.scot/openair/R_data/SCOT_metadata.RData",
    "ni": "https://www.airqualityni.co.uk/openair/R_data/NI_metadata.RData",
    "waqn": "https://airquality.gov.wales/sites/default/files/openair/R_data/WAQ_metadata.RData",
    "aqe": "https://airqualityengland.co.uk/assets/openair/R_data/AQE_metadata.RData",
    "local": "https://uk-air.defra.gov.uk/openair/LMAM/R_data/LMAM_metadata.RData",
    "lmam": "https://uk-air.defra.gov.uk/openair/LMAM/R_data/LMAM_metadata.RData",
}

DATA_BASE_URLS = {
    "aurn": "https://uk-air.defra.gov.uk/openair/R_data/",
    "saqn": "https://www.scottishairquality.scot/openair/R_data/",
    "saqd": "https://www.scottishairquality.scot/openair/R_data/",
    "ni": "https://www.airqualityni.co.uk/openair/R_data/",
    "waqn": "https://airquality.gov.wales/sites/default/files/openair/R_data/",
    "aqe": "https://airqualityengland.co.uk/assets/openair/R_data/",
    "local": "https://uk-air.defra.gov.uk/openair/LMAM/R_data/",
    "lmam": "https://uk-air.defra.gov.uk/openair/LMAM/R_data/",
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
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        warning(f"Failed to fetch RData from {url}: {e}")
        return None

    try:
        parsed = rdata.parser.parse_data(response.content)
        converted = rdata.conversion.convert(parsed)
        # RData returns a dict with one key - get the first (only) value
        data = converted[next(iter(converted))]
        return pd.DataFrame(data)
    except Exception as e:
        warning(f"Failed to parse RData from {url}: {e}")
        return None


# Metadata normalisation pipeline for regulatory networks
def normalise_regulatory_metadata(network_name: str) -> Normaliser:
    """
    Create a normalisation pipeline for regulatory network metadata.

    Args:
        network_name: Name of the network (e.g., "AURN", "SAQN")

    Returns:
        Normaliser: Function that normalises metadata DataFrame
    """
    return compose(
        drop_columns("parameter", "Parameter_name"),
        rename_columns({
            "site_id": "site_code",
            "local_authority": "owner",
        }),
        add_column("source_network", network_name.upper()),
        reset_index(),
    )


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
            # No measurands found - return empty DataFrame
            warning(f"No measurands found in DataFrame for {network_name}")
            return pd.DataFrame()

        # Apply transformation pipeline
        return compose(
            melt_measurands(
                id_vars=["site", "code", "date"],
                measurands=measurands_present,
            ),
            rename_columns({
                "site": "site_name",
                "code": "site_code",
                "date": "date_time",
            }),
            drop_columns("site_name"),  # We typically don't need this in data
            convert_timestamps("date_time", unit="s"),
            add_column("source_network", network_name.upper()),
            add_column("ratification", "None"),
            add_column("units", "ug/m3"),
            add_column("created_at", lambda df: datetime.now()),
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
        url = METADATA_URLS[network_name.lower()]
        df = fetch_rdata(url)

        if df is None:
            return pd.DataFrame()

        normaliser = normalise_regulatory_metadata(network_name)
        return normaliser(df)

    return fetch_metadata


# Factory function for creating data fetchers
def make_data_fetcher(network_name: str) -> DataFetcher:
    """
    Create a data fetcher function for a specific regulatory network.

    Args:
        network_name: Name of the network (e.g., "aurn", "saqn")

    Returns:
        DataFetcher: Function that fetches and normalises data
    """
    def fetch_data(
        sites: list[str],
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        base_url = DATA_BASE_URLS[network_name.lower()]
        years = range(start_date.year, end_date.year + 1)

        results = []
        for site in sites:
            for year in years:
                url = f"{base_url}{site.upper()}_{year}.RData"
                df = fetch_rdata(url)

                if df is not None:
                    # Parse the data key (format: SITECODE_YEAR)
                    site_key = f"{site.upper()}_{year}"

                    # RData file contains data with this key structure
                    # The fetch_rdata already extracted it, so we can use df directly
                    if not df.empty:
                        results.append(df)

        if not results:
            return pd.DataFrame()

        # Concatenate all results
        combined = pd.concat(results, ignore_index=True)

        # Normalise the combined data
        normaliser = normalise_regulatory_data(network_name)
        normalised = normaliser(combined)

        # Filter to the requested date range
        if not normalised.empty and "date_time" in normalised.columns:
            mask = (
                (normalised["date_time"] >= start_date) &
                (normalised["date_time"] <= end_date)
            )
            normalised = normalised[mask]

        return normalised

    return fetch_data


# Register AURN (the primary network)
register_source("AURN", {
    "name": "AURN",
    "fetch_metadata": make_metadata_fetcher("aurn"),
    "fetch_data": make_data_fetcher("aurn"),
    "normalise": normalise_regulatory_data("AURN"),
    "requires_api_key": False,
})

# Register SAQN (Scottish Air Quality Network)
register_source("SAQN", {
    "name": "SAQN",
    "fetch_metadata": make_metadata_fetcher("saqn"),
    "fetch_data": make_data_fetcher("saqn"),
    "normalise": normalise_regulatory_data("SAQN"),
    "requires_api_key": False,
})

# Register SAQD (alias for SAQN)
register_source("SAQD", {
    "name": "SAQD",
    "fetch_metadata": make_metadata_fetcher("saqd"),
    "fetch_data": make_data_fetcher("saqd"),
    "normalise": normalise_regulatory_data("SAQD"),
    "requires_api_key": False,
})

# Register NI (Northern Ireland)
register_source("NI", {
    "name": "NI",
    "fetch_metadata": make_metadata_fetcher("ni"),
    "fetch_data": make_data_fetcher("ni"),
    "normalise": normalise_regulatory_data("NI"),
    "requires_api_key": False,
})

# Register WAQN (Wales Air Quality Network)
register_source("WAQN", {
    "name": "WAQN",
    "fetch_metadata": make_metadata_fetcher("waqn"),
    "fetch_data": make_data_fetcher("waqn"),
    "normalise": normalise_regulatory_data("WAQN"),
    "requires_api_key": False,
})

# Register AQE (Air Quality England)
register_source("AQE", {
    "name": "AQE",
    "fetch_metadata": make_metadata_fetcher("aqe"),
    "fetch_data": make_data_fetcher("aqe"),
    "normalise": normalise_regulatory_data("AQE"),
    "requires_api_key": False,
})

# Register Local (Local Monitoring and Management)
register_source("LOCAL", {
    "name": "Local",
    "fetch_metadata": make_metadata_fetcher("local"),
    "fetch_data": make_data_fetcher("local"),
    "normalise": normalise_regulatory_data("Local"),
    "requires_api_key": False,
})

# Register LMAM (alias for Local)
register_source("LMAM", {
    "name": "LMAM",
    "fetch_metadata": make_metadata_fetcher("lmam"),
    "fetch_data": make_data_fetcher("lmam"),
    "normalise": normalise_regulatory_data("LMAM"),
    "requires_api_key": False,
})
