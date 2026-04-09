# aeolus-cli Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool (`aeolus-cli`) that wraps the `aeolus_aq` library, with an LLM-powered `ask` command that translates natural language into CLI commands.

**Architecture:** Separate repo at `sls/aeolus-cli/`. Layer 1 is typer commands wrapping `aeolus_aq` functions. Layer 2 is `aeolus ask`, which uses Anthropic tool-use (Haiku) to translate natural language to structured tool calls, rendered as CLI commands for user approval. The LLM abstraction is isolated for future provider swaps.

**Tech Stack:** Python 3.11+, typer, rich, aeolus_aq, anthropic (optional)

**Spec:** `docs/superpowers/specs/2026-04-09-aeolus-cli-design.md` in the aeolus repo.

---

## File Structure

```
sls/aeolus-cli/
├── pyproject.toml                    # Package config, entry point, extras
├── README.md                         # Usage examples
├── LICENSE                           # GPL-3.0-or-later
├── src/aeolus_cli/
│   ├── __init__.py                   # Version only
│   ├── main.py                       # Typer app, subcommand registration
│   ├── output.py                     # Shared formatting (tables, CSV writing)
│   ├── config.py                     # Config file reading (~/.aeolus/config.toml)
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── sources.py                # aeolus sources
│   │   ├── find_sites.py             # aeolus find-sites
│   │   ├── download.py               # aeolus download
│   │   ├── get_current.py            # aeolus get-current
│   │   ├── summarise.py              # aeolus summarise
│   │   └── plot.py                   # aeolus plot
│   └── ask/
│       ├── __init__.py
│       ├── orchestrator.py           # Top-level ask flow
│       ├── tools.py                  # Tool schemas for the LLM
│       ├── llm.py                    # LLM call abstraction (Anthropic)
│       ├── prompt.py                 # System prompt builder
│       └── render.py                 # Tool call → CLI command string
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # Shared fixtures
│   ├── test_sources.py
│   ├── test_find_sites.py
│   ├── test_download.py
│   ├── test_get_current.py
│   ├── test_summarise.py
│   ├── test_plot.py
│   ├── test_output.py
│   ├── test_config.py
│   ├── test_ask_tools.py
│   ├── test_ask_render.py
│   ├── test_ask_orchestrator.py
│   └── test_ask_prompt.py
└── CLAUDE.md
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `sls/aeolus-cli/pyproject.toml`
- Create: `sls/aeolus-cli/src/aeolus_cli/__init__.py`
- Create: `sls/aeolus-cli/src/aeolus_cli/main.py`
- Create: `sls/aeolus-cli/tests/__init__.py`
- Create: `sls/aeolus-cli/tests/conftest.py`
- Create: `sls/aeolus-cli/LICENSE`
- Create: `sls/aeolus-cli/CLAUDE.md`
- Create: `sls/aeolus-cli/README.md`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "aeolus-cli"
version = "0.1.0"
authors = [
  { name="Ruaraidh Dobson", email="ruaraidh.dobson@gmail.com" },
]
description = "Command-line tool for downloading air quality data via the aeolus library"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "aeolus_aq>=0.4.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
]
license = "GPL-3.0-or-later"

[project.optional-dependencies]
ask = ["anthropic>=0.40.0"]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "anthropic>=0.40.0",
]

[project.scripts]
aeolus = "aeolus_cli.main:app"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["-v", "--tb=short"]
markers = [
    "live: tests that hit real APIs or LLMs (run before releases only)",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

- [ ] **Step 2: Create __init__.py**

```python
# src/aeolus_cli/__init__.py
__version__ = "0.1.0"
```

- [ ] **Step 3: Create main.py with bare app**

```python
# src/aeolus_cli/main.py
import typer

app = typer.Typer(
    name="aeolus",
    help="Download and explore air quality data.",
    no_args_is_help=True,
)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Create test scaffolding**

```python
# tests/__init__.py
```

```python
# tests/conftest.py
"""Shared test fixtures for aeolus-cli."""
```

- [ ] **Step 5: Create LICENSE**

Copy GPL-3.0-or-later text (same as aeolus repo: `sls/aeolus/LICENSE`).

- [ ] **Step 6: Create CLAUDE.md**

```markdown
# aeolus-cli — Claude Code Context

CLI tool wrapping the `aeolus_aq` library for air quality data access.

## Quick Start

\```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest
\```

## Structure

- `src/aeolus_cli/commands/` — one file per CLI command, each wrapping an aeolus library function
- `src/aeolus_cli/ask/` — LLM-powered natural language to CLI translation
- `src/aeolus_cli/output.py` — shared formatting (tables, CSV writing)
- `src/aeolus_cli/config.py` — reads `~/.aeolus/config.toml` for API keys

## Testing

\```bash
pytest                    # all tests
pytest -m "not live"      # skip API/LLM tests
\```

## Design Spec

See `sls/aeolus/docs/superpowers/specs/2026-04-09-aeolus-cli-design.md`.
```

- [ ] **Step 7: Create minimal README.md**

```markdown
# aeolus

Command-line tool for downloading and exploring air quality data.

\```bash
pip install aeolus-cli
aeolus sources
aeolus find-sites AURN --near 51.5,-0.13 --radius 10
aeolus download AURN --sites MY1 KC1 --last 30d
\```

Wraps the [aeolus_aq](https://pypi.org/project/aeolus_aq/) library.
```

- [ ] **Step 8: Create venv, install, and verify**

```bash
cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
aeolus --help
```

Expected: typer prints help text with "Download and explore air quality data."

- [ ] **Step 9: Run tests (should pass with 0 collected)**

```bash
pytest
```

Expected: "no tests ran" or "0 items collected", exit 0.

- [ ] **Step 10: Init git repo and commit**

```bash
cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli
git init
git add pyproject.toml src/ tests/ LICENSE CLAUDE.md README.md
git commit -m "feat: initial project scaffolding"
```

---

## Task 2: Config Module

**Files:**
- Create: `src/aeolus_cli/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write tests for config loading**

```python
# tests/test_config.py
"""Tests for config file reading."""
import os
from pathlib import Path

import pytest


def test_get_key_from_env(monkeypatch):
    """Environment variable takes precedence."""
    from aeolus_cli.config import get_key

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
    assert get_key("ANTHROPIC_API_KEY") == "sk-from-env"


def test_get_key_from_config_file(monkeypatch, tmp_path):
    """Falls back to config file when env var is not set."""
    from aeolus_cli.config import get_key

    monkeypatch.delenv("BL_API_KEY", raising=False)
    config_file = tmp_path / "config.toml"
    config_file.write_text('[keys]\nBL_API_KEY = "bl-from-file"\n')
    assert get_key("BL_API_KEY", config_path=config_file) == "bl-from-file"


def test_get_key_returns_none_when_missing(monkeypatch, tmp_path):
    """Returns None when key is not in env or config."""
    from aeolus_cli.config import get_key

    monkeypatch.delenv("NONEXISTENT_KEY", raising=False)
    config_file = tmp_path / "config.toml"
    config_file.write_text("[keys]\n")
    assert get_key("NONEXISTENT_KEY", config_path=config_file) is None


def test_get_key_handles_missing_config_file(monkeypatch, tmp_path):
    """Gracefully handles missing config file."""
    from aeolus_cli.config import get_key

    monkeypatch.delenv("SOME_KEY", raising=False)
    missing = tmp_path / "does_not_exist.toml"
    assert get_key("SOME_KEY", config_path=missing) is None


def test_default_config_path():
    """Default config path is ~/.aeolus/config.toml."""
    from aeolus_cli.config import DEFAULT_CONFIG_PATH

    assert DEFAULT_CONFIG_PATH == Path.home() / ".aeolus" / "config.toml"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'aeolus_cli.config'`

- [ ] **Step 3: Implement config.py**

```python
# src/aeolus_cli/config.py
"""Read API keys from environment variables or ~/.aeolus/config.toml."""
import os
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python 3.11 has tomllib in stdlib

DEFAULT_CONFIG_PATH = Path.home() / ".aeolus" / "config.toml"


def _read_config(config_path: Path) -> dict:
    """Read and parse the TOML config file."""
    if not config_path.exists():
        return {}
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def get_key(
    key_name: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> str | None:
    """Look up an API key: env var first, then config file.

    Args:
        key_name: Name of the key (e.g. "ANTHROPIC_API_KEY").
        config_path: Path to TOML config file.

    Returns:
        The key value, or None if not found.
    """
    # 1. Environment variable wins
    value = os.environ.get(key_name)
    if value:
        return value

    # 2. Fall back to config file
    config = _read_config(config_path)
    keys_section = config.get("keys", {})
    return keys_section.get(key_name)
```

Note: Python 3.11 has `tomllib` in the standard library, so no extra dependency needed.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/aeolus_cli/config.py tests/test_config.py
git commit -m "feat: add config module for API key resolution"
```

---

## Task 3: Output Formatting Module

**Files:**
- Create: `src/aeolus_cli/output.py`
- Create: `tests/test_output.py`

- [ ] **Step 1: Write tests for output formatting**

```python
# tests/test_output.py
"""Tests for shared output formatting."""
import pandas as pd
import pytest
from io import StringIO
from pathlib import Path


def test_print_table_renders_dataframe(capsys):
    """print_table renders a DataFrame as a rich table."""
    from aeolus_cli.output import print_table

    df = pd.DataFrame({"name": ["AURN", "SAQN"], "coverage": ["UK", "Scotland"]})
    print_table(df, title="Sources")
    captured = capsys.readouterr()
    assert "AURN" in captured.out
    assert "SAQN" in captured.out


def test_write_csv_creates_file(tmp_path):
    """write_csv writes a DataFrame to a CSV file."""
    from aeolus_cli.output import write_csv

    df = pd.DataFrame({"site_code": ["MY1"], "value": [42.0]})
    out = tmp_path / "test.csv"
    write_csv(df, out)
    assert out.exists()
    content = out.read_text()
    assert "MY1" in content
    assert "42.0" in content


def test_write_csv_auto_generates_filename(tmp_path, monkeypatch):
    """write_csv generates a default filename when none is given."""
    from aeolus_cli.output import make_default_filename

    name = make_default_filename("AURN")
    # Should be like AURN_2026-04-09.csv
    assert name.startswith("AURN_")
    assert name.endswith(".csv")


def test_format_error_message():
    """format_error produces clean, no-traceback output."""
    from aeolus_cli.output import format_error

    msg = format_error(ValueError("Unknown source: FOO"))
    assert "Unknown source: FOO" in msg
    assert "Traceback" not in msg
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_output.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement output.py**

```python
# src/aeolus_cli/output.py
"""Shared output formatting for the aeolus CLI."""
from datetime import date
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

console = Console()


def print_table(df: pd.DataFrame, title: str | None = None) -> None:
    """Print a DataFrame as a formatted rich table."""
    table = Table(title=title, show_lines=False)
    for col in df.columns:
        table.add_column(str(col))
    for _, row in df.iterrows():
        table.add_row(*[str(v) for v in row])
    console.print(table)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to CSV."""
    df.to_csv(path, index=False)
    console.print(f"Saved to {path} ({len(df)} rows)")


def make_default_filename(source: str) -> str:
    """Generate a default output filename like AURN_2026-04-09.csv."""
    today = date.today().isoformat()
    return f"{source}_{today}.csv"


def format_error(exc: Exception) -> str:
    """Format an exception as a clean error message (no traceback)."""
    return f"Error: {exc}"


def print_error(exc: Exception) -> None:
    """Print a formatted error to stderr."""
    console.print(f"[red]{format_error(exc)}[/red]", stderr=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_output.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/aeolus_cli/output.py tests/test_output.py
git commit -m "feat: add shared output formatting module"
```

---

## Task 4: `aeolus sources` Command

**Files:**
- Create: `src/aeolus_cli/commands/__init__.py`
- Create: `src/aeolus_cli/commands/sources.py`
- Create: `tests/test_sources.py`
- Modify: `src/aeolus_cli/main.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_sources.py
"""Tests for aeolus sources command."""
from typer.testing import CliRunner
from unittest.mock import patch

runner = CliRunner()


def test_sources_lists_available_networks():
    """aeolus sources prints a table of available sources."""
    from aeolus_cli.main import app

    with patch("aeolus.list_sources", return_value=["AURN", "SAQN"]), \
         patch("aeolus.get_source_info", side_effect=[
             {"name": "AURN", "type": "network", "requires_api_key": False},
             {"name": "SAQN", "type": "network", "requires_api_key": False},
         ]):
        result = runner.invoke(app, ["sources"])
    assert result.exit_code == 0
    assert "AURN" in result.output
    assert "SAQN" in result.output


def test_sources_all_flag():
    """aeolus sources --all includes SOS backends."""
    from aeolus_cli.main import app

    with patch("aeolus.list_sources", return_value=["AURN", "AURN-SOS"]) as mock_ls:
        with patch("aeolus.get_source_info", side_effect=[
            {"name": "AURN", "type": "network", "requires_api_key": False},
            {"name": "AURN-SOS", "type": "network", "requires_api_key": False},
        ]):
            result = runner.invoke(app, ["sources", "--all"])
    mock_ls.assert_called_once_with(include_all=True)
    assert result.exit_code == 0
    assert "AURN-SOS" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sources.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement sources command**

```python
# src/aeolus_cli/commands/__init__.py
```

```python
# src/aeolus_cli/commands/sources.py
"""aeolus sources — list available data networks."""
import aeolus
import pandas as pd
import typer

from aeolus_cli.output import print_table

app = typer.Typer()


@app.callback(invoke_without_command=True)
def sources(
    all: bool = typer.Option(False, "--all", help="Include SOS backends"),
):
    """List available air quality data sources."""
    source_names = aeolus.list_sources(include_all=all)
    rows = []
    for name in source_names:
        info = aeolus.get_source_info(name)
        rows.append({
            "Source": info["name"],
            "Type": info.get("type", "network"),
            "API Key": "Yes" if info["requires_api_key"] else "No",
        })
    df = pd.DataFrame(rows)
    print_table(df, title="Available Sources")
```

- [ ] **Step 4: Register in main.py**

```python
# src/aeolus_cli/main.py
import typer

app = typer.Typer(
    name="aeolus",
    help="Download and explore air quality data.",
    no_args_is_help=True,
)

# Register subcommands
from aeolus_cli.commands.sources import app as sources_app

app.add_typer(sources_app, name="sources", help="List available data sources")


if __name__ == "__main__":
    app()
```

Note: We'll add more subcommands to main.py as we implement them. Each task that adds a command will include the line to add to main.py.

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_sources.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Manual smoke test**

```bash
aeolus sources
```

Expected: Rich table showing available sources.

- [ ] **Step 7: Commit**

```bash
git add src/aeolus_cli/commands/ tests/test_sources.py src/aeolus_cli/main.py
git commit -m "feat: add aeolus sources command"
```

---

## Task 5: `aeolus find-sites` Command

**Files:**
- Create: `src/aeolus_cli/commands/find_sites.py`
- Create: `tests/test_find_sites.py`
- Modify: `src/aeolus_cli/main.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_find_sites.py
"""Tests for aeolus find-sites command."""
import pandas as pd
from typer.testing import CliRunner
from unittest.mock import patch

runner = CliRunner()


def _mock_sites_df():
    return pd.DataFrame({
        "site_code": ["MY1", "KC1"],
        "site_name": ["Marylebone Road", "Kensington"],
        "latitude": [51.5225, 51.4955],
        "longitude": [-0.1546, -0.1988],
        "source_network": ["AURN", "AURN"],
    })


def test_find_sites_basic():
    """aeolus find-sites AURN lists sites."""
    from aeolus_cli.main import app

    with patch("aeolus.find_sites", return_value=_mock_sites_df()) as mock:
        result = runner.invoke(app, ["find-sites", "AURN"])
    mock.assert_called_once_with(source="AURN", near=None, radius_km=50.0, bbox=None)
    assert result.exit_code == 0
    assert "MY1" in result.output


def test_find_sites_near():
    """aeolus find-sites AURN --near 51.5,-0.13 --radius 10 passes params."""
    from aeolus_cli.main import app

    df = _mock_sites_df()
    df["distance_km"] = [1.2, 3.4]
    with patch("aeolus.find_sites", return_value=df) as mock:
        result = runner.invoke(app, ["find-sites", "AURN", "--near", "51.5,-0.13", "--radius", "10"])
    mock.assert_called_once_with(source="AURN", near=(51.5, -0.13), radius_km=10.0, bbox=None)
    assert result.exit_code == 0


def test_find_sites_lat_lon():
    """aeolus find-sites AURN --lat 51.5 --lon -0.13 is equivalent to --near."""
    from aeolus_cli.main import app

    with patch("aeolus.find_sites", return_value=_mock_sites_df()) as mock:
        result = runner.invoke(app, ["find-sites", "AURN", "--lat", "51.5", "--lon", "-0.13"])
    mock.assert_called_once_with(source="AURN", near=(51.5, -0.13), radius_km=50.0, bbox=None)
    assert result.exit_code == 0


def test_find_sites_bbox():
    """aeolus find-sites --bbox passes bounding box."""
    from aeolus_cli.main import app

    with patch("aeolus.find_sites", return_value=_mock_sites_df()) as mock:
        result = runner.invoke(app, ["find-sites", "--bbox", "-0.5,51.3,0.3,51.7"])
    mock.assert_called_once_with(source=None, near=None, radius_km=50.0, bbox=(-0.5, 51.3, 0.3, 51.7))
    assert result.exit_code == 0


def test_find_sites_near_and_lat_lon_errors():
    """Cannot use both --near and --lat/--lon."""
    from aeolus_cli.main import app

    result = runner.invoke(app, ["find-sites", "AURN", "--near", "51.5,-0.13", "--lat", "51.5"])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_find_sites.py -v
```

- [ ] **Step 3: Implement find-sites command**

```python
# src/aeolus_cli/commands/find_sites.py
"""aeolus find-sites — search for monitoring sites."""
from typing import Optional

import aeolus
import typer

from aeolus_cli.output import print_error, print_table

app = typer.Typer()


def _parse_near(near: str) -> tuple[float, float]:
    """Parse '51.5,-0.13' into (lat, lon) tuple."""
    parts = near.split(",")
    if len(parts) != 2:
        raise typer.BadParameter(f"Expected lat,lon format, got: {near}")
    return float(parts[0].strip()), float(parts[1].strip())


def _parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    """Parse '-0.5,51.3,0.3,51.7' into (min_lon, min_lat, max_lon, max_lat)."""
    parts = bbox.split(",")
    if len(parts) != 4:
        raise typer.BadParameter(f"Expected min_lon,min_lat,max_lon,max_lat format, got: {bbox}")
    return tuple(float(p.strip()) for p in parts)


@app.callback(invoke_without_command=True)
def find_sites(
    source: Optional[str] = typer.Argument(None, help="Source name (e.g. AURN)"),
    near: Optional[str] = typer.Option(None, help="Lat,lon for circular search (e.g. 51.5,-0.13)"),
    lat: Optional[float] = typer.Option(None, help="Latitude (alternative to --near)"),
    lon: Optional[float] = typer.Option(None, help="Longitude (alternative to --near)"),
    radius: float = typer.Option(50.0, "--radius", help="Radius in km (default 50)"),
    bbox: Optional[str] = typer.Option(None, help="Bounding box: min_lon,min_lat,max_lon,max_lat"),
):
    """Find air quality monitoring sites."""
    # Resolve --near vs --lat/--lon
    near_tuple = None
    if near is not None and (lat is not None or lon is not None):
        print_error(ValueError("Cannot use both --near and --lat/--lon"))
        raise typer.Exit(code=1)
    if near is not None:
        near_tuple = _parse_near(near)
    elif lat is not None and lon is not None:
        near_tuple = (lat, lon)
    elif lat is not None or lon is not None:
        print_error(ValueError("Both --lat and --lon are required"))
        raise typer.Exit(code=1)

    bbox_tuple = _parse_bbox(bbox) if bbox else None

    try:
        df = aeolus.find_sites(
            source=source,
            near=near_tuple,
            radius_km=radius,
            bbox=bbox_tuple,
        )
        if df.empty:
            typer.echo("No sites found.")
            raise typer.Exit(code=0)
        print_table(df)
    except Exception as e:
        print_error(e)
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Register in main.py**

Add to `main.py`:
```python
from aeolus_cli.commands.find_sites import app as find_sites_app
app.add_typer(find_sites_app, name="find-sites", help="Find monitoring sites")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_find_sites.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/aeolus_cli/commands/find_sites.py tests/test_find_sites.py src/aeolus_cli/main.py
git commit -m "feat: add aeolus find-sites command"
```

---

## Task 6: `aeolus download` Command

**Files:**
- Create: `src/aeolus_cli/commands/download.py`
- Create: `tests/test_download.py`
- Modify: `src/aeolus_cli/main.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_download.py
"""Tests for aeolus download command."""
import pandas as pd
from typer.testing import CliRunner
from unittest.mock import patch, ANY

runner = CliRunner()


def _mock_data():
    return pd.DataFrame({
        "site_code": ["MY1", "MY1"],
        "date_time": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
        "measurand": ["NO2", "NO2"],
        "value": [40.0, 42.0],
        "units": ["ug/m3", "ug/m3"],
        "source_network": ["AURN", "AURN"],
        "ratification": ["Provisional", "Provisional"],
        "created_at": ["2024-01-02T00:00:00Z", "2024-01-02T00:00:00Z"],
    })


def test_download_with_dates(tmp_path):
    """aeolus download AURN --sites MY1 --start ... --end ... writes CSV."""
    from aeolus_cli.main import app

    out = tmp_path / "test.csv"
    with patch("aeolus.download", return_value=_mock_data()):
        result = runner.invoke(app, [
            "download", "AURN",
            "--sites", "MY1",
            "--start", "2024-01-01",
            "--end", "2024-01-31",
            "-o", str(out),
        ])
    assert result.exit_code == 0
    assert out.exists()


def test_download_with_last(tmp_path):
    """aeolus download AURN --sites MY1 --last 30d uses last shorthand."""
    from aeolus_cli.main import app

    out = tmp_path / "test.csv"
    with patch("aeolus.download", return_value=_mock_data()) as mock:
        result = runner.invoke(app, [
            "download", "AURN",
            "--sites", "MY1",
            "--last", "30d",
            "-o", str(out),
        ])
    mock.assert_called_once()
    # Verify last= was passed
    _, kwargs = mock.call_args
    assert kwargs.get("last") == "30d"
    assert result.exit_code == 0


def test_download_measurands_filter(tmp_path):
    """--measurands filters the downloaded data."""
    from aeolus_cli.main import app

    out = tmp_path / "test.csv"
    data = _mock_data()
    with patch("aeolus.download", return_value=data):
        result = runner.invoke(app, [
            "download", "AURN",
            "--sites", "MY1",
            "--last", "30d",
            "--measurands", "NO2", "PM2.5",
            "-o", str(out),
        ])
    assert result.exit_code == 0


def test_download_requires_dates_or_last():
    """Errors if neither --start/--end nor --last is given."""
    from aeolus_cli.main import app

    result = runner.invoke(app, ["download", "AURN", "--sites", "MY1"])
    assert result.exit_code != 0


def test_download_default_filename(tmp_path, monkeypatch):
    """Default output file is <SOURCE>_<date>.csv in cwd."""
    from aeolus_cli.main import app

    monkeypatch.chdir(tmp_path)
    with patch("aeolus.download", return_value=_mock_data()):
        result = runner.invoke(app, [
            "download", "AURN",
            "--sites", "MY1",
            "--last", "30d",
        ])
    assert result.exit_code == 0
    # Check that a file was created in tmp_path
    csv_files = list(tmp_path.glob("AURN_*.csv"))
    assert len(csv_files) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_download.py -v
```

- [ ] **Step 3: Implement download command**

```python
# src/aeolus_cli/commands/download.py
"""aeolus download — fetch air quality data to CSV."""
from datetime import datetime
from pathlib import Path
from typing import Optional

import aeolus
import typer

from aeolus_cli.output import make_default_filename, print_error, write_csv

app = typer.Typer()


@app.callback(invoke_without_command=True)
def download(
    source: str = typer.Argument(..., help="Source name (e.g. AURN, SAQN)"),
    sites: list[str] = typer.Option(..., "--sites", help="Site codes"),
    start: Optional[str] = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)"),
    end: Optional[str] = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
    last: Optional[str] = typer.Option(None, "--last", help="Date range shorthand (e.g. 30d, 6m, 1y)"),
    measurands: Optional[list[str]] = typer.Option(None, "--measurands", help="Filter to these pollutants"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output CSV path"),
):
    """Download air quality data to CSV."""
    # Validate: need either start+end or last
    if last is None and (start is None or end is None):
        print_error(ValueError(
            "Specify --start and --end, or use --last (e.g. --last 30d)"
        ))
        raise typer.Exit(code=1)
    if last is not None and (start is not None or end is not None):
        print_error(ValueError("Cannot use --last together with --start/--end"))
        raise typer.Exit(code=1)

    # Parse dates
    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None

    try:
        data = aeolus.download(
            sources=source,
            sites=sites,
            start_date=start_dt,
            end_date=end_dt,
            last=last,
        )

        # Filter measurands if requested
        if measurands and not data.empty:
            data = data[data["measurand"].isin(measurands)]

        # Determine output path
        if output is None:
            output = Path(make_default_filename(source))

        write_csv(data, output)

    except Exception as e:
        print_error(e)
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Register in main.py**

Add to `main.py`:
```python
from aeolus_cli.commands.download import app as download_app
app.add_typer(download_app, name="download", help="Download air quality data to CSV")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_download.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/aeolus_cli/commands/download.py tests/test_download.py src/aeolus_cli/main.py
git commit -m "feat: add aeolus download command"
```

---

## Task 7: `aeolus get-current` Command

**Files:**
- Create: `src/aeolus_cli/commands/get_current.py`
- Create: `tests/test_get_current.py`
- Modify: `src/aeolus_cli/main.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_get_current.py
"""Tests for aeolus get-current command."""
import pandas as pd
from typer.testing import CliRunner
from unittest.mock import patch

runner = CliRunner()


def _mock_current():
    return pd.DataFrame({
        "site_code": ["MY1"],
        "date_time": ["2024-01-01T14:00:00Z"],
        "measurand": ["NO2"],
        "value": [38.0],
        "units": ["ug/m3"],
        "source_network": ["AURN"],
        "ratification": ["Provisional"],
        "created_at": ["2024-01-01T14:30:00Z"],
    })


def test_get_current_with_sites():
    """aeolus get-current AURN --sites MY1 shows latest readings."""
    from aeolus_cli.main import app

    with patch("aeolus.get_current", return_value=_mock_current()) as mock:
        result = runner.invoke(app, ["get-current", "AURN", "--sites", "MY1"])
    mock.assert_called_once_with("AURN", sites=["MY1"])
    assert result.exit_code == 0
    assert "MY1" in result.output


def test_get_current_with_near():
    """aeolus get-current AURN --near 51.5,-0.13 finds sites then gets current."""
    from aeolus_cli.main import app

    sites_df = pd.DataFrame({
        "site_code": ["MY1", "KC1"],
        "site_name": ["Marylebone Road", "Kensington"],
        "latitude": [51.5225, 51.4955],
        "longitude": [-0.1546, -0.1988],
        "source_network": ["AURN", "AURN"],
    })
    with patch("aeolus.find_sites", return_value=sites_df), \
         patch("aeolus.get_current", return_value=_mock_current()) as mock_current:
        result = runner.invoke(app, ["get-current", "AURN", "--near", "51.5,-0.13"])
    assert result.exit_code == 0
    # Should have called get_current with the discovered site codes
    mock_current.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_get_current.py -v
```

- [ ] **Step 3: Implement get-current command**

```python
# src/aeolus_cli/commands/get_current.py
"""aeolus get-current — latest readings from monitoring sites."""
from typing import Optional

import aeolus
import typer

from aeolus_cli.commands.find_sites import _parse_near
from aeolus_cli.output import print_error, print_table

app = typer.Typer()


@app.callback(invoke_without_command=True)
def get_current(
    source: str = typer.Argument(..., help="Source name (e.g. AURN)"),
    sites: Optional[list[str]] = typer.Option(None, "--sites", help="Site codes"),
    near: Optional[str] = typer.Option(None, "--near", help="Lat,lon to find nearby sites"),
    lat: Optional[float] = typer.Option(None, help="Latitude (alternative to --near)"),
    lon: Optional[float] = typer.Option(None, help="Longitude (alternative to --near)"),
    radius: float = typer.Option(10.0, "--radius", help="Radius in km for --near (default 10)"),
):
    """Get the most recent readings from monitoring sites."""
    try:
        # If --near/--lat/--lon given, discover sites first
        if near is not None or (lat is not None and lon is not None):
            near_tuple = _parse_near(near) if near else (lat, lon)
            found = aeolus.find_sites(source=source, near=near_tuple, radius_km=radius)
            if found.empty:
                typer.echo("No sites found nearby.")
                raise typer.Exit(code=0)
            site_codes = found["site_code"].tolist()
        elif sites:
            site_codes = sites
        else:
            print_error(ValueError("Specify --sites or --near to select sites"))
            raise typer.Exit(code=1)

        data = aeolus.get_current(source, sites=site_codes)
        if data.empty:
            typer.echo("No current readings available.")
            raise typer.Exit(code=0)
        print_table(data[["site_code", "date_time", "measurand", "value", "units"]])

    except typer.Exit:
        raise
    except Exception as e:
        print_error(e)
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Register in main.py**

Add to `main.py`:
```python
from aeolus_cli.commands.get_current import app as get_current_app
app.add_typer(get_current_app, name="get-current", help="Get latest readings")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_get_current.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/aeolus_cli/commands/get_current.py tests/test_get_current.py src/aeolus_cli/main.py
git commit -m "feat: add aeolus get-current command"
```

---

## Task 8: `aeolus summarise` Command

**Files:**
- Create: `src/aeolus_cli/commands/summarise.py`
- Create: `tests/test_summarise.py`
- Modify: `src/aeolus_cli/main.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_summarise.py
"""Tests for aeolus summarise command."""
import pandas as pd
from typer.testing import CliRunner
from unittest.mock import patch

runner = CliRunner()


def _write_test_csv(path):
    df = pd.DataFrame({
        "site_code": ["MY1", "MY1"],
        "date_time": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
        "measurand": ["NO2", "NO2"],
        "value": [40.0, 42.0],
        "units": ["ug/m3", "ug/m3"],
        "source_network": ["AURN", "AURN"],
        "ratification": ["Provisional", "Provisional"],
        "created_at": ["2024-01-02T00:00:00Z", "2024-01-02T00:00:00Z"],
    })
    df.to_csv(path, index=False)
    return df


def test_summarise_reads_csv(tmp_path):
    """aeolus summarise data.csv reads the file and prints a summary."""
    from aeolus_cli.main import app

    csv_path = tmp_path / "data.csv"
    _write_test_csv(csv_path)

    summary_df = pd.DataFrame({
        "site_code": ["MY1"],
        "source_network": ["AURN"],
        "measurand": ["NO2"],
        "start": ["2024-01-01"],
        "end": ["2024-01-01"],
        "records": [2],
        "valid": [2],
        "data_capture": [1.0],
    })
    with patch("aeolus.summarise", return_value=summary_df) as mock:
        result = runner.invoke(app, ["summarise", str(csv_path)])
    assert result.exit_code == 0
    assert "MY1" in result.output
    mock.assert_called_once()


def test_summarise_missing_file():
    """aeolus summarise nonexistent.csv gives a clear error."""
    from aeolus_cli.main import app

    result = runner.invoke(app, ["summarise", "/nonexistent/data.csv"])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_summarise.py -v
```

- [ ] **Step 3: Implement summarise command**

```python
# src/aeolus_cli/commands/summarise.py
"""aeolus summarise — quick overview of a downloaded CSV."""
from pathlib import Path

import aeolus
import pandas as pd
import typer

from aeolus_cli.output import print_error, print_table

app = typer.Typer()


@app.callback(invoke_without_command=True)
def summarise(
    file: Path = typer.Argument(..., help="Path to CSV file from aeolus download"),
):
    """Summarise a downloaded air quality data file."""
    if not file.exists():
        print_error(FileNotFoundError(f"File not found: {file}"))
        raise typer.Exit(code=1)

    try:
        data = pd.read_csv(file)
        summary = aeolus.summarise(data)
        if summary.empty:
            typer.echo("No data to summarise.")
            raise typer.Exit(code=0)
        print_table(summary, title=f"Summary of {file.name}")
    except typer.Exit:
        raise
    except Exception as e:
        print_error(e)
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Register in main.py**

Add to `main.py`:
```python
from aeolus_cli.commands.summarise import app as summarise_app
app.add_typer(summarise_app, name="summarise", help="Summarise a downloaded data file")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_summarise.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/aeolus_cli/commands/summarise.py tests/test_summarise.py src/aeolus_cli/main.py
git commit -m "feat: add aeolus summarise command"
```

---

## Task 9: `aeolus plot` Command

**Files:**
- Create: `src/aeolus_cli/commands/plot.py`
- Create: `tests/test_plot.py`
- Modify: `src/aeolus_cli/main.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_plot.py
"""Tests for aeolus plot command."""
import pandas as pd
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

runner = CliRunner()


def _write_test_csv(path):
    df = pd.DataFrame({
        "site_code": ["MY1", "MY1"],
        "date_time": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
        "measurand": ["NO2", "NO2"],
        "value": [40.0, 42.0],
        "units": ["ug/m3", "ug/m3"],
        "source_network": ["AURN", "AURN"],
        "ratification": ["Provisional", "Provisional"],
        "created_at": ["2024-01-02T00:00:00Z", "2024-01-02T00:00:00Z"],
    })
    df.to_csv(path, index=False)


def test_plot_creates_png(tmp_path):
    """aeolus plot data.csv creates a PNG file."""
    from aeolus_cli.main import app

    csv_path = tmp_path / "data.csv"
    _write_test_csv(csv_path)
    out_path = tmp_path / "plot.png"

    mock_fig = MagicMock()
    with patch("aeolus.viz.plot_timeseries", return_value=mock_fig):
        result = runner.invoke(app, ["plot", str(csv_path), "-o", str(out_path)])
    assert result.exit_code == 0
    mock_fig.savefig.assert_called_once_with(str(out_path), dpi=150, bbox_inches="tight")


def test_plot_default_output(tmp_path, monkeypatch):
    """Default output is <input_stem>_plot.png."""
    from aeolus_cli.main import app

    monkeypatch.chdir(tmp_path)
    csv_path = tmp_path / "manchester.csv"
    _write_test_csv(csv_path)

    mock_fig = MagicMock()
    with patch("aeolus.viz.plot_timeseries", return_value=mock_fig):
        result = runner.invoke(app, ["plot", str(csv_path)])
    assert result.exit_code == 0
    mock_fig.savefig.assert_called_once()
    saved_path = mock_fig.savefig.call_args[0][0]
    assert "manchester" in saved_path
    assert saved_path.endswith(".png")


def test_plot_missing_file():
    """aeolus plot nonexistent.csv gives a clear error."""
    from aeolus_cli.main import app

    result = runner.invoke(app, ["plot", "/nonexistent/data.csv"])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_plot.py -v
```

- [ ] **Step 3: Implement plot command**

```python
# src/aeolus_cli/commands/plot.py
"""aeolus plot — time series chart from a data CSV."""
from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from aeolus import viz

from aeolus_cli.output import console, print_error

app = typer.Typer()


@app.callback(invoke_without_command=True)
def plot(
    file: Path = typer.Argument(..., help="Path to CSV file from aeolus download"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output PNG path"),
):
    """Plot a time series chart from downloaded data."""
    if not file.exists():
        print_error(FileNotFoundError(f"File not found: {file}"))
        raise typer.Exit(code=1)

    try:
        data = pd.read_csv(file)
        fig = viz.plot_timeseries(data)

        if output is None:
            output_str = f"{file.stem}_plot.png"
        else:
            output_str = str(output)

        fig.savefig(output_str, dpi=150, bbox_inches="tight")
        console.print(f"Saved plot to {output_str}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(e)
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Register in main.py**

Add to `main.py`:
```python
from aeolus_cli.commands.plot import app as plot_app
app.add_typer(plot_app, name="plot", help="Plot a time series chart")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_plot.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/aeolus_cli/commands/plot.py tests/test_plot.py src/aeolus_cli/main.py
git commit -m "feat: add aeolus plot command"
```

---

## Task 10: `ask` Tool Schemas

**Files:**
- Create: `src/aeolus_cli/ask/__init__.py`
- Create: `src/aeolus_cli/ask/tools.py`
- Create: `tests/test_ask_tools.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_ask_tools.py
"""Tests for ask tool schemas."""


def test_tool_schemas_are_valid():
    """All tool schemas have required fields."""
    from aeolus_cli.ask.tools import TOOL_SCHEMAS

    for tool in TOOL_SCHEMAS:
        assert "name" in tool, f"Tool missing 'name': {tool}"
        assert "description" in tool
        assert "input_schema" in tool
        props = tool["input_schema"].get("properties", {})
        # Every tool should have confidence and explanation
        assert "confidence" in props, f"Tool {tool['name']} missing confidence"
        assert "explanation" in props, f"Tool {tool['name']} missing explanation"


def test_tool_names_match_commands():
    """Tool names correspond to CLI commands."""
    from aeolus_cli.ask.tools import TOOL_SCHEMAS

    names = {t["name"] for t in TOOL_SCHEMAS}
    expected = {"sources", "find_sites", "download", "get_current", "summarise", "plot"}
    assert names == expected


def test_download_tool_has_required_params():
    """Download tool has source, and at least dates or last."""
    from aeolus_cli.ask.tools import TOOL_SCHEMAS

    download = next(t for t in TOOL_SCHEMAS if t["name"] == "download")
    props = download["input_schema"]["properties"]
    assert "source" in props
    assert "sites" in props
    assert "start_date" in props
    assert "last" in props
    assert download["input_schema"]["required"] == ["source", "confidence", "explanation"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ask_tools.py -v
```

- [ ] **Step 3: Implement tool schemas**

```python
# src/aeolus_cli/ask/__init__.py
```

```python
# src/aeolus_cli/ask/tools.py
"""Tool schemas for the LLM to use when interpreting natural language queries.

Each schema mirrors a CLI command. The LLM returns a structured tool call
which is then rendered as a CLI command string and executed via the library.
"""

_CONFIDENCE_FIELD = {
    "type": "string",
    "enum": ["low", "medium", "high"],
    "description": "Your confidence that this is what the user wants.",
}

_EXPLANATION_FIELD = {
    "type": "string",
    "description": "One-line plain English explanation of what this command does.",
}

TOOL_SCHEMAS = [
    {
        "name": "sources",
        "description": (
            "List available air quality data sources/networks. "
            "Use when the user wants to know what data sources exist."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "all": {
                    "type": "boolean",
                    "description": "Include SOS alternative backends (default false).",
                },
                "confidence": _CONFIDENCE_FIELD,
                "explanation": _EXPLANATION_FIELD,
            },
            "required": ["confidence", "explanation"],
        },
    },
    {
        "name": "find_sites",
        "description": (
            "Find air quality monitoring sites. Can search by source network, "
            "location (lat/lon + radius), or bounding box."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source name, e.g. AURN, SAQN, EEA.",
                },
                "near_lat": {
                    "type": "number",
                    "description": "Latitude for circular search.",
                },
                "near_lon": {
                    "type": "number",
                    "description": "Longitude for circular search.",
                },
                "radius_km": {
                    "type": "number",
                    "description": "Search radius in km (default 50).",
                },
                "bbox": {
                    "type": "string",
                    "description": "Bounding box: min_lon,min_lat,max_lon,max_lat.",
                },
                "confidence": _CONFIDENCE_FIELD,
                "explanation": _EXPLANATION_FIELD,
            },
            "required": ["confidence", "explanation"],
        },
    },
    {
        "name": "download",
        "description": (
            "Download air quality data from a monitoring network to CSV. "
            "Requires a source and either start+end dates or a 'last' shorthand like '30d' or '1y'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source name, e.g. AURN, SAQN, EEA.",
                },
                "sites": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Site codes to download. Omit for all sites in the source.",
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format.",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format.",
                },
                "last": {
                    "type": "string",
                    "description": "Date range shorthand, e.g. 30d, 6m, 1y. Alternative to start/end dates.",
                },
                "measurands": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter to these pollutants, e.g. ['NO2', 'PM2.5'].",
                },
                "output": {
                    "type": "string",
                    "description": "Output CSV filename.",
                },
                "confidence": _CONFIDENCE_FIELD,
                "explanation": _EXPLANATION_FIELD,
            },
            "required": ["source", "confidence", "explanation"],
        },
    },
    {
        "name": "get_current",
        "description": (
            "Get the most recent (live) readings from monitoring sites. "
            "Works with UK regulatory networks (AURN, SAQN, WAQN, NI, AQE)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source name, e.g. AURN.",
                },
                "sites": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Site codes.",
                },
                "near_lat": {
                    "type": "number",
                    "description": "Latitude to find nearby sites.",
                },
                "near_lon": {
                    "type": "number",
                    "description": "Longitude to find nearby sites.",
                },
                "confidence": _CONFIDENCE_FIELD,
                "explanation": _EXPLANATION_FIELD,
            },
            "required": ["source", "confidence", "explanation"],
        },
    },
    {
        "name": "summarise",
        "description": (
            "Summarise a previously downloaded CSV file — shows sites, pollutants, "
            "date ranges, and data completeness."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Path to the CSV file to summarise.",
                },
                "confidence": _CONFIDENCE_FIELD,
                "explanation": _EXPLANATION_FIELD,
            },
            "required": ["file", "confidence", "explanation"],
        },
    },
    {
        "name": "plot",
        "description": (
            "Create a time series chart from a previously downloaded CSV file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Path to the CSV file to plot.",
                },
                "output": {
                    "type": "string",
                    "description": "Output PNG filename.",
                },
                "confidence": _CONFIDENCE_FIELD,
                "explanation": _EXPLANATION_FIELD,
            },
            "required": ["file", "confidence", "explanation"],
        },
    },
]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ask_tools.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/aeolus_cli/ask/ tests/test_ask_tools.py
git commit -m "feat: add tool schemas for ask LLM integration"
```

---

## Task 11: `ask` Render Module (Tool Call → CLI Command String)

**Files:**
- Create: `src/aeolus_cli/ask/render.py`
- Create: `tests/test_ask_render.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_ask_render.py
"""Tests for rendering tool calls as CLI command strings."""


def test_render_download_basic():
    """Download tool call renders as aeolus download command."""
    from aeolus_cli.ask.render import render_tool_call

    tool_call = {
        "name": "download",
        "input": {
            "source": "AURN",
            "sites": ["MY1", "KC1"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "confidence": "high",
            "explanation": "Downloads NO2 data from two London AURN sites for 2024.",
        },
    }
    cmd = render_tool_call(tool_call)
    assert cmd == "aeolus download AURN --sites MY1 KC1 --start 2024-01-01 --end 2024-12-31"


def test_render_download_with_last():
    """Download with last= renders --last flag."""
    from aeolus_cli.ask.render import render_tool_call

    tool_call = {
        "name": "download",
        "input": {
            "source": "SAQN",
            "last": "1y",
            "measurands": ["PM2.5", "NO2"],
            "output": "scotland.csv",
            "confidence": "high",
            "explanation": "Downloads PM2.5 and NO2 from all SAQN sites for the last year.",
        },
    }
    cmd = render_tool_call(tool_call)
    assert cmd == "aeolus download SAQN --last 1y --measurands PM2.5 NO2 -o scotland.csv"


def test_render_find_sites_near():
    """find_sites with near renders --near flag."""
    from aeolus_cli.ask.render import render_tool_call

    tool_call = {
        "name": "find_sites",
        "input": {
            "source": "AURN",
            "near_lat": 51.5,
            "near_lon": -0.13,
            "radius_km": 10.0,
            "confidence": "high",
            "explanation": "Finds AURN sites near central London.",
        },
    }
    cmd = render_tool_call(tool_call)
    assert cmd == "aeolus find-sites AURN --near 51.5,-0.13 --radius 10.0"


def test_render_sources():
    """Sources renders as simple command."""
    from aeolus_cli.ask.render import render_tool_call

    tool_call = {
        "name": "sources",
        "input": {"confidence": "high", "explanation": "Lists available networks."},
    }
    cmd = render_tool_call(tool_call)
    assert cmd == "aeolus sources"


def test_render_sources_all():
    """Sources --all renders the flag."""
    from aeolus_cli.ask.render import render_tool_call

    tool_call = {
        "name": "sources",
        "input": {"all": True, "confidence": "high", "explanation": "Lists all sources."},
    }
    cmd = render_tool_call(tool_call)
    assert cmd == "aeolus sources --all"


def test_render_get_current():
    """get_current renders correctly."""
    from aeolus_cli.ask.render import render_tool_call

    tool_call = {
        "name": "get_current",
        "input": {
            "source": "AURN",
            "sites": ["MY1"],
            "confidence": "high",
            "explanation": "Gets latest readings from Marylebone Road.",
        },
    }
    cmd = render_tool_call(tool_call)
    assert cmd == "aeolus get-current AURN --sites MY1"


def test_render_strips_metadata_fields():
    """confidence and explanation are not rendered in the command."""
    from aeolus_cli.ask.render import render_tool_call

    tool_call = {
        "name": "sources",
        "input": {"confidence": "high", "explanation": "test"},
    }
    cmd = render_tool_call(tool_call)
    assert "confidence" not in cmd
    assert "explanation" not in cmd
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ask_render.py -v
```

- [ ] **Step 3: Implement render.py**

```python
# src/aeolus_cli/ask/render.py
"""Render structured tool calls as CLI command strings."""

# Fields that are metadata for us, not CLI arguments
_META_FIELDS = {"confidence", "explanation"}


def render_tool_call(tool_call: dict) -> str:
    """Convert a structured tool call into an aeolus CLI command string.

    Args:
        tool_call: Dict with 'name' and 'input' keys from the LLM response.

    Returns:
        CLI command string like 'aeolus download AURN --sites MY1 KC1 --last 30d'.
    """
    name = tool_call["name"]
    params = {k: v for k, v in tool_call["input"].items() if k not in _META_FIELDS}

    # Map tool names to CLI command names (underscores → hyphens)
    cmd_name = name.replace("_", "-")

    if name == "sources":
        return _render_sources(params)
    elif name == "find_sites":
        return _render_find_sites(params)
    elif name == "download":
        return _render_download(params)
    elif name == "get_current":
        return _render_get_current(params)
    elif name == "summarise":
        return _render_summarise(params)
    elif name == "plot":
        return _render_plot(params)
    else:
        # Fallback: best-effort rendering
        parts = ["aeolus", cmd_name]
        for k, v in params.items():
            parts.append(f"--{k}")
            parts.append(str(v))
        return " ".join(parts)


def _render_sources(p: dict) -> str:
    parts = ["aeolus", "sources"]
    if p.get("all"):
        parts.append("--all")
    return " ".join(parts)


def _render_find_sites(p: dict) -> str:
    parts = ["aeolus", "find-sites"]
    if "source" in p:
        parts.append(p["source"])
    if "near_lat" in p and "near_lon" in p:
        parts.extend(["--near", f"{p['near_lat']},{p['near_lon']}"])
        if "radius_km" in p:
            parts.extend(["--radius", str(p["radius_km"])])
    if "bbox" in p:
        parts.extend(["--bbox", p["bbox"]])
    return " ".join(parts)


def _render_download(p: dict) -> str:
    parts = ["aeolus", "download", p["source"]]
    if "sites" in p:
        parts.extend(["--sites"] + p["sites"])
    if "start_date" in p:
        parts.extend(["--start", p["start_date"]])
    if "end_date" in p:
        parts.extend(["--end", p["end_date"]])
    if "last" in p:
        parts.extend(["--last", p["last"]])
    if "measurands" in p:
        parts.extend(["--measurands"] + p["measurands"])
    if "output" in p:
        parts.extend(["-o", p["output"]])
    return " ".join(parts)


def _render_get_current(p: dict) -> str:
    parts = ["aeolus", "get-current", p["source"]]
    if "sites" in p:
        parts.extend(["--sites"] + p["sites"])
    if "near_lat" in p and "near_lon" in p:
        parts.extend(["--near", f"{p['near_lat']},{p['near_lon']}"])
    return " ".join(parts)


def _render_summarise(p: dict) -> str:
    return f"aeolus summarise {p['file']}"


def _render_plot(p: dict) -> str:
    parts = ["aeolus", "plot", p["file"]]
    if "output" in p:
        parts.extend(["-o", p["output"]])
    return " ".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ask_render.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/aeolus_cli/ask/render.py tests/test_ask_render.py
git commit -m "feat: add tool call to CLI command renderer"
```

---

## Task 12: `ask` System Prompt Builder

**Files:**
- Create: `src/aeolus_cli/ask/prompt.py`
- Create: `tests/test_ask_prompt.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_ask_prompt.py
"""Tests for the ask system prompt builder."""
from unittest.mock import patch


def test_build_system_prompt_includes_sources():
    """System prompt lists available sources from the registry."""
    from aeolus_cli.ask.prompt import build_system_prompt

    with patch("aeolus.list_sources", return_value=["AURN", "SAQN"]), \
         patch("aeolus.get_source_info", side_effect=[
             {"name": "AURN", "type": "network", "requires_api_key": False},
             {"name": "SAQN", "type": "network", "requires_api_key": False},
         ]):
        prompt = build_system_prompt()
    assert "AURN" in prompt
    assert "SAQN" in prompt


def test_build_system_prompt_includes_behavioural_instructions():
    """System prompt contains key behavioural instructions."""
    from aeolus_cli.ask.prompt import build_system_prompt

    with patch("aeolus.list_sources", return_value=[]), \
         patch("aeolus.get_source_info"):
        prompt = build_system_prompt()
    assert "confidence" in prompt.lower()
    assert "explanation" in prompt.lower()


def test_build_system_prompt_includes_measurand_knowledge():
    """System prompt contains static knowledge about pollutant names."""
    from aeolus_cli.ask.prompt import build_system_prompt

    with patch("aeolus.list_sources", return_value=[]), \
         patch("aeolus.get_source_info"):
        prompt = build_system_prompt()
    assert "PM2.5" in prompt
    assert "NO2" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ask_prompt.py -v
```

- [ ] **Step 3: Implement prompt builder**

```python
# src/aeolus_cli/ask/prompt.py
"""Build the system prompt for the ask LLM, including live source knowledge."""
import aeolus


_STATIC_KNOWLEDGE = """\
## Pollutant Names and Aliases

Use these exact measurand names in queries:
- PM2.5 (fine particulate matter, also "fine particles", "PM2.5")
- PM10 (coarse particulate matter)
- NO2 (nitrogen dioxide)
- O3 (ozone)
- SO2 (sulphur dioxide)
- CO (carbon monoxide)
- NOX (nitrogen oxides, also "NOx")

## Geographic Coverage

- AURN: UK national network (~170 sites)
- SAQN: Scotland only
- WAQN: Wales only
- NI: Northern Ireland only
- AQE: Air Quality England (English local authority sites)
- LOCAL: Local authority networks (England)
- LMAM: London air quality mesh
- BREATHE_LONDON: London low-cost sensor network (needs BL_API_KEY)
- AIRQO: African cities (needs AIRQO_API_KEY)
- AIRNOW: USA, Canada, Mexico (needs AIRNOW_API_KEY)
- SENSOR_COMMUNITY: Global citizen science network
- EEA: Europe, 40+ countries
- SONITUS: Dublin, Ireland
- OPENAQ: Global portal (needs OPENAQ_API_KEY)
- PURPLEAIR: Global low-cost sensors (needs PURPLEAIR_API_KEY)

## Date Handling

- Use --last for relative dates: 30d, 6m, 1y, 2w
- Use --start/--end for absolute date ranges: YYYY-MM-DD format
- AURN reliable hourly data from mid-1990s onwards

## Common Gotchas

- Site codes are source-specific: MY1 is AURN, not SAQN
- download() requires explicit site codes; use find_sites first if needed
- get_current only works for UK regulatory networks (AURN, SAQN, WAQN, NI, AQE)
- Some sources need API keys — if a source needs one, mention it in your explanation
"""

_BEHAVIOURAL_INSTRUCTIONS = """\
## Your Role

You are a query builder for the aeolus air quality CLI tool. Your job is to
translate natural language requests into structured tool calls that map to CLI
commands.

## Rules

1. Always provide a confidence level (low/medium/high) and a brief explanation.
2. The explanation should be one sentence, plain English, helping the user
   understand what the command does and why you chose those parameters.
3. Prefer action over refusal. If the query is ambiguous, make a reasonable
   best guess and explain your interpretation.
4. If the query is truly unanswerable (data doesn't exist, impossible date
   range, etc.), respond with a text message explaining why — do not force
   a tool call.
5. If the user mentions a place name, use your knowledge of geography to
   determine the right source and approximate coordinates.
6. When the user doesn't specify sites, either omit the sites parameter
   (for all sites) or use find_sites to discover relevant ones.
7. Suggest a descriptive output filename when appropriate.
"""


def build_system_prompt() -> str:
    """Build the full system prompt with live source data and static knowledge.

    Returns:
        The system prompt string.
    """
    # Dynamic: current source registry
    source_lines = []
    for name in aeolus.list_sources():
        try:
            info = aeolus.get_source_info(name)
            key_note = " (requires API key)" if info["requires_api_key"] else ""
            source_lines.append(f"- {name}: {info['type']}{key_note}")
        except Exception:
            source_lines.append(f"- {name}")

    sources_section = "## Available Sources (live from registry)\n\n" + "\n".join(source_lines)

    return "\n\n".join([
        _BEHAVIOURAL_INSTRUCTIONS.strip(),
        sources_section,
        _STATIC_KNOWLEDGE.strip(),
    ])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ask_prompt.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/aeolus_cli/ask/prompt.py tests/test_ask_prompt.py
git commit -m "feat: add system prompt builder for ask command"
```

---

## Task 13: `ask` LLM Abstraction

**Files:**
- Create: `src/aeolus_cli/ask/llm.py`
- Create: `tests/test_ask_llm.py` (unit tests with mocked API)

- [ ] **Step 1: Write tests**

```python
# tests/test_ask_llm.py
"""Tests for the LLM abstraction layer."""
from unittest.mock import MagicMock, patch


def _mock_tool_use_response():
    """Create a mock Anthropic response with a tool use block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "download"
    tool_block.input = {
        "source": "AURN",
        "sites": ["MY1"],
        "last": "30d",
        "confidence": "high",
        "explanation": "Downloads AURN data from Marylebone Road for the last 30 days.",
    }

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = ""

    response = MagicMock()
    response.content = [text_block, tool_block]
    response.stop_reason = "tool_use"
    return response


def _mock_text_response():
    """Create a mock Anthropic response with just text (refusal)."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "I can't build a query for that because AURN doesn't cover Mars."

    response = MagicMock()
    response.content = [text_block]
    response.stop_reason = "end_turn"
    return response


def test_parse_response_extracts_tool_call():
    """parse_response returns a ToolCall for tool_use responses."""
    from aeolus_cli.ask.llm import parse_response

    result = parse_response(_mock_tool_use_response())
    assert result["type"] == "tool_call"
    assert result["tool_call"]["name"] == "download"
    assert result["tool_call"]["input"]["source"] == "AURN"
    assert result["confidence"] == "high"
    assert "explanation" in result


def test_parse_response_extracts_text_refusal():
    """parse_response returns a TextResponse for text-only responses."""
    from aeolus_cli.ask.llm import parse_response

    result = parse_response(_mock_text_response())
    assert result["type"] == "text"
    assert "Mars" in result["text"]


def test_call_llm_passes_correct_params():
    """call_llm passes system prompt, user message, and tools to Anthropic."""
    from aeolus_cli.ask.llm import call_llm

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response()

    with patch("aeolus_cli.ask.llm._get_client", return_value=mock_client):
        call_llm("get me AURN data", "system prompt here", [{"name": "download"}])

    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
    assert call_kwargs["system"] == "system prompt here"
    assert call_kwargs["tools"] == [{"name": "download"}]
    assert call_kwargs["messages"][0]["content"] == "get me AURN data"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ask_llm.py -v
```

- [ ] **Step 3: Implement LLM abstraction**

```python
# src/aeolus_cli/ask/llm.py
"""LLM abstraction layer. Anthropic SDK for now, structured for swapability."""
from typing import Any

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1024


def _get_client():
    """Get an Anthropic client. Raises ImportError with helpful message."""
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "aeolus ask requires the Anthropic SDK.\n"
            "Install it with: pip install aeolus-cli[ask]"
        )
    return anthropic.Anthropic()


def call_llm(
    user_text: str,
    system_prompt: str,
    tools: list[dict],
) -> Any:
    """Send a query to the LLM and return the raw response.

    Args:
        user_text: The user's natural language query.
        system_prompt: The system prompt with source knowledge.
        tools: List of tool schemas.

    Returns:
        The raw Anthropic API response.
    """
    client = _get_client()
    return client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=system_prompt,
        tools=tools,
        messages=[{"role": "user", "content": user_text}],
    )


def call_llm_explain(
    user_text: str,
    tool_call: dict,
    system_prompt: str,
) -> str:
    """Ask the LLM for a deeper explanation of a tool call.

    Args:
        user_text: The original user query.
        tool_call: The structured tool call that was generated.
        system_prompt: The system prompt.

    Returns:
        A multi-sentence explanation string.
    """
    client = _get_client()
    explain_prompt = (
        f"The user asked: \"{user_text}\"\n\n"
        f"You generated this command: {tool_call}\n\n"
        "Explain in 2-4 sentences what this command does, what the parameters mean, "
        "and how the user could modify it for different queries. "
        "Be helpful and educational."
    )
    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": explain_prompt}],
    )
    return response.content[0].text


def parse_response(response: Any) -> dict:
    """Parse an LLM response into a structured result.

    Returns:
        Dict with either:
        - {"type": "tool_call", "tool_call": {...}, "confidence": str, "explanation": str}
        - {"type": "text", "text": str}
    """
    # Look for tool_use blocks
    for block in response.content:
        if block.type == "tool_use":
            return {
                "type": "tool_call",
                "tool_call": {
                    "name": block.name,
                    "input": block.input,
                },
                "confidence": block.input.get("confidence", "medium"),
                "explanation": block.input.get("explanation", ""),
            }

    # Text-only response (refusal or clarification)
    text_parts = [b.text for b in response.content if b.type == "text" and b.text]
    return {
        "type": "text",
        "text": "\n".join(text_parts) if text_parts else "No response from the model.",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ask_llm.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/aeolus_cli/ask/llm.py tests/test_ask_llm.py
git commit -m "feat: add LLM abstraction layer for ask command"
```

---

## Task 14: `ask` Orchestrator and CLI Command

**Files:**
- Create: `src/aeolus_cli/ask/orchestrator.py`
- Create: `tests/test_ask_orchestrator.py`
- Modify: `src/aeolus_cli/main.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_ask_orchestrator.py
"""Tests for the ask orchestrator."""
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

runner = CliRunner()


def _mock_tool_result():
    return {
        "type": "tool_call",
        "tool_call": {
            "name": "download",
            "input": {
                "source": "AURN",
                "sites": ["MY1"],
                "last": "30d",
                "confidence": "high",
                "explanation": "Downloads AURN data from Marylebone Road for the last 30 days.",
            },
        },
        "confidence": "high",
        "explanation": "Downloads AURN data from Marylebone Road for the last 30 days.",
    }


def _mock_text_result():
    return {
        "type": "text",
        "text": "I can't build a query for that.",
    }


def test_ask_shows_command_and_explanation():
    """ask displays the rendered command and explanation."""
    from aeolus_cli.main import app

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_tool_result()), \
         patch("aeolus_cli.ask.orchestrator._confirm_and_execute"):
        result = runner.invoke(app, ["ask", "AURN data from MY1 last 30 days"])
    assert result.exit_code == 0


def test_ask_text_response_prints_message():
    """When LLM returns text instead of a tool call, display it."""
    from aeolus_cli.main import app

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_text_result()):
        result = runner.invoke(app, ["ask", "air quality on Mars"])
    assert result.exit_code == 0
    assert "can't build" in result.output


def test_ask_yes_flag_skips_confirmation(tmp_path, monkeypatch):
    """--yes skips the confirmation prompt."""
    from aeolus_cli.main import app
    import pandas as pd

    monkeypatch.chdir(tmp_path)
    mock_data = pd.DataFrame({
        "site_code": ["MY1"], "date_time": ["2024-01-01"], "measurand": ["NO2"],
        "value": [40.0], "units": ["ug/m3"], "source_network": ["AURN"],
        "ratification": ["P"], "created_at": ["2024-01-02"],
    })

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_tool_result()), \
         patch("aeolus.download", return_value=mock_data):
        result = runner.invoke(app, ["ask", "--yes", "AURN data from MY1 last 30 days"])
    assert result.exit_code == 0


def test_ask_no_args_prompts(monkeypatch):
    """aeolus ask with no args prompts for input."""
    from aeolus_cli.main import app

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_text_result()):
        result = runner.invoke(app, ["ask"], input="air quality on Mars\n")
    assert result.exit_code == 0


def test_ask_joins_unquoted_args():
    """aeolus ask PM2.5 from SAQN 2024 joins args into a single query."""
    from aeolus_cli.main import app

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_text_result()) as mock:
        result = runner.invoke(app, ["ask", "PM2.5", "from", "SAQN", "2024"])
    # The query should have been joined
    mock.assert_called_once()
    query = mock.call_args[0][0]
    assert query == "PM2.5 from SAQN 2024"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ask_orchestrator.py -v
```

- [ ] **Step 3: Implement orchestrator**

```python
# src/aeolus_cli/ask/orchestrator.py
"""Top-level orchestration for aeolus ask."""
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.prompt import Prompt

from aeolus_cli.ask.llm import call_llm, call_llm_explain, parse_response
from aeolus_cli.ask.prompt import build_system_prompt
from aeolus_cli.ask.render import render_tool_call
from aeolus_cli.ask.tools import TOOL_SCHEMAS
from aeolus_cli.config import get_key
from aeolus_cli.output import console, print_error

app = typer.Typer()


def _run_ask(query: str) -> dict:
    """Send the query to the LLM and parse the response."""
    system_prompt = build_system_prompt()
    raw_response = call_llm(query, system_prompt, TOOL_SCHEMAS)
    return parse_response(raw_response)


def _execute_tool_call(tool_call: dict) -> None:
    """Execute a tool call by invoking the corresponding aeolus function."""
    name = tool_call["name"]
    params = {k: v for k, v in tool_call["input"].items()
              if k not in ("confidence", "explanation")}

    if name == "download":
        import aeolus
        from aeolus_cli.output import make_default_filename, write_csv

        data = aeolus.download(
            sources=params["source"],
            sites=params.get("sites"),
            start_date=params.get("start_date"),
            end_date=params.get("end_date"),
            last=params.get("last"),
        )
        if params.get("measurands") and not data.empty:
            data = data[data["measurand"].isin(params["measurands"])]
        output = Path(params.get("output", make_default_filename(params["source"])))
        write_csv(data, output)

    elif name == "find_sites":
        import aeolus
        from aeolus_cli.output import print_table

        near = None
        if "near_lat" in params and "near_lon" in params:
            near = (params["near_lat"], params["near_lon"])
        df = aeolus.find_sites(
            source=params.get("source"),
            near=near,
            radius_km=params.get("radius_km", 50.0),
            bbox=params.get("bbox"),
        )
        print_table(df)

    elif name == "get_current":
        import aeolus
        from aeolus_cli.output import print_table

        if "near_lat" in params and "near_lon" in params:
            found = aeolus.find_sites(
                source=params["source"],
                near=(params["near_lat"], params["near_lon"]),
            )
            site_codes = found["site_code"].tolist()
        else:
            site_codes = params.get("sites", [])
        data = aeolus.get_current(params["source"], sites=site_codes)
        print_table(data[["site_code", "date_time", "measurand", "value", "units"]])

    elif name == "sources":
        import aeolus
        import pandas as pd
        from aeolus_cli.output import print_table

        source_names = aeolus.list_sources(include_all=params.get("all", False))
        rows = []
        for sn in source_names:
            info = aeolus.get_source_info(sn)
            rows.append({
                "Source": info["name"],
                "Type": info.get("type", "network"),
                "API Key": "Yes" if info["requires_api_key"] else "No",
            })
        print_table(pd.DataFrame(rows), title="Available Sources")

    elif name == "summarise":
        import aeolus
        import pandas as pd
        from aeolus_cli.output import print_table

        data = pd.read_csv(params["file"])
        summary = aeolus.summarise(data)
        print_table(summary, title=f"Summary of {params['file']}")

    elif name == "plot":
        import pandas as pd
        from aeolus import viz
        from aeolus_cli.output import console as _console

        data = pd.read_csv(params["file"])
        fig = viz.plot_timeseries(data)
        output = params.get("output", f"{Path(params['file']).stem}_plot.png")
        fig.savefig(output, dpi=150, bbox_inches="tight")
        _console.print(f"Saved plot to {output}")


def _confirm_and_execute(result: dict, query: str, yes: bool) -> None:
    """Show the command, get confirmation, and execute."""
    tool_call = result["tool_call"]
    cmd_str = render_tool_call(tool_call)
    explanation = result.get("explanation", "")

    console.print(f"\n  [bold]{cmd_str}[/bold]")
    if explanation:
        console.print(f"  [dim]{explanation}[/dim]\n")

    if yes:
        _execute_tool_call(tool_call)
        return

    choice = Prompt.ask(
        "Run?",
        choices=["y", "n", "e"],
        default="y",
    )

    if choice == "n":
        return
    elif choice == "e":
        # Deeper explanation
        try:
            deep = call_llm_explain(query, cmd_str, build_system_prompt())
            console.print(f"\n{deep}\n")
        except Exception as e:
            console.print(f"[dim]Could not get explanation: {e}[/dim]\n")
        # Re-prompt after explanation
        if Prompt.ask("Run?", choices=["y", "n"], default="y") == "n":
            return
    # Execute
    _execute_tool_call(tool_call)


@app.callback(invoke_without_command=True)
def ask(
    query: Optional[list[str]] = typer.Argument(None, help="Natural language query"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Translate a natural language query into an aeolus command."""
    # Check for API key
    key = get_key("ANTHROPIC_API_KEY")
    if not key:
        print_error(ValueError(
            "aeolus ask requires an Anthropic API key.\n"
            "Set ANTHROPIC_API_KEY in your environment or in ~/.aeolus/config.toml"
        ))
        raise typer.Exit(code=1)

    # Build query string
    if query:
        query_str = " ".join(query)
    else:
        query_str = Prompt.ask("What data are you looking for?")
        if not query_str.strip():
            raise typer.Exit(code=0)

    try:
        result = _run_ask(query_str)

        if result["type"] == "text":
            console.print(result["text"])
            raise typer.Exit(code=0)

        _confirm_and_execute(result, query_str, yes)

    except typer.Exit:
        raise
    except ImportError as e:
        print_error(e)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(e)
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Register in main.py**

Add to `main.py`:
```python
from aeolus_cli.ask.orchestrator import app as ask_app
app.add_typer(ask_app, name="ask", help="Translate natural language to aeolus commands")
```

Final `main.py` should look like:
```python
# src/aeolus_cli/main.py
import typer

app = typer.Typer(
    name="aeolus",
    help="Download and explore air quality data.",
    no_args_is_help=True,
)

# Layer 1 commands
from aeolus_cli.commands.sources import app as sources_app
from aeolus_cli.commands.find_sites import app as find_sites_app
from aeolus_cli.commands.download import app as download_app
from aeolus_cli.commands.get_current import app as get_current_app
from aeolus_cli.commands.summarise import app as summarise_app
from aeolus_cli.commands.plot import app as plot_app

app.add_typer(sources_app, name="sources", help="List available data sources")
app.add_typer(find_sites_app, name="find-sites", help="Find monitoring sites")
app.add_typer(download_app, name="download", help="Download air quality data to CSV")
app.add_typer(get_current_app, name="get-current", help="Get latest readings")
app.add_typer(summarise_app, name="summarise", help="Summarise a downloaded data file")
app.add_typer(plot_app, name="plot", help="Plot a time series chart")

# Layer 2
from aeolus_cli.ask.orchestrator import app as ask_app
app.add_typer(ask_app, name="ask", help="Translate natural language to aeolus commands")


if __name__ == "__main__":
    app()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_ask_orchestrator.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/aeolus_cli/ask/orchestrator.py tests/test_ask_orchestrator.py src/aeolus_cli/main.py
git commit -m "feat: add ask orchestrator and wire up all commands"
```

---

## Task 15: Full Test Suite Pass and Smoke Test

**Files:** None new — verification only.

- [ ] **Step 1: Run all tests**

```bash
pytest -v
```

Expected: All tests pass (approximately 30+ tests).

- [ ] **Step 2: Manual smoke test — Layer 1**

```bash
aeolus --help
aeolus sources
aeolus find-sites AURN --near 51.5,-0.13 --radius 5
aeolus download AURN --sites MY1 --last 7d
aeolus summarise AURN_*.csv
aeolus plot AURN_*.csv
```

Verify each command produces sensible output.

- [ ] **Step 3: Manual smoke test — Layer 2**

Requires `ANTHROPIC_API_KEY` to be set.

```bash
aeolus ask "What sources are available?"
aeolus ask "NO2 from Marylebone Road, last week"
aeolus ask PM2.5 from SAQN sites near Edinburgh last year
aeolus ask "current air quality near Big Ben"
aeolus ask "air quality data from Mars"
```

Verify: each produces a sensible command (or graceful refusal for Mars), the confirmation flow works (Y/n/e), and `--yes` executes immediately.

- [ ] **Step 4: Commit any fixes from smoke testing**

```bash
git add -A
git commit -m "fix: address issues found in smoke testing"
```

(Only if fixes were needed.)

- [ ] **Step 5: Final commit — tag v0.1.0**

```bash
git tag v0.1.0
```
