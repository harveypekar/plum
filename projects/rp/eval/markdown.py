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
        "```mermaid",
        "xychart-beta",
        f'  title "{title}"',
        f"  x-axis [{turn_labels}]",
        '  y-axis "Score" 1 --> 5',
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
