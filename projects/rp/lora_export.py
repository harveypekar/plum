"""Export conversation data as ShareGPT-format training pairs for LoRA fine-tuning.

Reads conversations from the DB, assembles the system prompt from character cards
and pipeline template, and outputs multi-turn ShareGPT JSON suitable for
unsloth/axolotl training.

Usage:
    # Export all conversations for a user card
    python -m projects.rp.lora_export --user-card-id 11

    # Export specific conversations
    python -m projects.rp.lora_export --conv-ids 13,62,68

    # Only export conversations with min message count
    python -m projects.rp.lora_export --user-card-id 11 --min-messages 20

    # Filter by minimum eval score (requires eval results)
    python -m projects.rp.lora_export --user-card-id 11 --min-score 3.5
"""

import argparse
import asyncio
import json
import logging

import asyncpg

from .pipeline import DEFAULT_PROMPT_TEMPLATE, _split_template, render_template

logging.basicConfig(level=logging.INFO, format="%(message)s")
_log = logging.getLogger(__name__)


async def _get_pool():
    import os
    return await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=2)


def _build_system_prompt(ai_card: dict, user_card: dict, scenario: dict) -> str:
    """Reconstruct the system prompt as the pipeline would build it."""
    ai_data = ai_card.get("data", ai_card)
    user_data = user_card.get("data", user_card)

    values = {
        "scenario": scenario.get("description", ""),
        "description": ai_data.get("description", ""),
        "personality": ai_data.get("personality", ""),
        "mes_example": ai_data.get("mes_example", ""),
        "char": ai_data.get("name", "Character"),
        "user": user_data.get("name", "User"),
        "user_description": user_data.get("description", ""),
        "user_pronouns": user_data.get("pronouns", ""),
        "char_pronouns": ai_data.get("pronouns", ""),
    }

    system_part, post_part = _split_template(DEFAULT_PROMPT_TEMPLATE)
    system_prompt = render_template(system_part, values)

    # Apply variable substitution
    char_name = ai_data.get("name", "Character")
    user_name = user_data.get("name", "User")
    for var, val in [("${user}", user_name), ("${char}", char_name),
                     ("${scenario}", scenario.get("description", ""))]:
        system_prompt = system_prompt.replace(var, val)

    if post_part:
        post_prompt = render_template(post_part, values)
        for var, val in [("${user}", user_name), ("${char}", char_name)]:
            post_prompt = post_prompt.replace(var, val)
        system_prompt += "\n\n" + post_prompt

    return system_prompt


async def _get_conv_data(pool, conv_id: int) -> dict | None:
    """Fetch conversation with its cards, scenario, and messages."""
    conv = await pool.fetchrow(
        "SELECT id, ai_card_id, user_card_id, scenario_id, model "
        "FROM rp_conversations WHERE id = $1", conv_id)
    if not conv:
        return None

    ai_row = await pool.fetchrow(
        "SELECT card_data FROM rp_character_cards WHERE id = $1", conv["ai_card_id"])
    user_row = await pool.fetchrow(
        "SELECT card_data FROM rp_character_cards WHERE id = $1", conv["user_card_id"])
    if not ai_row or not user_row:
        return None
    ai_card = ai_row["card_data"] if isinstance(ai_row["card_data"], dict) else json.loads(ai_row["card_data"])
    user_card = user_row["card_data"] if isinstance(user_row["card_data"], dict) else json.loads(user_row["card_data"])

    scenario = {}
    if conv["scenario_id"]:
        row = await pool.fetchrow(
            "SELECT name, description, settings FROM rp_scenarios WHERE id = $1",
            conv["scenario_id"])
        if row:
            scenario = dict(row)

    messages = await pool.fetch(
        "SELECT id, role, content FROM rp_messages "
        "WHERE conversation_id = $1 ORDER BY sequence", conv_id)

    return {
        "conv_id": conv_id,
        "ai_card": ai_card,
        "user_card": user_card,
        "scenario": scenario,
        "messages": [dict(m) for m in messages],
    }


def _conv_to_sharegpt(conv_data: dict) -> dict:
    """Convert a conversation to ShareGPT multi-turn format."""
    system_prompt = _build_system_prompt(
        conv_data["ai_card"], conv_data["user_card"], conv_data["scenario"])

    conversations = [{"from": "system", "value": system_prompt}]
    for msg in conv_data["messages"]:
        role = "human" if msg["role"] == "user" else "gpt"
        conversations.append({"from": role, "value": msg["content"]})

    ai_data = conv_data["ai_card"].get("data", conv_data["ai_card"])
    return {
        "conversations": conversations,
        "metadata": {
            "conv_id": conv_data["conv_id"],
            "character": ai_data.get("name", "unknown"),
        },
    }


def truncate_by_score(
    messages: list[dict],
    scores: dict[int, float],
    min_score: float,
    include_unscored: bool = False,
) -> list[dict]:
    """Truncate a message list at the first assistant message below threshold."""
    result = []
    for msg in messages:
        if msg["role"] == "assistant":
            msg_score = scores.get(msg["id"])
            if msg_score is None and not include_unscored:
                if result and result[-1]["role"] == "user":
                    result.pop()
                break
            elif msg_score is not None and msg_score < min_score:
                if result and result[-1]["role"] == "user":
                    result.pop()
                break
        result.append(msg)
    return result


async def main():
    parser = argparse.ArgumentParser(description="Export LoRA training data")
    parser.add_argument("--user-card-id", type=int, help="Export all convs for this user card")
    parser.add_argument("--conv-ids", type=str, help="Comma-separated conversation IDs")
    parser.add_argument("--min-messages", type=int, default=10, help="Min messages per conv (default: 10)")
    parser.add_argument("--min-msg-score", type=float, default=0,
                        help="Min per-message eval score to include (0 = no filter)")
    parser.add_argument("--include-unscored", action="store_true",
                        help="Include messages without scores (default: exclude)")
    parser.add_argument("--output", "-o", type=str, default="-", help="Output file (default: stdout)")
    args = parser.parse_args()

    pool = await _get_pool()

    # Get conversation IDs
    if args.conv_ids:
        conv_ids = [int(x.strip()) for x in args.conv_ids.split(",")]
    elif args.user_card_id:
        rows = await pool.fetch(
            "SELECT c.id FROM rp_conversations c "
            "JOIN rp_messages m ON m.conversation_id = c.id "
            "WHERE c.user_card_id = $1 "
            "GROUP BY c.id HAVING count(m.id) >= $2 "
            "ORDER BY c.id",
            args.user_card_id, args.min_messages)
        conv_ids = [r["id"] for r in rows]
    else:
        parser.error("Specify --user-card-id or --conv-ids")

    _log.info("Found %d conversations", len(conv_ids))

    results = []
    for conv_id in conv_ids:
        conv_data = await _get_conv_data(pool, conv_id)
        if not conv_data:
            _log.warning("Skipping conv %d: missing data", conv_id)
            continue

        original_turns = len([m for m in conv_data["messages"] if m["role"] == "assistant"])

        if args.min_msg_score > 0:
            msg_ids = [m["id"] for m in conv_data["messages"] if m["role"] == "assistant"]
            if msg_ids:
                score_rows = await pool.fetch(
                    "SELECT target_id, weighted_average FROM rp_eval_metrics "
                    "WHERE target_type = 'message' AND target_id = ANY($1::text[])",
                    [f"msg:{mid}" for mid in msg_ids],
                )
                scores = {}
                for row in score_rows:
                    mid = int(row["target_id"].split(":")[1])
                    scores[mid] = float(row["weighted_average"])

                conv_data["messages"] = truncate_by_score(
                    conv_data["messages"], scores, args.min_msg_score,
                    include_unscored=args.include_unscored,
                )

        if not conv_data["messages"]:
            _log.warning("Skipping conv %d: no messages after filtering", conv_id)
            continue

        entry = _conv_to_sharegpt(conv_data)
        exported_turns = len([m for m in entry["conversations"] if m["from"] == "gpt"])
        entry["metadata"]["original_turns"] = original_turns
        entry["metadata"]["exported_turns"] = exported_turns
        results.append(entry)
        _log.info("  conv %d: %s — %d/%d turns", conv_id,
                  entry["metadata"]["character"], exported_turns, original_turns)

    await pool.close()

    # Write output
    output = json.dumps(results, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(output)
    else:
        with open(args.output, "w") as f:
            f.write(output)
        _log.info("Wrote %d conversations (%d total turns) to %s",
                  len(results),
                  sum(r["metadata"]["exported_turns"] for r in results),
                  args.output)


if __name__ == "__main__":
    asyncio.run(main())
