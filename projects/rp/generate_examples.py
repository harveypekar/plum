"""Standalone CLI script to generate few-shot RP examples and store them in the DB.

Usage:
    python generate_examples.py --model qwen3:8b --count 200
    python generate_examples.py --dry-run --count 5
"""

import argparse
import asyncio
import os

import asyncpg
import httpx

# -- Axes for structured generation --

SETTINGS = [
    "apartment/home",
    "outdoor/park",
    "workplace",
    "bar/restaurant",
    "transit/liminal",
]

TONES = [
    "playful/teasing",
    "tender/vulnerable",
    "tense/confrontational",
    "quiet/domestic",
    "heated/passionate",
]

STYLES = [
    "dialogue-heavy",
    "action-heavy",
    "internal-monologue-rich",
    "mixed",
]

STYLE_GUIDANCE = {
    "dialogue-heavy": "mostly spoken dialogue with minimal action tags",
    "action-heavy": "detailed physical actions and body language, with brief dialogue",
    "internal-monologue-rich": "inner thoughts shown in italics (*like this*) mixed with actions and dialogue",
    "mixed": "a natural mix of dialogue, action, and inner thoughts",
}

SYSTEM_PROMPT = """\
You are generating training examples for a roleplay AI. Write a single realistic exchange between two characters in a roleplay scenario.

Rules:
- Use "the user" and "the character" instead of names
- The exchange should feel natural and in-character
- Total length: 150-250 tokens
- Format your response EXACTLY as:
USER: [user's message]
CHARACTER: [character's response]\
"""


def build_combinations() -> list[tuple[str, str, str]]:
    """Return all 100 (setting, tone, style) combinations."""
    combos = []
    for setting in SETTINGS:
        for tone in TONES:
            for style in STYLES:
                combos.append((setting, tone, style))
    return combos


def build_user_prompt(setting: str, tone: str, style: str) -> str:
    guidance = STYLE_GUIDANCE[style]
    return (
        f"Write a {tone} exchange in a {setting} setting. Use {style} style.\n"
        f"The character should respond with {guidance}."
    )


def build_scene_context(setting: str, tone: str, style: str) -> str:
    return f"{tone} exchange in {setting}, {style} style"


def parse_response(content: str) -> tuple[str, str] | None:
    """Extract user_message and assistant_message from model output.

    Returns None if parsing fails.
    """
    user_msg = None
    char_msg = None

    # Normalize line endings
    content = content.replace("\r\n", "\n").strip()

    # Look for USER: marker
    user_idx = content.find("USER:")
    char_idx = content.find("CHARACTER:")

    if user_idx == -1 or char_idx == -1:
        return None

    if user_idx < char_idx:
        # USER: comes first
        user_raw = content[user_idx + len("USER:"):char_idx].strip()
        char_raw = content[char_idx + len("CHARACTER:"):].strip()
    else:
        # CHARACTER: comes first (unusual, but handle it)
        char_raw = content[char_idx + len("CHARACTER:"):user_idx].strip()
        user_raw = content[user_idx + len("USER:"):].strip()

    user_msg = user_raw.strip()
    char_msg = char_raw.strip()

    if not user_msg or not char_msg:
        return None

    return user_msg, char_msg


async def generate_example(
    client: httpx.AsyncClient,
    ollama_url: str,
    model: str,
    setting: str,
    tone: str,
    style: str,
) -> tuple[str, str] | None:
    """Call Ollama to generate one example. Returns (user_msg, char_msg) or None."""
    user_prompt = build_user_prompt(setting, tone, style)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }
    resp = await client.post(f"{ollama_url}/api/chat", json=payload, timeout=120.0)
    resp.raise_for_status()
    data = resp.json()
    content = data["message"]["content"]
    return parse_response(content)


async def embed_text(
    client: httpx.AsyncClient,
    ollama_url: str,
    embed_model: str,
    text: str,
) -> list[float]:
    """Embed text using Ollama embed endpoint."""
    payload = {"model": embed_model, "input": text}
    resp = await client.post(f"{ollama_url}/api/embed", json=payload, timeout=60.0)
    resp.raise_for_status()
    data = resp.json()
    return data["embeddings"][0]


async def insert_example(
    pool: asyncpg.Pool,
    scene_context: str,
    user_message: str,
    assistant_message: str,
    embedding: list[float],
    token_estimate: int,
) -> int:
    """Insert a few-shot example into the DB. Returns the new row id."""
    embedding_str = "[" + ",".join(str(f) for f in embedding) + "]"
    row = await pool.fetchrow(
        "INSERT INTO rp_fewshot_examples "
        "(scene_context, user_message, assistant_message, embedding, token_estimate) "
        "VALUES ($1, $2, $3, $4::vector, $5) "
        "RETURNING id",
        scene_context,
        user_message,
        assistant_message,
        embedding_str,
        token_estimate,
    )
    return row["id"]


def plan_generation(count: int) -> list[tuple[str, str, str, int]]:
    """Return the ordered list of (setting, tone, style, example_idx) to generate.

    For count >= 200: 2 examples per combination.
    For count < 200: round-robin through combinations, at least 1 each.
    """
    combos = build_combinations()  # 100 combos
    total_combos = len(combos)  # 100
    plan: list[tuple[str, str, str, int]] = []

    if count >= total_combos * 2:
        # 2 per combination
        for setting, tone, style in combos:
            plan.append((setting, tone, style, 0))
            plan.append((setting, tone, style, 1))
    elif count >= total_combos:
        # 1 per combination guaranteed, extras round-robin
        for setting, tone, style in combos:
            plan.append((setting, tone, style, 0))
        extras = count - total_combos
        for i in range(extras):
            setting, tone, style = combos[i % total_combos]
            plan.append((setting, tone, style, 1))
    else:
        # Fewer than 100: round-robin through combinations
        for i in range(count):
            setting, tone, style = combos[i % total_combos]
            plan.append((setting, tone, style, 0))

    return plan[:count]


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate few-shot RP examples")
    parser.add_argument("--model", default="qwen3:8b", help="Ollama model for generation")
    parser.add_argument("--count", type=int, default=200, help="Total examples to generate")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama base URL")
    parser.add_argument("--embed-model", default="nomic-embed-text", help="Embedding model name")
    parser.add_argument(
        "--db-url",
        default=None,
        help="Database URL (default: DATABASE_URL env var or postgresql://localhost/plum)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be generated without calling the model or DB",
    )
    args = parser.parse_args()

    db_url = args.db_url or os.environ.get("DATABASE_URL", "postgresql://localhost/plum")

    plan = plan_generation(args.count)

    print(f"Planned {len(plan)} examples across {len(set((s, t, st) for s, t, st, _ in plan))} combinations")
    print(f"Model: {args.model}  Embed: {args.embed_model}  DB: {db_url}")
    print()

    if args.dry_run:
        print("=== DRY RUN — showing planned generations ===\n")
        for i, (setting, tone, style, ex_idx) in enumerate(plan):
            scene_context = build_scene_context(setting, tone, style)
            user_prompt = build_user_prompt(setting, tone, style)
            print(f"[{i + 1}/{len(plan)}] {scene_context}")
            print(f"  Prompt: {user_prompt}")
            print()
        return

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
    generated = 0
    skipped = 0

    try:
        async with httpx.AsyncClient() as client:
            for i, (setting, tone, style, _ex_idx) in enumerate(plan):
                scene_context = build_scene_context(setting, tone, style)
                print(f"[{i + 1}/{len(plan)}] {scene_context}", end="", flush=True)

                parsed = await generate_example(
                    client, args.ollama_url, args.model, setting, tone, style
                )

                if parsed is None:
                    print(" — WARNING: parse failed, skipping")
                    skipped += 1
                    continue

                user_message, assistant_message = parsed
                full_text = scene_context + "\n" + user_message + "\n" + assistant_message
                token_estimate = (len(user_message) + len(assistant_message)) // 4

                embedding = await embed_text(
                    client, args.ollama_url, args.embed_model, full_text
                )

                row_id = await insert_example(
                    pool,
                    scene_context,
                    user_message,
                    assistant_message,
                    embedding,
                    token_estimate,
                )
                generated += 1
                print(f" — id={row_id} tokens≈{token_estimate}")

    finally:
        await pool.close()

    print(f"\nDone. Generated: {generated}, Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(main())
