# Conversation Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `report` subcommand to the RP eval CLI that generates a markdown document with inlined pipeline events, per-turn eval scores, aggregate metrics, and Mermaid charts.

**Architecture:** New `markdown.py` module handles rendering. `cli.py` gets a `report` subparser and `run_report()` that orchestrates data fetching, eval execution, and markdown generation. Follows the existing pattern of other subcommands.

**Tech Stack:** Python, asyncpg, httpx (via existing eval engine), Mermaid xychart-beta for charts.

**Spec:** `docs/superpowers/specs/2026-03-28-conv-report-design.md`

---

### Task 1: Create `markdown.py` with `render_report()`

**Files:**
- Create: `projects/rp/eval/markdown.py`

- [ ] **Step 1: Create `markdown.py` with the `render_report` function**

This is the core rendering module. It takes pre-assembled data and returns a markdown string.

```python
"""Markdown report renderer for conversation evals."""

from .engine import EvalResult, Rubric
from .log_reader import Conversation, Turn


def _format_stats(stats: dict) -> str:
    """Format Ollama raw_stats into a readable line."""
    if not stats:
        return ""
    eval_dur = stats.get("eval_duration", 0) / 1e9
    prompt_count = stats.get("prompt_eval_count", 0)
    eval_count = stats.get("eval_count", 0)
    return f"**Ollama:** {eval_dur:.1f}s eval, {prompt_count} tokens prompt, {eval_count} tokens generated"


def _render_eval_table(result: EvalResult | str, rubric: Rubric, label: str) -> str:
    """Render an eval result as a markdown table, or an error placeholder."""
    if isinstance(result, str):
        return f"> **{label} eval failed:** {result}\n"

    lines = [
        f"### {label} ({result.weighted_average:.1f} avg)\n",
        "| Dimension | Score | Explanation |",
        "|-----------|-------|-------------|",
    ]
    dim_names = {d.key: d.name for d in rubric.dimensions}
    for s in result.scores:
        name = dim_names.get(s.dimension, s.dimension)
        score = str(s.score) if s.score >= 0 else "?"
        lines.append(f"| {name} | {score} | {s.explanation} |")
    return "\n".join(lines) + "\n"


def _render_pipeline(turn: Turn) -> str:
    """Render pipeline details as a collapsed section."""
    parts = []
    if turn.research_query:
        parts.append(f"**Research:** {turn.research_query} → {turn.research_result}")
    if turn.fewshot_count:
        parts.append(f"**Fewshot:** {turn.fewshot_count} examples injected")
    stats_line = _format_stats(turn.raw_stats)
    if stats_line:
        parts.append(stats_line)
    if not parts:
        return ""
    inner = "\n\n".join(parts)
    return f"<details><summary>Pipeline</summary>\n\n{inner}\n\n</details>\n"


def _render_scene_state_diff(turn: Turn) -> str:
    """Render scene state before/after as a collapsed section."""
    if not turn.scene_state_after:
        return ""
    before = turn.scene_state_before or "(none)"
    return (
        f"<details><summary>Scene State Diff</summary>\n\n"
        f"**Before:**\n{before}\n\n"
        f"**After:**\n{turn.scene_state_after}\n\n"
        f"</details>\n"
    )


def _render_turn(
    turn: Turn,
    turn_num: int,
    show_system_prompt: bool,
    response_result: EvalResult | str | None,
    scene_state_result: EvalResult | str | None,
    response_rubric: Rubric,
    scene_state_rubric: Rubric,
) -> str:
    """Render a single conversation turn."""
    sections = [f"## Turn {turn_num}\n"]

    if show_system_prompt and turn.system_prompt:
        sections.append(
            f"<details><summary>System Prompt</summary>\n\n"
            f"{turn.system_prompt}\n\n</details>\n"
        )

    # User message as blockquote
    user_lines = turn.user_message.split("\n")
    quoted = "\n> ".join(user_lines)
    sections.append(f"> **User:**\n> {quoted}\n")

    # Pipeline details
    pipeline = _render_pipeline(turn)
    if pipeline:
        sections.append(pipeline)

    # Assistant message
    sections.append(f"**Assistant:**\n\n{turn.assistant_message}\n")

    # Response eval
    if response_result is not None:
        sections.append(_render_eval_table(response_result, response_rubric, "Response Eval"))

    # Scene state diff + eval
    diff = _render_scene_state_diff(turn)
    if diff:
        sections.append(diff)
    if scene_state_result is not None:
        sections.append(_render_eval_table(scene_state_result, scene_state_rubric, "Scene State Eval"))

    return "\n".join(sections)


def _render_summary(
    response_results: dict[int, EvalResult | str],
    scene_state_results: dict[int, EvalResult | str],
    response_rubric: Rubric,
    scene_state_rubric: Rubric,
) -> str:
    """Render aggregate scores and Mermaid charts."""
    sections = ["## Summary\n"]

    # Collect valid results
    resp_evals = [r for r in response_results.values() if isinstance(r, EvalResult)]
    ss_evals = [r for r in scene_state_results.values() if isinstance(r, EvalResult)]

    # Aggregate table
    resp_avg = sum(r.weighted_average for r in resp_evals) / len(resp_evals) if resp_evals else 0
    ss_avg = sum(r.weighted_average for r in ss_evals) / len(ss_evals) if ss_evals else 0

    sections.append("### Aggregate Scores\n")
    sections.append("| Metric | Avg |")
    sections.append("|--------|-----|")
    if resp_evals:
        sections.append(f"| Response Quality | {resp_avg:.1f} |")
    if ss_evals:
        sections.append(f"| Scene State Quality | {ss_avg:.1f} |")
    sections.append("")

    # Response chart
    if len(resp_evals) >= 2:
        sections.append(_render_mermaid_chart(
            "Response Quality by Turn",
            response_results,
            response_rubric,
        ))

    # Scene state chart
    if len(ss_evals) >= 2:
        sections.append(_render_mermaid_chart(
            "Scene State Quality by Turn",
            scene_state_results,
            scene_state_rubric,
        ))

    return "\n".join(sections)


def _render_mermaid_chart(
    title: str,
    results: dict[int, EvalResult | str],
    rubric: Rubric,
) -> str:
    """Render a Mermaid xychart-beta line chart for dimension scores over turns."""
    # Filter to valid results, sorted by turn index
    valid = sorted(
        [(idx, r) for idx, r in results.items() if isinstance(r, EvalResult)],
        key=lambda x: x[0],
    )
    if not valid:
        return ""

    turn_labels = ", ".join(f'"T{idx}"' for idx, _ in valid)

    lines = [
        f"```mermaid",
        f"xychart-beta",
        f'  title "{title}"',
        f"  x-axis [{turn_labels}]",
        f'  y-axis "Score" 1 --> 5',
    ]

    for dim in rubric.dimensions:
        scores = []
        for _, result in valid:
            score_val = next(
                (s.score for s in result.scores if s.dimension == dim.key),
                -1,
            )
            scores.append(str(score_val) if score_val >= 0 else "0")
        scores_str = ", ".join(scores)
        lines.append(f'  line "{dim.name}" [{scores_str}]')

    lines.append("```\n")
    return "\n".join(lines)


def render_report(
    conv: Conversation,
    response_results: dict[int, EvalResult | str],
    scene_state_results: dict[int, EvalResult | str],
    response_rubric: Rubric,
    scene_state_rubric: Rubric,
    judge_model: str,
    ai_card_name: str,
    user_card_name: str,
    conv_date: str,
) -> str:
    """Render a full conversation report as markdown."""
    sections = []

    # Header
    sections.append(f"# Conversation {conv.conv_id} — {ai_card_name} × {user_card_name}")
    sections.append(
        f"Model: {conv.model} | Judge: {judge_model} "
        f"| Turns: {conv.turn_count} | Date: {conv_date}\n"
    )
    sections.append("---\n")

    # Turns
    for i, turn in enumerate(conv.turns):
        turn_num = i + 1
        show_system_prompt = (i == 0)
        resp = response_results.get(turn.turn_index)
        ss = scene_state_results.get(turn.turn_index)
        sections.append(_render_turn(
            turn, turn_num, show_system_prompt,
            resp, ss, response_rubric, scene_state_rubric,
        ))
        sections.append("---\n")

    # Summary
    sections.append(_render_summary(
        response_results, scene_state_results,
        response_rubric, scene_state_rubric,
    ))

    return "\n".join(sections)
```

- [ ] **Step 2: Verify the file is syntactically valid**

Run: `cd /mnt/d/prg/plum && source projects/aiserver/.venv/bin/activate && python -c "import projects.rp.eval.markdown"`
Expected: no output (clean import)

- [ ] **Step 3: Commit**

```bash
git add projects/rp/eval/markdown.py
git commit -m "feat(rp-eval): add markdown report renderer"
```

---

### Task 2: Add `report` subcommand to `cli.py`

**Files:**
- Modify: `projects/rp/eval/cli.py`

- [ ] **Step 1: Add report subparser in `build_parser()`**

In `build_parser()`, after the `p_show` block (around line 107), add:

```python
    p_report = sub.add_parser("report", help="Generate markdown conversation report")
    _add_common_args(p_report)
    p_report.add_argument("--conv-id", type=int, required=True, help="Conversation ID")
    p_report.add_argument("--log-path", default=None, help="Custom log.txt path")
    p_report.add_argument("--output", default=None, help="Output file path (default: stdout)")
```

- [ ] **Step 2: Add `run_report()` async function**

Add before the `main()` function:

```python
async def run_report(args, pool: asyncpg.Pool, ollama_url: str):
    from .log_reader import parse_conversation
    from .evaluators import response as response_eval
    from .evaluators import scene_state as scene_state_eval
    from .markdown import render_report

    log_path = Path(args.log_path) if args.log_path else None
    response_rubric = load_rubric("response", Path(args.rubric) if args.rubric else None)
    scene_state_rubric = load_rubric("scene_state")

    # Step 1: Fetch conversation metadata from DB
    conv_row = await pool.fetchrow("""
        SELECT c.model, c.created_at,
               ai.name AS ai_card_name, u.name AS user_card_name
        FROM rp_conversations c
        JOIN rp_character_cards ai ON ai.id = c.ai_card_id
        JOIN rp_character_cards u ON u.id = c.user_card_id
        WHERE c.id = $1
    """, args.conv_id)
    if not conv_row:
        print(f"Conversation {args.conv_id} not found in database", file=sys.stderr)
        sys.exit(1)

    ai_card_name = conv_row["ai_card_name"]
    user_card_name = conv_row["user_card_name"]
    conv_date = conv_row["created_at"].strftime("%Y-%m-%d")

    # Step 2: Parse turns from log
    conv = parse_conversation(args.conv_id, log_path)
    if not conv:
        print(f"Conversation {args.conv_id} not found in log", file=sys.stderr)
        sys.exit(1)

    resp_turns = response_eval.get_evaluable_turns(conv)
    ss_turns = scene_state_eval.get_evaluable_turns(conv)

    if args.limit:
        resp_turns = resp_turns[:args.limit]
        ss_turns = ss_turns[:args.limit]

    if args.dry_run:
        print(f"Would generate report for conv {args.conv_id}")
        print(f"  AI: {ai_card_name}  User: {user_card_name}  Model: {conv.model}")
        print(f"  Response turns: {len(resp_turns)}  Scene state turns: {len(ss_turns)}")
        return

    total_evals = len(resp_turns) + len(ss_turns)
    print(f"Judge: {args.judge_model}  Conv: {args.conv_id}  Evals: {total_evals}")
    print(f"  {ai_card_name} × {user_card_name}  Model: {conv.model}")
    await _warmup_model(ollama_url, args.judge_model)

    # Step 3: Run response evals
    response_results: dict[int, EvalResult | str] = {}
    eval_times: list[float] = []
    all_response_results: list[EvalResult] = []

    for i, turn in enumerate(resp_turns):
        preview = turn.user_message[:60].replace("\n", " ")
        print(f"[resp {i+1}/{len(resp_turns)}] turn{turn.turn_index} {preview}...", end="", flush=True)
        try:
            context = response_eval.build_context_for_turn(turn, conv)
            t0 = time.time()
            result = await judge(
                ollama_url, args.judge_model, response_rubric, context,
                evaluator="response",
                target_id=f"{conv.conv_id}:{turn.turn_index}",
                target_label=f"conv{conv.conv_id} turn{turn.turn_index}",
            )
            elapsed = time.time() - t0
            eval_times.append(elapsed)
            response_results[turn.turn_index] = result
            all_response_results.append(result)
            _print_progress(result, i, len(resp_turns), elapsed, eval_times)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            print(f" ERROR: {msg}")
            response_results[turn.turn_index] = msg

    # Step 4: Run scene state evals
    scene_state_results: dict[int, EvalResult | str] = {}
    all_ss_results: list[EvalResult] = []
    eval_times.clear()

    for i, turn in enumerate(ss_turns):
        preview = turn.user_message[:60].replace("\n", " ")
        print(f"[scene {i+1}/{len(ss_turns)}] turn{turn.turn_index} {preview}...", end="", flush=True)
        try:
            context = scene_state_eval.build_context_for_turn(turn)
            t0 = time.time()
            result = await judge(
                ollama_url, args.judge_model, scene_state_rubric, context,
                evaluator="scene_state",
                target_id=f"{conv.conv_id}:{turn.turn_index}",
                target_label=f"conv{conv.conv_id} turn{turn.turn_index}",
            )
            elapsed = time.time() - t0
            eval_times.append(elapsed)
            scene_state_results[turn.turn_index] = result
            all_ss_results.append(result)
            _print_progress(result, i, len(ss_turns), elapsed, eval_times)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            print(f" ERROR: {msg}")
            scene_state_results[turn.turn_index] = msg

    # Save if requested
    if args.save:
        if all_response_results:
            await _save_results(all_response_results, "response", response_rubric.name, pool)
        if all_ss_results:
            await _save_results(all_ss_results, "scene_state", scene_state_rubric.name, pool)

    # Render markdown
    md = render_report(
        conv, response_results, scene_state_results,
        response_rubric, scene_state_rubric,
        args.judge_model, ai_card_name, user_card_name, conv_date,
    )

    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"\nReport written to {args.output}")
    else:
        print(f"\n{'=' * 60}\n")
        print(md)
```

- [ ] **Step 3: Wire `report` into `main()` dispatch**

In `main()`, add the `report` branch after the `scenario` elif (around line 578):

```python
        elif args.command == "report":
            await run_report(args, pool, ollama_url)
```

- [ ] **Step 4: Verify CLI parses correctly**

Run: `cd /mnt/d/prg/plum && source projects/aiserver/.venv/bin/activate && python -m projects.rp.eval report --help`
Expected: shows help with `--conv-id`, `--output`, `--log-path`, plus common args

- [ ] **Step 5: Verify dry-run works**

Run: `cd /mnt/d/prg/plum && source projects/aiserver/.venv/bin/activate && python -m projects.rp.eval report --conv-id 58 --dry-run`
Expected: prints conversation metadata and turn counts without running evals

- [ ] **Step 6: Commit**

```bash
git add projects/rp/eval/cli.py
git commit -m "feat(rp-eval): add report subcommand for markdown conversation reports"
```

---

### Task 3: End-to-end test

**Files:** none (manual verification)

- [ ] **Step 1: Run a full report on a real conversation**

Run: `cd /mnt/d/prg/plum && source projects/aiserver/.venv/bin/activate && python -m projects.rp.eval report --conv-id 58 --output /tmp/conv58.md --save`
Expected: progress output as evals run, then "Report written to /tmp/conv58.md"

- [ ] **Step 2: Inspect the generated markdown**

Check `/tmp/conv58.md` for:
- Header with card names, model, date
- Turn sections with user/assistant messages
- System prompt collapsed in Turn 1 only
- Pipeline details collapsed where present
- Response eval tables (7 dimensions) on each turn
- Scene state diff + eval tables on turns with state changes
- Summary with aggregate scores
- Mermaid charts at the end

- [ ] **Step 3: Final commit if any fixes were needed**

```bash
git add projects/rp/eval/markdown.py projects/rp/eval/cli.py
git commit -m "fix(rp-eval): report command polish from end-to-end test"
```
