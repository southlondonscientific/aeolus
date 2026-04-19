"""Consistency tests across ALL registered sources.

Each test asserts a cross-cutting invariant that must hold for every data
source. New sources are picked up automatically via the registry — no need
to edit these tests when adding a source.

The main invariant here is that ``source_network`` values emitted by each
source must match the registry key used to look that source up. If a source
emits ``"Breathe London"`` but is registered under ``"BREATHE_LONDON"``,
downstream flows that do ``get_source(df["source_network"].iloc[0])`` break
silently.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from aeolus.registry import get_source, list_sources


def _primary_network_sources() -> list[str]:
    """Return primary, non-portal network source keys for metadata tests."""
    keys = []
    for key in list_sources(include_all=True):
        spec = get_source(key)
        if spec is None:
            continue
        if not spec.get("primary", True):
            continue
        if spec.get("type") == "portal":
            # Portals need spatial filters — skip for simple metadata tests
            continue
        if key.endswith("-SOS"):
            continue
        keys.append(key)
    return keys


def test_every_source_normaliser_emits_registry_key():
    """Source adapters must emit source_network matching their registry key.

    We scan the source code for string literals assigned to source_network.
    This is a static check — no network calls, runs fast on every test run.
    """
    import re
    from pathlib import Path

    src = Path(__file__).parent.parent / "src" / "aeolus" / "sources"
    # Map registry key -> expected string
    registry_keys = set(list_sources(include_all=True))

    # Three emission patterns to check (each assigns a value to source_network):
    #   "source_network": "VALUE"         — dict key/value
    #   add_column("source_network", "VALUE")
    #   df["source_network"] = "VALUE"
    patterns = [
        (re.compile(r'"source_network"\s*:\s*"([^"]+)"'), 'dict value'),
        (re.compile(r'add_column\(\s*"source_network"\s*,\s*"([^"]+)"'), "add_column"),
        (re.compile(r'"source_network"\s*\]\s*=\s*"([^"]+)"'), "assignment"),
    ]

    violations = []
    for py_file in src.glob("*.py"):
        text = py_file.read_text()
        for pat, kind in patterns:
            for match in pat.finditer(text):
                value = match.group(1)
                if value not in registry_keys:
                    line_no = text[: match.start()].count("\n") + 1
                    violations.append(
                        f"{py_file.name}:{line_no}: {kind} emits "
                        f"source_network={value!r}, not a registry key"
                    )

    assert not violations, (
        "source_network values must match registry keys. Violations:\n  "
        + "\n  ".join(sorted(set(violations)))
    )


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
