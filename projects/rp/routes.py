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

_ollama = None
_pipeline = None
_resolve_model = None


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
        card = await db.create_card(name, card_data, avatar=avatar)
        # Auto-extract scenario from card if present
        data = card_data.get("data", card_data)
        scenario_text = data.get("scenario", "")
        if scenario_text.strip():
            await db.create_scenario(name + " — Scenario", scenario_text, {})
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

    _card_gen_model = "q25"

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
            "Write vivid, specific descriptions with depth and quirks.\n"
            "Respond with ONLY the JSON object. No markdown fences, no explanation."
        )

        model = _resolve_model(_card_gen_model) if _resolve_model else _card_gen_model
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

        model = _resolve_model(_card_gen_model) if _resolve_model else _card_gen_model
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
        # First message priority: scenario > card
        ai_card = await db.get_card(conv.ai_card_id)
        ai_data = ai_card["card_data"].get("data", ai_card["card_data"])
        scenario = await db.get_scenario(conv.scenario_id) if conv.scenario_id else None
        first_mes = (scenario or {}).get("first_message", "") or ai_data.get("first_mes", "")
        if first_mes:
            user_card = await db.get_card(conv.user_card_id)
            user_data = user_card["card_data"].get("data", user_card["card_data"])
            first_mes = first_mes.replace("${user}", user_data.get("name", "User"))
            first_mes = first_mes.replace("${char}", ai_data.get("name", "Character"))
            await db.add_message(result["id"], "assistant", first_mes)
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
        messages = await db.get_messages(conv_id)
        msg_list = [{"role": m["role"], "content": m["content"]} for m in messages]
        model = _resolve_model(conv["model"])
        clean = await _generate_scene_state(model, msg_list)
        await db.update_scene_state(conv_id, clean)
        return {"scene_state": clean}

    # -- Chat --

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

    _log = logging.getLogger("rp.routes")

    _scene_state_model = "q25"
    _scene_state_window = 8

    def _build_scene_state_prompt(messages: list[dict]) -> str:
        recent = messages[-_scene_state_window:]
        history = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
        return (
            "Below are the LAST FEW messages of a roleplay conversation. "
            "Based ONLY on these final messages, describe the CURRENT state of the scene "
            "as it stands RIGHT NOW at the very end.\n\n"
            "If characters moved, changed clothes, or shifted position in these messages, "
            "report the NEW state, not where they were before.\n\n"
            "Format — one short line per category:\n"
            "Location: (where are they right now)\n"
            "Clothing: (what each character is currently wearing, or naked)\n"
            "Position: (posture, who is where, physical contact)\n"
            "Props: (objects currently in play)\n"
            "Mood: (emotional atmosphere right now)\n\n"
            "No narration, no story, no explanation. Just the current facts.\n\n"
            f"Recent messages:\n{history}"
        )

    async def _generate_scene_state(model: str, messages: list[dict]) -> str:
        prompt = _build_scene_state_prompt(messages)
        summary_model = _resolve_model(_scene_state_model) if _resolve_model else model
        result = await _ollama.generate(
            model=summary_model, prompt=prompt,
            system="Output only the scene state summary. No thinking, no preamble.",
            options={"temperature": 0.2, "num_predict": 150, "think": False},
        )
        clean = result.strip()
        if "<think>" in clean:
            clean = clean.split("</think>")[-1].strip()
        return clean

    async def _auto_update_scene_state(conv_id: int, model: str, messages: list[dict]):
        """Background task: ask LLM to summarize current scene state."""
        try:
            clean = await _generate_scene_state(model, messages)
            await db.update_scene_state(conv_id, clean)
        except Exception as e:
            _log.warning("Scene state auto-update failed: %s", e)

    @app.post("/rp/conversations/{conv_id}/message")
    async def send_message(conv_id: int, req: SendMessageRequest):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")

        await db.add_message(conv_id, "user", req.content)

        messages = await db.get_messages(conv_id)
        ctx = await _build_pipeline_ctx(conv, messages)

        model = _resolve_model(conv["model"])
        scenario = ctx.get("scenario") or {}
        settings = scenario.get("settings", {})
        ollama_options = {k: v for k, v in settings.items() if k not in ("context_strategy", "max_context_tokens", "model")}

        chat_messages = _build_chat_messages(ctx)
        user_name = _get_user_name(ctx)

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
                # Update scene state in background
                updated_msgs = ctx["messages"] + [{"role": "assistant", "content": post_ctx["response"]}]
                asyncio.create_task(_auto_update_scene_state(conv_id, model, updated_msgs))
            except Exception as e:
                yield json.dumps({"error": f"Failed to save response: {e}", "done": True}) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

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
        ollama_options = {k: v for k, v in settings.items() if k not in ("context_strategy", "max_context_tokens", "model")}

        chat_messages = _build_chat_messages(ctx)
        user_name = _get_user_name(ctx)

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
                # Update scene state in background
                updated_msgs = ctx["messages"] + [{"role": "assistant", "content": post_ctx["response"]}]
                asyncio.create_task(_auto_update_scene_state(conv_id, model, updated_msgs))
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
        ollama_options = {k: v for k, v in settings.items() if k not in ("context_strategy", "max_context_tokens", "model")}

        chat_messages = _build_chat_messages(ctx)
        user_name = _get_user_name(ctx)

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
                # Update scene state in background
                updated_msgs = ctx["messages"] + [{"role": "assistant", "content": post_ctx["response"]}]
                asyncio.create_task(_auto_update_scene_state(conv_id, model, updated_msgs))
            except Exception as e:
                yield json.dumps({"error": f"Failed to save response: {e}", "done": True}) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    # -- Static files --
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/rp", StaticFiles(directory=str(static_dir), html=True), name="rp-static")
