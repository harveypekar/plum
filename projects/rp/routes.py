import asyncio
import json
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from . import db
from .cards import parse_card_png, export_card_png, extract_name
from .models import (
    CardCreate, CardResponse, ScenarioCreate, ScenarioResponse,
    ConversationCreate, ConversationResponse, ConversationDetailResponse,
    MessageResponse, SendMessageRequest, EditMessageRequest, SceneStateRequest,
)
from .pipeline import create_default_pipeline
from .mcp_client import get_router as get_mcp_router
from .research import research_dispatch
from .fewshot import get_fewshot_messages
from . import conv_log

# Priority levels from aiserver's inference queue (lower = higher priority).
# Duplicated here to avoid a circular import from the host process.
_PRI_INTERACTIVE = 0   # UI chat: /message, /continue, /regenerate, /auto-reply
_PRI_BACKGROUND = 5    # card generation, scene state, summaries

_log = logging.getLogger(__name__)

_ollama = None
_pipeline = None
_resolve_model = None


async def init_mcp():
    """Register and discover MCP tool servers."""
    import sys
    from pathlib import Path
    router = get_mcp_router()
    server_path = str(Path(__file__).parent / "mcp_wikipedia.py")
    # Use the same python that's running this process (the venv's python)
    python = sys.executable
    router.register_server("wikipedia", python, [server_path])
    await router.discover_tools()
    _log.info("MCP tools ready: %s", list(router._tools.keys()) if router.has_tools else "none")


def setup(app: FastAPI, ollama, resolve_model=None):
    global _ollama, _pipeline, _resolve_model
    _ollama = ollama
    _pipeline = create_default_pipeline()
    _resolve_model = resolve_model or (lambda m: m)

    # -- Cards --

    @app.get("/rp/cards", response_model=list[CardResponse])
    async def list_cards():
        return await db.list_cards()

    @app.post("/rp/cards", response_model=CardResponse)
    async def create_card(card: CardCreate):
        return await db.create_card(card.name, card.card_data)

    @app.post("/rp/cards/import", response_model=CardResponse)
    async def import_card(file: UploadFile = File(...)):
        png_data = await file.read()
        if len(png_data) > 10 * 1024 * 1024:
            raise HTTPException(413, "File too large (max 10 MB)")
        try:
            card_data, avatar = parse_card_png(png_data)
        except ValueError as e:
            raise HTTPException(400, str(e))
        name = extract_name(card_data)
        # Check for existing card with same name
        existing = await db.find_card_by_name(name)
        if existing:
            # Update the existing card instead of creating a duplicate
            card = await db.update_card(existing["id"], name, card_data, avatar=avatar)
        else:
            card = await db.create_card(name, card_data, avatar=avatar)
        # Auto-extract scenario from card if present
        data = card_data.get("data", card_data)
        scenario_text = data.get("scenario", "")
        if scenario_text.strip():
            scenario_name = name + " — Scenario"
            existing_scenario = await db.find_scenario_by_name(scenario_name)
            if not existing_scenario:
                await db.create_scenario(scenario_name, scenario_text, {})
        return card

    @app.get("/rp/cards/{card_id}", response_model=CardResponse)
    async def get_card(card_id: int):
        card = await db.get_card(card_id)
        if not card:
            raise HTTPException(404, "Card not found")
        return card

    @app.put("/rp/cards/{card_id}", response_model=CardResponse)
    async def update_card(card_id: int, card: CardCreate):
        result = await db.update_card(card_id, card.name, card.card_data)
        if not result:
            raise HTTPException(404, "Card not found")
        return result

    @app.delete("/rp/cards/{card_id}")
    async def delete_card(card_id: int):
        if not await db.delete_card(card_id):
            raise HTTPException(404, "Card not found")
        return {"ok": True}

    @app.put("/rp/cards/{card_id}/avatar")
    async def upload_avatar(card_id: int, file: UploadFile = File(...)):
        data = await file.read()
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(413, "File too large (max 5 MB)")
        if not await db.set_card_avatar(card_id, data):
            raise HTTPException(404, "Card not found")
        return {"ok": True}

    @app.get("/rp/cards/{card_id}/avatar")
    async def get_avatar(card_id: int):
        avatar = await db.get_card_avatar(card_id)
        if not avatar:
            raise HTTPException(404, "No avatar")
        return Response(content=avatar, media_type="image/png")

    @app.get("/rp/cards/{card_id}/export")
    async def export_card(card_id: int):
        card = await db.get_card(card_id)
        if not card:
            raise HTTPException(404, "Card not found")
        avatar = await db.get_card_avatar(card_id)
        png = export_card_png(card["card_data"], avatar)
        return Response(
            content=png, media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="{card["name"]}.png"'},
        )

    @app.post("/rp/cards/{card_id}/extract-scenario", response_model=ScenarioResponse)
    async def extract_scenario(card_id: int):
        card = await db.get_card(card_id)
        if not card:
            raise HTTPException(404, "Card not found")
        data = card["card_data"].get("data", card["card_data"])
        scenario_text = data.get("scenario", "")
        if not scenario_text.strip():
            raise HTTPException(400, "Card has no scenario text")
        return await db.create_scenario(card["name"] + " — Scenario", scenario_text, {})

    # -- Card Generation --

    _card_gen_model = "qwen3:14b"

    _card_fields = {
        "name": "A unique, memorable character name",
        "description": "Physical appearance, background, key traits (2-3 paragraphs, vivid detail)",
        "personality": "Personality traits, mannerisms, speech patterns (1-2 paragraphs)",
        "first_mes": "Character's opening message in a scene, third person with dialogue (1-2 paragraphs)",
        "mes_example": "2-3 example exchanges showing how the character speaks and acts",
        "scenario": "A default scenario/setting for this character (1 paragraph)",
        "tags": "Comma-separated genre/trait tags",
    }

    @app.post("/rp/cards/generate")
    async def generate_card(request: Request):
        """Generate a full character card from a description."""
        req = await request.json()
        description = req.get("description", "")
        if not description:
            raise HTTPException(400, "No description provided")

        system = (
            "You are a character card designer for roleplay.\n"
            "Given a character concept, create a detailed card as a JSON object with these fields:\n"
            "- name: character name\n"
            "- description: physical appearance, background, key traits (2-3 paragraphs)\n"
            "- personality: personality traits, mannerisms, speech patterns (1-2 paragraphs)\n"
            "- first_mes: opening message in third person with dialogue (1-2 paragraphs)\n"
            "- mes_example: 2-3 example exchanges as a single string\n"
            "- scenario: default scenario (1 paragraph)\n"
            "- tags: array of string tags\n\n"
            "Match the genre and tone of the user's description. Do NOT default to fantasy.\n"
            "Write vivid, specific descriptions with depth and quirks.\n"
            "Respond with ONLY the JSON object. No markdown fences, no explanation."
        )

        req_model = req.get("model", "") or _card_gen_model
        model = _resolve_model(req_model) if _resolve_model else req_model
        result = await _ollama.generate(
            model=model, prompt=description, system=system,
            options={"temperature": 0.7, "num_predict": 2048, "think": False},
        )
        card_data = _parse_card_json(result)
        if card_data is None:
            return {"error": "LLM returned invalid JSON", "raw": result.strip()}
        return {"card": card_data}

    @app.post("/rp/cards/generate-field")
    async def generate_field(request: Request):
        """Regenerate a single field of a character card."""
        req = await request.json()
        card = req.get("card", {})
        field = req.get("field", "")
        instructions = req.get("instructions", "")

        if field not in _card_fields:
            raise HTTPException(400, f"Unknown field: {field}")

        field_desc = _card_fields[field]
        prompt = (
            f"Here is a character card:\n{json.dumps(card, indent=2)}\n\n"
            f"Regenerate ONLY the '{field}' field.\n"
            f"Field description: {field_desc}\n"
        )
        if instructions:
            prompt += f"User instructions: {instructions}\n"
        prompt += f"\nRespond with ONLY the new value for '{field}'. No JSON, no field name, just the content."

        req_model = req.get("model", "") or _card_gen_model
        model = _resolve_model(req_model) if _resolve_model else req_model
        result = await _ollama.generate(
            model=model, prompt=prompt,
            system="Output only the requested field content. No thinking, no preamble, no quotes around the value.",
            options={"temperature": 0.7, "num_predict": 512, "think": False},
        )
        clean = result.strip()
        if "<think>" in clean:
            clean = clean.split("</think>")[-1].strip()
        # For tags field, try to parse as array
        if field == "tags":
            clean = [t.strip().strip('"') for t in clean.split(",")]
        return {"field": field, "value": clean}

    def _parse_card_json(raw: str):
        """Parse LLM output as card JSON, handling common issues."""
        clean = raw.strip()
        if "<think>" in clean:
            clean = clean.split("</think>")[-1].strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            return None
        # Unwrap {card: ...} wrapper if present
        if "card" in data and isinstance(data["card"], dict):
            data = data["card"]
        # Normalize mes_example: array -> joined string
        if isinstance(data.get("mes_example"), list):
            data["mes_example"] = "\n\n".join(data["mes_example"])
        # Normalize tags: string -> array
        if isinstance(data.get("tags"), str):
            data["tags"] = [t.strip() for t in data["tags"].split(",")]
        return data

    # -- Scenarios --

    @app.get("/rp/scenarios", response_model=list[ScenarioResponse])
    async def list_scenarios():
        return await db.list_scenarios()

    @app.post("/rp/scenarios", response_model=ScenarioResponse)
    async def create_scenario(scenario: ScenarioCreate):
        return await db.create_scenario(scenario.name, scenario.description, scenario.settings, scenario.first_message)

    @app.get("/rp/scenarios/{scenario_id}", response_model=ScenarioResponse)
    async def get_scenario(scenario_id: int):
        s = await db.get_scenario(scenario_id)
        if not s:
            raise HTTPException(404, "Scenario not found")
        return s

    @app.put("/rp/scenarios/{scenario_id}", response_model=ScenarioResponse)
    async def update_scenario(scenario_id: int, scenario: ScenarioCreate):
        result = await db.update_scenario(scenario_id, scenario.name, scenario.description, scenario.settings, scenario.first_message)
        if not result:
            raise HTTPException(404, "Scenario not found")
        return result

    @app.delete("/rp/scenarios/{scenario_id}")
    async def delete_scenario(scenario_id: int):
        if not await db.delete_scenario(scenario_id):
            raise HTTPException(404, "Scenario not found")
        return {"ok": True}

    # -- Conversations --

    @app.get("/rp/conversations")
    async def list_conversations():
        return await db.list_conversations()

    @app.post("/rp/conversations", response_model=ConversationResponse)
    async def create_conversation(conv: ConversationCreate):
        # Verify cards exist
        if not await db.get_card(conv.user_card_id):
            raise HTTPException(404, "User card not found")
        if not await db.get_card(conv.ai_card_id):
            raise HTTPException(404, "AI card not found")
        result = await db.create_conversation(
            conv.user_card_id, conv.ai_card_id, conv.scenario_id, conv.model
        )
        ai_card = await db.get_card(conv.ai_card_id)
        user_card = await db.get_card(conv.user_card_id)
        scenario = await db.get_scenario(conv.scenario_id) if conv.scenario_id else None
        model = conv.model

        first_mes = await _get_or_generate_first_message(result, ai_card, user_card, scenario, model)

        if first_mes:
            await db.add_message(result["id"], "assistant", first_mes)
            # Initial scene state from first message + scenario + card context
            ai_data = ai_card["card_data"].get("data", ai_card["card_data"])
            user_data = user_card["card_data"].get("data", user_card["card_data"])
            scenario_desc = (scenario or {}).get("description", "")
            asyncio.create_task(_auto_update_scene_state(
                result["id"], model,
                ai_data.get("name", "Character"), user_data.get("name", "User"),
                ai_data.get("description", ""), scenario_desc))
        return result

    @app.get("/rp/conversations/{conv_id}", response_model=ConversationDetailResponse)
    async def get_conversation(conv_id: int):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        user_card = await db.get_card(conv["user_card_id"])
        ai_card = await db.get_card(conv["ai_card_id"])
        if not user_card or not ai_card:
            raise HTTPException(404, "Card referenced by conversation no longer exists")
        scenario = await db.get_scenario(conv["scenario_id"]) if conv["scenario_id"] else None
        messages = await db.get_messages(conv_id)
        return ConversationDetailResponse(
            conversation=conv, user_card=user_card, ai_card=ai_card,
            scenario=scenario, messages=messages,
        )

    @app.delete("/rp/conversations/{conv_id}")
    async def delete_conversation(conv_id: int):
        if not await db.delete_conversation(conv_id):
            raise HTTPException(404, "Conversation not found")
        return {"ok": True}

    @app.post("/rp/conversations/{conv_id}/restart")
    async def restart_conversation(conv_id: int):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        await db.delete_all_messages(conv_id)
        await db.update_scene_state(conv_id, "")

        ai_card = await db.get_card(conv["ai_card_id"])
        user_card = await db.get_card(conv["user_card_id"])
        scenario = await db.get_scenario(conv["scenario_id"]) if conv["scenario_id"] else None
        model = conv["model"]

        first_mes = await _get_or_generate_first_message(conv, ai_card, user_card, scenario, model)

        if first_mes:
            await db.add_message(conv_id, "assistant", first_mes)
            # Initial scene state from first message + scenario + card context
            ai_data = ai_card["card_data"].get("data", ai_card["card_data"])
            user_data = user_card["card_data"].get("data", user_card["card_data"])
            scenario_desc = (scenario or {}).get("description", "")
            asyncio.create_task(_auto_update_scene_state(
                conv_id, model,
                ai_data.get("name", "Character"), user_data.get("name", "User"),
                ai_data.get("description", ""), scenario_desc))
        return {"ok": True}

    @app.put("/rp/conversations/{conv_id}/scene-state")
    async def update_scene_state(conv_id: int, req: SceneStateRequest):
        if not await db.update_scene_state(conv_id, req.scene_state):
            raise HTTPException(404, "Conversation not found")
        return {"ok": True}

    @app.post("/rp/conversations/{conv_id}/refresh-scene-state")
    async def refresh_scene_state(conv_id: int):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        all_msgs = await db.get_messages(conv_id)
        model = _resolve_model(conv["model"])
        previous_state = conv.get("scene_state", "")
        last_msg_id = conv.get("scene_state_msg_id")
        # Use messages since last scene state generation
        if last_msg_id is not None:
            new_msgs = [m for m in all_msgs if m["id"] > last_msg_id]
        else:
            new_msgs = all_msgs
        if not new_msgs:
            new_msgs = all_msgs
        latest_msg_id = new_msgs[-1]["id"] if new_msgs else None
        msg_list = [{"role": m["role"], "content": m["content"]} for m in new_msgs]
        ai_card = await db.get_card(conv["ai_card_id"])
        user_card = await db.get_card(conv["user_card_id"])
        ai_data = ai_card.get("card_data", {}).get("data", ai_card.get("card_data", {}))
        user_data = user_card.get("card_data", {}).get("data", user_card.get("card_data", {}))
        scenario = await db.get_scenario(conv["scenario_id"]) if conv.get("scenario_id") else None
        scenario_desc = (scenario or {}).get("description", "")
        clean = await _generate_scene_state(
            model, msg_list, previous_state,
            ai_name=ai_data.get("name", "Character"),
            user_name=user_data.get("name", "User"),
            ai_personality=ai_data.get("description", ""),
            scenario_context=scenario_desc
        )
        await db.update_scene_state(conv_id, clean, latest_msg_id)
        conv_log.log_scene_state(conv_id, previous_state, clean)
        return {"scene_state": clean}

    # -- Chat --

    _chat_defaults = {"num_predict": 768, "temperature": 1.05, "repeat_penalty": 1.08, "min_p": 0.1}

    def _build_ollama_options(settings: dict) -> dict:
        """Build ollama options from scenario settings with sensible defaults."""
        opts = dict(_chat_defaults)
        for k, v in settings.items():
            if k not in ("context_strategy", "max_context_tokens", "model"):
                opts[k] = v
        return opts

    _template_path = Path(__file__).parent / "prompt.md"

    async def _build_pipeline_ctx(conv, messages):
        """Load cards, scenario, template file and run pipeline pre-hooks."""
        user_card = await db.get_card(conv["user_card_id"])
        ai_card = await db.get_card(conv["ai_card_id"])
        scenario = await db.get_scenario(conv["scenario_id"]) if conv["scenario_id"] else {}
        scenario = scenario or {}

        # Read prompt template from file (re-read each time so edits take effect)
        prompt_template = ""
        if _template_path.exists():
            prompt_template = _template_path.read_text()

        ctx = {
            "user_card": user_card,
            "ai_card": ai_card,
            "scenario": scenario,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "system_prompt": "",
            "post_prompt": "",
            "scene_state": conv.get("scene_state", ""),
            "prompt_template": prompt_template,
        }
        return await _pipeline.run_pre(ctx)

    def _get_ai_name(ctx):
        """Extract AI character name for response prefixing."""
        ai_data = ctx.get("ai_card", {}).get("card_data", {}).get("data", ctx.get("ai_card", {}).get("card_data", {}))
        return ai_data.get("name", "Character")

    async def _get_or_generate_first_message(conv, ai_card, user_card, scenario, model):
        """Check cache, return if fresh, otherwise generate and cache."""
        ai_data = ai_card["card_data"].get("data", ai_card["card_data"])
        user_data = user_card["card_data"].get("data", user_card["card_data"])
        char_name = ai_data.get("name", "Character")
        user_name = user_data.get("name", "User")

        def _replace_vars(text):
            return (text
                    .replace("{{user}}", user_name).replace("{{char}}", char_name)
                    .replace("${user}", user_name).replace("${char}", char_name))

        # If scenario or card has a pre-written first message, use it directly
        scenario_first = (scenario or {}).get("first_message", "").strip()
        card_first = ai_data.get("first_mes", "").strip()
        if scenario_first:
            return _replace_vars(scenario_first)
        if card_first:
            return _replace_vars(card_first)

        # Otherwise, check cache then generate
        card_hash = db.compute_card_hash(ai_card)
        scenario_hash = db.compute_scenario_hash(scenario)
        combo_hash = db.compute_combo_hash(card_hash, scenario_hash, model)

        cached = await db.get_cached_first_message(combo_hash, card_hash, scenario_hash)
        if cached:
            _log.info("First message cache hit for combo %s", combo_hash)
            return cached

        try:
            first_mes = await _generate_first_message(conv, ai_card, user_card, scenario)
        except Exception as e:
            _log.warning("Failed to generate first message: %s", e)
            return ""

        await db.set_cached_first_message(combo_hash, card_hash, scenario_hash, model, first_mes)
        _log.info("First message cached for combo %s", combo_hash)
        return first_mes

    async def _generate_first_message(conv, ai_card, user_card, scenario):
        """Generate a first message in the character's voice using scenario + card style reference."""
        ai_data = ai_card["card_data"].get("data", ai_card["card_data"])
        user_data = user_card["card_data"].get("data", user_card["card_data"])
        char_name = ai_data.get("name", "Character")
        user_name = user_data.get("name", "User")

        # Build the generation prompt
        scenario_desc = (scenario or {}).get("description", "")
        style_reference = ai_data.get("first_mes", "")
        system_prompt = ai_data.get("system_prompt", "")
        description = ai_data.get("description", "")
        personality = ai_data.get("personality", "")

        prompt_parts = []
        if system_prompt:
            prompt_parts.append(system_prompt)
        if description:
            prompt_parts.append(f"Character: {description}")
        if personality:
            prompt_parts.append(f"Personality: {personality}")

        prompt_parts.append(
            f"\nWrite the opening scene for a roleplay conversation. "
            f"Write as {char_name} in the style demonstrated below."
        )
        if scenario_desc:
            prompt_parts.append(f"\nScenario to set up:\n{scenario_desc}")
        else:
            prompt_parts.append(f"\nSet up a natural opening scene where {char_name} and {user_name} encounter each other.")

        if style_reference:
            # Replace template vars in the reference
            ref = style_reference.replace("{{user}}", user_name).replace("{{char}}", char_name)
            prompt_parts.append(
                f"\nStyle reference (match this prose register, voice, and level of detail — "
                f"do NOT copy the content, write a NEW scene for the scenario above):\n{ref}"
            )

        prompt_parts.append(
            f"\nWrite ONLY {char_name}'s opening. Do not write {user_name}'s actions or dialogue. "
            f"300-500 words."
        )

        full_prompt = "\n\n".join(prompt_parts)
        model = _resolve_model(conv["model"])

        result = await asyncio.wait_for(
            _ollama.generate(
                model=model, prompt=full_prompt,
                system=f"You are writing the opening narration for {char_name}. Stay in character.",
                options={"temperature": 1.05, "num_predict": 768, "min_p": 0.1, "repeat_penalty": 1.08},
            ),
            timeout=300,
        )
        # Clean up
        clean = result.strip()
        # Strip char name prefix if echoed
        if clean.startswith(char_name + ":"):
            clean = clean[len(char_name) + 1:].strip()
        elif clean.startswith(char_name + " "):
            clean = clean[len(char_name) + 1:].strip()
        return clean

    def _build_chat_messages(ctx):
        """Assemble the messages array for chat_stream()."""
        chat_messages = [{"role": "system", "content": ctx["system_prompt"]}]
        chat_messages.extend(ctx["messages"])
        if ctx.get("post_prompt"):
            chat_messages.append({"role": "system", "content": ctx["post_prompt"]})
        # Add partial assistant message to anchor the model's voice
        ai_name = _get_ai_name(ctx)
        chat_messages.append({"role": "assistant", "content": ai_name + " "})
        return chat_messages

    def _get_user_name(ctx):
        """Extract user character name for stop sequences."""
        user_data = ctx.get("user_card", {}).get("card_data", {}).get("data", ctx.get("user_card", {}).get("card_data", {}))
        return user_data.get("name", "User")

    def _get_ai_personality(ctx):
        """Extract AI character personality description."""
        ai_data = ctx.get("ai_card", {}).get("card_data", {}).get("data", ctx.get("ai_card", {}).get("card_data", {}))
        return ai_data.get("description", "")

    _log = logging.getLogger("rp.routes")

    _scene_state_model = "q25"

    def _build_scene_state_prompt(messages: list[dict], previous_state: str = "",
                                   ai_name: str = "Character", user_name: str = "User",
                                   ai_personality: str = "",
                                   scenario_context: str = "") -> str:
        history = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        prev_section = ""
        if previous_state.strip():
            prev_section = (
                "PREVIOUS SCENE STATE (carry forward anything not contradicted by new messages):\n"
                f"{previous_state.strip()}\n\n"
            )
        personality_hint = ""
        if ai_personality:
            short = ai_personality[:200].rsplit(" ", 1)[0]
            personality_hint = f"{ai_name}'s personality: {short}\n\n"
        scenario_section = ""
        if scenario_context.strip():
            scenario_section = f"Scenario context: {scenario_context.strip()}\n\n"
        initial = not previous_state.strip() and len(messages) <= 1
        if initial:
            instruction = (
                "This is the opening of a new scene. Establish the INITIAL scene state "
                "based on the scenario context and first message below.\n\n"
            )
        else:
            instruction = (
                "Below are the most recent messages. UPDATE the scene state based on what changed.\n"
                "Keep everything from the previous state that still holds true. "
                "Only change what the new messages contradict or add.\n\n"
            )
        return (
            f"{prev_section}"
            f"{personality_hint}"
            f"{scenario_section}"
            f"{instruction}"
            f"Characters: {ai_name} (AI) and {user_name} (user).\n\n"
            "Format — one short line per category:\n"
            "Location: (where are they right now)\n"
            f"Clothing: (what {ai_name} and {user_name} are currently wearing RIGHT NOW — track removals: if a character undressed, they are naked, not still wearing the old clothes. Write 'naked' or 'nude' when appropriate)\n"
            "Restraints: (describe the specific tie/pattern AND what it practically limits — e.g. 'wrists behind back — no free hand use' — or 'none')\n"
            "Position: (posture, who is where, physical contact)\n"
            "Props: (objects currently in play)\n"
            "Mood: (emotional atmosphere right now)\n"
            "ONLY state facts explicitly shown or described in the messages. Do NOT invent or assume details not present.\n"
            "If clothing is not mentioned, write 'not described' — do NOT guess.\n"
            "No narration, no story, no explanation. Just the current facts.\n\n"
            f"Recent messages:\n{history}"
        )

    async def _generate_scene_state(model: str, messages: list[dict], previous_state: str = "",
                                     ai_name: str = "Character", user_name: str = "User",
                                     ai_personality: str = "",
                                     scenario_context: str = "") -> str:
        prompt = _build_scene_state_prompt(messages, previous_state, ai_name, user_name, ai_personality, scenario_context)
        summary_model = _resolve_model(_scene_state_model) if _resolve_model else model
        from .scene_state import clean_scene_state_response
        result = await _ollama.generate(
            model=summary_model, prompt=prompt,
            system="Output only the scene state summary. No thinking, no preamble.",
            options={"temperature": 0.2, "num_predict": 200, "think": False},
        )
        return clean_scene_state_response(result)

    async def _auto_update_scene_state(conv_id: int, model: str,
                                        ai_name: str = "Character", user_name: str = "User",
                                        ai_personality: str = "",
                                        scenario_context: str = ""):
        """Background task: generate scene state from previous state + new messages."""
        try:
            conv = await db.get_conversation(conv_id)
            if not conv:
                return
            previous_state = conv.get("scene_state", "")
            last_msg_id = conv.get("scene_state_msg_id")
            all_msgs = await db.get_messages(conv_id)
            if not all_msgs:
                return
            # Slice to only messages since last scene state generation
            if last_msg_id is not None:
                new_msgs = [m for m in all_msgs if m["id"] > last_msg_id]
            else:
                new_msgs = all_msgs
            if not new_msgs:
                return
            latest_msg_id = new_msgs[-1]["id"]
            msg_list = [{"role": m["role"], "content": m["content"]} for m in new_msgs]
            clean = await _generate_scene_state(model, msg_list, previous_state,
                                                ai_name, user_name, ai_personality, scenario_context)
            await db.update_scene_state(conv_id, clean, latest_msg_id)
            conv_log.log_scene_state(conv_id, previous_state, clean)
        except Exception as e:
            _log.warning("Scene state auto-update failed: %s", e)

    @app.post("/rp/conversations/{conv_id}/message")
    async def send_message(conv_id: int, req: SendMessageRequest):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")

        await db.add_message(conv_id, "user", req.content)
        conv_log.log_response(conv_id, "user", req.content)

        messages = await db.get_messages(conv_id)
        ctx = await _build_pipeline_ctx(conv, messages)

        model = _resolve_model(conv["model"])
        scenario = ctx.get("scenario") or {}
        settings = scenario.get("settings", {})
        ollama_options = _build_ollama_options(settings)

        # Two-model research dispatch: check if user message needs factual lookup
        research = await research_dispatch(_ollama, req.content)
        if research:
            _log.info("Injecting research into context (%d chars)", len(research))
            conv_log.log_research(conv_id, req.content, research)
            ctx["post_prompt"] = (
                ctx.get("post_prompt", "")
                + "\n\n[Research notes — weave these facts naturally if relevant, "
                + "don't quote them verbatim or mention looking anything up]\n"
                + research
            )

        # Vector-matched fewshot examples: inject style-similar examples
        fewshot_msgs = await get_fewshot_messages(_ollama, ctx["messages"], card_id=conv["ai_card_id"])
        if fewshot_msgs and ctx["messages"]:
            _log.info("Injecting %d fewshot examples (vector-matched)", len(fewshot_msgs) // 2)
            conv_log.log_fewshot(conv_id, len(fewshot_msgs) // 2, fewshot_msgs)
            # Prepend after greeting (messages[0]), before real conversation
            ctx["messages"] = [ctx["messages"][0]] + fewshot_msgs + ctx["messages"][1:]

        chat_messages = _build_chat_messages(ctx)
        user_name = _get_user_name(ctx)
        conv_log.log_prompt(conv_id, "send_message", model,
                            ctx["system_prompt"], ctx.get("post_prompt", ""),
                            ctx["messages"], ollama_options)

        async def stream():
            yield json.dumps({
                "debug_prompt": ctx["system_prompt"],
                "debug_user_prompt": ctx.get("post_prompt", ""),
                "debug_messages": ctx["messages"],
            }) + "\n"

            cur_messages = list(chat_messages)
            max_tool_rounds = 3
            final_text = ""
            raw = {}

            for _round in range(max_tool_rounds + 1):
                tokens = []
                try:
                    async for chunk in _ollama.chat_stream(
                        model=model, messages=cur_messages,
                        options=ollama_options, stop=[f"{user_name}:"],
                    ):
                        yield json.dumps(chunk) + "\n"
                        if chunk.get("done"):
                            raw = chunk
                        elif not chunk.get("thinking"):
                            tokens.append(chunk["token"])
                except Exception as e:
                    yield json.dumps({"error": str(e), "done": True}) + "\n"
                    return

                response_text = "".join(tokens)
                router = get_mcp_router()
                tool_calls = router.parse_tool_calls(response_text) if router.has_tools else []

                if not tool_calls or _round == max_tool_rounds:
                    final_text = response_text
                    break

                # Resolve tool calls and continue generation
                tool_results = []
                for name, args, match_str in tool_calls:
                    _log.info("MCP tool call: %s(%s)", name, args)
                    yield json.dumps({"tool_call": name, "args": args}) + "\n"
                    result = await router.call_tool(name, args)
                    tool_results.append(f"[RESULT from {name}: {result}]")
                    yield json.dumps({"tool_result": name, "preview": result[:200]}) + "\n"

                # Strip tool calls from response, append results, ask model to continue
                clean = response_text
                for _, _, match_str in tool_calls:
                    clean = clean.replace(match_str, "")
                clean = clean.strip()

                cur_messages.append({"role": "assistant", "content": clean})
                cur_messages.append({"role": "user", "content": "\n".join(tool_results) + "\n\nContinue your response naturally, incorporating the information above. Do not use [TOOL:] again for the same query."})

            try:
                post_ctx = {"response": final_text, "ai_name": _get_ai_name(ctx)}
                post_ctx = await _pipeline.run_post(post_ctx)
                await db.add_message(conv_id, "assistant", post_ctx["response"], raw_response=raw)
                conv_log.log_response(conv_id, "assistant", post_ctx["response"], raw)
                # Update scene state in background
                asyncio.create_task(_auto_update_scene_state(conv_id, model,
                                                _get_ai_name(ctx), _get_user_name(ctx), _get_ai_personality(ctx)))
            except Exception as e:
                yield json.dumps({"error": f"Failed to save response: {e}", "done": True}) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    @app.post("/rp/conversations/{conv_id}/save-partial")
    async def save_partial(conv_id: int, req: SendMessageRequest):
        """Save a partial response when the user hits Stop mid-stream."""
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        content = req.content.strip()
        if not content:
            return {"ok": False}
        await db.add_message(conv_id, "assistant", content)
        return {"ok": True}

    @app.put("/rp/messages/{msg_id}", response_model=MessageResponse)
    async def edit_message(msg_id: int, req: EditMessageRequest):
        result = await db.update_message(msg_id, req.content)
        if not result:
            raise HTTPException(404, "Message not found")
        return result

    @app.delete("/rp/messages/{msg_id}")
    async def delete_message(msg_id: int):
        if not await db.delete_message(msg_id):
            raise HTTPException(404, "Message not found")
        return {"ok": True}

    @app.post("/rp/conversations/{conv_id}/regenerate")
    async def regenerate(conv_id: int):
        messages = await db.get_messages(conv_id)
        if not messages:
            raise HTTPException(400, "No messages to regenerate")
        last = messages[-1]
        if last["role"] != "assistant":
            raise HTTPException(400, "Last message is not from assistant")
        await db.delete_message(last["id"])

        conv = await db.get_conversation(conv_id)
        messages = await db.get_messages(conv_id)
        ctx = await _build_pipeline_ctx(conv, messages)

        model = _resolve_model(conv["model"])
        scenario = ctx.get("scenario") or {}
        settings = scenario.get("settings", {})
        ollama_options = _build_ollama_options(settings)

        chat_messages = _build_chat_messages(ctx)
        user_name = _get_user_name(ctx)
        conv_log.log_prompt(conv_id, "regenerate", model,
                            ctx["system_prompt"], ctx.get("post_prompt", ""),
                            ctx["messages"], ollama_options)

        async def stream():
            yield json.dumps({
                "debug_prompt": ctx["system_prompt"],
                "debug_user_prompt": ctx.get("post_prompt", ""),
                "debug_messages": ctx["messages"],
            }) + "\n"

            tokens = []
            raw = {}
            try:
                async for chunk in _ollama.chat_stream(
                    model=model, messages=chat_messages,
                    options=ollama_options, stop=[f"{user_name}:"],
                ):
                    yield json.dumps(chunk) + "\n"
                    if chunk.get("done"):
                        raw = chunk
                    elif not chunk.get("thinking"):
                        tokens.append(chunk["token"])
            except Exception as e:
                yield json.dumps({"error": str(e), "done": True}) + "\n"
                return
            try:
                response_text = "".join(tokens)
                post_ctx = {"response": response_text, "ai_name": _get_ai_name(ctx)}
                post_ctx = await _pipeline.run_post(post_ctx)
                await db.add_message(conv_id, "assistant", post_ctx["response"], raw_response=raw)
                conv_log.log_response(conv_id, "assistant", post_ctx["response"], raw)
                # Update scene state in background
                asyncio.create_task(_auto_update_scene_state(conv_id, model,
                                                _get_ai_name(ctx), _get_user_name(ctx), _get_ai_personality(ctx)))
            except Exception as e:
                yield json.dumps({"error": f"Failed to save response: {e}", "done": True}) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    @app.post("/rp/conversations/{conv_id}/continue")
    async def continue_conversation(conv_id: int):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")

        messages = await db.get_messages(conv_id)
        ctx = await _build_pipeline_ctx(conv, messages)

        model = _resolve_model(conv["model"])
        scenario = ctx.get("scenario") or {}
        settings = scenario.get("settings", {})
        ollama_options = _build_ollama_options(settings)

        chat_messages = _build_chat_messages(ctx)
        user_name = _get_user_name(ctx)
        conv_log.log_prompt(conv_id, "continue", model,
                            ctx["system_prompt"], ctx.get("post_prompt", ""),
                            ctx["messages"], ollama_options)

        async def stream():
            yield json.dumps({
                "debug_prompt": ctx["system_prompt"],
                "debug_user_prompt": ctx.get("post_prompt", ""),
                "debug_messages": ctx["messages"],
            }) + "\n"

            tokens = []
            raw = {}
            try:
                async for chunk in _ollama.chat_stream(
                    model=model, messages=chat_messages,
                    options=ollama_options, stop=[f"{user_name}:"],
                ):
                    yield json.dumps(chunk) + "\n"
                    if chunk.get("done"):
                        raw = chunk
                    elif not chunk.get("thinking"):
                        tokens.append(chunk["token"])
            except Exception as e:
                yield json.dumps({"error": str(e), "done": True}) + "\n"
                return
            try:
                response_text = "".join(tokens)
                post_ctx = {"response": response_text, "ai_name": _get_ai_name(ctx)}
                post_ctx = await _pipeline.run_post(post_ctx)
                await db.add_message(conv_id, "assistant", post_ctx["response"], raw_response=raw)
                conv_log.log_response(conv_id, "assistant", post_ctx["response"], raw)
                # Update scene state in background
                asyncio.create_task(_auto_update_scene_state(conv_id, model,
                                                _get_ai_name(ctx), _get_user_name(ctx), _get_ai_personality(ctx)))
            except Exception as e:
                yield json.dumps({"error": f"Failed to save response: {e}", "done": True}) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    @app.post("/rp/conversations/{conv_id}/auto-reply")
    async def auto_reply(conv_id: int):
        """Generate the next message for whichever side should go next.
        If last message was assistant, generate as user card (and save as 'user').
        If last message was user, generate as ai card (and save as 'assistant').
        """
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")

        messages = await db.get_messages(conv_id)
        last_role = messages[-1]["role"] if messages else "user"
        # Determine which side generates next
        generating_as_user = last_role == "assistant"
        save_role = "user" if generating_as_user else "assistant"

        if generating_as_user:
            # Swap cards so pipeline builds prompt for user's character
            swapped_conv = dict(conv)
            swapped_conv["user_card_id"] = conv["ai_card_id"]
            swapped_conv["ai_card_id"] = conv["user_card_id"]
            # Flip message roles so the model sees the conversation from the other side
            swapped_messages = []
            for m in messages:
                sm = dict(m)
                sm["role"] = "assistant" if m["role"] == "user" else "user"
                swapped_messages.append(sm)
            ctx = await _build_pipeline_ctx(swapped_conv, swapped_messages)
            # Override post prompt for user-side: shorter, more reactive
            user_card = await db.get_card(conv["user_card_id"])
            user_data = user_card["card_data"].get("data", user_card["card_data"])
            user_name_str = user_data.get("name", "User")
            ai_card = await db.get_card(conv["ai_card_id"])
            ai_data = ai_card["card_data"].get("data", ai_card["card_data"])
            ai_name_str = ai_data.get("name", "Character")
            ctx["post_prompt"] = (
                f"Write {user_name_str}'s next action or dialogue. Stay in character as {user_name_str}.\n"
                f"NEVER write {ai_name_str}'s actions, speech, or thoughts.\n"
                "Write 1-2 short paragraphs. Mix action and dialogue.\n"
                "Use first person for actions (e.g. 'I walk over') and direct speech for dialogue.\n"
                "Be reactive to what just happened — don't repeat or restart the scene."
            )
            # Re-inject scene state into overridden post prompt
            scene_state = ctx.get("scene_state", "")
            if scene_state.strip():
                ctx["post_prompt"] += "\n\n[Current Scene State — do NOT contradict this]\n" + scene_state.strip()
        else:
            ctx = await _build_pipeline_ctx(conv, messages)

        _auto_user_model = "qwen3:14b"
        if generating_as_user:
            model = _resolve_model(_auto_user_model)
        else:
            model = _resolve_model(conv["model"])
        scenario = ctx.get("scenario") or {}
        settings = scenario.get("settings", {})
        ollama_options = _build_ollama_options(settings)
        if generating_as_user:
            # Instruct model: lower temperature, no thinking
            ollama_options = {"temperature": 0.7, "num_predict": 256, "think": False}

        chat_messages = _build_chat_messages(ctx)
        user_name = _get_user_name(ctx)
        conv_log.log_prompt(conv_id, "auto_reply", model,
                            ctx["system_prompt"], ctx.get("post_prompt", ""),
                            ctx["messages"], ollama_options)

        async def stream():
            yield json.dumps({
                "debug_prompt": ctx["system_prompt"],
                "debug_user_prompt": ctx.get("post_prompt", ""),
                "debug_messages": ctx["messages"],
                "auto_role": save_role,
            }) + "\n"

            tokens = []
            raw = {}
            try:
                async for chunk in _ollama.chat_stream(
                    model=model, messages=chat_messages,
                    options=ollama_options, stop=[f"{user_name}:"],
                ):
                    yield json.dumps(chunk) + "\n"
                    if chunk.get("done"):
                        raw = chunk
                    elif not chunk.get("thinking"):
                        tokens.append(chunk["token"])
            except Exception as e:
                yield json.dumps({"error": str(e), "done": True}) + "\n"
                return

            try:
                response_text = "".join(tokens)
                post_ctx = {"response": response_text, "ai_name": _get_ai_name(ctx)}
                post_ctx = await _pipeline.run_post(post_ctx)
                await db.add_message(conv_id, save_role, post_ctx["response"], raw_response=raw)
                conv_log.log_response(conv_id, save_role, post_ctx["response"], raw)
                # Update scene state in background
                asyncio.create_task(_auto_update_scene_state(conv_id, model,
                                                _get_ai_name(ctx), _get_user_name(ctx), _get_ai_personality(ctx)))
            except Exception as e:
                yield json.dumps({"error": f"Failed to save response: {e}", "done": True}) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    # -- Static files --
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/rp", StaticFiles(directory=str(static_dir), html=True), name="rp-static")
