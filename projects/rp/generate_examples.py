"""Mine real conversations and regenerate high-quality assistant responses as fewshot examples.

Extracts real user messages from the database, feeds them to a large model with full
character card context, and stores the regenerated responses as per-card fewshot examples.

Usage:
    python generate_examples.py --card-id 2 --model qwen3:8b
    python generate_examples.py --card-id 2 --model qwen3:32b --limit 50
    python generate_examples.py --card-id 2 --dry-run
    python generate_examples.py --card-id 2 --deactivate-old
"""

import argparse
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

import asyncpg
import httpx
from dotenv import load_dotenv

# Load .env from repo root
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Reuse aiserver's URL resolution for wsl-gateway fallback
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "aiserver"))
from config import resolve_url  # noqa: E402

EMBED_MODEL = "nomic-embed-text"


async def get_card(pool: asyncpg.Pool, card_id: int) -> dict | None:
    row = await pool.fetchrow(
        "SELECT id, name, card_data FROM rp_character_cards WHERE id = $1",
        card_id,
    )
    return dict(row) if row else None


async def get_conversation_pairs(
    pool: asyncpg.Pool, card_id: int, limit: int
) -> list[dict]:
    """Extract user/assistant message pairs from conversations using this AI card.

    Returns pairs with surrounding context (the preceding assistant message, if any)
    to help the regeneration model understand the scene.
    """
    rows = await pool.fetch(
        "SELECT m.id, m.conversation_id, m.role, m.content, m.sequence "
        "FROM rp_messages m "
        "JOIN rp_conversations c ON m.conversation_id = c.id "
        "WHERE c.ai_card_id = $1 "
        "ORDER BY m.conversation_id, m.sequence",
        card_id,
    )

    # Fetch scenario first_message for each conversation (scene-setting context)
    scenario_rows = await pool.fetch(
        "SELECT c.id as conv_id, s.first_message "
        "FROM rp_conversations c "
        "JOIN rp_scenarios s ON c.scenario_id = s.id "
        "WHERE c.ai_card_id = $1 AND s.first_message != ''",
        card_id,
    )
    scenario_first: dict[int, str] = {
        r["conv_id"]: r["first_message"] for r in scenario_rows
    }

    # Fetch user card name per conversation for {{user}} substitution
    user_card_rows = await pool.fetch(
        "SELECT c.id as conv_id, uc.card_data "
        "FROM rp_conversations c "
        "JOIN rp_character_cards uc ON c.user_card_id = uc.id "
        "WHERE c.ai_card_id = $1",
        card_id,
    )
    user_name_by_conv: dict[int, str] = {}
    for r in user_card_rows:
        cd = r["card_data"]
        if isinstance(cd, str):
            cd = json.loads(cd)
        d = cd.get("data", cd)
        user_name_by_conv[r["conv_id"]] = d.get("name", "User")

    pairs = []
    messages_by_conv: dict[int, list[dict]] = {}
    for r in rows:
        conv_id = r["conversation_id"]
        if conv_id not in messages_by_conv:
            messages_by_conv[conv_id] = []
        messages_by_conv[conv_id].append(dict(r))

    for conv_id, msgs in messages_by_conv.items():
        for i, msg in enumerate(msgs):
            if msg["role"] != "user":
                continue
            # Find the next assistant message
            assistant_msg = None
            for j in range(i + 1, len(msgs)):
                if msgs[j]["role"] == "assistant":
                    assistant_msg = msgs[j]
                    break
            if assistant_msg is None:
                continue

            # Gather preceding context (up to 2 messages before)
            context_msgs = []
            if i == 0 and conv_id in scenario_first:
                # First user message — use scenario first_message as scene context
                context_msgs.append({
                    "role": "assistant",
                    "content": scenario_first[conv_id],
                })
            else:
                for k in range(max(0, i - 2), i):
                    context_msgs.append(msgs[k])

            pairs.append({
                "conversation_id": conv_id,
                "user_message": msg["content"],
                "original_assistant": assistant_msg["content"],
                "context": context_msgs,
                "user_name": user_name_by_conv.get(conv_id, "User"),
            })

    # Deduplicate by user message content
    seen = set()
    unique_pairs = []
    for pair in pairs:
        key = pair["user_message"].strip()[:200]
        if key not in seen:
            seen.add(key)
            unique_pairs.append(pair)
    pairs = unique_pairs

    if limit and len(pairs) > limit:
        pairs = pairs[:limit]

    return pairs


def build_system_prompt(card: dict, user_name: str = "User") -> str:
    """Build a system prompt from card data, matching the pipeline's template."""
    card_data = card.get("card_data", {})
    if isinstance(card_data, str):
        card_data = json.loads(card_data)
    data = card_data.get("data", card_data)
    char_name = data.get("name", card.get("name", "Character"))

    parts = []
    desc = data.get("description", "")
    if desc:
        parts.append(f"--- {char_name} ---\n{desc}")
    personality = data.get("personality", "")
    if personality:
        parts.append(f"Personality: {personality}")
    mes_example = data.get("mes_example", "")
    if mes_example:
        parts.append(f"Example dialogue:\n{mes_example}")

    parts.append(
        f"\nWrite only {char_name}'s next response. Stay in character. "
        f"Do not narrate the user's actions.\n"
        f"Vary response length to match the beat. "
        f"Describe bodies naturally when clothing state calls for it. "
        f"Honor the scene state. Emotions don't reset between messages. "
        f"{char_name} is NOT a mirror — has their own perspective and thoughts."
    )

    prompt = "\n\n".join(parts)
    # Resolve mustache variables that leak from card data
    prompt = prompt.replace("{{char}}", char_name).replace("{{user}}", user_name)
    return prompt


async def regenerate_response(
    client: httpx.AsyncClient,
    ollama_url: str,
    model: str,
    system_prompt: str,
    context_msgs: list[dict],
    user_message: str,
) -> str | None:
    """Send the user message + card context to a model and get a regenerated response."""
    messages = [{"role": "system", "content": system_prompt}]

    # Add preceding context so the model has scene awareness
    for msg in context_msgs:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    payload = {"model": model, "messages": messages, "stream": False}
    resp = await client.post(
        f"{ollama_url}/api/chat", json=payload, timeout=600.0
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Ollama {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    return data["message"]["content"]


async def embed_text(
    client: httpx.AsyncClient,
    ollama_url: str,
    text: str,
) -> list[float]:
    payload = {"model": EMBED_MODEL, "input": text}
    resp = await client.post(
        f"{ollama_url}/api/embed", json=payload, timeout=180.0
    )
    resp.raise_for_status()
    data = resp.json()
    return data["embeddings"][0]


async def insert_example(
    pool: asyncpg.Pool,
    card_id: int,
    scene_context: str,
    user_message: str,
    assistant_message: str,
    embedding: list[float],
    model: str,
    token_estimate: int,
) -> int:
    embedding_str = "[" + ",".join(str(f) for f in embedding) + "]"
    row = await pool.fetchrow(
        "INSERT INTO rp_fewshot_examples "
        "(card_id, scene_context, user_message, assistant_message, "
        "embedding, model, token_estimate) "
        "VALUES ($1, $2, $3, $4, $5::vector, $6, $7) "
        "RETURNING id",
        card_id, scene_context, user_message, assistant_message,
        embedding_str, model, token_estimate,
    )
    return row["id"]


async def deactivate_old_examples(pool: asyncpg.Pool, card_id: int) -> int:
    """Deactivate all existing fewshot examples for this card."""
    result = await pool.execute(
        "UPDATE rp_fewshot_examples SET active = FALSE "
        "WHERE card_id = $1 AND active = TRUE",
        card_id,
    )
    # result is like "UPDATE 5"
    return int(result.split()[-1])


async def get_existing_user_messages(pool: asyncpg.Pool, card_id: int) -> set[str]:
    """Return the set of user_message values that already have active examples."""
    rows = await pool.fetch(
        "SELECT user_message FROM rp_fewshot_examples "
        "WHERE card_id = $1 AND active = TRUE",
        card_id,
    )
    return {r["user_message"] for r in rows}


async def deactivate_generic_examples(pool: asyncpg.Pool) -> int:
    """Deactivate card-agnostic examples (card_id IS NULL)."""
    result = await pool.execute(
        "UPDATE rp_fewshot_examples SET active = FALSE "
        "WHERE card_id IS NULL AND active = TRUE"
    )
    return int(result.split()[-1])


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mine real conversations to generate per-card fewshot examples"
    )
    parser.add_argument(
        "--card-id", type=int, required=True,
        help="AI character card ID to generate examples for",
    )
    parser.add_argument(
        "--model", default="qwen3:8b",
        help="Ollama model for regenerating responses",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Max message pairs to process (0 = all)",
    )
    parser.add_argument(
        "--ollama-url",
        default=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
        help="Ollama base URL",
    )
    parser.add_argument(
        "--db-url", default=None,
        help="Database URL (default: DATABASE_URL env or postgresql://localhost/plum)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be generated without calling models or writing to DB",
    )
    parser.add_argument(
        "--deactivate-old", action="store_true",
        help="Deactivate existing fewshot examples for this card before generating",
    )
    parser.add_argument(
        "--deactivate-generic", action="store_true",
        help="Deactivate card-agnostic (card_id=NULL) examples",
    )
    args = parser.parse_args()
    args.ollama_url = resolve_url(args.ollama_url)

    db_url = args.db_url or os.environ.get(
        "DATABASE_URL", "postgresql://plum@localhost:5432/plum"
    )

    # Mask password for debug output
    from urllib.parse import urlparse
    _parsed = urlparse(db_url)
    _safe = db_url.replace(f":{_parsed.password}@", ":***@") if _parsed.password else db_url
    print(f"DB: {_safe}")

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)

    try:
        card = await get_card(pool, args.card_id)
        if not card:
            print(f"Card {args.card_id} not found")
            return

        card_data = card.get("card_data", {})
        if isinstance(card_data, str):
            card_data = json.loads(card_data)
        data = card_data.get("data", card_data)
        char_name = data.get("name", card.get("name", "?"))
        print(f"Card: {char_name} (id={args.card_id})")
        print(f"Model: {args.model}  Embed: {EMBED_MODEL}  DB: {_safe}")

        if args.deactivate_generic:
            n = await deactivate_generic_examples(pool)
            print(f"Deactivated {n} generic (card_id=NULL) examples")

        if args.deactivate_old:
            n = await deactivate_old_examples(pool, args.card_id)
            print(f"Deactivated {n} existing examples for {char_name}")

        pairs = await get_conversation_pairs(
            pool, args.card_id, limit=0
        )
        total_mined = len(pairs)

        # Incremental: skip pairs that already have active examples
        existing = await get_existing_user_messages(pool, args.card_id)
        if existing:
            pairs = [p for p in pairs if p["user_message"] not in existing]
            print(
                f"Mined {total_mined} pairs, {len(existing)} already generated, "
                f"{len(pairs)} new"
            )
        else:
            print(f"Mined {total_mined} pairs, none previously generated")

        # Randomize so partial runs get diverse coverage
        random.shuffle(pairs)

        if args.limit and len(pairs) > args.limit:
            pairs = pairs[:args.limit]

        print(f"Processing {len(pairs)} pairs\n")

        if not pairs:
            print("No conversation pairs found for this card.")
            return

        if args.dry_run:
            print("=== DRY RUN ===\n")
            for i, pair in enumerate(pairs):
                user_preview = pair["user_message"][:120].replace("\n", " ")
                orig_preview = pair["original_assistant"][:120].replace("\n", " ")
                print(f"[{i + 1}/{len(pairs)}] conv={pair['conversation_id']}")
                print(f"  User: {user_preview}...")
                print(f"  Original: {orig_preview}...")
                print(f"  Context msgs: {len(pair['context'])}")
                print()
            return

        # Cache system prompts per user_name (usually just one)
        system_prompts: dict[str, str] = {}
        generated = 0
        skipped = 0
        gen_times: list[float] = []

        async with httpx.AsyncClient() as client:
            # Warm up: load model with a tiny request
            print("Loading model...", end="", flush=True)
            t_load = time.time()
            try:
                await client.post(
                    f"{args.ollama_url}/api/chat",
                    json={"model": args.model, "messages": [
                        {"role": "user", "content": "hi"}
                    ], "stream": False},
                    timeout=600.0,
                )
            except Exception:
                pass
            load_secs = time.time() - t_load
            print(f" {load_secs:.1f}s")

            for i, pair in enumerate(pairs):
                user_preview = pair["user_message"][:80].replace("\n", " ")
                print(
                    f"[{i + 1}/{len(pairs)}] conv={pair['conversation_id']} "
                    f"{user_preview}...",
                    end="", flush=True,
                )

                try:
                    uname = pair["user_name"]
                    if uname not in system_prompts:
                        system_prompts[uname] = build_system_prompt(card, uname)
                    system_prompt = system_prompts[uname]

                    t0 = time.time()
                    response = await regenerate_response(
                        client, args.ollama_url, args.model,
                        system_prompt, pair["context"],
                        pair["user_message"],
                    )
                    gen_secs = time.time() - t0

                    # Clean any {{user}}/{{char}} the model echoed
                    response = response.replace("{{char}}", char_name).replace("{{user}}", uname)

                    if not response or not response.strip():
                        print(" -- SKIP: empty response")
                        skipped += 1
                        continue

                    gen_times.append(gen_secs)
                    avg_secs = sum(gen_times) / len(gen_times)
                    remaining = len(pairs) - (i + 1)
                    eta_mins = (avg_secs * remaining) / 60

                    # Scene context for the embedding: user message + response
                    scene_context = (
                        pair["user_message"] + "\n" + response
                    )
                    token_estimate = (
                        len(pair["user_message"]) + len(response)
                    ) // 4

                    embedding = await embed_text(
                        client, args.ollama_url, scene_context
                    )

                    row_id = await insert_example(
                        pool, args.card_id, scene_context,
                        pair["user_message"], response,
                        embedding, args.model, token_estimate,
                    )
                    generated += 1
                    print(
                        f" -- id={row_id} tokens~{token_estimate} "
                        f"({gen_secs:.1f}s, avg {avg_secs:.1f}s, "
                        f"ETA {eta_mins:.0f}m)"
                    )

                except Exception as e:
                    print(f" -- ERROR [{type(e).__name__}]: {e}")
                    skipped += 1

        total_mins = sum(gen_times) / 60 if gen_times else 0
        print(
            f"\nDone. Generated: {generated}, Skipped: {skipped}, "
            f"Total: {total_mins:.1f}m, Avg: {sum(gen_times)/len(gen_times):.1f}s/example"
            if gen_times else f"\nDone. Generated: {generated}, Skipped: {skipped}"
        )

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
