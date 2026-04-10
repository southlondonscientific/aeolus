# aeolus ask Chaining Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `aeolus ask` return and execute multi-step workflows in a single LLM call, with sequential execution, one-shot confirmation, and stop-on-failure behaviour.

**Architecture:** `parse_response` returns a list of tool calls instead of a single one. The orchestrator iterates over the list, rendering each as a CLI command for display, asking for one confirmation, then executing each via `_execute_tool_call` in order. No agent loop, no feedback between steps; dependencies flow via shared filenames. A `NoDataError` exception makes empty-download handling explicit so chains stop cleanly. A `MAX_CHAIN_LENGTH` of 5 is enforced as a safety cap.

**Tech Stack:** Python 3.11+, typer, rich, pytest, anthropic SDK

**Spec:** `docs/superpowers/specs/2026-04-10-aeolus-ask-chaining-design.md` in the aeolus repo. Read it first.

**Working directory:** All paths below are relative to `/Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli/`. Run the dev venv via `.venv/bin/pytest`, `.venv/bin/python`, etc. Do NOT use `source .venv/bin/activate`.

---

## File Structure

```
sls/aeolus-cli/
├── src/aeolus_cli/
│   ├── ask/
│   │   ├── errors.py           # NEW: NoDataError exception
│   │   ├── llm.py              # MODIFY: parse_response returns tool_calls list; add call_llm_explain_chain; remove call_llm_explain
│   │   ├── orchestrator.py     # MODIFY: _confirm_and_execute_chain, chain-aware execution loop, --step flag, NoDataError raising, MAX_CHAIN_LENGTH
│   │   └── prompt.py           # MODIFY: add chaining rules, find_sites→download prohibition, MAX_CHAIN_LENGTH note
└── tests/
    ├── test_ask_llm.py          # MODIFY: multi-tool-call tests, rename single-call test, remove explain test
    ├── test_ask_orchestrator.py # MODIFY: chain execution tests, --step tests, length cap test, NoDataError tests, update existing tests to new dict shape
    ├── test_ask_prompt.py       # MODIFY: assert chaining rule, find_sites prohibition, MAX_CHAIN_LENGTH text
    └── test_ask_render.py       # MODIFY: add render/execute consistency tests
```

**Implementation order rationale:** Start with the bottom of the stack (`errors.py`) so later tasks can import it. Then `llm.py` (the data structure change) because the orchestrator depends on it. Then `prompt.py` (pure strings, no code dependency). Then `orchestrator.py`, which is the largest change and depends on everything above. Finally the consistency tests in `test_ask_render.py` (independent of chaining and can land last).

---

## Task 1: NoDataError Exception

**Files:**
- Create: `src/aeolus_cli/ask/errors.py`
- Test: `tests/test_ask_errors.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ask_errors.py
"""Tests for ask exception types."""


def test_no_data_error_is_exception():
    """NoDataError is a subclass of Exception and carries a message."""
    from aeolus_cli.ask.errors import NoDataError

    err = NoDataError("No rows returned from AURN for 2026-04-09.")
    assert isinstance(err, Exception)
    assert str(err) == "No rows returned from AURN for 2026-04-09."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aeolus_cli.ask.errors'`

- [ ] **Step 3: Create errors.py**

```python
# src/aeolus_cli/ask/errors.py
"""Exception types for the ask subsystem."""


class NoDataError(Exception):
    """Raised when a download returns no rows.

    This is a clean, non-crash outcome — the caller should catch it, print
    a user-facing message, and exit successfully (exit code 0). In a chain,
    it also signals that subsequent steps should be skipped because their
    input file does not exist.
    """
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_errors.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli
git add src/aeolus_cli/ask/errors.py tests/test_ask_errors.py
git commit -m "feat: add NoDataError for clean empty-download handling in chains"
```

---

## Task 2: parse_response Returns List of Tool Calls

**Files:**
- Modify: `src/aeolus_cli/ask/llm.py`
- Modify: `tests/test_ask_llm.py`

This task changes the shape of `parse_response`. Downstream callers (the orchestrator and its tests) will temporarily break; we fix them in Task 6. To keep tests passing between tasks, update `test_ask_llm.py` to the new shape here, and leave the orchestrator for Task 6. Run only `test_ask_llm.py` at the end of this task; the orchestrator tests will be repaired later.

- [ ] **Step 1: Write the new llm tests**

Replace the contents of `tests/test_ask_llm.py` with:

```python
# tests/test_ask_llm.py
"""Tests for the LLM abstraction layer."""
from unittest.mock import MagicMock, patch


def _make_tool_block(name: str, input_dict: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = input_dict
    return block


def _make_text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _mock_single_tool_use_response() -> MagicMock:
    download_block = _make_tool_block("download", {
        "source": "AURN",
        "sites": ["MY1"],
        "last": "30d",
        "confidence": "high",
        "explanation": "Downloads AURN data for the last 30 days.",
    })
    text_block = _make_text_block("")
    response = MagicMock()
    response.content = [text_block, download_block]
    response.stop_reason = "tool_use"
    return response


def _mock_multi_tool_use_response() -> MagicMock:
    download_block = _make_tool_block("download", {
        "source": "AURN",
        "sites": ["MY1"],
        "last": "30d",
        "output": "my1_30d.csv",
        "confidence": "high",
        "explanation": "Download NO2 data.",
    })
    plot_block = _make_tool_block("plot", {
        "file": "my1_30d.csv",
        "output": "my1_30d.png",
        "confidence": "high",
        "explanation": "Plot the time series.",
    })
    response = MagicMock()
    response.content = [download_block, plot_block]
    response.stop_reason = "tool_use"
    return response


def _mock_text_response() -> MagicMock:
    text_block = _make_text_block("I can't build a query for that because AURN doesn't cover Mars.")
    response = MagicMock()
    response.content = [text_block]
    response.stop_reason = "end_turn"
    return response


def test_parse_response_single_tool_call_is_list_of_one():
    """A single tool_use block yields a tool_calls list of length 1."""
    from aeolus_cli.ask.llm import parse_response

    result = parse_response(_mock_single_tool_use_response())
    assert result["type"] == "tool_calls"
    assert isinstance(result["tool_calls"], list)
    assert len(result["tool_calls"]) == 1
    tc = result["tool_calls"][0]
    assert tc["name"] == "download"
    assert tc["input"]["source"] == "AURN"
    assert tc["input"]["confidence"] == "high"


def test_parse_response_extracts_multiple_tool_calls():
    """Multiple tool_use blocks are returned in order."""
    from aeolus_cli.ask.llm import parse_response

    result = parse_response(_mock_multi_tool_use_response())
    assert result["type"] == "tool_calls"
    assert len(result["tool_calls"]) == 2
    assert result["tool_calls"][0]["name"] == "download"
    assert result["tool_calls"][1]["name"] == "plot"
    assert result["tool_calls"][0]["input"]["output"] == "my1_30d.csv"
    assert result["tool_calls"][1]["input"]["file"] == "my1_30d.csv"


def test_parse_response_extracts_text_refusal():
    """Text-only responses are returned with type 'text'."""
    from aeolus_cli.ask.llm import parse_response

    result = parse_response(_mock_text_response())
    assert result["type"] == "text"
    assert "Mars" in result["text"]


def test_call_llm_passes_correct_params():
    """call_llm passes system prompt, user message, and tools to Anthropic."""
    from aeolus_cli.ask.llm import call_llm

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_single_tool_use_response()

    with patch("aeolus_cli.ask.llm._get_client", return_value=mock_client):
        call_llm("get me AURN data", "system prompt here", [{"name": "download"}])

    mock_client.messages.create.assert_called_once()
    kwargs = mock_client.messages.create.call_args[1]
    assert kwargs["model"] == "claude-haiku-4-5-20251001"
    assert kwargs["system"] == "system prompt here"
    assert kwargs["tools"] == [{"name": "download"}]
    assert kwargs["messages"][0]["content"] == "get me AURN data"


def test_call_llm_explain_chain_single_command():
    """Single-command explain uses the single-command prompt template."""
    from aeolus_cli.ask.llm import call_llm_explain_chain

    mock_response = MagicMock()
    mock_response.content = [_make_text_block("This command downloads AURN data.")]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("aeolus_cli.ask.llm._get_client", return_value=mock_client):
        result = call_llm_explain_chain(
            "get me AURN data",
            [{"name": "download", "input": {"source": "AURN"}}],
            "system prompt",
        )

    assert result == "This command downloads AURN data."
    kwargs = mock_client.messages.create.call_args[1]
    # The single-command variant is a 2-4 sentence explainer
    user_msg = kwargs["messages"][0]["content"]
    assert "2-4 sentences" in user_msg
    assert "aeolus download AURN" in user_msg


def test_call_llm_explain_chain_multi_step():
    """Multi-step explain uses the workflow prompt template with 3-5 sentences."""
    from aeolus_cli.ask.llm import call_llm_explain_chain

    mock_response = MagicMock()
    mock_response.content = [_make_text_block("This workflow downloads and then plots the data.")]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    tool_calls = [
        {"name": "download", "input": {"source": "AURN", "last": "30d", "output": "x.csv"}},
        {"name": "plot", "input": {"file": "x.csv", "output": "x.png"}},
    ]

    with patch("aeolus_cli.ask.llm._get_client", return_value=mock_client):
        result = call_llm_explain_chain("download and plot", tool_calls, "system prompt")

    assert "workflow" in result.lower() or "download" in result.lower()
    kwargs = mock_client.messages.create.call_args[1]
    user_msg = kwargs["messages"][0]["content"]
    assert "3-5 sentences" in user_msg
    # Both steps should appear in the prompt
    assert "1." in user_msg and "2." in user_msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_llm.py -v`
Expected: FAIL — several failures, notably around `result["type"] == "tool_calls"` (currently returns `"tool_call"`), and `call_llm_explain_chain` does not exist.

- [ ] **Step 3: Update llm.py**

Replace the contents of `src/aeolus_cli/ask/llm.py` with:

```python
"""LLM abstraction layer. Anthropic SDK for now, structured for swapability."""
from typing import Any

from aeolus_cli.ask.render import render_tool_call

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
    from aeolus_cli.config import get_key

    api_key = get_key("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=api_key)


def call_llm(user_text: str, system_prompt: str, tools: list[dict]) -> Any:
    """Send a query to the LLM and return the raw response."""
    client = _get_client()
    return client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=system_prompt,
        tools=tools,
        messages=[{"role": "user", "content": user_text}],
    )


def call_llm_explain_chain(
    user_text: str,
    tool_calls: list[dict],
    system_prompt: str,
) -> str:
    """Ask the LLM for a deeper explanation of a workflow (one or more steps).

    For a single command, produces a 2-4 sentence explanation of that command.
    For a chain, produces a 3-5 sentence explanation of the workflow, focusing
    on the narrative between steps rather than individual command syntax.
    """
    client = _get_client()
    cmds = "\n".join(
        f"  {i}. {render_tool_call(tc)}" for i, tc in enumerate(tool_calls, 1)
    )

    if len(tool_calls) > 1:
        explain_prompt = (
            f'The user asked: "{user_text}"\n\n'
            f"You generated this workflow:\n{cmds}\n\n"
            "Explain in 3-5 sentences what this workflow does overall, why the "
            "steps are in this order, and what the user will end up with. Focus "
            "on the narrative between steps, not individual command syntax."
        )
    else:
        explain_prompt = (
            f'The user asked: "{user_text}"\n\n'
            f"You generated this command:\n{cmds}\n\n"
            "Explain in 2-4 sentences what this command does, what the parameters "
            "mean, and how the user could modify it for different queries. "
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

    Returns one of:
      - {"type": "tool_calls", "tool_calls": [{"name": ..., "input": {...}}, ...]}
      - {"type": "text", "text": "..."}

    A single tool_use block still yields a tool_calls list of length 1.
    """
    tool_calls = []
    for block in response.content:
        if block.type == "tool_use":
            tool_calls.append({"name": block.name, "input": block.input})

    if tool_calls:
        return {"type": "tool_calls", "tool_calls": tool_calls}

    text_parts = [b.text for b in response.content if b.type == "text" and b.text]
    return {
        "type": "text",
        "text": "\n".join(text_parts) if text_parts else "No response from the model.",
    }
```

Note: we removed `call_llm_explain` (old name) and added `call_llm_explain_chain`. The orchestrator still references `call_llm_explain` from Task 0 state; this will cause an ImportError when the orchestrator is loaded. That's acceptable until Task 6 because:
1. `test_ask_llm.py` does not import the orchestrator.
2. `test_ask_orchestrator.py` is expected to be broken between Task 2 and Task 6 and is fixed in Task 6.

- [ ] **Step 4: Run the llm tests to verify they pass**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_llm.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli
git add src/aeolus_cli/ask/llm.py tests/test_ask_llm.py
git commit -m "feat(llm): parse_response returns tool_calls list; add call_llm_explain_chain"
```

---

## Task 3: Prompt Updates (Chaining Rules + find_sites Prohibition + Length Cap)

**Files:**
- Modify: `src/aeolus_cli/ask/prompt.py`
- Modify: `tests/test_ask_prompt.py`

- [ ] **Step 1: Add the new prompt tests**

Append these tests to `tests/test_ask_prompt.py`:

```python
def test_build_system_prompt_includes_chaining_rules():
    """Prompt explains how and when to chain multiple tool calls."""
    from unittest.mock import patch
    from aeolus_cli.ask.prompt import build_system_prompt

    with patch("aeolus.list_sources", return_value=[]), \
         patch("aeolus.get_source_info"):
        prompt = build_system_prompt()
    assert "chain" in prompt.lower()
    assert "identical" in prompt.lower()
    assert "filename stem" in prompt.lower() or "stems" in prompt.lower()


def test_build_system_prompt_forbids_find_sites_before_download():
    """Prompt tells the LLM not to chain find_sites → download."""
    from unittest.mock import patch
    from aeolus_cli.ask.prompt import build_system_prompt

    with patch("aeolus.list_sources", return_value=[]), \
         patch("aeolus.get_source_info"):
        prompt = build_system_prompt()
    # We check for the essential phrase that explains this rule
    lower = prompt.lower()
    assert "do not chain find_sites" in lower or "do not chain find-sites" in lower
    assert "near_lat" in prompt


def test_build_system_prompt_mentions_max_chain_length():
    """Prompt mentions the maximum chain length of 5."""
    from unittest.mock import patch
    from aeolus_cli.ask.prompt import build_system_prompt

    with patch("aeolus.list_sources", return_value=[]), \
         patch("aeolus.get_source_info"):
        prompt = build_system_prompt()
    assert "maximum is 5" in prompt or "max 5" in prompt.lower() or "5 steps" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_prompt.py -v`
Expected: 3 new tests FAIL; the 3 existing tests (sources, behavioural, measurand) still PASS.

- [ ] **Step 3: Update prompt.py**

In `src/aeolus_cli/ask/prompt.py`, replace the `_BEHAVIOURAL_INSTRUCTIONS` string with the version below. The existing rules 1-9 are preserved; new rules 10-13 are appended. Leave `_STATIC_KNOWLEDGE` and `build_system_prompt` unchanged.

```python
_BEHAVIOURAL_INSTRUCTIONS = """\
## Your Role

You are a query builder for the aeolus air quality CLI tool. Your job is to
translate natural language requests into structured tool calls that map to CLI
commands.

## Rules

1. Always provide a confidence level (low/medium/high) and a brief explanation.
2. The explanation should be one sentence, plain English, helping the user
   understand what the command does and why you chose those parameters.
3. ALWAYS generate a tool call. NEVER ask clarifying questions or reply with
   text asking for more information. If the query is ambiguous, make your best
   guess and explain your interpretation in the explanation field. The user can
   reject the command if it's wrong — that's what the confirmation step is for.
4. The ONLY time you may reply with text instead of a tool call is when the
   query is truly impossible (e.g. data that doesn't exist, a country with no
   coverage). Even then, keep it to one sentence.
5. If the user mentions a place name, use your knowledge of geography to
   determine the right source and approximate coordinates.
6. When the user doesn't specify pollutants, download all available — do not ask.
7. When the user doesn't specify a source, pick the best one for the location.
   For London: use AQE. For UK generally: use AURN. For Scotland: use SAQN.
   For Europe: use EEA. Do NOT use LMAM — its data endpoint is currently broken.
8. When the user wants to DOWNLOAD data near a location, use the download tool
   with near_lat/near_lon — it will discover sites automatically. Do NOT use
   find_sites when the user's intent is to download data. Only use find_sites
   when the user explicitly wants to discover/list sites.
9. Suggest a descriptive output filename when appropriate.

## Chaining Multiple Commands

You may return multiple tool calls in one response when the user explicitly
asks for multiple actions (e.g. "download X and plot it"). The commands run
in order and stop on the first failure.

10. Only chain when the user explicitly asks for multiple actions. Downloading
    alone does NOT imply summarising or plotting — do not add steps the user
    did not ask for.

11. When steps share a file, use IDENTICAL filename STEMS across steps. The
    extensions will differ (.csv for download, .png for plot) but the stem
    must match. Example:
      - Step 1: download ... -o manchester_no2_2025.csv
      - Step 2: summarise manchester_no2_2025.csv
      - Step 3: plot manchester_no2_2025.csv -o manchester_no2_2025.png
    Each step still needs its own confidence and explanation fields — answer
    them per step, not for the whole chain.

12. Keep chains short. A typical chain is 2-3 steps, and the maximum is 5
    steps. If a request seems to need more, your interpretation is probably
    wrong — ask yourself whether a single command would work instead.

13. If you need site codes for a download, use download with near_lat/near_lon
    directly. Do NOT chain find_sites before download — find_sites prints a
    table to the terminal, and you cannot see its output when planning the
    next step, so the download step would have to guess site codes. The
    download tool handles location-based site discovery internally.
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_prompt.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli
git add src/aeolus_cli/ask/prompt.py tests/test_ask_prompt.py
git commit -m "feat(prompt): add chaining rules, forbid find_sites→download, cap at 5 steps"
```

---

## Task 4: NoDataError in Orchestrator's Download Branch

**Files:**
- Modify: `src/aeolus_cli/ask/orchestrator.py` (download branch of `_execute_tool_call`)
- Test: `tests/test_ask_orchestrator.py` (new focused test)

This task makes the download branch of `_execute_tool_call` raise `NoDataError` on empty data instead of printing a warning and returning. We do NOT change the chain loop yet — that's Task 6. The existing `_confirm_and_execute` code path still calls `_execute_tool_call` directly, so it will see the exception; we update its `try/except` in Task 6.

Because the orchestrator tests currently still use the old `parse_response` shape (they'll be updated in Task 6), we can't run the full orchestrator test file yet. We add ONE focused unit test for `_execute_tool_call` with the download branch and run only that test.

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_ask_orchestrator.py`:

```python
def test_execute_tool_call_download_raises_no_data_error_on_empty(tmp_path, monkeypatch):
    """Download branch raises NoDataError when aeolus.download returns empty."""
    import pandas as pd
    from unittest.mock import patch
    from aeolus_cli.ask.errors import NoDataError
    from aeolus_cli.ask.orchestrator import _execute_tool_call

    monkeypatch.chdir(tmp_path)
    empty_df = pd.DataFrame(columns=[
        "site_code", "date_time", "measurand", "value", "units",
        "source_network", "ratification", "created_at",
    ])

    tool_call = {
        "name": "download",
        "input": {
            "source": "AURN",
            "sites": ["MY1"],
            "last": "30d",
            "confidence": "high",
            "explanation": "test",
        },
    }

    with patch("aeolus.download", return_value=empty_df):
        with pytest.raises(NoDataError):
            _execute_tool_call(tool_call)
```

Also ensure `import pytest` is present at the top of `tests/test_ask_orchestrator.py`; if not, add it.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_orchestrator.py::test_execute_tool_call_download_raises_no_data_error_on_empty -v`
Expected: FAIL — the function currently prints a warning and returns instead of raising.

- [ ] **Step 3: Update the download branch in orchestrator.py**

In `src/aeolus_cli/ask/orchestrator.py`, find the download branch inside `_execute_tool_call`. It currently ends with:

```python
        if data.empty:
            console.print("[yellow]No data returned. The sites may not have data for this date range.[/yellow]")
            return

        output = Path(params.get("output", make_default_filename(params["source"], sites=sites)))
        write_csv(data, output)
```

Replace the empty-data handling so it raises `NoDataError` with a descriptive message:

```python
        if data.empty:
            raise NoDataError(
                f"No data returned from {params['source']} for the requested "
                "sites and date range."
            )

        output = Path(params.get("output", make_default_filename(params["source"], sites=sites)))
        write_csv(data, output)
```

And add the import at the top of the file, near the other `from aeolus_cli.ask.*` imports:

```python
from aeolus_cli.ask.errors import NoDataError
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_orchestrator.py::test_execute_tool_call_download_raises_no_data_error_on_empty -v`
Expected: PASS (1 passed). Other tests in the file may still be broken because of the Task 2 shape change — that is expected and fixed in Task 6.

- [ ] **Step 5: Commit**

```bash
cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli
git add src/aeolus_cli/ask/orchestrator.py tests/test_ask_orchestrator.py
git commit -m "feat(orchestrator): download branch raises NoDataError on empty result"
```

---

## Task 5: Chain-Aware Helpers in Orchestrator

**Files:**
- Modify: `src/aeolus_cli/ask/orchestrator.py` (add `MAX_CHAIN_LENGTH`, `_print_skipped`, `_render_plan`; do NOT yet wire up chain execution)

This task adds the small helper functions that Task 6 will glue together. Each helper is testable in isolation, so we test it individually before writing the bigger `_confirm_and_execute_chain` in Task 6.

- [ ] **Step 1: Write tests for the helpers**

Append to `tests/test_ask_orchestrator.py`:

```python
def test_max_chain_length_constant():
    """MAX_CHAIN_LENGTH is 5 (belt-and-braces cap)."""
    from aeolus_cli.ask.orchestrator import MAX_CHAIN_LENGTH
    assert MAX_CHAIN_LENGTH == 5


def test_print_skipped_lists_remaining_commands(capsys):
    """_print_skipped prints the step index and the rendered remaining commands."""
    from aeolus_cli.ask.orchestrator import _print_skipped

    remaining = [
        {"name": "summarise", "input": {"file": "x.csv", "confidence": "high", "explanation": ""}},
        {"name": "plot", "input": {"file": "x.csv", "output": "x.png", "confidence": "high", "explanation": ""}},
    ]
    _print_skipped(2, remaining)
    out = capsys.readouterr().out
    assert "Stopped on step 2" in out
    assert "aeolus summarise x.csv" in out
    assert "aeolus plot x.csv -o x.png" in out


def test_render_plan_with_single_command_suppresses_step_prefix(capsys):
    """_render_plan with one call does not print 'Step 1/1:'."""
    from aeolus_cli.ask.orchestrator import _render_plan

    calls = [{"name": "sources", "input": {"confidence": "high", "explanation": "Lists sources."}}]
    _render_plan(calls)
    out = capsys.readouterr().out
    assert "Step 1/1" not in out
    assert "aeolus sources" in out
    assert "Lists sources." in out


def test_render_plan_with_multi_command_shows_step_prefix(capsys):
    """_render_plan with multiple calls prints 'Step i/n:' for each."""
    from aeolus_cli.ask.orchestrator import _render_plan

    calls = [
        {"name": "download", "input": {"source": "AURN", "sites": ["MY1"], "last": "30d", "output": "x.csv", "confidence": "high", "explanation": "Downloads data."}},
        {"name": "plot", "input": {"file": "x.csv", "output": "x.png", "confidence": "high", "explanation": "Plots it."}},
    ]
    _render_plan(calls)
    out = capsys.readouterr().out
    assert "Step 1/2" in out
    assert "Step 2/2" in out
    assert "aeolus download AURN" in out
    assert "aeolus plot x.csv" in out
    assert "Downloads data." in out
    assert "Plots it." in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_orchestrator.py::test_max_chain_length_constant tests/test_ask_orchestrator.py::test_print_skipped_lists_remaining_commands tests/test_ask_orchestrator.py::test_render_plan_with_single_command_suppresses_step_prefix tests/test_ask_orchestrator.py::test_render_plan_with_multi_command_shows_step_prefix -v`
Expected: 4 failures (ImportError on `MAX_CHAIN_LENGTH`, `_print_skipped`, `_render_plan`).

- [ ] **Step 3: Add the helpers to orchestrator.py**

Near the top of `src/aeolus_cli/ask/orchestrator.py`, after the existing imports, add the constant:

```python
MAX_CHAIN_LENGTH = 5
```

Add two helper functions anywhere in the module above `_confirm_and_execute` (the existing function — we leave it alone this task; Task 6 replaces it). Use these exact definitions:

```python
def _render_plan(calls: list[dict]) -> None:
    """Display the list of commands (and their explanations) to the user.

    When there is only one command, the 'Step 1/1:' prefix is suppressed
    so single-command responses look identical to the pre-chaining UX.
    """
    n = len(calls)
    for i, call in enumerate(calls, 1):
        cmd_str = render_tool_call(call)
        explanation = call["input"].get("explanation", "")
        prefix = f"Step {i}/{n}: " if n > 1 else ""
        console.print(f"\n  [bold]{prefix}{cmd_str}[/bold]")
        if explanation:
            console.print(f"  [dim]{explanation}[/dim]")
    if n > 1:
        # Trailing blank line before the confirmation prompt
        console.print("")


def _print_skipped(failed_step: int, remaining_calls: list[dict]) -> None:
    """Print the list of commands that were not run.

    Args:
        failed_step: The 1-indexed step number that failed or was aborted.
        remaining_calls: The list of tool_call dicts that did not execute.
    """
    console.print(f"\n[yellow]Stopped on step {failed_step}. Did not run:[/yellow]")
    for call in remaining_calls:
        console.print(f"  - {render_tool_call(call)}")
```

- [ ] **Step 4: Run the four new tests to verify they pass**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_orchestrator.py::test_max_chain_length_constant tests/test_ask_orchestrator.py::test_print_skipped_lists_remaining_commands tests/test_ask_orchestrator.py::test_render_plan_with_single_command_suppresses_step_prefix tests/test_ask_orchestrator.py::test_render_plan_with_multi_command_shows_step_prefix -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli
git add src/aeolus_cli/ask/orchestrator.py tests/test_ask_orchestrator.py
git commit -m "feat(orchestrator): add MAX_CHAIN_LENGTH, _render_plan, _print_skipped helpers"
```

---

## Task 6: Chain Execution and --step Flag (the Big One)

**Files:**
- Modify: `src/aeolus_cli/ask/orchestrator.py` (replace `_confirm_and_execute` with `_confirm_and_execute_chain`, update `ask` CLI signature, wire it all up)
- Modify: `tests/test_ask_orchestrator.py` (update existing tests to new shape, add chain tests)

This is the largest task. It replaces the single-command orchestration with a chain-aware version, adds the `--step` flag, enforces `MAX_CHAIN_LENGTH`, and updates all existing orchestrator tests to use the new `{"type": "tool_calls", "tool_calls": [...]}` shape.

- [ ] **Step 1: Rewrite the existing orchestrator tests and add the new ones**

Replace the contents of `tests/test_ask_orchestrator.py` with the full version below. This preserves all pre-existing tests (updated to the new shape) and adds the new chain-related tests. Note: the `test_execute_tool_call_download_raises_no_data_error_on_empty` and helper tests from Tasks 4 and 5 are included here too.

```python
"""Tests for the ask orchestrator."""
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner

runner = CliRunner()


def _mock_single_tool_result() -> dict:
    return {
        "type": "tool_calls",
        "tool_calls": [
            {
                "name": "download",
                "input": {
                    "source": "AURN",
                    "sites": ["MY1"],
                    "last": "30d",
                    "confidence": "high",
                    "explanation": "Downloads AURN data from Marylebone Road for the last 30 days.",
                },
            },
        ],
    }


def _mock_chain_result() -> dict:
    return {
        "type": "tool_calls",
        "tool_calls": [
            {
                "name": "download",
                "input": {
                    "source": "AURN",
                    "sites": ["MY1"],
                    "last": "30d",
                    "output": "my1_30d.csv",
                    "confidence": "high",
                    "explanation": "Downloads data.",
                },
            },
            {
                "name": "plot",
                "input": {
                    "file": "my1_30d.csv",
                    "output": "my1_30d.png",
                    "confidence": "high",
                    "explanation": "Plots it.",
                },
            },
        ],
    }


def _mock_three_step_chain_result() -> dict:
    return {
        "type": "tool_calls",
        "tool_calls": [
            {
                "name": "download",
                "input": {
                    "source": "AURN",
                    "sites": ["MY1"],
                    "last": "30d",
                    "output": "my1_30d.csv",
                    "confidence": "high",
                    "explanation": "Downloads data.",
                },
            },
            {
                "name": "summarise",
                "input": {
                    "file": "my1_30d.csv",
                    "confidence": "high",
                    "explanation": "Summarises it.",
                },
            },
            {
                "name": "plot",
                "input": {
                    "file": "my1_30d.csv",
                    "output": "my1_30d.png",
                    "confidence": "high",
                    "explanation": "Plots it.",
                },
            },
        ],
    }


def _mock_text_result() -> dict:
    return {"type": "text", "text": "I can't build a query for that."}


def _mock_download_data() -> pd.DataFrame:
    return pd.DataFrame({
        "site_code": ["MY1"], "date_time": ["2024-01-01"], "measurand": ["NO2"],
        "value": [40.0], "units": ["ug/m3"], "source_network": ["AURN"],
        "ratification": ["P"], "created_at": ["2024-01-02"],
    })


# -------------------------------------------------------------
# Helper / unit tests for _execute_tool_call, _render_plan, etc.
# -------------------------------------------------------------


def test_max_chain_length_constant():
    from aeolus_cli.ask.orchestrator import MAX_CHAIN_LENGTH
    assert MAX_CHAIN_LENGTH == 5


def test_print_skipped_lists_remaining_commands(capsys):
    from aeolus_cli.ask.orchestrator import _print_skipped

    remaining = [
        {"name": "summarise", "input": {"file": "x.csv", "confidence": "high", "explanation": ""}},
        {"name": "plot", "input": {"file": "x.csv", "output": "x.png", "confidence": "high", "explanation": ""}},
    ]
    _print_skipped(2, remaining)
    out = capsys.readouterr().out
    assert "Stopped on step 2" in out
    assert "aeolus summarise x.csv" in out
    assert "aeolus plot x.csv -o x.png" in out


def test_render_plan_with_single_command_suppresses_step_prefix(capsys):
    from aeolus_cli.ask.orchestrator import _render_plan

    calls = [{"name": "sources", "input": {"confidence": "high", "explanation": "Lists sources."}}]
    _render_plan(calls)
    out = capsys.readouterr().out
    assert "Step 1/1" not in out
    assert "aeolus sources" in out
    assert "Lists sources." in out


def test_render_plan_with_multi_command_shows_step_prefix(capsys):
    from aeolus_cli.ask.orchestrator import _render_plan

    calls = [
        {"name": "download", "input": {"source": "AURN", "sites": ["MY1"], "last": "30d", "output": "x.csv", "confidence": "high", "explanation": "Downloads data."}},
        {"name": "plot", "input": {"file": "x.csv", "output": "x.png", "confidence": "high", "explanation": "Plots it."}},
    ]
    _render_plan(calls)
    out = capsys.readouterr().out
    assert "Step 1/2" in out
    assert "Step 2/2" in out
    assert "aeolus download AURN" in out
    assert "aeolus plot x.csv" in out
    assert "Downloads data." in out
    assert "Plots it." in out


def test_execute_tool_call_download_raises_no_data_error_on_empty(tmp_path, monkeypatch):
    """Download branch raises NoDataError when aeolus.download returns empty."""
    from aeolus_cli.ask.errors import NoDataError
    from aeolus_cli.ask.orchestrator import _execute_tool_call

    monkeypatch.chdir(tmp_path)
    empty_df = pd.DataFrame(columns=[
        "site_code", "date_time", "measurand", "value", "units",
        "source_network", "ratification", "created_at",
    ])

    tool_call = {
        "name": "download",
        "input": {
            "source": "AURN",
            "sites": ["MY1"],
            "last": "30d",
            "confidence": "high",
            "explanation": "test",
        },
    }

    with patch("aeolus.download", return_value=empty_df):
        with pytest.raises(NoDataError):
            _execute_tool_call(tool_call)


# -------------------------------------------------------------
# CLI-level tests via CliRunner (the full ask command)
# -------------------------------------------------------------


def test_ask_shows_command_and_explanation():
    """ask displays the rendered command and explanation."""
    from aeolus_cli.main import app

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_single_tool_result()), \
         patch("aeolus_cli.ask.orchestrator._confirm_and_execute_chain"), \
         patch("aeolus_cli.config.get_key", return_value="sk-test"):
        result = runner.invoke(app, ["ask", "AURN data from MY1 last 30 days"])
    assert result.exit_code == 0


def test_ask_text_response_prints_message():
    """When LLM returns text instead of a tool call, display it."""
    from aeolus_cli.main import app

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_text_result()), \
         patch("aeolus_cli.config.get_key", return_value="sk-test"):
        result = runner.invoke(app, ["ask", "air quality on Mars"])
    assert result.exit_code == 0
    assert "can't build" in result.output


def test_ask_yes_flag_skips_confirmation(tmp_path, monkeypatch):
    """--yes skips the confirmation prompt."""
    from aeolus_cli.main import app

    monkeypatch.chdir(tmp_path)
    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_single_tool_result()), \
         patch("aeolus.download", return_value=_mock_download_data()), \
         patch("aeolus_cli.config.get_key", return_value="sk-test"):
        result = runner.invoke(app, ["ask", "--yes", "AURN data from MY1 last 30 days"])
    assert result.exit_code == 0


def test_ask_no_args_prompts(monkeypatch):
    """aeolus ask with no args prompts for input."""
    from aeolus_cli.main import app

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_text_result()), \
         patch("aeolus_cli.config.get_key", return_value="sk-test"):
        result = runner.invoke(app, ["ask"], input="air quality on Mars\n")
    assert result.exit_code == 0


def test_ask_joins_unquoted_args():
    """aeolus ask PM2.5 from SAQN 2024 joins args into a single query."""
    from aeolus_cli.main import app

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_text_result()) as mock, \
         patch("aeolus_cli.config.get_key", return_value="sk-test"):
        runner.invoke(app, ["ask", "PM2.5", "from", "SAQN", "2024"])
    mock.assert_called_once()
    query = mock.call_args[0][0]
    assert query == "PM2.5 from SAQN 2024"


# -------------------------------------------------------------
# Chain execution tests
# -------------------------------------------------------------


def test_chain_executes_both_steps_in_order(tmp_path, monkeypatch):
    """A 2-step chain runs download then plot in that order."""
    from aeolus_cli.main import app

    monkeypatch.chdir(tmp_path)
    mock_fig = MagicMock()

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_chain_result()), \
         patch("aeolus.download", return_value=_mock_download_data()) as mock_download, \
         patch("aeolus.viz.plot_timeseries", return_value=mock_fig) as mock_plot, \
         patch("aeolus_cli.config.get_key", return_value="sk-test"):
        result = runner.invoke(app, ["ask", "--yes", "download and plot"])

    assert result.exit_code == 0
    mock_download.assert_called_once()
    mock_plot.assert_called_once()
    # Plot should have been called AFTER download (call order preserved)
    # We verify the csv file it reads from exists after download ran.
    assert (tmp_path / "my1_30d.csv").exists()


def test_chain_stops_on_empty_data(tmp_path, monkeypatch):
    """NoDataError from step 1 stops the chain; step 2 is listed as skipped."""
    from aeolus_cli.main import app

    monkeypatch.chdir(tmp_path)
    empty_df = pd.DataFrame(columns=[
        "site_code", "date_time", "measurand", "value", "units",
        "source_network", "ratification", "created_at",
    ])

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_chain_result()), \
         patch("aeolus.download", return_value=empty_df), \
         patch("aeolus_cli.config.get_key", return_value="sk-test"):
        result = runner.invoke(app, ["ask", "--yes", "download and plot"])

    # Empty data is a clean stop — exit code 0, not a crash
    assert result.exit_code == 0
    assert "Stopped on step 1" in result.output
    assert "aeolus plot my1_30d.csv" in result.output


def test_chain_stops_on_unexpected_exception(tmp_path, monkeypatch):
    """A non-NoDataError exception from step 1 stops the chain with exit code 1."""
    from aeolus_cli.main import app

    monkeypatch.chdir(tmp_path)

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_chain_result()), \
         patch("aeolus.download", side_effect=ValueError("API error")), \
         patch("aeolus_cli.config.get_key", return_value="sk-test"):
        result = runner.invoke(app, ["ask", "--yes", "download and plot"])

    assert result.exit_code != 0
    assert "Stopped on step 1" in result.output
    assert "aeolus plot my1_30d.csv" in result.output


def test_step_mode_prompts_per_step(tmp_path, monkeypatch):
    """--step prompts before each step after the first."""
    from aeolus_cli.main import app

    monkeypatch.chdir(tmp_path)
    mock_fig = MagicMock()

    # Simulate: "y" for initial confirmation, then "n" to abort step 2
    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_chain_result()), \
         patch("aeolus.download", return_value=_mock_download_data()) as mock_download, \
         patch("aeolus.viz.plot_timeseries", return_value=mock_fig) as mock_plot, \
         patch("aeolus_cli.config.get_key", return_value="sk-test"):
        result = runner.invoke(
            app,
            ["ask", "--step", "download and plot"],
            input="y\nn\n",  # "y" for initial, "n" for step 2
        )

    assert result.exit_code == 0
    mock_download.assert_called_once()
    mock_plot.assert_not_called()
    assert "Stopped on step 2" in result.output
    assert "aeolus plot my1_30d.csv" in result.output


def test_chain_exceeding_max_length_is_rejected():
    """A chain of 6 steps is refused with a helpful error, no step runs."""
    from aeolus_cli.main import app

    six_step = {
        "type": "tool_calls",
        "tool_calls": [
            {
                "name": "sources",
                "input": {"confidence": "high", "explanation": f"Step {i}"},
            }
            for i in range(1, 7)
        ],
    }

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=six_step), \
         patch("aeolus.list_sources", return_value=[]) as mock_ls, \
         patch("aeolus_cli.config.get_key", return_value="sk-test"):
        result = runner.invoke(app, ["ask", "--yes", "do six things"])

    assert result.exit_code != 0
    assert "6 steps" in result.output or "maximum" in result.output.lower()
    # No step should have executed
    mock_ls.assert_not_called()


def test_single_command_exit_code_is_0():
    """A single tool call runs cleanly and exits 0."""
    from aeolus_cli.main import app

    with patch("aeolus_cli.ask.orchestrator._run_ask", return_value=_mock_single_tool_result()), \
         patch("aeolus.download", return_value=_mock_download_data()), \
         patch("aeolus_cli.config.get_key", return_value="sk-test"):
        result = runner.invoke(app, ["ask", "--yes", "download"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_orchestrator.py -v`
Expected: most tests FAIL — several complain that `_confirm_and_execute_chain` doesn't exist, that `_confirm_and_execute` patches don't find the symbol, or that chain-related code paths aren't wired up. The existing `_execute_tool_call` tests and helper tests should still PASS.

- [ ] **Step 3: Rewrite orchestrator.py**

Replace the contents of `src/aeolus_cli/ask/orchestrator.py` with the full version below. This preserves `_execute_tool_call` (including the Task 4 `NoDataError` raising) and the helpers added in Task 5, and replaces `_confirm_and_execute` with `_confirm_and_execute_chain`. The CLI `ask` function gains a `--step` flag.

```python
"""Top-level orchestration for aeolus ask."""
from pathlib import Path
from typing import Optional

import typer
from rich.prompt import Prompt

from aeolus_cli.ask.errors import NoDataError
from aeolus_cli.ask.llm import call_llm, call_llm_explain_chain, parse_response
from aeolus_cli.ask.prompt import build_system_prompt
from aeolus_cli.ask.render import render_tool_call
from aeolus_cli.ask.tools import TOOL_SCHEMAS
import aeolus_cli.config as _config
from aeolus_cli.output import console, print_error


MAX_CHAIN_LENGTH = 5


def _run_ask(query: str) -> dict:
    """Send the query to the LLM and parse the response."""
    system_prompt = build_system_prompt()
    raw_response = call_llm(query, system_prompt, TOOL_SCHEMAS)
    return parse_response(raw_response)


def _execute_tool_call(tool_call: dict) -> None:
    """Execute a tool call by invoking the corresponding aeolus function.

    Raises NoDataError when a download returns an empty DataFrame — chains
    catch this to stop gracefully and list skipped steps.
    """
    name = tool_call["name"]
    params = {k: v for k, v in tool_call["input"].items()
              if k not in ("confidence", "explanation")}

    if name == "download":
        import aeolus
        from datetime import datetime
        from aeolus_cli.output import make_default_filename, write_csv

        # Discover sites from near_lat/near_lon if no explicit sites
        sites = params.get("sites")
        if sites is None and "near_lat" in params and "near_lon" in params:
            found = aeolus.find_sites(
                source=params["source"],
                near=(params["near_lat"], params["near_lon"]),
                radius_km=params.get("radius_km", 15.0),
            )
            sites = found["site_code"].tolist() if not found.empty else []

        # Parse date strings to datetime objects
        start_date = datetime.fromisoformat(params["start_date"]) if params.get("start_date") else None
        end_date = datetime.fromisoformat(params["end_date"]) if params.get("end_date") else None

        data = aeolus.download(
            sources=params["source"],
            sites=sites,
            start_date=start_date,
            end_date=end_date,
            last=params.get("last"),
        )
        if params.get("measurands") and not data.empty:
            data = data[data["measurand"].isin(params["measurands"])]

        if data.empty:
            raise NoDataError(
                f"No data returned from {params['source']} for the requested "
                "sites and date range."
            )

        output = Path(params.get("output", make_default_filename(params["source"], sites=sites)))
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
                "Source": info["name"], "Type": info.get("type", "network"),
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
        data = pd.read_csv(params["file"])
        fig = viz.plot_timeseries(data)
        output = params.get("output", f"{Path(params['file']).stem}_plot.png")
        fig.savefig(output, dpi=150, bbox_inches="tight")
        console.print(f"Saved plot to {output}")


def _render_plan(calls: list[dict]) -> None:
    """Display the list of commands (and their explanations) to the user.

    When there is only one command, the 'Step 1/1:' prefix is suppressed
    so single-command responses look identical to the pre-chaining UX.
    """
    n = len(calls)
    for i, call in enumerate(calls, 1):
        cmd_str = render_tool_call(call)
        explanation = call["input"].get("explanation", "")
        prefix = f"Step {i}/{n}: " if n > 1 else ""
        console.print(f"\n  [bold]{prefix}{cmd_str}[/bold]")
        if explanation:
            console.print(f"  [dim]{explanation}[/dim]")
    if n > 1:
        console.print("")


def _print_skipped(failed_step: int, remaining_calls: list[dict]) -> None:
    """Print the list of commands that were not run.

    Args:
        failed_step: The 1-indexed step number that failed or was aborted.
        remaining_calls: The list of tool_call dicts that did not execute.
    """
    console.print(f"\n[yellow]Stopped on step {failed_step}. Did not run:[/yellow]")
    for call in remaining_calls:
        console.print(f"  - {render_tool_call(call)}")


def _confirm_and_execute_chain(
    result: dict,
    query: str,
    yes: bool,
    step_mode: bool,
) -> None:
    """Show the plan, confirm, and execute each step.

    Stops on the first failure and lists skipped steps. Handles the
    --step mode by prompting before each step after the first.
    """
    calls = result["tool_calls"]
    n = len(calls)

    # Defensive cap — the prompt already discourages long chains, but be
    # belt-and-braces in case the LLM goes off-piste.
    if n > MAX_CHAIN_LENGTH:
        print_error(ValueError(
            f"The model proposed a chain of {n} steps, which exceeds the "
            f"maximum of {MAX_CHAIN_LENGTH}. This usually means the request "
            "was interpreted too broadly. Please rephrase more specifically."
        ))
        raise typer.Exit(code=1)

    _render_plan(calls)

    # Initial confirmation
    if not yes:
        choice = Prompt.ask("Run?", choices=["y", "n", "e"], default="y")
        if choice == "n":
            return
        if choice == "e":
            try:
                deep = call_llm_explain_chain(query, calls, build_system_prompt())
                console.print(f"\n{deep}\n")
            except Exception as e:
                console.print(f"[dim]Could not get explanation: {e}[/dim]\n")
            if Prompt.ask("Run?", choices=["y", "n"], default="y") == "n":
                return

    # Execute each step, stopping on failure
    for i, call in enumerate(calls, 1):
        # Per-step confirmation in --step mode (after the first step)
        if step_mode and i > 1 and not yes:
            if Prompt.ask(f"Run step {i}?", choices=["y", "n"], default="y") == "n":
                _print_skipped(i, calls[i - 1 :])
                return

        prefix = f"Step {i}/{n}: " if n > 1 else ""
        console.print(f"\n[bold]{prefix}{render_tool_call(call)}[/bold]")

        try:
            _execute_tool_call(call)
        except NoDataError as e:
            console.print(f"[yellow]{e}[/yellow]")
            if i < n:
                _print_skipped(i, calls[i:])
            return
        except Exception as e:
            print_error(e)
            if i < n:
                _print_skipped(i, calls[i:])
            raise typer.Exit(code=1)


def ask(
    query: Optional[list[str]] = typer.Argument(
        None,
        help=(
            "Natural language query. Wrap in double quotes if it contains "
            "apostrophes or other punctuation, e.g. \"what's the NO2 in Southwark\". "
            "Or run `aeolus ask -i` for interactive mode."
        ),
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Prompt for the query instead of reading it from arguments (allows apostrophes).",
    ),
    step: bool = typer.Option(
        False,
        "--step",
        help="Confirm each step in a chain individually (ignored for single-command responses).",
    ),
):
    """Translate a natural language query into an aeolus command.

    Tip: if your query contains apostrophes (e.g. "what's"), wrap it in double
    quotes or use -i for interactive mode — otherwise your shell will choke
    on the unmatched quote.
    """
    key = _config.get_key("ANTHROPIC_API_KEY")
    if not key:
        print_error(ValueError(
            "aeolus ask requires an Anthropic API key.\n"
            "Set ANTHROPIC_API_KEY in your environment or in ~/.aeolus/config.toml"
        ))
        raise typer.Exit(code=1)

    if interactive or not query:
        query_str = Prompt.ask("What data are you looking for?")
        if not query_str.strip():
            raise typer.Exit(code=0)
    else:
        query_str = " ".join(query)

    try:
        result = _run_ask(query_str)
        if result["type"] == "text":
            console.print(result["text"])
            raise typer.Exit(code=0)
        _confirm_and_execute_chain(result, query_str, yes, step)
    except typer.Exit:
        raise
    except ImportError as e:
        print_error(e)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(e)
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Run the full orchestrator tests to verify they pass**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_orchestrator.py -v`
Expected: all tests PASS. At minimum: `test_max_chain_length_constant`, `test_print_skipped_lists_remaining_commands`, `test_render_plan_with_single_command_suppresses_step_prefix`, `test_render_plan_with_multi_command_shows_step_prefix`, `test_execute_tool_call_download_raises_no_data_error_on_empty`, `test_ask_shows_command_and_explanation`, `test_ask_text_response_prints_message`, `test_ask_yes_flag_skips_confirmation`, `test_ask_no_args_prompts`, `test_ask_joins_unquoted_args`, `test_chain_executes_both_steps_in_order`, `test_chain_stops_on_empty_data`, `test_chain_stops_on_unexpected_exception`, `test_step_mode_prompts_per_step`, `test_chain_exceeding_max_length_is_rejected`, `test_single_command_exit_code_is_0`.

- [ ] **Step 5: Run the full test suite to verify nothing else broke**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli
git add src/aeolus_cli/ask/orchestrator.py tests/test_ask_orchestrator.py
git commit -m "feat(ask): chain execution with --step, stop-on-failure, length cap"
```

---

## Task 7: Render/Execute Consistency Tests

**Files:**
- Modify: `tests/test_ask_render.py` (add consistency tests)

This task adds defensive tests that catch drift between `render_tool_call` and `_execute_tool_call`. The idea: for every tool, build a dict with every documented parameter, then check that the rendered command string mentions each parameter in some visible form (either the flag name, the value itself, or a recognisable substring). The test is intentionally loose — it's a smoke test for "did you forget to add the new param to both functions", not a strict grammar check.

- [ ] **Step 1: Add the consistency tests**

Append to `tests/test_ask_render.py`:

```python
# ------------------------------------------------------------
# Render/execute drift guards
# ------------------------------------------------------------
import pytest


# For each tool, a "full" input dict containing every documented parameter
# (excluding confidence and explanation which are meta fields).
_FULL_PARAMS_BY_TOOL = {
    "sources": {
        "all": True,
    },
    "find_sites": {
        "source": "AURN",
        "near_lat": 51.5,
        "near_lon": -0.13,
        "radius_km": 10.0,
        "bbox": "-0.5,51.3,0.3,51.7",
    },
    "download": {
        "source": "AURN",
        "sites": ["MY1", "KC1"],
        "near_lat": 51.5,
        "near_lon": -0.13,
        "radius_km": 15.0,
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "last": "30d",
        "measurands": ["NO2", "PM2.5"],
        "output": "out.csv",
    },
    "get_current": {
        "source": "AURN",
        "sites": ["MY1"],
        "near_lat": 51.5,
        "near_lon": -0.13,
    },
    "summarise": {
        "file": "data.csv",
    },
    "plot": {
        "file": "data.csv",
        "output": "plot.png",
    },
}


def _param_visible_in(key: str, value, rendered: str) -> bool:
    """Is a parameter plausibly represented in the rendered command string?

    Checks for a few things: (a) the stringified value appears, (b) a recognisable
    flag appears (e.g. --sites, --near, --radius), (c) for list values, every
    element appears. It's deliberately loose because the render format varies
    by parameter (near_lat and near_lon collapse into --near "lat,lon", etc.).
    """
    if isinstance(value, bool):
        # Boolean flags — presence of the flag name is enough when True
        if value and f"--{key}" in rendered:
            return True
        # When False, the flag shouldn't appear; vacuously visible
        return not value
    if isinstance(value, list):
        return all(str(item) in rendered for item in value)
    if key in ("near_lat", "near_lon"):
        # These collapse into --near lat,lon
        return "--near" in rendered and str(value) in rendered
    if key == "radius_km":
        return "--radius" in rendered and str(value) in rendered
    if key == "start_date":
        return "--start" in rendered and str(value) in rendered
    if key == "end_date":
        return "--end" in rendered and str(value) in rendered
    if key == "output":
        return "-o" in rendered and str(value) in rendered
    # Default: just look for the value as a substring
    return str(value) in rendered


@pytest.mark.parametrize("tool_name", list(_FULL_PARAMS_BY_TOOL.keys()))
def test_render_includes_every_documented_parameter(tool_name):
    """Every parameter in the tool's documented schema appears in the rendered command.

    Guards against the bug where execute honours a parameter but render forgets
    to display it — meaning the user sees a command that differs from what runs.
    """
    from aeolus_cli.ask.render import render_tool_call

    full_params = dict(_FULL_PARAMS_BY_TOOL[tool_name])
    full_params["confidence"] = "high"
    full_params["explanation"] = "test"

    tool_call = {"name": tool_name, "input": full_params}
    rendered = render_tool_call(tool_call)

    # sources is a special case: `all` is the only param and it's a flag
    # find_sites has mutually exclusive near vs bbox — render may pick only one.
    # We skip checking for bbox when near_lat is also present.
    for key, value in full_params.items():
        if key in ("confidence", "explanation"):
            continue
        # Special case: find_sites can only render one of near/bbox, not both.
        if tool_name == "find_sites" and key == "bbox":
            continue
        assert _param_visible_in(key, value, rendered), (
            f"Tool {tool_name} parameter {key}={value!r} is not visible in "
            f"rendered command: {rendered!r}"
        )
```

- [ ] **Step 2: Run the new tests to verify they pass**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_render.py -v`
Expected: all existing tests plus 6 new parametrised tests PASS.

- [ ] **Step 3: Sanity check — deliberately break the render function and confirm the test catches it**

This is a one-off verification that the consistency tests work. In `src/aeolus_cli/ask/render.py`, temporarily comment out the `measurands` handling in `_render_download`:

```python
    # if "measurands" in p:
    #     parts.extend(["--measurands"] + p["measurands"])
```

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest tests/test_ask_render.py::test_render_includes_every_documented_parameter -v`
Expected: the `download` parametrisation FAILS with a clear message mentioning `measurands`.

Then **revert** the render.py change (uncomment the `measurands` handling). Re-run the tests:
Expected: all PASS.

- [ ] **Step 4: Run the full test suite**

Run: `cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli && .venv/bin/pytest -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli
git add tests/test_ask_render.py
git commit -m "test(render): add drift guards between render_tool_call and execute"
```

---

## Task 8: Manual Smoke Test

**Files:** None. This is a manual verification step against the real Anthropic API.

This task is not automatable. It verifies that the whole pipeline works end-to-end with a real LLM, since our unit tests all mock the API.

**Prerequisites:**
- `ANTHROPIC_API_KEY` is set in `~/.aeolus/config.toml` (it already is per the session history).
- The editable install is current: run `uv tool install --editable /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli --with anthropic --force` if in doubt.

- [ ] **Step 1: Chain that should execute successfully**

```bash
cd /tmp
mkdir -p aeolus_chain_test
cd aeolus_chain_test
aeolus ask "download NO2 from AURN near central London for the last 7 days and plot it"
```

Expected:
- Two-step plan is displayed: `Step 1/2: aeolus download AURN --near 51.5074,-0.1278 ... --measurands NO2 ... -o <stem>.csv` and `Step 2/2: aeolus plot <stem>.csv -o <stem>.png`.
- Filenames have matching stems.
- Each step has a one-line explanation.
- `Run? [y/n/e] (y):` prompt appears.
- Answering `y` runs both steps; download shows a progress bar; plot prints `Saved plot to <stem>.png`.
- Both `<stem>.csv` and `<stem>.png` exist in the current directory after completion.

- [ ] **Step 2: Chain that should stop on empty data**

Find a date range that returns no data (e.g. tomorrow):

```bash
aeolus ask "download from AURN site MY1 for tomorrow and summarise it"
```

Expected:
- Two-step plan is displayed.
- User confirms with `y`.
- Step 1 runs, hits empty data, prints the yellow "No data returned from AURN..." message.
- `Stopped on step 1. Did not run:` appears, followed by `- aeolus summarise <stem>.csv`.
- Exit code is 0 (empty data is not a crash). Verify with `echo $?`.

- [ ] **Step 3: Single-command response (no chain)**

```bash
aeolus ask "what sources are available"
```

Expected:
- Single command shown: `aeolus sources`. NO `Step 1/1:` prefix.
- Confirming runs the command and prints the sources table.

- [ ] **Step 4: `--step` flag aborts mid-chain**

```bash
aeolus ask --step "download NO2 from AURN site MY1 for the last 7 days and plot it"
```

Expected:
- Plan displayed, initial confirm prompt.
- Answering `y` runs step 1 (download).
- Before step 2, prompt appears: `Run step 2? [y/n] (y):`.
- Answering `n` prints `Stopped on step 2. Did not run: - aeolus plot ...` and exits 0.

- [ ] **Step 5: `--yes` runs the whole chain unattended**

```bash
rm -f *.csv *.png
aeolus ask --yes "download NO2 from AURN site MY1 for the last 7 days and plot it"
```

Expected: no confirmation prompts, both steps run, both files are produced.

- [ ] **Step 6: `e` option explains the whole workflow**

```bash
aeolus ask "download NO2 from AURN site MY1 for the last 7 days and plot it"
```

When prompted, answer `e`.

Expected:
- A 3-5 sentence explanation of the whole workflow is printed.
- A follow-up `Run? [y/n]` prompt appears.
- Answering `n` exits cleanly.

- [ ] **Step 7: Record observed behaviour**

If any of steps 1–6 deviate from expected, open an issue in the repo or report back. If everything passes, the feature is ready to ship.

---

## Task 9: Reinstall the uv Tool

**Files:** None. Makes the new version available on the user's PATH.

- [ ] **Step 1: Reinstall editable**

```bash
uv tool install --editable /Users/ruaraidhdobson/Dropbox/Personal/sls/aeolus-cli --with anthropic --force
```

Expected: `~ aeolus-cli==0.1.0` and `Installed 1 executable: aeolus`.

- [ ] **Step 2: Verify the --step flag is visible in help**

```bash
aeolus ask --help
```

Expected: `--step` appears in the options list with the description "Confirm each step in a chain individually...".

- [ ] **Step 3: No commit** — this step produces no code changes. Done.
