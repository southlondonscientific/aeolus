# Aeolus: download and standardise air quality data
# Copyright (C) 2025 Ruaraidh Dobson, South London Scientific

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
One spelling per unit.

Upstreams write the same unit many ways (``ug.m-3``, ``µg/m³``, ``UG/M3``). Every
adapter and every metrics path canonicalises through :func:`canonical_unit`, so
there is a single list to maintain rather than one per module.
"""

import re

import pandas as pd

# "<prefix>g per cubic metre" in any of its notations -> "<prefix>g/m3"
_MASS_PER_VOLUME = re.compile(r"^([umn])g\s*(?:/|\.|\s)?\s*m\s*(?:\^)?-?3$")


def canonical_unit(unit):
    """Return the canonical spelling of *unit* (``ug/m3``, ``mg/m3``, ``ng/m3``, ``ppb``, ``ppm``).

    Units that are not concentration units (``C``, ``%``, ``hPa``, ``AQI``) and
    missing values are returned unchanged.
    """
    if unit is None or not isinstance(unit, str):
        return unit
    text = unit.strip()
    folded = text.lower().replace("µ", "u").replace("μ", "u").replace("³", "3")
    match = _MASS_PER_VOLUME.match(folded)
    if match:
        return f"{match.group(1)}g/m3"
    if folded in ("ppb", "ppm"):
        return folded
    return text


def canonical_units(units: pd.Series) -> pd.Series:
    """Vectorised :func:`canonical_unit`, mapping each distinct value once."""
    distinct = pd.unique(units.astype(object))
    return units.astype(object).map({u: canonical_unit(u) for u in distinct})
