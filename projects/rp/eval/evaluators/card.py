"""Character card evaluator.

Fetches card data from the database, extracts all relevant fields,
and runs evaluation via the engine.
"""

import json

import asyncpg

from ..engine import EvalResult, Rubric, judge, load_rubric


def _extract_card_data(card_row: dict) -> dict:
    """Extract the inner data dict from a SillyTavern v2 card row."""
    cd = card_row.get("card_data", {})
    if isinstance(cd, str):
        cd = json.loads(cd)
    return cd.get("data", cd)


def _build_context(data: dict) -> dict:
    """Assemble the context dict for the judge from card data fields."""
    # Format character book entries if present
    book_text = ""
    book = data.get("character_book", {})
    if isinstance(book, dict):
        entries = book.get("entries", [])
        if entries:
            parts = []
            for e in entries:
                keys = e.get("keys", [])
                content = e.get("content", "")
                if content:
                    key_str = ", ".join(keys) if keys else "(no keys)"
                    parts.append(f"[{key_str}]\n{content}")
            book_text = "\n\n".join(parts)

    return {
        "description": data.get("description", ""),
        "personality": data.get("personality", ""),
        "mes_example": data.get("mes_example", ""),
        "first_mes": data.get("first_mes", ""),
        "scenario": data.get("scenario", ""),
        "system_prompt": data.get("system_prompt", ""),
        "post_history_instructions": data.get("post_history_instructions", ""),
        "character_book": book_text,
    }


async def evaluate_single(
    pool: asyncpg.Pool,
    aiserver_url: str,
    judge_model: str,
    card_id: int,
    rubric: Rubric | None = None,
) -> EvalResult:
    """Evaluate a single character card by ID."""
    rubric = rubric or load_rubric("card")

    row = await pool.fetchrow(
        "SELECT id, name, card_data FROM rp_character_cards WHERE id = $1",
        card_id,
    )
    if not row:
        raise ValueError(f"Card {card_id} not found")

    data = _extract_card_data(dict(row))
    char_name = data.get("name", row["name"])
    context = _build_context(data)

    return await judge(
        aiserver_url, judge_model, rubric, context,
        evaluator="card",
        target_id=str(card_id),
        target_label=char_name,
    )


async def evaluate_all(
    pool: asyncpg.Pool,
    aiserver_url: str,
    judge_model: str,
    rubric: Rubric | None = None,
) -> tuple[list[dict], Rubric]:
    """Fetch all cards for batch evaluation. Returns (rows, rubric).

    Caller drives the eval loop (same pattern as fewshot batch).
    """
    rubric = rubric or load_rubric("card")

    rows = await pool.fetch(
        "SELECT id, name, card_data FROM rp_character_cards ORDER BY id"
    )
    return [dict(r) for r in rows], rubric


def build_context_for_row(card_row: dict) -> dict:
    """Public helper for CLI to build context from a pre-fetched row."""
    data = _extract_card_data(card_row)
    return _build_context(data)
