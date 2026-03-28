# Conversation Report — Design Spec

**Date:** 2026-03-28
**Status:** Draft

## Goal

New `report` subcommand for `python -m projects.rp.eval` that generates a markdown document for a conversation. The report inlines all hidden pipeline events (system prompt, research, fewshot, scene state diffs, Ollama stats), runs response and scene state evals for every turn, shows full per-turn score breakdowns, and ends with aggregate metrics and Mermaid charts.

## Command Interface

```bash
python -m projects.rp.eval report --conv-id 58
python -m projects.rp.eval report --conv-id 58 --output conv58.md
python -m projects.rp.eval report --conv-id 58 --judge-model qwen3:32b --save
```

### Arguments

| Arg | Required | Default | Notes |
|-----|----------|---------|-------|
| `--conv-id` | yes | — | Conversation to report on |
| `--log-path` | no | `projects/rp/log.txt` | Custom log file path |
| `--output` | no | stdout | File path for output |
| `--judge-model` | no | `qwen3:32b` | Ollama judge model |
| `--ollama-url` | no | `$OLLAMA_URL` / `localhost:11434` | Ollama endpoint |
| `--db-url` | no | `$DATABASE_URL` | PostgreSQL connection |
| `--save` | no | false | Persist eval results to DB |
| `--dry-run` | no | false | Preview turns without running evals |
| `--limit` | no | 0 (all) | Cap number of turns to evaluate |

Inherited from `_add_common_args`: `--judge-model`, `--ollama-url`, `--db-url`, `--json`, `--dry-run`, `--save`, `--limit`. The `--output` and `--conv-id` args are report-specific.

## Data Assembly

Four steps, in order:

1. **Fetch conversation metadata from DB** — query `rp_conversations` joined with `rp_character_cards` to get card names (`user_card_name`, `ai_card_name`), model, and `created_at` date. This data is not available from the log file.

2. **Parse turns from log.txt** — `log_reader.parse_conversation(conv_id)`. Provides all pipeline events per turn: system prompt, post prompt, research injection, fewshot injection, scene state before/after, Ollama stats.

3. **Run response evals** — for every turn, build context via `response_eval.build_context_for_turn(turn, conv)` (takes two args) and call `judge()`. Uses the `response` rubric (7 dimensions). If eval fails for a turn, record the error and continue.

4. **Run scene state evals** — for every turn that has a scene state diff (`scene_state_after` is non-empty), build context via `scene_state_eval.build_context_for_turn(turn)` (takes one arg) and call `judge()`. Uses the `scene_state` rubric (5 dimensions). If eval fails, record the error and continue.

If `--save` is passed, persist results to DB via `save_metrics()` with `target_type="response"` for response evals and `target_type="scene_state"` for scene state evals.

### Error Handling

If a judge call fails for a turn, the report still renders that turn's messages and pipeline events. The eval table is replaced with an error placeholder: `> **Eval failed:** {error message}`

## Files

| File | Action | Purpose |
|------|--------|---------|
| `projects/rp/eval/cli.py` | Edit | Add `report` subcommand parser + `run_report()` |
| `projects/rp/eval/markdown.py` | Create | Markdown rendering logic |

### `markdown.py` Responsibilities

Single public function:

```python
def render_report(
    conv: Conversation,
    response_results: dict[int, EvalResult | str],   # keyed by turn_index; str = error msg
    scene_state_results: dict[int, EvalResult | str], # keyed by turn_index; str = error msg
    response_rubric: Rubric,
    scene_state_rubric: Rubric,
    judge_model: str,
    ai_card_name: str,
    user_card_name: str,
    conv_date: str,
) -> str:
```

Returns the complete markdown string. Card names and date come from the DB query in step 1.

### `cli.py` Changes

- Add `report` subparser in `build_parser()` with the arguments above
- Add `run_report()` async function that:
  1. Parses the conversation from log
  2. Warms up the judge model
  3. Iterates turns, running response + scene state evals with progress output
  4. Optionally saves results
  5. Calls `markdown.render_report()` and writes to output

## Markdown Structure

```
# Conversation {id} — {ai_card_name} × {user_card_name}
Model: {model} | Judge: {judge_model} | Turns: {n} | Date: {date}

---

## Turn 1

<details><summary>System Prompt</summary>
{system_prompt}
</details>

> **User:**
> {user_message}

<details><summary>Pipeline</summary>
**Research:** {query} → {result}
**Fewshot:** {count} examples injected
**Ollama:** {eval_duration_sec}s eval, {prompt_eval_count} tokens prompt, {eval_count} tokens generated
(Note: Ollama reports durations in nanoseconds; convert to seconds for display)
</details>

**Assistant:**

{assistant_message}

### Response Eval ({weighted_avg} avg)

| Dimension | Score | Explanation |
|-----------|-------|-------------|
| {name} | {score} | {explanation} |
| ... | ... | ... |

<details><summary>Scene State Diff</summary>

**Before:**
{scene_state_before}

**After:**
{scene_state_after}
</details>

### Scene State Eval ({weighted_avg} avg)

| Dimension | Score | Explanation |
|-----------|-------|-------------|
| {name} | {score} | {explanation} |
| ... | ... | ... |

---

[repeat for each turn]

---

## Summary

### Aggregate Scores
| Metric | Avg |
|--------|-----|
| Response Quality | {avg} |
| Scene State Quality | {avg} |

### Response Dimensions Over Time
```mermaid
xychart-beta
  title "Response Quality by Turn"
  x-axis [{turn labels}]
  y-axis "Score" 1 --> 5
  line "Character Consistency" [{scores}]
  line "Emotional Persistence" [{scores}]
  ...
```

### Scene State Dimensions Over Time
```mermaid
xychart-beta
  title "Scene State Quality by Turn"
  x-axis [{turn labels}]
  y-axis "Score" 1 --> 5
  line "Factual Accuracy" [{scores}]
  ...
```
```

### Layout Rules

- System prompt shown in `<details>` collapse on Turn 1 only (identical across turns)
- Pipeline events (research, fewshot, Ollama stats) in `<details>` collapse — omit sections with no data
- Scene state diff in `<details>` collapse — only shown for turns with state changes
- Eval tables are NOT collapsed — primary value of the report
- Mermaid xychart-beta for line charts — one line per dimension, turns on x-axis
- Scene state chart x-axis only includes turns that have scene state evals (not all turns have state updates), so labels may be e.g. `[T1, T4, T7]` rather than sequential
- Response chart x-axis includes all evaluated turns
