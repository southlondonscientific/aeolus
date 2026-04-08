"""Reusable Hypothesis strategies for generating aeolus-domain test data."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from hypothesis import strategies as st
from hypothesis.extra.pandas import column, data_frames

from aeolus.types import DATA_COLUMNS

# ---------------------------------------------------------------------------
# Atom strategies
# ---------------------------------------------------------------------------

latitudes = st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False)

longitudes = st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False)

positive_radii = st.floats(min_value=0.1, max_value=2000.0, allow_nan=False, allow_infinity=False)

site_codes = st.from_regex(r"[A-Z0-9]{2,10}", fullmatch=True)

pollutant_names = st.sampled_from(["NO2", "O3", "PM2.5", "PM10", "SO2", "CO"])

unit_names = st.sampled_from(["ug/m3", "µg/m³", "ppb", "ppm", "mg/m3"])

network_names = st.sampled_from(
    ["AURN", "SAQN", "WAQN", "BREATHE_LONDON", "AIRQO", "SENSOR_COMMUNITY"]
)

concentrations = st.floats(min_value=-100.0, max_value=10000.0, allow_infinity=False).map(
    lambda x: x  # allow NaN by default from hypothesis
) | st.just(float("nan"))

_MIN_DT = datetime(2000, 1, 1, tzinfo=timezone.utc)
_MAX_DT = datetime(2030, 12, 31, tzinfo=timezone.utc)

timestamps = st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2030, 12, 31)).map(
    lambda dt: dt.replace(tzinfo=timezone.utc)
)

ratification_values = st.sampled_from(
    ["Ratified", "Provisional", "None", "Unknown", "Unvalidated"]
)

# ---------------------------------------------------------------------------
# Composite strategies
# ---------------------------------------------------------------------------


@st.composite
def aeolus_dataframes(
    draw: st.DrawFn,
    min_rows: int = 1,
    max_rows: int = 50,
    messy: bool = False,
) -> pd.DataFrame:
    """Generate a DataFrame with the standard aeolus 8-column schema.

    Parameters
    ----------
    min_rows : int
        Minimum number of rows (0 allows empty DataFrames).
    max_rows : int
        Maximum number of rows.
    messy : bool
        If True, inject NaNs into ~20% of value cells and occasionally
        duplicate some rows.
    """
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))

    if n_rows == 0:
        return pd.DataFrame(columns=DATA_COLUMNS)

    data: dict[str, list] = {
        "site_code": draw(st.lists(site_codes, min_size=n_rows, max_size=n_rows)),
        "date_time": draw(st.lists(timestamps, min_size=n_rows, max_size=n_rows)),
        "measurand": draw(st.lists(pollutant_names, min_size=n_rows, max_size=n_rows)),
        "value": draw(
            st.lists(
                st.floats(min_value=-100.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
                min_size=n_rows,
                max_size=n_rows,
            )
        ),
        "units": draw(st.lists(unit_names, min_size=n_rows, max_size=n_rows)),
        "source_network": draw(st.lists(network_names, min_size=n_rows, max_size=n_rows)),
        "ratification": draw(st.lists(ratification_values, min_size=n_rows, max_size=n_rows)),
        "created_at": draw(st.lists(timestamps, min_size=n_rows, max_size=n_rows)),
    }

    df = pd.DataFrame(data)

    if messy and n_rows > 0:
        # Inject NaNs into ~20% of value cells
        nan_mask = draw(
            st.lists(
                st.booleans(),
                min_size=n_rows,
                max_size=n_rows,
            )
        )
        for i, should_nan in enumerate(nan_mask):
            # ~20% chance via a separate draw per row would be slow;
            # use the boolean list and take roughly 20%
            if should_nan and i % 5 == 0:
                df.at[i, "value"] = np.nan

        # Occasionally duplicate some rows
        if draw(st.booleans()) and n_rows >= 2:
            n_dups = draw(st.integers(min_value=1, max_value=max(1, n_rows // 4)))
            dup_indices = draw(
                st.lists(
                    st.integers(min_value=0, max_value=n_rows - 1),
                    min_size=n_dups,
                    max_size=n_dups,
                )
            )
            df = pd.concat([df, df.iloc[dup_indices]], ignore_index=True)

    return df


@st.composite
def wide_dataframes(
    draw: st.DrawFn,
    min_rows: int = 1,
    max_rows: int = 50,
) -> pd.DataFrame:
    """Generate wide-format DataFrames (one column per pollutant).

    Mimics what regulatory sources return before melting to long format.
    Columns: ``date``, ``site``, plus 1-4 pollutant columns.
    """
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))

    if n_rows == 0:
        return pd.DataFrame(columns=["date", "site"])

    # Pick 1-4 pollutants for columns
    all_pollutants = ["NO2", "O3", "PM2.5", "PM10", "SO2", "CO"]
    n_pollutants = draw(st.integers(min_value=1, max_value=4))
    pollutants = draw(
        st.lists(
            st.sampled_from(all_pollutants),
            min_size=n_pollutants,
            max_size=n_pollutants,
            unique=True,
        )
    )

    data: dict[str, list] = {
        "date": draw(st.lists(timestamps, min_size=n_rows, max_size=n_rows)),
        "site": draw(st.lists(site_codes, min_size=n_rows, max_size=n_rows)),
    }

    for pollutant in pollutants:
        data[pollutant] = draw(
            st.lists(
                st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
                | st.just(float("nan")),
                min_size=n_rows,
                max_size=n_rows,
            )
        )

    return pd.DataFrame(data)


@st.composite
def column_rename_mappings(
    draw: st.DrawFn,
    columns: list[str],
) -> dict[str, str]:
    """Generate a rename mapping for a random subset of *columns*.

    Returns a dict mapping original column names to new randomly-generated
    names. The subset may be empty.
    """
    if not columns:
        return {}

    # Pick a random subset of columns to rename
    subset = draw(
        st.lists(
            st.sampled_from(columns),
            min_size=0,
            max_size=len(columns),
            unique=True,
        )
    )

    mapping: dict[str, str] = {}
    for col in subset:
        new_name = draw(
            st.from_regex(r"[a-z_][a-z0-9_]{0,15}", fullmatch=True)
        )
        mapping[col] = new_name

    return mapping
