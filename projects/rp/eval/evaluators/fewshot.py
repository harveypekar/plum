"""Fewshot example evaluator.

Fetches fewshot examples and their associated card data from the database,
assembles context for the judge, and runs evaluation via the engine.
"""

import json

import asyncpg

from ..engine import EvalResult, Rubric, judge, load_rubric


def _extract_card_fields(card_row: dict) -> dict:
    """Extract card fields from a DB row, handling SillyTavern v2 nesting."""
    cd = card_row.get("card_data", {})
    if isinstance(cd, str):
        cd = json.loads(cd)
    data = cd.get("data", cd)
    return {
        "name": data.get("name", card_row.get("name", "?")),
        "description": data.get("description", ""),
        "personality": data.get("personality", ""),
        "mes_example": data.get("mes_example", ""),
        "first_mes": data.get("first_mes", ""),
    }


async def evaluate_single(
    pool: asyncpg.Pool,
    aiserver_url: str,
    judge_model: str,
    example_id: int,
    rubric: Rubric | None = None,
) -> EvalResult:
    """Evaluate a single fewshot example by ID."""
    rubric = rubric or load_rubric("fewshot")

    row = await pool.fetchrow(
        "SELECT e.*, c.name as card_name, c.card_data "
        "FROM rp_fewshot_examples e "
        "LEFT JOIN rp_character_cards c ON e.card_id = c.id "
        "WHERE e.id = $1",
        example_id,
    )
    if not row:
        raise ValueError(f"Fewshot example {example_id} not found")

    card_fields = _extract_card_fields(dict(row))
    context = _build_context(dict(row), card_fields)

    return await judge(
        aiserver_url, judge_model, rubric, context,
        evaluator="fewshot",
        target_id=str(example_id),
        target_label=f"{card_fields['name']} #{example_id}",
    )


async def evaluate_batch(
    pool: asyncpg.Pool,
    aiserver_url: str,
    judge_model: str,
    card_id: int,
    limit: int = 0,
    rubric: Rubric | None = None,
) -> list[EvalResult]:
    """Evaluate all active fewshot examples for a card."""
    rubric = rubric or load_rubric("fewshot")

    card_row = await pool.fetchrow(
        "SELECT id, name, card_data FROM rp_character_cards WHERE id = $1",
        card_id,
    )
    if not card_row:
        raise ValueError(f"Card {card_id} not found")
    card_fields = _extract_card_fields(dict(card_row))

    query = (
        "SELECT * FROM rp_fewshot_examples "
        "WHERE card_id = $1 AND active = TRUE "
        "ORDER BY id"
    )
    rows = await pool.fetch(query, card_id)

    if limit and len(rows) > limit:
        rows = rows[:limit]

    return rows, card_fields, rubric


def _build_context(example: dict, card_fields: dict) -> dict:
    """Assemble the context dict for the judge from a fewshot example + card."""
    parts = []
    if card_fields["description"]:
        parts.append(card_fields["description"])
    if card_fields["personality"]:
        parts.append(f"Personality: {card_fields['personality']}")

    return {
        "card_description": "\n\n".join(parts) if parts else "(no card description)",
        "card_personality": card_fields["personality"] or "(no personality defined)",
        "card_mes_example": card_fields["mes_example"] or "(no example dialogue)",
        "user_message": example["user_message"],
        "assistant_message": example["assistant_message"],
    }


def build_context_for_row(example_row: dict, card_fields: dict) -> dict:
    """Public helper for CLI to build context from a pre-fetched row."""
    return _build_context(dict(example_row), card_fields)
