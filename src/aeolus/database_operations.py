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
Store air quality data and site data in a structured manner.
"""

import os
import site
import warnings
from datetime import datetime
from logging import warning

import pandas as pd
from sqlalchemy import text
from sqlmodel import Field, Session, SQLModel, create_engine


class AQ_site(SQLModel, table=True):
    """
    Represents an air quality site.
    """

    id: int | None = Field(default=None, primary_key=True)
    source_network: str
    site_code: str
    site_name: str
    latitude: float | None
    longitude: float | None
    sensor_model: str | None
    location_type: str | None
    owner: str | None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AQ_data(SQLModel, table=True):
    """
    Represents an air quality data point.
    """

    id: int | None = Field(default=None, primary_key=True)
    source_network: str
    site_code: str
    date_time: datetime
    units: str
    measurand: str
    value: float | None
    ratification: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


def add_sites_to_database(
    df: pd.DataFrame, database_file: str | None = None, database_url: str | None = None
):
    if database_file is None and database_url is None:
        raise ValueError("One of database_file or database_url must be provided")
    elif database_file is not None and database_url is not None:
        raise ValueError("Provide only one of database_file or database_url")
    if database_url is not None:
        engine_url = database_url
    else:
        engine_url = f"sqlite:///{database_file}"

    engine = create_engine(engine_url, echo=True)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for index, row in df.iterrows():
            row.fillna("", inplace=True)

            site_code = row["site_code"]
            site_name = row["site_name"]
            try:
                longitude = float(row["longitude"])
            except ValueError:
                longitude = None
            try:
                latitude = float(row["latitude"])
            except ValueError:
                latitude = None
            source_network = row["source_network"]
            location_type = row["location_type"]
            try:
                owner = row["owner"]
            except KeyError:
                owner = None

            site = AQ_site(
                site_code=site_code,
                site_name=site_name,
                longitude=longitude,
                latitude=latitude,
                source_network=source_network,
                location_type=location_type,
                owner=owner,
            )
            # check for duplicate site_code
            existing_site = (
                session.query(AQ_site).filter_by(site_code=site_code).first()
            )
            if existing_site:
                warnings.warn(f"Duplicate site_code {site_code} found")
            else:
                session.add(site)

        # Commit the changes to the database only after all data has been added
        session.commit()


def db_worker(queue, engine):
    with Session(engine) as session:
        while True:
            batch = []
            while len(batch) < 10:
                batch.append(queue.get())
            # session.add_all(batch)
            for each in batch:
                for index, row in each.iterrows():
                    session.add(
                        AQ_data(
                            source_network=row["source_network"],
                            site_code=row["site_code"],
                            measurand=row["measurand"],
                            value=row["value"],
                            date_time=row["date_time"],
                            ratification=row["ratification"],
                            units=row["units"],
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                        )
                    )
            session.commit()
            queue.task_done()


def add_data_to_database(
    df: pd.DataFrame, database_file: str | None = None, database_url: str | None = None
) -> bool:
    if database_file is None and database_url is None:
        raise ValueError("One of database_file or database_url must be provided")
    elif database_file is not None and database_url is not None:
        raise ValueError("Provide only one of database_file or database_url")
    if database_url is not None:
        engine_url = database_url
    else:
        engine_url = f"sqlite:///{database_file}"

    engine = create_engine(engine_url, echo=True)
    SQLModel.metadata.create_all(engine)
    # r_norm.to_sql("AQ_data", engine, if_exists="append", index_label="id")

    with Session(engine) as session:
        for index, row in df.iterrows():
            # print(row["date_time"])
            # print(type(row["date_time"]))
            session.add(
                AQ_data(
                    source_network=row["source_network"],
                    site_code=row["site_code"],
                    measurand=row["measurand"],
                    value=row["value"],
                    date_time=row["date_time"],
                    ratification=row["ratification"],
                    units=row["units"],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
        session.commit()
        return True


def get_site_metadata(
    site_code: str | None = None,
    network: str | None = None,
    location_type: str | None = None,
    owner: str | None = None,
    database_file: str | None = None,
    database_url: str | None = None,
) -> pd.DataFrame:
    """
    Returns metadata for sites based on the provided parameters. Note that
    only one of site_code, network, location_type, or owner will be used. If
    more than one is provided, precedence is given to site_code, then network,
    then location_type, and finally owner.
    """
    if database_file is None and database_url is None:
        raise ValueError("One of database_file or database_url must be provided")
    elif database_file is not None and database_url is not None:
        raise ValueError("Provide only one of database_file or database_url")
    if database_url is not None:
        engine_url = database_url
    else:
        engine_url = f"sqlite:///{database_file}"

    # sanitize the parameters
    site_code = site_code.upper() if site_code else None
    network = network.upper() if network else None

    engine = create_engine(engine_url, echo=True)
    SQLModel.metadata.create_all(engine)

    if site_code is not None:
        site_code = site_code.upper()
        with Session(engine) as session:
            site_data = (
                session.query(AQ_site).filter(AQ_site.site_code == site_code).statement
            )

    elif network is not None:
        with Session(engine) as session:
            site_data = (
                session.query(AQ_site)
                .filter(AQ_site.source_network == network)
                .statement
            )
    elif location_type is not None:
        with Session(engine) as session:
            site_data = (
                session.query(AQ_site)
                .filter(AQ_site.location_type == location_type)
                .all()
            )
    elif owner is not None:
        with Session(engine) as session:
            site_data = session.query(AQ_site).filter(AQ_site.owner == owner).statement
    else:
        with Session(engine) as session:
            site_data = session.query(AQ_site).statement

    site_data = pd.read_sql_query(site_data, engine)
    return site_data


# def get_aq_data(site_id: str)
