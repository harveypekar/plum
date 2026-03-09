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
            os.environ.get("DATABASE_URL", "postgresql://localhost/plum"),
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


# -- Prompt Templates --

async def list_templates() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, name, content, created_at::text, updated_at::text "
        "FROM rp_prompt_templates ORDER BY name"
    )
    return [dict(r) for r in rows]


async def get_template(template_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, content, created_at::text, updated_at::text "
        "FROM rp_prompt_templates WHERE id = $1", template_id,
    )
    return dict(row) if row else None


async def create_template(name: str, content: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO rp_prompt_templates (name, content) "
        "VALUES ($1, $2) RETURNING id, name, content, "
        "created_at::text, updated_at::text",
        name, content,
    )
    return dict(row)


async def update_template(template_id: int, name: str, content: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "UPDATE rp_prompt_templates SET name=$2, content=$3, "
        "updated_at=NOW() WHERE id=$1 RETURNING id, name, content, "
        "created_at::text, updated_at::text",
        template_id, name, content,
    )
    return dict(row) if row else None


async def delete_template(template_id: int) -> bool:
    pool = await get_pool()
    result = await pool.execute("DELETE FROM rp_prompt_templates WHERE id = $1", template_id)
    return result == "DELETE 1"


# -- Scenarios --

async def list_scenarios() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, name, description, settings, created_at::text, updated_at::text "
        "FROM rp_scenarios ORDER BY name"
    )
    return [dict(r) for r in rows]


async def get_scenario(scenario_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, description, settings, created_at::text, updated_at::text "
        "FROM rp_scenarios WHERE id = $1", scenario_id,
    )
    return dict(row) if row else None


async def create_scenario(name: str, description: str, settings: dict) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO rp_scenarios (name, description, settings) "
        "VALUES ($1, $2, $3) RETURNING id, name, description, settings, "
        "created_at::text, updated_at::text",
        name, description, settings,
    )
    return dict(row)


async def update_scenario(scenario_id: int, name: str, description: str, settings: dict) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "UPDATE rp_scenarios SET name=$2, description=$3, settings=$4, "
        "updated_at=NOW() WHERE id=$1 RETURNING id, name, description, settings, "
        "created_at::text, updated_at::text",
        scenario_id, name, description, settings,
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
        "model, created_at::text, updated_at::text",
        user_card_id, ai_card_id, scenario_id, model,
    )
    return dict(row)


async def get_conversation(conv_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, user_card_id, ai_card_id, scenario_id, model, "
        "created_at::text, updated_at::text FROM rp_conversations WHERE id = $1",
        conv_id,
    )
    return dict(row) if row else None


async def delete_conversation(conv_id: int) -> bool:
    pool = await get_pool()
    result = await pool.execute("DELETE FROM rp_conversations WHERE id = $1", conv_id)
    return result == "DELETE 1"


# -- Messages --

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
