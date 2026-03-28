"""Scenario evaluator.

Fetches scenario data from the database and runs evaluation via the engine.
"""

import json

import asyncpg

from ..engine import EvalResult, Rubric, judge, load_rubric


def _build_context(row: dict) -> dict:
    """Assemble the context dict for the judge from a scenario row."""
    settings = row.get("settings", {})
    if isinstance(settings, str):
        settings = json.loads(settings) if settings else {}
    settings_text = json.dumps(settings, indent=2) if settings else "(default settings)"

    return {
        "description": row.get("description", ""),
        "first_message": row.get("first_message", ""),
        "settings": settings_text,
    }


async def evaluate_single(
    pool: asyncpg.Pool,
    aiserver_url: str,
    judge_model: str,
    scenario_id: int,
    rubric: Rubric | None = None,
) -> EvalResult:
    """Evaluate a single scenario by ID."""
    rubric = rubric or load_rubric("scenario")

    row = await pool.fetchrow(
        "SELECT * FROM rp_scenarios WHERE id = $1", scenario_id,
    )
    if not row:
        raise ValueError(f"Scenario {scenario_id} not found")

    context = _build_context(dict(row))

    return await judge(
        aiserver_url, judge_model, rubric, context,
        evaluator="scenario",
        target_id=str(scenario_id),
        target_label=row["name"],
    )


async def evaluate_all(
    pool: asyncpg.Pool,
    aiserver_url: str,
    judge_model: str,
    rubric: Rubric | None = None,
) -> tuple[list[dict], Rubric]:
    """Fetch all scenarios for batch evaluation. Returns (rows, rubric)."""
    rubric = rubric or load_rubric("scenario")

    rows = await pool.fetch("SELECT * FROM rp_scenarios ORDER BY id")
    return [dict(r) for r in rows], rubric


def build_context_for_row(row: dict) -> dict:
    """Public helper for CLI to build context from a pre-fetched row."""
    return _build_context(row)
