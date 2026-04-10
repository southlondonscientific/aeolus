# aeolus ask — Command Chaining Design Spec

*2026-04-10*

## Overview

Let `aeolus ask` compose multi-step workflows in a single LLM call. The user asks for something that needs multiple commands ("download NO2 from MY1 last year and plot it"), the LLM returns all the tool calls in one response, and the orchestrator executes them in order with a single confirmation.

The LLM is a **workflow composer**, not an agent. It plans every step upfront, shows the plan to the user, and runs it. There is no feedback loop between steps — the LLM does not see the output of step 1 before planning step 2. Dependencies between steps are handled via shared filenames (step 1 writes `foo.csv`, step 2 plots `foo.csv`).

This is deliberately the simpler of two paths: a "real" agent loop (where the LLM observes each tool result and decides the next step) is explicitly out of scope for v1.

## User Experience

### Example: a two-step chain

```
$ aeolus ask "download NO2 from MY1 last year and plot it"

  Step 1/2: aeolus download AURN --sites MY1 --start 2025-04-10 --end 2026-04-10 --measurands NO2 -o my1_no2_2025.csv
    Downloads a year of NO2 data from Marylebone Road (MY1) on the AURN network.
  
  Step 2/2: aeolus plot my1_no2_2025.csv -o my1_no2_2025.png
    Creates a time series chart of the downloaded data.

Run? [y/n/e] (y): y

Step 1/2: aeolus download AURN --sites MY1 --start 2025-04-10 --end 2026-04-10 --measurands NO2 -o my1_no2_2025.csv
Downloading AURN: 100%|█████████| 1/1 [00:02<00:00]
Saved to my1_no2_2025.csv (8760 rows)

Step 2/2: aeolus plot my1_no2_2025.csv -o my1_no2_2025.png
Saved plot to my1_no2_2025.png
```

### Example: a chain that stops on failure

```
$ aeolus ask "download from MY1 yesterday and summarise it"

  Step 1/2: aeolus download AURN --sites MY1 --start 2026-04-09 --end 2026-04-09 -o my1_20260409.csv
    Downloads AURN data from Marylebone Road for yesterday.
  
  Step 2/2: aeolus summarise my1_20260409.csv
    Shows sites, pollutants, date range, and data completeness.

Run? [y/n/e] (y): y

Step 1/2: aeolus download AURN --sites MY1 --start 2026-04-09 --end 2026-04-09 -o my1_20260409.csv
Downloading AURN: 100%|█████████| 1/1 [00:01<00:00]
No data returned. The sites may not have data for this date range.

Stopped on step 1. Did not run:
  - aeolus summarise my1_20260409.csv
```

### Single-command responses (no chain)

When the LLM returns a single tool call, the UX is unchanged from today. The `Step 1/1:` prefix is suppressed so simple queries still look clean:

```
$ aeolus ask sources

  aeolus sources
    Lists available air quality data sources.

Run? [y/n/e] (y):
```

### `--step` flag for per-step confirmation

Default: one confirmation for the whole chain.

Opt-in: `--step` prompts `Y/n` before each subsequent step, so the user can abort mid-chain without Ctrl-C:

```
$ aeolus ask --step "download then plot"
  Step 1/2: aeolus download ...
  Step 2/2: aeolus plot ...

Run? [y/n/e] (y): y

Step 1/2: aeolus download ...
Saved to my1_2025.csv (8760 rows)

Run step 2? [y/n] (y): n

Stopped before step 2. Did not run:
  - aeolus plot my1_2025.csv -o my1_2025.png
```

### `--yes` for chains

Unchanged semantics: skips all confirmation, runs every step. Risk noted in the help text: chains can overwrite existing files without warning when `-y` is used. Acceptable because `-y` is opt-in.

### Deep explanation (`e` option)

When the user presses `e` at the confirmation prompt and the response is a chain, the CLI makes **one** LLM call asking for an explanation of the whole workflow (not per-step). The explanation focuses on the narrative between steps ("we download first, then summarise to check data quality, then plot to visualise trends") rather than the individual command syntax, which the one-line per-step explanations already cover.

For single-command responses, `e` works as it does today — one LLM call explaining the single command.

## Architecture

The only code changes are in `ask/llm.py`, `ask/orchestrator.py`, `ask/prompt.py`, and the CLI signature in `ask/orchestrator.py`. No changes to `render.py`, `tools.py`, or any of the Layer 1 commands. No library changes.

### Data structure change

`parse_response` in `ask/llm.py` returns all tool_use blocks instead of just the first one.

**Before:**
```python
{
    "type": "tool_call",
    "tool_call": {"name": "download", "input": {...}},
    "confidence": "high",
    "explanation": "...",
}
```

**After:**
```python
{
    "type": "tool_calls",  # plural
    "tool_calls": [
        {"name": "download", "input": {...}},
        {"name": "plot", "input": {...}},
    ],
}
```

Each tool call carries its own `confidence` and `explanation` inside its own `input` dict (as today). The top-level `confidence`/`explanation` fields are removed — callers access them per-call.

Text-only responses are unchanged: `{"type": "text", "text": "..."}`.

### Orchestrator flow

`_confirm_and_execute` becomes `_confirm_and_execute_chain`. Pseudocode:

```python
def _confirm_and_execute_chain(result, query, yes, step_mode):
    calls = result["tool_calls"]
    n = len(calls)
    
    # Display the full plan
    for i, call in enumerate(calls, 1):
        cmd_str = render_tool_call(call)
        explanation = call["input"].get("explanation", "")
        prefix = f"Step {i}/{n}: " if n > 1 else ""
        console.print(f"  [bold]{prefix}{cmd_str}[/bold]")
        if explanation:
            console.print(f"    [dim]{explanation}[/dim]")
    
    # Initial confirmation
    if not yes:
        choice = Prompt.ask("Run?", choices=["y", "n", "e"], default="y")
        if choice == "n":
            return
        if choice == "e":
            # One LLM call explaining the whole chain (or single command)
            try:
                deep = call_llm_explain_chain(query, calls, build_system_prompt())
                console.print(f"\n{deep}\n")
            except Exception as e:
                console.print(f"[dim]Could not get explanation: {e}[/dim]\n")
            if Prompt.ask("Run?", choices=["y", "n"], default="y") == "n":
                return
    
    # Execute each step, stopping on failure
    for i, call in enumerate(calls, 1):
        prefix = f"Step {i}/{n}: " if n > 1 else ""
        console.print(f"\n[bold]{prefix}{render_tool_call(call)}[/bold]")
        
        # Per-step confirmation in --step mode (after the first step)
        if step_mode and i > 1 and not yes:
            if Prompt.ask(f"Run step {i}?", choices=["y", "n"], default="y") == "n":
                _print_skipped(i, calls[i-1:])
                return
        
        try:
            _execute_tool_call(call)
        except NoDataError as e:
            # Empty download — clean stop, not a crash
            console.print(f"[yellow]{e}[/yellow]")
            if i < n:
                _print_skipped(i, calls[i:])
            return
        except Exception as e:
            print_error(e)
            if i < n:
                _print_skipped(i, calls[i:])
            raise typer.Exit(code=1)


def _print_skipped(failed_step: int, remaining_calls: list[dict]) -> None:
    """Print the list of commands that were not run."""
    console.print(f"\n[yellow]Stopped on step {failed_step}. Did not run:[/yellow]")
    for call in remaining_calls:
        console.print(f"  - {render_tool_call(call)}")
```

### Empty-result handling

Today, when `_execute_tool_call` for `download` gets 0 rows, it prints a yellow warning and returns. In a chain this would look like success to the loop, and the next step (e.g. `plot`) would fail with a confusing "file not found" because no CSV was written.

**Fix:** introduce a `NoDataError` exception in `ask/errors.py`:

```python
# src/aeolus_cli/ask/errors.py
class NoDataError(Exception):
    """Raised when a download returns no rows, so chained steps cannot proceed."""
```

The download branch of `_execute_tool_call` raises `NoDataError` when `data.empty`, instead of printing a warning and returning. The chain loop catches it, prints the yellow message itself, and reports any skipped steps.

For single-command responses, the loop still catches `NoDataError` and returns cleanly — same UX as today (yellow warning, no CSV written, exit 0). No regression.

### Filename handling

The LLM is instructed via the system prompt to use identical **stems** (not full filenames — different steps have different extensions: `.csv` for download, `.png` for plot, etc.) across all steps in a chain.

The live sanity check confirmed Haiku does this correctly with the planned prompt: asked to "download NO2 from AURN site MY1 for the last 30 days and plot it", it produced:
- Step 1: `output: NO2_MY1.csv`
- Step 2: `file: NO2_MY1.csv, output: NO2_MY1.png`

No enforcement or validation on our side. If the LLM generates mismatched stems, step 2 fails with "file not found" and the chain stops cleanly — the user sees the problem and can rephrase.

## Prompt Changes

Add a new section to `prompt.py`'s behavioural instructions:

```
## Chaining Multiple Commands

You may return multiple tool calls in one response when the user explicitly
asks for multiple actions (e.g. "download X and plot it"). The commands run
in order and stop on the first failure.

Rules for chaining:

1. Only chain when the user explicitly asks for multiple actions. Downloading
   alone does NOT imply summarising or plotting — do not add steps the user
   did not ask for.

2. When steps share a file, use IDENTICAL filename STEMS across steps. The
   extensions will differ (.csv for download, .png for plot) but the stem
   must match. Example:
   - Step 1: download ... -o manchester_no2_2025.csv
   - Step 2: summarise manchester_no2_2025.csv
   - Step 3: plot manchester_no2_2025.csv -o manchester_no2_2025.png

3. Each step still needs its own confidence and explanation fields. Answer
   them per step, not for the whole chain.

4. Keep chains short. A typical chain is 2-3 steps. If a request seems to
   need more, your interpretation is probably wrong.
```

Plus one or two examples added to the static knowledge section showing chained queries and their expected tool-call shapes.

### Explain prompt change

Add `call_llm_explain_chain(user_text, tool_calls, system_prompt)` in `ask/llm.py`:

```python
def call_llm_explain_chain(user_text, tool_calls, system_prompt):
    """Ask the LLM for a deeper explanation of a workflow (one or more steps)."""
    cmds = "\n".join(f"  {i}. {render_tool_call(tc)}" for i, tc in enumerate(tool_calls, 1))
    if len(tool_calls) > 1:
        prompt = (
            f'The user asked: "{user_text}"\n\n'
            f"You generated this workflow:\n{cmds}\n\n"
            "Explain in 3-5 sentences what this workflow does overall, why the "
            "steps are in this order, and what the user will end up with. Focus "
            "on the narrative between steps, not individual command syntax."
        )
    else:
        # Single command — existing behaviour
        prompt = (
            f'The user asked: "{user_text}"\n\n'
            f"You generated this command: {cmds}\n\n"
            "Explain in 2-4 sentences what this command does, what the parameters "
            "mean, and how the user could modify it for different queries."
        )
    response = client.messages.create(
        model=_MODEL, max_tokens=_MAX_TOKENS, system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
```

The old `call_llm_explain` function is replaced by this. The orchestrator's `e` handler calls the new function regardless of chain length.

## CLI signature change

`ask/orchestrator.py` adds a `--step` flag:

```python
def ask(
    query: Optional[list[str]] = typer.Argument(None, ...),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    interactive: bool = typer.Option(False, "--interactive", "-i", ...),
    step: bool = typer.Option(False, "--step", help="Confirm each step in a chain individually"),
):
```

## Testing

### Unit tests

**`test_ask_llm.py`** — add:
- `test_parse_response_extracts_multiple_tool_calls`: mock response with 2 tool_use blocks, verify `result["type"] == "tool_calls"` and the list contains both in order.
- `test_parse_response_single_tool_call_is_list_of_one`: a single tool_use still yields `{"type": "tool_calls", "tool_calls": [one_item]}`.

**`test_ask_orchestrator.py`** — add:
- `test_chain_executes_both_steps_in_order`: mock LLM result with download + plot, verify both `aeolus.download` and `viz.plot_timeseries` are called in that order.
- `test_chain_stops_on_failure`: first step succeeds, second raises; verify third step (if any) is skipped and the skipped list is printed.
- `test_chain_stops_on_empty_data`: download returns empty DataFrame, `NoDataError` is raised, subsequent steps are skipped, exit code is 0 (not 1).
- `test_step_mode_prompts_per_step`: `--step` mode, user answers "n" at step 2, verify step 2 and later don't execute.
- `test_single_command_suppresses_step_prefix`: length-1 `tool_calls` list doesn't render "Step 1/1:".
- `test_yes_flag_runs_whole_chain`: `--yes` skips confirmation and runs all steps.

**`test_ask_prompt.py`** — add:
- `test_prompt_includes_chaining_instructions`: `build_system_prompt()` contains the words "chain" and "identical" (case-insensitive) to verify the new section is included.

**`test_ask_render.py`** — no changes. Render is per-call and unchanged.

### Live smoke tests

These are manual, run before releases, not part of CI:
- `aeolus ask "download NO2 from MY1 last 30 days and plot it"` — verify chain executes and produces both files.
- `aeolus ask "download from a site that returns nothing and plot it"` — verify clean stop with skipped list.
- `aeolus ask --step "download and summarise"` — verify per-step prompt.
- `aeolus ask sources` — verify single-command path still works and looks clean.

## Non-goals

- **Agent loops.** No tool_result feedback. The LLM plans once, we execute.
- **Cross-step validation.** We do not pre-check that step 2's input file matches step 1's output. If the LLM gets it wrong, the chain fails at execution and the user sees it.
- **Parallel execution.** Steps always run sequentially, even if they're independent.
- **Chain length limits.** No hard cap. The prompt discourages long chains; in practice 2-3 steps is typical.
- **Persistent workflow history.** No replay, no "re-run that chain". Each invocation is independent.
