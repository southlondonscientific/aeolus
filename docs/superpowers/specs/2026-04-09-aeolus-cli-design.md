# aeolus-cli Design Spec

*2026-04-09*

## Overview

A command-line tool for downloading and exploring air quality data, wrapping the `aeolus_aq` Python library. Aimed at researchers who aren't confident with Python — people who use R, spreadsheets, or clunky web interfaces. The CLI is the primary product; an LLM-powered `ask` command translates natural language into CLI commands, teaching users the tool by showing them what it would run.

## Package Identity

- **PyPI name:** `aeolus-cli`
- **Command:** `aeolus`
- **Repo:** Separate from `aeolus_aq`. Lives at `sls/aeolus-cli/` alongside sibling SLS projects.
- **Licence:** GPL-3.0-or-later (matches `aeolus_aq`).

## Dependencies

| Layer | Packages |
|-------|----------|
| Layer 1 (CLI) | `aeolus_aq`, `typer`, `rich` |
| Layer 2 (ask) | `anthropic` — optional extra: `pip install aeolus-cli[ask]` |

## Project Layout

```
aeolus-cli/
├── pyproject.toml
├── src/aeolus_cli/
│   ├── __init__.py
│   ├── main.py              # typer app, entry point
│   ├── commands/
│   │   ├── sources.py        # aeolus sources
│   │   ├── find_sites.py     # aeolus find-sites
│   │   ├── download.py       # aeolus download
│   │   ├── get_current.py    # aeolus get-current
│   │   ├── summarise.py      # aeolus summarise
│   │   └── plot.py           # aeolus plot
│   ├── ask/
│   │   ├── __init__.py
│   │   ├── orchestrator.py   # send text → get tool call → display → execute
│   │   ├── tools.py          # tool schemas (provider-agnostic shape)
│   │   ├── llm.py            # LLM abstraction (Anthropic for now, swappable)
│   │   └── prompt.py         # system prompt with source knowledge
│   └── output.py             # shared formatting (tables, CSV writing, etc.)
├── tests/
└── README.md
```

## Commands

### Layer 1 — Plain CLI (no LLM)

Each command is a thin wrapper around an existing `aeolus_aq` library function.

**`aeolus sources`** — list available networks.
```
aeolus sources              # table: name, API key required, coverage
aeolus sources --all        # include SOS backends
```
Maps to: `aeolus.list_sources()`, `aeolus.get_source_info()`.

**`aeolus find-sites`** — search for monitoring sites.
```
aeolus find-sites AURN
aeolus find-sites AURN --near 51.5,-0.13 --radius 10
aeolus find-sites AURN --lat 51.5 --lon -0.13 --radius 10  # equivalent
aeolus find-sites --bbox -0.5,51.3,0.3,51.7
```
Maps to: `aeolus.find_sites()`.

**`aeolus download`** — fetch data to CSV.
```
aeolus download AURN --sites MY1 KC1 --start 2024-01-01 --end 2024-12-31
aeolus download AURN --sites MY1 --last 30d
aeolus download SAQN --measurands PM2.5 NO2 --last 1y -o scotland.csv
```
Maps to: `aeolus.download()`. Default output: `<source>_<date>.csv` in current directory. CSV only (no Parquet, no xlsx in v1).

**`aeolus get-current`** — live readings.
```
aeolus get-current AURN --sites MY1 KC1
aeolus get-current AURN --near 51.5,-0.13
aeolus get-current AURN --lat 51.5 --lon -0.13   # equivalent
```
Maps to: `aeolus.get_current()`.

**`aeolus summarise`** — quick overview of a downloaded file.
```
aeolus summarise data.csv
aeolus summarise data.csv --detailed
```
Maps to: `aeolus.summarise()`.

**`aeolus plot`** — time series chart from data.
```
aeolus plot data.csv
aeolus plot data.csv -o trend.png
```
Maps to: `aeolus.viz` plotting functions. Simple time series only in v1.

### Layer 2 — `aeolus ask` (LLM-assisted)

Translates natural language into CLI commands.

```
aeolus ask "PM2.5 from all SAQN sites, 2024"
aeolus ask PM2.5 from all SAQN sites 2024       # no quotes also works
aeolus ask "PM2.5 from all SAQN sites, 2024" --yes
aeolus ask                                        # interactive prompt
```

Flags:
- `--yes` / `-y` — skip confirmation, execute immediately.
- No other flags. `ask` captures all remaining arguments as the query. Words that look like flags (`--near`) in the natural language won't collide because `ask` has only `--yes`.

Bare `aeolus ask` with no arguments prompts: "What data are you looking for?"

## `ask` Architecture

### Flow

```
User input (natural language)
    │
    ▼
Build messages:
  - System prompt (source knowledge from registry, CLI command docs, tone)
  - User message
  - Tool schemas (one per CLI command, structured parameters)
    │
    ▼
LLM call (Anthropic Haiku, tool-use)
    │
    ▼
Response is one of:
  ├─ Tool call(s)
  │   Render as CLI command + one-line explanation
  │   Show:
  │     aeolus download SAQN --measurands PM2.5 NO2 --last 1y -o saqn_2024.csv
  │     SAQN is Scotland's air quality network. This fetches all sites.
  │     [Run? Y/n/e(xplain)]
  │   Y → execute
  │   n → exit
  │   e → second LLM call for deeper explanation, then re-prompt Y/n
  │
  ├─ Multiple tool calls → show as sequential commands
  │
  └─ Text response → LLM declined or needs to explain why it can't help
      Display and exit.
```

### Tool-use approach (Approach B)

The LLM receives Anthropic-format tool schemas mirroring the CLI commands. Each tool has typed parameters (`source: str`, `sites: list[str]`, etc.) plus:

- `confidence`: low / medium / high — the LLM's self-assessed confidence. Used in testing and logging; not shown to user by default.
- `explanation`: one-line plain English explanation of what the command does and why.

The structured tool call is translated into both:
1. A display string (the CLI command the user sees)
2. A library call (for execution)

This avoids string parsing and gives reliable structured output.

### System prompt

Built from:
- Live source registry: `aeolus.list_sources()`, `aeolus.get_source_info()` — names, coverage, API key requirements.
- Static knowledge section: measurand names and aliases, geographic hints (which networks cover which countries), common gotchas.
- Behavioural instructions: be concise, always provide an explanation, prefer action over refusal on ambiguous queries, decline gracefully on impossible queries.

### Model selection

Haiku for all queries. No model escalation in v1. Estimated cost: ~$0.001 per query.

### LLM abstraction

The LLM interaction is isolated in `ask/llm.py`:
- `build_messages(user_text, tools, system_prompt) → messages`
- `call_llm(messages) → raw_response`
- `parse_response(raw_response) → ToolCall | TextResponse`

Anthropic SDK for v1. Structured so swapping to another provider means changing one module.

### Behaviour on edge cases

- **LLM produces a bad command:** User sees it, presses `n`, exits. No auto-retry — rephrasing is more useful than retrying the same input.
- **Command executes but fails:** Normal CLI error handling. The library raises exceptions; the CLI catches them and prints a human-readable message.
- **Unanswerable query:** The LLM returns a text response explaining why, instead of a tool call.
- **Ambiguous query:** The LLM makes a reasonable best guess, shows the command, lets the user reject. Bias toward action.

## Configuration

### API keys

Resolution order (highest priority first):
1. Environment variable
2. `~/.aeolus/config.toml`

Config file format:
```toml
[keys]
ANTHROPIC_API_KEY = "sk-ant-..."
BL_API_KEY = "abc123"
```

Scales to future non-key config:
```toml
[keys]
ANTHROPIC_API_KEY = "sk-ant-..."

[defaults]
format = "csv"
model = "haiku"
```

### v1 key management

No `aeolus config` command in v1. Users set env vars or hand-edit the TOML file. Error message when key is missing mentions both options. `aeolus config set KEY value` is planned for v1.1.

## Error handling

- All exceptions from the aeolus library are caught and displayed as human-readable messages. No tracebacks.
- Non-zero exit codes on failure.
- Missing API key: clear message naming the key and how to set it.
- Network errors: simple retry advice, not stack traces.

## Testing

### Layer 1 tests
- CLI arg parsing via typer's `CliRunner`
- Output formatting (table rendering, CSV file writing)
- Error cases (bad source name, missing sites, no data returned)
- Mock `aeolus_aq` library calls — the library has its own test suite

### `ask` tests
- **Unit:** Mock LLM calls. Verify tool schemas are well-formed. Verify tool call → CLI command rendering. Verify confirmation flow (Y/n/e).
- **Prompt regression:** Set of natural language inputs with expected tool calls (source, sites, measurands, dates). Run against real Haiku API as integration tests. Use the `confidence` field to flag uncertain responses.
- **Edge cases:** Unanswerable queries return text. Ambiguous queries produce best-guess commands.

### Smoke / live tests
- Marked `live`, run before releases only.
- Request data from multiple sources in multiple ways via the full CLI.
- Analogous to aeolus's `conformance` test marker.

### Not tested here
- The aeolus library itself (has its own suite).
- Hypothesis — no useful property-based testing surface in a CLI wrapper.

## Non-goals for v1

- **Conversation.** `ask` is single-shot. No memory, no follow-ups.
- **Multi-provider LLM.** Anthropic only. Code is structured for swapability but no `--model` flag.
- **Web interface.** CLI only. Layer 3 from the concept doc is future work.
- **`aeolus config` command.** Hand-edit TOML or use env vars. Command comes in v1.1.
- **`aeolus info`.** Needs library-level metadata improvements first.
- **xlsx output.** CSV only.
- **Piping between `ask` invocations.** Each invocation is independent.
- **Query logging/replay.** Interesting idea, not v1.
