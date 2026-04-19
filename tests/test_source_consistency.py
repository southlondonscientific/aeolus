"""Consistency tests across ALL registered sources.

Each test asserts a cross-cutting invariant that must hold for every data
source. New sources are picked up automatically via the registry — no need
to edit these tests when adding a source.

These are static checks: they scan source code for string literals assigned
to schema-critical columns (``source_network``, ``units``, ``ratification``,
``measurand``). They run fast, don't need network access, and catch whole
classes of "one source emits X, another emits Y" bugs where downstream
dispatch breaks silently.

If you need to add a new canonical value (e.g. a new ratification status),
update the vocabulary set here — that change is the signal to audit every
consumer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from aeolus.registry import get_source, list_sources


# ============================================================================
# Canonical vocabularies
# ============================================================================

# These are the canonical values each schema column may take across sources.
# When adding a new value, think twice: does every downstream consumer
# (metrics, AQI, viz, MCP tools) handle it? If yes, add it here and update
# docs. If no, map it to an existing value in the source adapter.

CANONICAL_UNITS: frozenset[str] = frozenset({
    # Pollutant concentrations
    "ug/m3",   # micrograms per cubic metre (most gases and particulates)
    "mg/m3",   # milligrams per cubic metre (CO)
    "ppb",     # parts per billion (Breathe London may return this)
    "ppm",     # parts per million
    # Non-pollutant units some sources co-publish (temperature, humidity, AQI)
    "C",       # temperature in Celsius (PurpleAir, AirNow, Sensor.Community)
    "F",       # temperature in Fahrenheit
    "%",       # relative humidity (Sensor.Community)
    "hPa",     # atmospheric pressure (hectopascals)
    "Pa",      # atmospheric pressure (pascals — Sensor.Community raw)
    "AQI",     # raw AQI values (AirNow fallback when concentration unavailable)
})

CANONICAL_RATIFICATION: frozenset[str] = frozenset({
    "Ratified",                 # verified by network operator
    "Verified",                 # EEA terminology — equivalent to Ratified
    "Validated",                # PurpleAir terminology — passed dual-channel QA
    "Provisional",              # awaiting ratification
    "Unvalidated",              # low-cost sensor, no formal QA process
    "Indicative",               # research-grade, informally validated
    "Below Detection Limit",    # PurpleAir QA flag — value at/below detection threshold
    "Channel Disagreement",     # PurpleAir QA flag — A/B channel disagreement
    "Single Channel",           # PurpleAir QA flag — only one sensor channel reporting
    "None",                     # ratification status not available
    "Unknown",                  # unknown ratification status
})

# Canonical spellings of the standard air-quality pollutants.  Every source
# that reports one of these substances must spell it this way — no "PM25"
# vs "PM2.5", no "no2" vs "NO2".  Sources may legitimately report additional
# measurands (VOCs, meteorological, etc.); those aren't constrained here.
CANONICAL_POLLUTANTS: frozenset[str] = frozenset({
    "CO",
    "NO",
    "NO2",
    "NOx",
    "O3",
    "PM1",
    "PM2.5",
    "PM10",
    "SO2",
})

# Known case variants that indicate a mapping bug.  If any adapter emits
# these, it's a regression.
BAD_POLLUTANT_SPELLINGS: frozenset[str] = frozenset({
    "pm2.5", "pm25", "PM25", "pm2_5", "PM_2.5",
    "pm10", "PM_10",
    "no2", "nO2",
    "o3", "co", "so2",
})

VALID_SOURCE_TYPES: frozenset[str] = frozenset({"network", "portal"})


# ============================================================================
# Static scanning utilities
# ============================================================================

_SOURCES_DIR = Path(__file__).parent.parent / "src" / "aeolus" / "sources"


def _emission_patterns(field: str) -> list[tuple[re.Pattern, str]]:
    """Regex patterns that match string literals assigned to ``field``."""
    return [
        (re.compile(r'"' + field + r'"\s*:\s*"([^"]+)"'), "dict value"),
        (re.compile(r'add_column\(\s*"' + field + r'"\s*,\s*"([^"]+)"'), "add_column"),
        (re.compile(r'"' + field + r'"\s*\]\s*=\s*"([^"]+)"'), "df[col]= "),
    ]


def _scan_field_emissions(field: str) -> list[tuple[str, int, str, str]]:
    """Scan all source files for string literals assigned to ``field``.

    Returns a list of ``(filename, line_number, kind, value)`` tuples.
    """
    results = []
    for py_file in _SOURCES_DIR.glob("*.py"):
        text = py_file.read_text()
        for pat, kind in _emission_patterns(field):
            for match in pat.finditer(text):
                value = match.group(1)
                line_no = text[: match.start()].count("\n") + 1
                results.append((py_file.name, line_no, kind, value))
    return results


# ============================================================================
# source_network consistency
# ============================================================================


def test_every_source_normaliser_emits_registry_key():
    """source_network values must match a registry key.

    Otherwise downstream flows that do ``get_source(df["source_network"])``
    break silently (e.g. get_current() returning zero readings).
    """
    registry_keys = set(list_sources(include_all=True))
    violations = [
        f"{f}:{n}: {k} emits source_network={v!r}, not a registry key"
        for f, n, k, v in _scan_field_emissions("source_network")
        if v not in registry_keys
    ]
    assert not violations, (
        "source_network values must match registry keys:\n  "
        + "\n  ".join(sorted(set(violations)))
    )


# ============================================================================
# units consistency
# ============================================================================


def test_every_source_emits_canonical_units():
    """units values must come from the canonical vocabulary.

    Ad-hoc spellings (``ug.m-3``, ``µg/m³``) must be normalised inside the
    source adapter to canonical form before reaching the user's DataFrame.
    """
    violations = [
        f"{f}:{n}: {k} emits units={v!r} (not in canonical vocabulary)"
        for f, n, k, v in _scan_field_emissions("units")
        if v not in CANONICAL_UNITS
    ]
    assert not violations, (
        f"units must be one of {sorted(CANONICAL_UNITS)}:\n  "
        + "\n  ".join(sorted(set(violations)))
    )


# ============================================================================
# ratification consistency
# ============================================================================


def test_every_source_emits_canonical_ratification():
    """ratification values must come from the canonical vocabulary."""
    violations = [
        f"{f}:{n}: {k} emits ratification={v!r} (not in canonical vocabulary)"
        for f, n, k, v in _scan_field_emissions("ratification")
        if v not in CANONICAL_RATIFICATION
    ]
    assert not violations, (
        f"ratification must be one of {sorted(CANONICAL_RATIFICATION)}:\n  "
        + "\n  ".join(sorted(set(violations)))
    )


# ============================================================================
# measurand canonical-name consistency
# ============================================================================


def test_no_bad_pollutant_spellings_in_sources():
    """No source adapter may emit non-canonical spellings for standard pollutants.

    Maps like SPECIES_MAP are fine on the *input* side (they translate from
    raw API values to canonical names) — what this catches is downstream
    code that uses an unconverted or misspelled name like ``PM25`` in a
    DataFrame column assignment.
    """
    # Scan any string literal that looks like a measurand emission.
    # These patterns cover direct assignments, not mapping-table keys
    # (which *should* contain raw API values like "PM25" → canonical "PM2.5").
    violations = []
    emission_patterns = [
        # "measurand": "value"
        re.compile(r'"measurand"\s*:\s*"([^"]+)"'),
        # add_column("measurand", "value")
        re.compile(r'add_column\(\s*"measurand"\s*,\s*"([^"]+)"'),
        # df["measurand"] = "value"
        re.compile(r'"measurand"\s*\]\s*=\s*"([^"]+)"'),
    ]

    for py_file in _SOURCES_DIR.glob("*.py"):
        text = py_file.read_text()
        for pat in emission_patterns:
            for match in pat.finditer(text):
                value = match.group(1)
                if value in BAD_POLLUTANT_SPELLINGS:
                    line_no = text[: match.start()].count("\n") + 1
                    canonical = {
                        "pm25": "PM2.5", "PM25": "PM2.5", "pm2.5": "PM2.5", "pm2_5": "PM2.5", "PM_2.5": "PM2.5",
                        "pm10": "PM10", "PM_10": "PM10",
                        "no2": "NO2", "nO2": "NO2",
                        "o3": "O3", "co": "CO", "so2": "SO2",
                    }.get(value, value)
                    violations.append(
                        f"{py_file.name}:{line_no}: emits measurand={value!r} "
                        f"(canonical: {canonical!r})"
                    )

    assert not violations, (
        "measurand column must only contain canonical pollutant spellings:\n  "
        + "\n  ".join(sorted(set(violations)))
    )


def test_species_maps_produce_canonical_names():
    """Any SPECIES_MAP / pollutant dict in a source module whose values
    include standard pollutants must use the canonical spelling as the value."""
    # Look for dict literals where values overlap with bad spellings
    violations = []
    # Match "KEY": "VALUE" where VALUE is a bad spelling
    dict_pat = re.compile(r'"[A-Za-z0-9._]+"\s*:\s*"([^"]+)"')

    for py_file in _SOURCES_DIR.glob("*.py"):
        text = py_file.read_text()
        # Find MAP-style assignments whose value side contains bad spellings
        for line_no, line in enumerate(text.split("\n"), 1):
            for m in dict_pat.finditer(line):
                value = m.group(1)
                if value in BAD_POLLUTANT_SPELLINGS:
                    # Only flag if the surrounding context suggests pollutant mapping
                    context_line = line.strip().lower()
                    if any(
                        k in context_line for k in ("species", "pollutant", "measurand")
                    ):
                        violations.append(
                            f"{py_file.name}:{line_no}: mapping produces {value!r} "
                            f"(should map to canonical pollutant name)"
                        )

    assert not violations, (
        "Pollutant mapping tables must produce canonical names:\n  "
        + "\n  ".join(sorted(set(violations)))
    )


# ============================================================================
# Registry-level consistency
# ============================================================================


def test_registry_keys_are_uppercase():
    """All registry keys should be uppercase for consistency."""
    for key in list_sources(include_all=True):
        assert key == key.upper(), f"Registry key {key!r} is not uppercase"


def test_every_source_spec_has_required_fields():
    """Every source spec must provide the fields documented in SourceSpec."""
    required = {"name", "fetch_metadata", "fetch_data", "normalise", "requires_api_key"}
    for key in list_sources(include_all=True):
        spec = get_source(key)
        missing = required - set(spec.keys())
        assert not missing, f"{key}: missing required fields {missing}"


def test_every_source_spec_has_valid_type():
    """Every source must declare type='network' or type='portal'."""
    violations = []
    for key in list_sources(include_all=True):
        spec = get_source(key)
        source_type = spec.get("type")
        if source_type is None:
            violations.append(f"{key}: missing 'type' field")
        elif source_type not in VALID_SOURCE_TYPES:
            violations.append(
                f"{key}: type={source_type!r} not in {sorted(VALID_SOURCE_TYPES)}"
            )
    assert not violations, "\n  ".join(["Source type violations:"] + violations)


def test_requires_api_key_is_bool():
    """requires_api_key must be a boolean, not a string or other truthy value."""
    violations = []
    for key in list_sources(include_all=True):
        spec = get_source(key)
        val = spec.get("requires_api_key")
        if not isinstance(val, bool):
            violations.append(
                f"{key}: requires_api_key={val!r} (type {type(val).__name__}), expected bool"
            )
    assert not violations, "\n  ".join(["requires_api_key violations:"] + violations)


def test_fetcher_fields_are_callable():
    """fetch_metadata, fetch_data, normalise must be callables."""
    violations = []
    for key in list_sources(include_all=True):
        spec = get_source(key)
        for field in ("fetch_metadata", "fetch_data", "normalise"):
            val = spec.get(field)
            if val is not None and not callable(val):
                violations.append(f"{key}: {field} is not callable (type {type(val).__name__})")
    assert not violations, "\n  ".join(["Callable-field violations:"] + violations)


# ============================================================================
# Case-sensitivity contract
# ============================================================================


def test_source_name_lookup_is_case_insensitive():
    """Registry lookups by source name must be case-insensitive so users
    can pass either "LAQN" or "laqn" to download()/find_sites()."""
    for key in list_sources(include_all=True):
        # Case-invariance holds as long as case variants resolve to the same spec
        assert get_source(key.lower()) is get_source(key), (
            f"get_source({key.lower()!r}) did not resolve to the same spec as "
            f"get_source({key!r}) — source-name lookup is case-sensitive"
        )
        assert get_source(key.swapcase()) is get_source(key), (
            f"get_source({key.swapcase()!r}) failed — swapcase must also resolve"
        )
