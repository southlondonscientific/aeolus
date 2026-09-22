"""The user-facing docs and notebooks describe the v0.5.0 contract, not the 0.4 one.

Fails on pre-0.5.0 vocabulary so a docs rewrite cannot silently regress.
Developer notes (docs/dev, docs/superpowers), the CHANGELOG and the migration
guide are exempt: they legitimately talk about the old names.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

USER_DOCS = [
    ROOT / "README.md",
    ROOT / "CLAUDE.md",
    ROOT / "notebooks" / "README.md",
    *sorted((ROOT / "docs" / "getting-started").glob("*.md")),
    *sorted((ROOT / "docs" / "guide").glob("*.md")),
    *sorted((ROOT / "docs" / "sources").glob("*.md")),
    *sorted((ROOT / "docs" / "api").glob("*.md")),
    ROOT / "docs" / "index.md",
    ROOT / "docs" / "dev" / "openair_comparison.md",  # in the site nav
]
EXEMPT = {ROOT / "docs" / "guide" / "migrating-to-0.5.md"}
NOTEBOOKS = sorted((ROOT / "notebooks").glob("*.ipynb"))

# Phrases that only made sense before v0.5.0.
FORBIDDEN = [
    re.compile(r"8-column|eight columns|\b8 columns", re.I),
    re.compile(r"ratification\s*=\s*['\"]", re.I),           # ratification='Indicative' etc.
    re.compile(r"marked as `?(Unvalidated|Indicative|Provisional|provisional)`?"),
    re.compile(r"\*\*Data quality\*\*:\s*(Indicative|Unvalidated|Ratified|Provisional)"),
    re.compile(r"not yet wired|return(s)? an empty frame|only the up-to-date feed"),  # EEA before PR #17
]
# `source_network` / `ratification` may appear only where the line says they are legacy mirrors.
LEGACY = re.compile(r"\bsource_network\b|\bratification\b(?!_stage)", re.I)
LEGACY_CONTEXT = re.compile(r"deprecated|mirror|legacy|1\.0|Migrat|migrat|AEOLUS_LEGACY_COLUMNS|ratification_stage|legacy_ratification")


def _offending_lines(text: str):
    for n, line in enumerate(text.splitlines(), 1):
        for pat in FORBIDDEN:
            if pat.search(line):
                yield n, line.strip()
        if LEGACY.search(line) and not LEGACY_CONTEXT.search(line):
            yield n, line.strip()


@pytest.mark.parametrize("path", [p for p in USER_DOCS if p.exists() and p not in EXEMPT], ids=lambda p: str(p.relative_to(ROOT)))
def test_user_docs_use_v050_vocabulary(path):
    bad = list(_offending_lines(path.read_text()))
    assert not bad, f"{path.relative_to(ROOT)} still uses pre-0.5.0 vocabulary:\n" + "\n".join(f"  {n}: {l}" for n, l in bad)


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_source_uses_v050_vocabulary(path):
    """Code AND markdown cells (outputs are not checked: they are whatever the API printed)."""
    nb = json.loads(path.read_text())
    bad = []
    for i, cell in enumerate(nb["cells"]):
        for n, line in _offending_lines("".join(cell["source"])):
            bad.append(f"cell {i} ({cell['cell_type']}) line {n}: {line}")
    assert not bad, f"{path.name} still uses pre-0.5.0 vocabulary:\n" + "\n".join(bad)


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_kernel_is_python3(path):
    nb = json.loads(path.read_text())
    assert nb["metadata"]["kernelspec"]["name"] == "python3", "kernelspec must be the portable 'python3'"


def test_version_strings_agree():
    import tomllib

    import aeolus

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert aeolus.__version__ == pyproject["project"]["version"]
    assert f"**Current Version:** {aeolus.__version__}" in (ROOT / "CLAUDE.md").read_text()
