"""Generate synthetic multi-turn conversations for LoRA training data.

Creates diverse slice-of-life conversations between Valentina (user) and
various AI characters using the 70B model, with content filtering for
quality and safety.

Usage:
    # Generate conversations for all new cards
    python -m projects.rp.lora_generate --user-card-id 11 --ai-card-ids 28,29,30,31

    # Control conversation count and length
    python -m projects.rp.lora_generate --user-card-id 11 --ai-card-ids 29 \
        --num-convs 5 --turns-per-conv 15

    # Dry run: generate scenarios only, don't run conversations
    python -m projects.rp.lora_generate --user-card-id 11 --ai-card-ids 29 --scenarios-only
"""

import argparse
import asyncio
import json
import logging
import random
import re

import asyncpg

from .pipeline import DEFAULT_PROMPT_TEMPLATE, _split_template, render_template

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
_log = logging.getLogger(__name__)

# --- Content filters ---

STOCK_PHRASES = [
    "ruin you for anyone else", "ruin me for anyone else",
    "ruined for anyone else", "ruined me for everyone",
    "electricity coursed", "electricity shot through",
    "shivers down her spine", "shivers down my spine",
    "breath caught in", "breath hitched",
    "heart pounded in", "heart hammered in",
    "pulse quickened", "pulse raced",
    "a gasp escaped", "a moan escaped",
    "core tightened", "coil tightened",
    "undone by", "came undone",
    "claimed her lips", "claimed his lips",
    "molten heat", "pooling heat",
    "like a prayer", "whispered like a prayer",
    "swallowed thickly", "adam's apple bobbed",
]

VIOLENCE_PATTERNS = [
    r"\b(force[ds]? (?:her|him|them)(?:self)? (?:down|onto|against|into))",
    r"\b(pin(?:ned|ning) (?:her|him|them) down)",
    r"\b(struggle[ds]? (?:against|to get))",
    r"\b(couldn'?t (?:move|escape|get away|breathe))",
    r"\b(no[,.]? (?:stop|don'?t|please))",
    r"\b((?:slap|hit|strike|choke|grab)(?:s|bed|ped|king)? (?:her|him|them))",
    r"\b(tears (?:of|from) (?:pain|fear))",
    r"\b(begg(?:ed|ing) (?:her|him|them) to stop)",
]

CONSENT_FLAGS = [
    r"\b(didn'?t (?:want|ask|consent))",
    r"\b(without (?:her|his|their) (?:permission|consent))",
    r"\b((?:too )?drunk to)",
    r"\b((?:she|he|they) (?:froze|went rigid|stiffened).*(?:hands|touch))",
    r"\b(push(?:ed|ing) (?:her|his|their) hands? away)",
]


def check_stock_phrases(text: str) -> list[str]:
    """Return list of stock phrases found in text."""
    lower = text.lower()
    return [p for p in STOCK_PHRASES if p in lower]


def check_safety(text: str) -> list[str]:
    """Return list of safety flags (violence/consent issues) found in text."""
    flags = []
    lower = text.lower()
    for pattern in VIOLENCE_PATTERNS + CONSENT_FLAGS:
        if re.search(pattern, lower):
            flags.append(pattern)
    return flags


# --- Scenario generation ---

SCENARIO_CATEGORIES = [
    {
        "category": "everyday",
        "description": "Mundane daily life moments",
        "examples": [
            "grocery shopping together",
            "cooking dinner after a long day",
            "stuck in traffic",
            "doing laundry at a laundromat",
            "waiting room at a doctor's office",
        ],
    },
    {
        "category": "emotional_heavy",
        "description": "Intense emotional situations",
        "examples": [
            "one character just got devastating news",
            "panic attack in public",
            "grief after losing someone",
            "confronting a painful truth about the relationship",
            "breakdown after holding it together for too long",
        ],
    },
    {
        "category": "conflict",
        "description": "Disagreements and friction",
        "examples": [
            "argument about something that seems small but isn't",
            "one person forgot something important",
            "different expectations about the relationship",
            "jealousy over a new friend",
            "miscommunication that escalated",
        ],
    },
    {
        "category": "romance",
        "description": "Romantic tension and intimacy (emotional)",
        "examples": [
            "first time saying I love you",
            "slow dance in the kitchen",
            "vulnerable conversation in bed at 3am",
            "reuniting after time apart",
            "realizing feelings have changed",
        ],
    },
    {
        "category": "nsfw_tender",
        "description": "Physical intimacy — tender, consensual, emotionally grounded",
        "examples": [
            "first time together, nervous and gentle",
            "morning after, lazy and warm",
            "comfort through physical closeness after emotional conversation",
            "playful escalation from teasing",
            "slow, deliberate, eye-contact-heavy intimacy",
        ],
    },
    {
        "category": "nsfw_passionate",
        "description": "Physical intimacy — intense, consensual, driven by desire",
        "examples": [
            "tension that finally breaks after buildup",
            "making up after a fight",
            "spontaneous in an unexpected place",
            "one person takes charge, other enthusiastically responds",
            "exploring something new together with communication",
        ],
    },
    {
        "category": "friendship",
        "description": "Platonic closeness and support",
        "examples": [
            "helping someone move apartments",
            "road trip with car trouble",
            "one person calls the other crying at 2am",
            "celebrating a small victory nobody else cares about",
            "sitting in comfortable silence",
        ],
    },
    {
        "category": "awkward",
        "description": "Socially uncomfortable moments",
        "examples": [
            "running into an ex with the new person",
            "accidentally oversharing with a stranger",
            "misreading a social situation",
            "caught in a lie about something stupid",
            "having to explain something embarrassing",
        ],
    },
]


async def generate_scenarios(ollama, model: str, ai_card: dict, user_card: dict,
                             num_per_category: int = 3) -> list[dict]:
    """Generate diverse scenarios for a character pair."""
    ai_data = ai_card.get("data", ai_card)
    user_data = user_card.get("data", user_card)
    char_name = ai_data.get("name", "Character")
    user_name = user_data.get("name", "User")

    all_scenarios = []

    for cat in SCENARIO_CATEGORIES:
        prompt = (
            f"Generate {num_per_category} specific, grounded slice-of-life scenarios "
            f"for a roleplay conversation between {char_name} and {user_name}.\n\n"
            f"{char_name}: {ai_data.get('description', '')[:300]}\n"
            f"{user_name}: {user_data.get('description', '')[:300]}\n\n"
            f"Category: {cat['category']} — {cat['description']}\n"
            f"Examples of this category: {', '.join(cat['examples'][:3])}\n\n"
            "Rules:\n"
            "- Slice of life only. No fantasy, no supernatural, no sci-fi.\n"
            "- Specific and concrete — include a location, time of day, and what just happened.\n"
            "- Each scenario is 2-3 sentences.\n"
            "- Characters should already know each other (friends, roommates, partners, coworkers).\n"
            f"- Scenarios should fit {char_name}'s personality and background.\n"
        )
        if "nsfw" in cat["category"]:
            prompt += (
                "- All physical intimacy must be clearly consensual and enthusiastic.\n"
                "- No violence, coercion, dubious consent, or power imbalance.\n"
                "- Ground it in emotion and connection, not just physical acts.\n"
            )
        prompt += (
            f"\nOutput ONLY a JSON array of {num_per_category} strings. No explanation.\n"
            "Example: [\"Scenario one.\", \"Scenario two.\", \"Scenario three.\"]"
        )

        raw = await ollama.generate(
            model=model, prompt=prompt,
            system="Output valid JSON only. No markdown fences.",
            options={"temperature": 0.9, "num_predict": 1024, "think": False},
        )
        try:
            # Try to extract JSON array from response
            clean = raw.strip()
            if "```" in clean:
                clean = clean.split("```")[1].strip()
                if clean.startswith("json"):
                    clean = clean[4:].strip()
            scenarios = json.loads(clean)
            if isinstance(scenarios, list):
                for s in scenarios:
                    all_scenarios.append({"category": cat["category"], "text": s})
        except (json.JSONDecodeError, IndexError):
            _log.warning("Failed to parse scenarios for %s/%s", char_name, cat["category"])
            continue

    random.shuffle(all_scenarios)
    return all_scenarios


# --- Conversation generation ---

async def generate_user_message(ollama, model: str, context: dict) -> str:
    """Generate a Valentina-style user message."""
    prompt = (
        f"You are writing as {context['user_name']} in a roleplay conversation "
        f"with {context['char_name']}.\n\n"
        f"{context['user_name']}'s personality: {context['user_personality'][:300]}\n\n"
        f"Scenario: {context['scenario']}\n\n"
    )
    if context.get("history"):
        prompt += "Conversation so far:\n"
        for msg in context["history"][-6:]:  # last 3 exchanges for context
            prompt += f"  {msg['from']}: {msg['value'][:200]}\n"
        prompt += "\n"

    prompt += (
        f"Write {context['user_name']}'s next message. Rules:\n"
        "- Short and natural — 1-4 sentences typical, occasionally longer for emotional moments\n"
        "- Can include actions, dialogue, and internal thoughts\n"
        "- Internal thoughts are things the other character CANNOT perceive\n"
        "- Casual, direct writing style — not flowery or literary\n"
        "- Drive the scene forward — don't just react, initiate things\n"
        f"\nWrite ONLY {context['user_name']}'s message. No quotes around the whole thing. "
        "No prefix like 'User:'. Just the message."
    )

    raw = await ollama.generate(
        model=model, prompt=prompt,
        system=f"You are {context['user_name']}. Write their next message only.",
        options={"temperature": 1.0, "num_predict": 300, "think": False},
    )
    return raw.strip().strip('"')


async def generate_assistant_message(ollama, model: str, system_prompt: str,
                                     messages: list[dict]) -> str:
    """Generate a character response using the full chat pipeline."""
    # Build chat messages in Ollama format
    chat_msgs = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        role = "user" if msg["from"] == "human" else "assistant"
        chat_msgs.append({"role": role, "content": msg["value"]})

    raw = await ollama.chat(
        model=model, messages=chat_msgs,
        options={"temperature": 1.05, "num_predict": 768,
                 "min_p": 0.1, "repeat_penalty": 1.08},
    )
    return raw.strip()


def build_system_prompt(ai_card: dict, user_card: dict, scenario_text: str) -> str:
    """Build system prompt from cards and scenario."""
    ai_data = ai_card.get("data", ai_card)
    user_data = user_card.get("data", user_card)

    values = {
        "scenario": scenario_text,
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

    char_name = ai_data.get("name", "Character")
    user_name = user_data.get("name", "User")
    for var, val in [("${user}", user_name), ("${char}", char_name),
                     ("${scenario}", scenario_text)]:
        system_prompt = system_prompt.replace(var, val)

    if post_part:
        post_prompt = render_template(post_part, values)
        for var, val in [("${user}", user_name), ("${char}", char_name)]:
            post_prompt = post_prompt.replace(var, val)
        system_prompt += "\n\n" + post_prompt

    return system_prompt


async def generate_conversation(ollama, model_70b: str, ai_card: dict, user_card: dict,
                                scenario: dict, num_turns: int = 12) -> dict | None:
    """Generate a full multi-turn conversation."""
    ai_data = ai_card.get("data", ai_card)
    user_data = user_card.get("data", user_card)
    char_name = ai_data.get("name", "Character")
    user_name = user_data.get("name", "User")

    system_prompt = build_system_prompt(ai_card, user_card, scenario["text"])

    messages = []  # ShareGPT format: {"from": "human"/"gpt", "value": "..."}
    stock_phrase_count = 0
    safety_flag_count = 0

    context = {
        "char_name": char_name,
        "user_name": user_name,
        "user_personality": user_data.get("personality", "") or user_data.get("description", ""),
        "scenario": scenario["text"],
        "history": messages,
    }

    for turn in range(num_turns):
        # Generate user message
        user_msg = await generate_user_message(ollama, model_70b, context)
        if not user_msg:
            _log.warning("Empty user message at turn %d, stopping", turn)
            break

        # Safety check on user message
        safety = check_safety(user_msg)
        if safety:
            _log.warning("Safety flag in generated user msg at turn %d, stopping: %s",
                        turn, safety[0])
            break

        messages.append({"from": "human", "value": user_msg})

        # Generate assistant response
        assistant_msg = await generate_assistant_message(
            ollama, model_70b, system_prompt, messages)
        if not assistant_msg:
            _log.warning("Empty assistant message at turn %d, stopping", turn)
            messages.pop()  # remove orphaned user message
            break

        # Check assistant response quality
        safety = check_safety(assistant_msg)
        if safety:
            safety_flag_count += 1
            _log.warning("Safety flag in assistant msg at turn %d: %s", turn, safety[0])
            if safety_flag_count >= 2:
                _log.warning("Too many safety flags, discarding conversation")
                return None
            messages.pop()  # remove the user message that led here
            continue

        stock = check_stock_phrases(assistant_msg)
        if stock:
            stock_phrase_count += 1
            _log.info("  turn %d: stock phrase detected: %s", turn, stock[0])
            if stock_phrase_count >= 3:
                _log.warning("Too many stock phrases, stopping early")
                break

        messages.append({"from": "gpt", "value": assistant_msg})

    if len([m for m in messages if m["from"] == "gpt"]) < 3:
        _log.warning("Too few valid turns, discarding")
        return None

    return {
        "conversations": [{"from": "system", "value": system_prompt}] + messages,
        "metadata": {
            "character": char_name,
            "category": scenario["category"],
            "scenario": scenario["text"],
            "turns": len([m for m in messages if m["from"] == "gpt"]),
            "stock_phrases_found": stock_phrase_count,
            "generated": True,
        },
    }


# --- Ollama client ---

class OllamaClient:
    """Minimal async Ollama client for generation."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        self.base_url = base_url

    @staticmethod
    def _parse_ndjson(text: str) -> str:
        """Parse aiserver NDJSON stream into text, skipping think tokens."""
        parts = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Skip thinking tokens and done markers
            if chunk.get("thinking"):
                continue
            if chunk.get("done"):
                continue
            if "error" in chunk:
                raise RuntimeError(f"Ollama error: {chunk['error']}")
            # aiserver format: {"token": "..."} or Ollama format: {"response": "..."}
            if "token" in chunk:
                parts.append(chunk["token"])
            elif "response" in chunk:
                parts.append(chunk["response"])
            elif "message" in chunk and "content" in chunk["message"]:
                parts.append(chunk["message"]["content"])
        return "".join(parts)

    async def generate(self, model: str, prompt: str, system: str = "",
                       options: dict | None = None) -> str:
        import aiohttp
        payload = {"model": model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/generate", json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Generate failed ({resp.status}): {text}")
                return self._parse_ndjson(await resp.text())

    async def chat(self, model: str, messages: list[dict],
                   options: dict | None = None) -> str:
        import aiohttp
        payload = {"model": model, "messages": messages, "stream": False}
        if options:
            payload["options"] = options

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/chat", json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Chat failed ({resp.status}): {text}")
                return self._parse_ndjson(await resp.text())


async def _get_card(pool, card_id: int) -> dict:
    row = await pool.fetchrow(
        "SELECT card_data FROM rp_character_cards WHERE id = $1", card_id)
    if not row:
        raise ValueError(f"Card {card_id} not found")
    cd = row["card_data"]
    return cd if isinstance(cd, dict) else json.loads(cd)


async def main():
    parser = argparse.ArgumentParser(description="Generate LoRA training conversations")
    parser.add_argument("--user-card-id", type=int, required=True, help="User card ID (Valentina)")
    parser.add_argument("--ai-card-ids", type=str, required=True, help="Comma-separated AI card IDs")
    parser.add_argument("--model", type=str, default="ScrambieBambie/L3.3-MS-Nevoria-70B:i1-Q4_K_M",
                        help="Model for generation")
    parser.add_argument("--num-convs", type=int, default=3, help="Conversations per card (default: 3)")
    parser.add_argument("--turns-per-conv", type=int, default=12, help="Turns per conversation (default: 12)")
    parser.add_argument("--scenarios-per-category", type=int, default=2, help="Scenarios per category (default: 2)")
    parser.add_argument("--scenarios-only", action="store_true", help="Only generate and print scenarios")
    parser.add_argument("--aiserver-url", type=str, default="http://127.0.0.1:8080")
    parser.add_argument("--output", "-o", type=str, default="lora_generated.json")
    args = parser.parse_args()

    import os
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=2)
    ollama = OllamaClient(args.aiserver_url)

    ai_card_ids = [int(x.strip()) for x in args.ai_card_ids.split(",")]
    user_card = await _get_card(pool, args.user_card_id)

    all_results = []

    for ai_card_id in ai_card_ids:
        ai_card = await _get_card(pool, ai_card_id)
        ai_data = ai_card.get("data", ai_card)
        char_name = ai_data.get("name", "???")
        _log.info("=== %s (card %d) ===", char_name, ai_card_id)

        # Generate scenarios
        _log.info("Generating scenarios...")
        scenarios = await generate_scenarios(
            ollama, args.model, ai_card, user_card,
            num_per_category=args.scenarios_per_category)
        _log.info("Generated %d scenarios", len(scenarios))

        if args.scenarios_only:
            for s in scenarios:
                print(f"  [{s['category']}] {s['text']}")
            continue

        # Pick scenarios for conversations
        selected = scenarios[:args.num_convs]

        for i, scenario in enumerate(selected):
            _log.info("Conv %d/%d [%s]: %s",
                     i + 1, args.num_convs, scenario["category"], scenario["text"][:80])

            result = await generate_conversation(
                ollama, args.model, ai_card, user_card,
                scenario, num_turns=args.turns_per_conv)

            if result:
                all_results.append(result)
                turns = result["metadata"]["turns"]
                stock = result["metadata"]["stock_phrases_found"]
                _log.info("  -> %d turns, %d stock phrases", turns, stock)
            else:
                _log.warning("  -> discarded")

    await pool.close()

    if args.scenarios_only:
        return

    # Write output
    with open(args.output, "w") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    total_turns = sum(r["metadata"]["turns"] for r in all_results)
    _log.info("Wrote %d conversations (%d turns) to %s",
             len(all_results), total_turns, args.output)


if __name__ == "__main__":
    asyncio.run(main())
