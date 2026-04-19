"""Structural pattern checks for source adapters.

Paired with ``tests/test_source_consistency.py`` (which enforces vocabulary
and value-level invariants) and documented in
``docs/dev/connector_pattern.md``.

These tests use AST parsing + regex scans to flag deviations from the
canonical connector pattern. They're static — no network, fast — and run
on every PR so new sources and refactors don't drift silently.

When an assertion fires, read the error message: it'll tell you the file,
the line, and how to fix. If the canonical pattern itself needs to change,
update this file *and* ``docs/dev/connector_pattern.md`` together.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


_SOURCES_DIR = Path(__file__).parent.parent / "src" / "aeolus" / "sources"

# Sources that legitimately deviate from some checks, with reasons.
# Keep this list tight — deviations should be rare and justified.
_SDK_SOURCES = {
    "openaq": "Uses OpenAQ SDK which handles retries internally",
    "purpleair": "Uses purpleair-api SDK for some calls",
}


def _source_files() -> list[Path]:
    """Return every adapter module (excluding __init__)."""
    return sorted(
        p for p in _SOURCES_DIR.glob("*.py")
        if p.stem != "__init__"
    )


# ============================================================================
# Docstring presence
# ============================================================================


def test_every_source_has_module_docstring():
    """Every source module starts with a module-level docstring."""
    violations = []
    for path in _source_files():
        tree = ast.parse(path.read_text())
        docstring = ast.get_docstring(tree)
        if not docstring or len(docstring.strip()) < 20:
            violations.append(f"{path.name}: missing or very short module docstring")
    assert not violations, "\n  ".join(["Docstring violations:"] + violations)


def test_every_docstring_mentions_an_api_url():
    """Module docstrings should mention the API endpoint so users/future devs
    can find the source's documentation quickly."""
    violations = []
    for path in _source_files():
        tree = ast.parse(path.read_text())
        docstring = ast.get_docstring(tree) or ""
        # A URL or explicit "API:" / "endpoint:" hint is enough
        has_url = bool(re.search(r"https?://", docstring))
        has_api_hint = bool(re.search(r"\b(API|endpoint)\b", docstring, re.IGNORECASE))
        if not (has_url or has_api_hint):
            violations.append(
                f"{path.name}: docstring mentions no URL and no API/endpoint reference"
            )
    assert not violations, "\n  ".join(["Docstring URL violations:"] + violations)


# ============================================================================
# Retry decorator coverage
# ============================================================================


def _functions_calling_requests(path: Path) -> list[tuple[str, int, list[str]]]:
    """Find functions containing ``requests.<verb>(`` and their decorators.

    Returns list of (function_name, line_no, decorator_names).
    """
    text = path.read_text()
    tree = ast.parse(text)
    results = []

    # Walk top-level and nested functions
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Does this function contain a `requests.*(` call?
        source = ast.get_source_segment(text, node) or ""
        if not re.search(r"\brequests\.(get|post|put|delete|request|patch|head)\s*\(", source):
            continue

        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(dec.attr)
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    decorators.append(dec.func.attr)

        results.append((node.name, node.lineno, decorators))

    return results


def test_requests_calls_have_retry_decorator():
    """Every function that calls ``requests.*`` must be decorated with
    ``@retry_on_network_error`` (or another retry decorator)."""
    retry_decorators = {
        "retry_on_network_error",
        "retry_aggressive",
        "retry_gentle",
        "with_retry",
    }
    violations = []
    for path in _source_files():
        if path.stem in _SDK_SOURCES:
            continue
        for fname, lineno, decorators in _functions_calling_requests(path):
            if not set(decorators) & retry_decorators:
                violations.append(
                    f"{path.name}:{lineno} def {fname}: calls requests.* but has "
                    f"no retry decorator (found {decorators!r})"
                )
    assert not violations, "\n  ".join(
        ["Missing retry decorators:"] + violations
    )


# ============================================================================
# Empty-frame helper usage
# ============================================================================


def test_no_bare_empty_dataframe_for_schema_columns():
    """Sources must use ``empty_data_frame()`` / ``empty_metadata_frame()``
    for schema-shaped empty DataFrames.

    Matches literal ``pd.DataFrame(columns=[...])`` constructors where the
    column list overlaps significantly with the canonical DATA_COLUMNS or
    METADATA_COLUMNS — those are empty-schema frames that should use the
    helper instead.
    """
    # Keep these in sync with aeolus.types
    data_cols = {"site_code", "date_time", "measurand", "value", "units", "source_network"}
    meta_cols = {"site_code", "site_name", "latitude", "longitude", "source_network"}

    violations = []
    # Regex matches pd.DataFrame(...columns=[...]...)
    pat = re.compile(
        r"pd\.DataFrame\s*\([^)]*columns\s*=\s*\[([^\]]+)\]",
        re.DOTALL,
    )
    for path in _source_files():
        text = path.read_text()
        for m in pat.finditer(text):
            cols_str = m.group(1)
            found_cols = set(re.findall(r'"([^"]+)"', cols_str))
            # If ≥ 3 columns match a canonical schema, it's an empty-schema frame
            if len(found_cols & data_cols) >= 3 or len(found_cols & meta_cols) >= 3:
                line_no = text[: m.start()].count("\n") + 1
                violations.append(
                    f"{path.name}:{line_no}: bare pd.DataFrame(columns=[...]) with "
                    f"schema columns — use empty_data_frame() or empty_metadata_frame()"
                )
    assert not violations, "\n  ".join(
        ["Bare empty-schema DataFrames:"] + violations
    )


# ============================================================================
# Warning behaviour
# ============================================================================


def test_sources_use_aeolus_data_warning():
    """Every source module (except pure helpers) emits AeolusDataWarning at
    least once — i.e. they don't fail silently on empty API responses."""
    violations = []
    # Sources that legitimately never need AeolusDataWarning:
    # (none currently — if adding, justify here)
    exempt = set()

    for path in _source_files():
        if path.stem in exempt:
            continue
        text = path.read_text()
        if "AeolusDataWarning" not in text:
            violations.append(
                f"{path.name}: does not reference AeolusDataWarning — "
                f"empty/error paths should surface warnings to users"
            )
    assert not violations, "\n  ".join(["Silent sources:"] + violations)


# ============================================================================
# Section structure
# ============================================================================


def test_every_source_uses_section_dividers():
    """Source modules should delimit major sections with a divider comment
    (``# ======= LABEL =======``). Not mandatory for short modules."""
    min_divider_count = 3  # at least CONSTANTS, something, REGISTRATION
    divider_pat = re.compile(r"^# ={5,}\s*$", re.MULTILINE)
    violations = []
    for path in _source_files():
        text = path.read_text()
        # Short modules (< 200 lines) don't need dividers
        if text.count("\n") < 200:
            continue
        count = len(divider_pat.findall(text))
        if count < min_divider_count:
            violations.append(
                f"{path.name}: only {count} section divider(s) found "
                f"(expect >= {min_divider_count} for modules over 200 lines)"
            )
    assert not violations, "\n  ".join(["Missing section dividers:"] + violations)


# ============================================================================
# Signature shapes
# ============================================================================


def _find_fetch_data_signatures(path: Path) -> list[tuple[str, int, list[str]]]:
    """Find every top-level function named fetch_*_data and its arg names."""
    text = path.read_text()
    tree = ast.parse(text)
    out = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("fetch_") and node.name.endswith("_data"):
            args = [a.arg for a in node.args.args]
            out.append((node.name, node.lineno, args))
    return out


def test_fetch_data_signatures_are_consistent():
    """``fetch_X_data`` must take (sites, start_date, end_date) in that order."""
    expected_prefix = ["sites", "start_date", "end_date"]
    violations = []
    for path in _source_files():
        for fname, lineno, args in _find_fetch_data_signatures(path):
            if args[:3] != expected_prefix:
                violations.append(
                    f"{path.name}:{lineno} def {fname}{tuple(args)}: "
                    f"expected prefix {tuple(expected_prefix)}"
                )
    assert not violations, "\n  ".join(["Signature violations:"] + violations)
