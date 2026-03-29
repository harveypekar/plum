import hashlib
import json
import os
import asyncpg
from pathlib import Path

_pool: asyncpg.Pool | None = None


async def _init_connection(conn):
    await conn.set_type_codec(
        'jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog'
    )


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            os.environ.get("DATABASE_URL", "postgresql://plum@localhost:5432/plum"),
            min_size=1,
            max_size=5,
            init=_init_connection,
        )
    return _pool


async def init_schema():
    """Run schema.sql to create tables if they don't exist."""
    pool = await get_pool()
    schema = (Path(__file__).parent / "schema.sql").read_text()
    async with pool.acquire() as conn:
        await conn.execute(schema)


async def close():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# -- Cards --

async def list_cards() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, name, avatar IS NOT NULL as has_avatar, card_data, "
        "created_at::text, updated_at::text FROM rp_character_cards ORDER BY name"
    )
    return [dict(r) for r in rows]


async def get_card(card_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, avatar IS NOT NULL as has_avatar, card_data, "
        "created_at::text, updated_at::text FROM rp_character_cards WHERE id = $1",
        card_id,
    )
    return dict(row) if row else None


async def find_card_by_name(name: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, avatar IS NOT NULL as has_avatar, card_data, "
        "created_at::text, updated_at::text FROM rp_character_cards WHERE name = $1",
        name,
    )
    return dict(row) if row else None


async def create_card(name: str, card_data: dict, avatar: bytes | None = None) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO rp_character_cards (name, card_data, avatar) "
        "VALUES ($1, $2, $3) RETURNING id, name, avatar IS NOT NULL as has_avatar, "
        "card_data, created_at::text, updated_at::text",
        name, card_data, avatar,
    )
    return dict(row)


async def update_card(card_id: int, name: str, card_data: dict, avatar: bytes | None = None) -> dict | None:
    pool = await get_pool()
    if avatar is not None:
        row = await pool.fetchrow(
            "UPDATE rp_character_cards SET name=$2, card_data=$3, avatar=$4, "
            "updated_at=NOW() WHERE id=$1 RETURNING id, name, avatar IS NOT NULL as has_avatar, "
            "card_data, created_at::text, updated_at::text",
            card_id, name, card_data, avatar,
        )
    else:
        row = await pool.fetchrow(
            "UPDATE rp_character_cards SET name=$2, card_data=$3, "
            "updated_at=NOW() WHERE id=$1 RETURNING id, name, avatar IS NOT NULL as has_avatar, "
            "card_data, created_at::text, updated_at::text",
            card_id, name, card_data,
        )
    return dict(row) if row else None


async def delete_card(card_id: int) -> bool:
    pool = await get_pool()
    result = await pool.execute("DELETE FROM rp_character_cards WHERE id = $1", card_id)
    return result == "DELETE 1"


async def get_card_avatar(card_id: int) -> bytes | None:
    pool = await get_pool()
    return await pool.fetchval("SELECT avatar FROM rp_character_cards WHERE id = $1", card_id)


async def set_card_avatar(card_id: int, avatar: bytes) -> bool:
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE rp_character_cards SET avatar=$2, updated_at=NOW() WHERE id=$1",
        card_id, avatar,
    )
    return result == "UPDATE 1"


# -- Scenarios --

async def list_scenarios() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, name, description, first_message, settings, "
        "created_at::text, updated_at::text FROM rp_scenarios ORDER BY name"
    )
    return [dict(r) for r in rows]


async def get_scenario(scenario_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, description, first_message, settings, "
        "created_at::text, updated_at::text FROM rp_scenarios WHERE id = $1",
        scenario_id,
    )
    return dict(row) if row else None


async def find_scenario_by_name(name: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, description, first_message, settings, "
        "created_at::text, updated_at::text FROM rp_scenarios WHERE name = $1",
        name,
    )
    return dict(row) if row else None


async def create_scenario(name: str, description: str, settings: dict,
                           first_message: str = "") -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO rp_scenarios (name, description, first_message, settings) "
        "VALUES ($1, $2, $3, $4) RETURNING id, name, description, first_message, "
        "settings, created_at::text, updated_at::text",
        name, description, first_message, settings,
    )
    return dict(row)


async def update_scenario(scenario_id: int, name: str, description: str,
                            settings: dict, first_message: str = "") -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "UPDATE rp_scenarios SET name=$2, description=$3, first_message=$4, "
        "settings=$5, updated_at=NOW() WHERE id=$1 RETURNING id, name, description, "
        "first_message, settings, created_at::text, updated_at::text",
        scenario_id, name, description, first_message, settings,
    )
    return dict(row) if row else None


async def delete_scenario(scenario_id: int) -> bool:
    pool = await get_pool()
    result = await pool.execute("DELETE FROM rp_scenarios WHERE id = $1", scenario_id)
    return result == "DELETE 1"


# -- Conversations --

async def list_conversations() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT c.id, c.user_card_id, c.ai_card_id, c.scenario_id, c.model, "
        "c.created_at::text, c.updated_at::text, "
        "uc.name as user_name, ac.name as ai_name "
        "FROM rp_conversations c "
        "JOIN rp_character_cards uc ON c.user_card_id = uc.id "
        "JOIN rp_character_cards ac ON c.ai_card_id = ac.id "
        "ORDER BY c.updated_at DESC"
    )
    return [dict(r) for r in rows]


async def create_conversation(user_card_id: int, ai_card_id: int,
                               scenario_id: int | None, model: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO rp_conversations (user_card_id, ai_card_id, scenario_id, model) "
        "VALUES ($1, $2, $3, $4) RETURNING id, user_card_id, ai_card_id, scenario_id, "
        "model, scene_state, scene_state_msg_id, summary_msg_id, created_at::text, updated_at::text",
        user_card_id, ai_card_id, scenario_id, model,
    )
    return dict(row)


async def get_conversation(conv_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, user_card_id, ai_card_id, scenario_id, model, scene_state, scene_state_msg_id, "
        "summary_msg_id, created_at::text, updated_at::text FROM rp_conversations WHERE id = $1",
        conv_id,
    )
    return dict(row) if row else None


async def update_scene_state(conv_id: int, scene_state: str, msg_id: int | None = None) -> bool:
    pool = await get_pool()
    if msg_id is not None:
        result = await pool.execute(
            "UPDATE rp_conversations SET scene_state=$2, scene_state_msg_id=$3, updated_at=NOW() WHERE id=$1",
            conv_id, scene_state, msg_id,
        )
    else:
        result = await pool.execute(
            "UPDATE rp_conversations SET scene_state=$2, updated_at=NOW() WHERE id=$1",
            conv_id, scene_state,
        )
    return result == "UPDATE 1"


async def delete_conversation(conv_id: int) -> bool:
    pool = await get_pool()
    result = await pool.execute("DELETE FROM rp_conversations WHERE id = $1", conv_id)
    return result == "DELETE 1"


# -- Messages --

async def delete_all_messages(conv_id: int):
    pool = await get_pool()
    await pool.execute("DELETE FROM rp_messages WHERE conversation_id = $1", conv_id)


async def get_messages(conv_id: int) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, conversation_id, role, content, raw_response, sequence, "
        "created_at::text FROM rp_messages WHERE conversation_id = $1 ORDER BY sequence",
        conv_id,
    )
    return [dict(r) for r in rows]


async def add_message(conv_id: int, role: str, content: str,
                      raw_response: dict | None = None) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO rp_messages (conversation_id, role, content, raw_response, sequence) "
        "VALUES ($1, $2, $3, $4, "
        "(SELECT COALESCE(MAX(sequence), 0) + 1 FROM rp_messages WHERE conversation_id = $1)) "
        "RETURNING id, conversation_id, role, content, "
        "raw_response, sequence, created_at::text",
        conv_id, role, content, raw_response,
    )
    await pool.execute(
        "UPDATE rp_conversations SET updated_at = NOW() WHERE id = $1", conv_id
    )
    return dict(row)


async def update_message(msg_id: int, content: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "UPDATE rp_messages SET content = $2 WHERE id = $1 "
        "RETURNING id, conversation_id, role, content, raw_response, sequence, created_at::text",
        msg_id, content,
    )
    return dict(row) if row else None


async def delete_message(msg_id: int) -> bool:
    pool = await get_pool()
    result = await pool.execute("DELETE FROM rp_messages WHERE id = $1", msg_id)
    return result == "DELETE 1"


# -- First Message Cache --

def _hash_data(data) -> str:
    """Stable hash of any JSON-serializable data."""
    raw = json.dumps(data, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def compute_card_hash(card: dict) -> str:
    """Hash the card's identity + voice-relevant fields.

    Includes card ID to prevent cross-card cache collisions — two different
    characters with similar descriptions must never share a cached first message.
    """
    data = card.get("card_data", {}).get("data", card.get("card_data", {}))
    relevant = {
        "id": card.get("id"),
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "personality": data.get("personality", ""),
        "system_prompt": data.get("system_prompt", ""),
        "first_mes": data.get("first_mes", ""),
        "mes_example": data.get("mes_example", ""),
    }
    return _hash_data(relevant)


def compute_scenario_hash(scenario: dict | None) -> str:
    """Hash the scenario's content fields."""
    if not scenario:
        return _hash_data({"none": True})
    return _hash_data({
        "description": scenario.get("description", ""),
        "first_message": scenario.get("first_message", ""),
    })


def compute_combo_hash(card_hash: str, scenario_hash: str, model: str) -> str:
    """Combine card + scenario + model into a single lookup hash."""
    return _hash_data({"card": card_hash, "scenario": scenario_hash, "model": model})


async def get_cached_first_message(combo_hash: str, card_hash: str, scenario_hash: str) -> str | None:
    """Return cached first message if combo_hash matches AND component hashes are still fresh."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT content, card_hash, scenario_hash FROM rp_first_message_cache WHERE combo_hash = $1",
        combo_hash,
    )
    if not row:
        return None
    # Verify component hashes haven't drifted
    if row["card_hash"] != card_hash or row["scenario_hash"] != scenario_hash:
        await pool.execute("DELETE FROM rp_first_message_cache WHERE combo_hash = $1", combo_hash)
        return None
    return row["content"]


async def set_cached_first_message(combo_hash: str, card_hash: str, scenario_hash: str, model: str, content: str):
    """Store or update a cached first message."""
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO rp_first_message_cache (combo_hash, card_hash, scenario_hash, model, content) "
        "VALUES ($1, $2, $3, $4, $5) "
        "ON CONFLICT (combo_hash) DO UPDATE SET card_hash=$2, scenario_hash=$3, content=$5, created_at=NOW()",
        combo_hash, card_hash, scenario_hash, model, content,
    )


# -- Few-shot Examples --

async def search_fewshot_examples(embedding: list[float], card_id: int,
                                   limit: int = 2) -> list[dict]:
    """Return the closest few-shot examples for a card by cosine similarity."""
    pool = await get_pool()
    embedding_str = "[" + ",".join(str(f) for f in embedding) + "]"
    rows = await pool.fetch(
        "SELECT id, scene_context, user_message, assistant_message, token_estimate, "
        "1 - (embedding <=> $1::vector) as similarity "
        "FROM rp_fewshot_examples WHERE active AND card_id = $3 "
        "ORDER BY embedding <=> $1::vector LIMIT $2",
        embedding_str, limit, card_id,
    )
    return [dict(r) for r in rows]


async def add_fewshot_example(card_id: int, scene_context: str, user_message: str,
                               assistant_message: str, embedding: list[float],
                               model: str, token_estimate: int) -> dict:
    """Insert a new few-shot example and return the created row."""
    pool = await get_pool()
    embedding_str = "[" + ",".join(str(f) for f in embedding) + "]"
    row = await pool.fetchrow(
        "INSERT INTO rp_fewshot_examples "
        "(card_id, scene_context, user_message, assistant_message, embedding, model, token_estimate) "
        "VALUES ($1, $2, $3, $4, $5::vector, $6, $7) "
        "RETURNING id, card_id, scene_context, user_message, assistant_message, "
        "model, token_estimate, active, created_at::text",
        card_id, scene_context, user_message, assistant_message, embedding_str,
        model, token_estimate,
    )
    return dict(row)


# -- Conversation Summaries --

async def get_latest_summary(conv_id: int) -> dict | None:
    """Return the most recent summary for a conversation."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, conversation_id, summary, through_msg_id, through_sequence, "
        "msg_count, token_estimate, created_at::text "
        "FROM rp_conversation_summaries "
        "WHERE conversation_id = $1 ORDER BY through_sequence DESC LIMIT 1",
        conv_id,
    )
    return dict(row) if row else None


async def save_summary(conv_id: int, summary: str, through_msg_id: int,
                       through_sequence: int, msg_count: int,
                       token_estimate: int) -> dict:
    """Insert a new summary row."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO rp_conversation_summaries "
        "(conversation_id, summary, through_msg_id, through_sequence, msg_count, token_estimate) "
        "VALUES ($1, $2, $3, $4, $5, $6) "
        "RETURNING id, conversation_id, summary, through_msg_id, through_sequence, "
        "msg_count, token_estimate, created_at::text",
        conv_id, summary, through_msg_id, through_sequence, msg_count, token_estimate,
    )
    return dict(row)


async def delete_summaries(conv_id: int):
    """Delete all summaries for a conversation (used on restart)."""
    pool = await get_pool()
    await pool.execute(
        "DELETE FROM rp_conversation_summaries WHERE conversation_id = $1", conv_id
    )
    await pool.execute(
        "UPDATE rp_conversations SET summary_msg_id = NULL WHERE id = $1", conv_id
    )


async def update_summary_msg_id(conv_id: int, msg_id: int) -> bool:
    """Update the summary tracking column on the conversation."""
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE rp_conversations SET summary_msg_id=$2, updated_at=NOW() WHERE id=$1",
        conv_id, msg_id,
    )
    return result == "UPDATE 1"


async def count_fewshot_examples(card_id: int | None = None) -> int:
    """Return the count of active few-shot examples, optionally filtered by card."""
    pool = await get_pool()
    if card_id is not None:
        return await pool.fetchval(
            "SELECT COUNT(*) FROM rp_fewshot_examples WHERE active AND card_id = $1",
            card_id,
        )
    return await pool.fetchval(
        "SELECT COUNT(*) FROM rp_fewshot_examples WHERE active"
    )


# -- Eval Metrics --

async def save_metrics(*, domain: str, target_type: str, target_id: str,
                       target_label: str, judge_model: str, rubric_name: str,
                       scores: list[dict], weighted_average: float,
                       raw_judge_output: str = "", pool=None):
    """Persist a single eval result to rp_eval_metrics."""
    if pool is None:
        pool = await get_pool()
    await pool.execute(
        "INSERT INTO rp_eval_metrics "
        "(domain, target_type, target_id, target_label, judge_model, "
        " rubric_name, scores, weighted_average, raw_judge_output) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)",
        domain, target_type, target_id, target_label, judge_model,
        rubric_name, json.dumps(scores), weighted_average, raw_judge_output,
    )


async def get_metrics(*, target_type: str, target_id: str | None = None,
                      limit: int = 50, pool=None) -> list[dict]:
    """Retrieve eval metrics, newest first."""
    if pool is None:
        pool = await get_pool()
    if target_id:
        rows = await pool.fetch(
            "SELECT * FROM rp_eval_metrics "
            "WHERE target_type = $1 AND target_id = $2 "
            "ORDER BY created_at DESC LIMIT $3",
            target_type, target_id, limit,
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM rp_eval_metrics "
            "WHERE target_type = $1 "
            "ORDER BY created_at DESC LIMIT $2",
            target_type, limit,
        )
    return [dict(r) for r in rows]
