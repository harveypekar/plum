"""Score aggregation and output formatting for eval results."""

from dataclasses import dataclass

from .engine import EvalResult, Rubric


@dataclass
class AggregateReport:
    evaluator: str
    target_label: str
    total_items: int
    dimension_averages: dict[str, float]
    dimension_weights: dict[str, float]
    weighted_overall: float
    worst_items: list[tuple[str, str, float]]  # (id, label, weighted_avg)
    best_items: list[tuple[str, str, float]]
    scale_max: int


def aggregate(results: list[EvalResult], rubric: Rubric, label: str = "") -> AggregateReport:
    """Compute per-dimension averages and identify best/worst items."""
    if not results:
        return AggregateReport(
            evaluator="", target_label=label, total_items=0,
            dimension_averages={}, dimension_weights={},
            weighted_overall=0.0, worst_items=[], best_items=[],
            scale_max=rubric.scale_max,
        )

    dim_weights = {d.key: d.weight for d in rubric.dimensions}
    dim_totals: dict[str, list[int]] = {d.key: [] for d in rubric.dimensions}

    for result in results:
        for s in result.scores:
            if s.score >= 0:
                dim_totals[s.dimension].append(s.score)

    dim_avgs = {}
    for key, values in dim_totals.items():
        dim_avgs[key] = sum(values) / len(values) if values else 0.0

    overall_sum = sum(dim_avgs[k] * dim_weights[k] for k in dim_avgs)
    overall_weight = sum(dim_weights[k] for k in dim_avgs if dim_avgs[k] > 0)
    overall = overall_sum / overall_weight if overall_weight else 0.0

    ranked = sorted(results, key=lambda r: r.weighted_average)
    worst = [(r.target_id, r.target_label, r.weighted_average) for r in ranked[:5]]
    best = [(r.target_id, r.target_label, r.weighted_average) for r in reversed(ranked[-5:])]

    return AggregateReport(
        evaluator=results[0].evaluator,
        target_label=label,
        total_items=len(results),
        dimension_averages=dim_avgs,
        dimension_weights=dim_weights,
        weighted_overall=overall,
        worst_items=worst,
        best_items=best,
        scale_max=rubric.scale_max,
    )


def format_single(result: EvalResult, rubric: Rubric) -> str:
    """Format a single eval result as a compact one-liner + detail."""
    dim_weights = {d.key: d.weight for d in rubric.dimensions}
    parts = []
    for s in result.scores:
        w = dim_weights.get(s.dimension, 1.0)
        tag = f" ({w}x)" if w != 1.0 else ""
        mark = str(s.score) if s.score >= 0 else "?"
        parts.append(f"{s.dimension}:{mark}{tag}")
    header = f"  [{result.target_label}] avg={result.weighted_average:.1f}  {' '.join(parts)}"

    detail_lines = []
    for s in result.scores:
        if s.explanation:
            detail_lines.append(f"    {s.dimension}: {s.explanation}")

    return header + ("\n" + "\n".join(detail_lines) if detail_lines else "")


def format_report(report: AggregateReport) -> str:
    """Format an aggregate report with bar charts and rankings."""
    if report.total_items == 0:
        return f"No items to report for {report.target_label}."

    mx = report.scale_max
    lines = [
        f"\n{'=' * 60}",
        f"  {report.evaluator.upper()} QUALITY: {report.target_label} ({report.total_items} items)",
        f"  Overall: {report.weighted_overall:.1f}/{mx}",
        f"{'=' * 60}",
        "",
    ]

    # Dimension averages with bar charts
    max_name_len = max(len(d.name) for d in _iter_dims(report)) if report.dimension_averages else 0
    for key, avg in report.dimension_averages.items():
        weight = report.dimension_weights.get(key, 1.0)
        name = key.replace("_", " ").title()
        bar_len = 20
        filled = int(round(avg / mx * bar_len))
        bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
        weight_tag = f" ({weight}x)" if weight != 1.0 else ""
        lines.append(f"  {name:<{max_name_len + 5}} {avg:.1f}/{mx}  {bar}{weight_tag}")

    if report.worst_items:
        lines.append(f"\n  Bottom {len(report.worst_items)}:")
        for tid, label, avg in report.worst_items:
            lines.append(f"    #{tid:<4} {avg:.1f}  {label}")

    if report.best_items:
        lines.append(f"\n  Top {len(report.best_items)}:")
        for tid, label, avg in report.best_items:
            lines.append(f"    #{tid:<4} {avg:.1f}  {label}")

    lines.append("")
    return "\n".join(lines)


def to_json(report: AggregateReport, results: list[EvalResult]) -> dict:
    """Serialize report + individual results to JSON-friendly dict."""
    return {
        "evaluator": report.evaluator,
        "target_label": report.target_label,
        "total_items": report.total_items,
        "weighted_overall": round(report.weighted_overall, 2),
        "dimension_averages": {k: round(v, 2) for k, v in report.dimension_averages.items()},
        "worst": [{"id": i, "label": label, "avg": round(a, 2)} for i, label, a in report.worst_items],
        "best": [{"id": i, "label": label, "avg": round(a, 2)} for i, label, a in report.best_items],
        "results": [
            {
                "target_id": r.target_id,
                "target_label": r.target_label,
                "weighted_average": round(r.weighted_average, 2),
                "scores": [
                    {"dimension": s.dimension, "score": s.score, "explanation": s.explanation}
                    for s in r.scores
                ],
            }
            for r in results
        ],
    }


def _iter_dims(report):
    """Helper to yield pseudo-dimension objects for name formatting."""
    for key in report.dimension_averages:

        class _D:
            pass

        d = _D()
        d.name = key.replace("_", " ").title()
        yield d
