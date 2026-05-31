import asyncio
import json
import logging
import random
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from . import db
from .cards import parse_card_png, export_card_png, extract_name
from .models import (
    CardCreate, CardResponse, ScenarioCreate, ScenarioResponse,
    ConversationCreate, ConversationResponse, ConversationDetailResponse,
    ConversationCharacterResponse,
    MessageResponse, SendMessageRequest, SavePartialRequest, EditMessageRequest,
    SceneStateRequest, AuthorsNoteRequest,
    AddCharacterRequest, UpdateCharacterRequest,
)
from .pipeline import create_default_pipeline
from .budget import BudgetError, allocate_injections
from .mcp_client import get_router as get_mcp_router
from .research import research_dispatch
from .fewshot import get_fewshot_messages
from .summarize import maybe_generate_summary
from .prompt_builder import (
    get_ai_name, get_user_name, get_ai_personality, get_ai_pronouns,
    get_user_pronouns, get_user_description, build_chat_messages,
    build_multi_char_messages, build_ollama_options, scale_num_predict,
    budget_to_json, build_pipeline_ctx, build_pipeline_ctx_for_character,
    budget_ctx,
)
from .lorebook import extract_character_book
from . import conv_log

# Priority levels from aiserver's inference queue (lower = higher priority).
# Duplicated here to avoid a circular import from the host process.
_PRI_INTERACTIVE = 0   # UI chat: /message, /continue, /regenerate, /auto-reply
_PRI_BACKGROUND = 5    # card generation, scene state, summaries

_log = logging.getLogger("rp.routes")

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

    from .stock_phrases import make_stock_phrase_rewriter
    _pipeline.add_post(make_stock_phrase_rewriter(_ollama, _resolve_model))

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
        char_book = extract_character_book(card_data)
        if char_book and char_book.get("entries"):
            lorebook = await db.get_or_create_lorebook(
                card["id"],
                name=char_book.get("name", ""),
                scan_depth=char_book.get("scan_depth", 10),
                token_budget=char_book.get("token_budget", 2048),
            )
            await db.bulk_import_lorebook_entries(lorebook["id"], char_book["entries"])
            _log.info("Imported %d lorebook entries for card %s",
                      len(char_book["entries"]), name)
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

    # -- Lorebook --

    from .models import (
        LorebookEntryCreate, LorebookEntryResponse, LorebookUpdate, LorebookResponse,
    )

    @app.get("/rp/cards/{card_id}/lorebook", response_model=LorebookResponse)
    async def get_lorebook(card_id: int):
        card = await db.get_card(card_id)
        if not card:
            raise HTTPException(404, "Card not found")
        lorebook = await db.get_lorebook_for_card(card_id)
        if not lorebook:
            lorebook = await db.get_or_create_lorebook(card_id)
        entries = await db.get_lorebook_entries(lorebook["id"])
        return {**lorebook, "entries": entries}

    @app.put("/rp/cards/{card_id}/lorebook", response_model=LorebookResponse)
    async def update_lorebook_settings(card_id: int, req: LorebookUpdate):
        card = await db.get_card(card_id)
        if not card:
            raise HTTPException(404, "Card not found")
        lorebook = await db.get_lorebook_for_card(card_id)
        if not lorebook:
            lorebook = await db.get_or_create_lorebook(card_id)
        updated = await db.update_lorebook(lorebook["id"], **req.model_dump(exclude_none=True))
        entries = await db.get_lorebook_entries(updated["id"])
        return {**updated, "entries": entries}

    @app.post("/rp/cards/{card_id}/lorebook/entries", response_model=LorebookEntryResponse)
    async def create_entry(card_id: int, req: LorebookEntryCreate):
        card = await db.get_card(card_id)
        if not card:
            raise HTTPException(404, "Card not found")
        lorebook = await db.get_lorebook_for_card(card_id)
        if not lorebook:
            lorebook = await db.get_or_create_lorebook(card_id)
        return await db.create_lorebook_entry(lorebook["id"], **req.model_dump())

    @app.put("/rp/lorebook/entries/{entry_id}", response_model=LorebookEntryResponse)
    async def update_entry(entry_id: int, req: LorebookEntryCreate):
        result = await db.update_lorebook_entry(entry_id, **req.model_dump(exclude_unset=True))
        if not result:
            raise HTTPException(404, "Entry not found")
        return result

    @app.delete("/rp/lorebook/entries/{entry_id}")
    async def delete_entry(entry_id: int):
        if not await db.delete_lorebook_entry(entry_id):
            raise HTTPException(404, "Entry not found")
        return {"ok": True}

    @app.post("/rp/cards/{card_id}/lorebook/import")
    async def reimport_lorebook(card_id: int):
        card = await db.get_card(card_id)
        if not card:
            raise HTTPException(404, "Card not found")
        char_book = extract_character_book(card["card_data"])
        if not char_book or not char_book.get("entries"):
            raise HTTPException(400, "No character_book in card data")
        lorebook = await db.get_or_create_lorebook(
            card_id,
            name=char_book.get("name", ""),
            scan_depth=char_book.get("scan_depth", 10),
            token_budget=char_book.get("token_budget", 2048),
        )
        count = await db.bulk_import_lorebook_entries(lorebook["id"], char_book["entries"])
        return {"ok": True, "imported": count}

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
        if not await db.get_card(conv.user_card_id):
            raise HTTPException(404, "User card not found")
        if not await db.get_card(conv.ai_card_id):
            raise HTTPException(404, "AI card not found")

        all_ai_ids = [conv.ai_card_id] + [cid for cid in conv.ai_card_ids if cid != conv.ai_card_id]
        for cid in all_ai_ids[1:]:
            if not await db.get_card(cid):
                raise HTTPException(404, f"AI card {cid} not found")

        result = await db.create_conversation(
            conv.user_card_id, conv.ai_card_id, conv.scenario_id, conv.model
        )

        colors = ["#4a9eff", "#ff6b6b", "#51cf66", "#ffd43b", "#cc5de8", "#ff922b"]
        for i, cid in enumerate(all_ai_ids):
            await db.add_conversation_character(
                result["id"], cid,
                color=colors[i % len(colors)],
                generation_order=i,
            )

        ai_card = await db.get_card(conv.ai_card_id)
        user_card = await db.get_card(conv.user_card_id)
        scenario = await db.get_scenario(conv.scenario_id) if conv.scenario_id else None
        model = conv.model

        first_mes = await _get_or_generate_first_message(result, ai_card, user_card, scenario, model)

        if first_mes:
            await db.add_message(result["id"], "assistant", first_mes,
                                 character_card_id=conv.ai_card_id)
            ai_data = ai_card["card_data"].get("data", ai_card["card_data"])
            user_data = user_card["card_data"].get("data", user_card["card_data"])
            scenario_desc = (scenario or {}).get("description", "")
            asyncio.create_task(_auto_update_scene_state(
                result["id"], model,
                ai_data.get("name", "Character"), user_data.get("name", "User"),
                ai_data.get("description", ""),
                user_description=user_data.get("description", ""),
                scenario_context=scenario_desc))
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
        characters = await db.get_conversation_characters(conv_id)
        ai_cards = []
        for ch in characters:
            card = await db.get_card(ch["card_id"])
            if card:
                ai_cards.append(card)
        return ConversationDetailResponse(
            conversation=conv, user_card=user_card, ai_card=ai_card,
            ai_cards=ai_cards, characters=characters,
            scenario=scenario, messages=messages,
        )

    @app.delete("/rp/conversations/{conv_id}")
    async def delete_conversation(conv_id: int):
        if not await db.delete_conversation(conv_id):
            raise HTTPException(404, "Conversation not found")
        return {"ok": True}

    @app.get("/rp/conversations/{conv_id}/characters",
             response_model=list[ConversationCharacterResponse])
    async def list_characters(conv_id: int):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        return await db.get_conversation_characters(conv_id)

    @app.post("/rp/conversations/{conv_id}/characters",
              response_model=ConversationCharacterResponse)
    async def add_character(conv_id: int, req: AddCharacterRequest):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        if not await db.get_card(req.card_id):
            raise HTTPException(404, "Card not found")
        return await db.add_conversation_character(
            conv_id, req.card_id, color=req.color, generation_order=req.generation_order)

    @app.delete("/rp/conversations/{conv_id}/characters/{card_id}")
    async def remove_character(conv_id: int, card_id: int):
        if not await db.remove_conversation_character(conv_id, card_id):
            raise HTTPException(404, "Character not in conversation")
        return {"ok": True}

    @app.put("/rp/conversations/{conv_id}/characters/{card_id}",
             response_model=ConversationCharacterResponse)
    async def update_character(conv_id: int, card_id: int, req: UpdateCharacterRequest):
        kwargs = {}
        if req.color is not None:
            kwargs["color"] = req.color
        if req.generation_order is not None:
            kwargs["generation_order"] = req.generation_order
        result = await db.update_conversation_character(conv_id, card_id, **kwargs)
        if not result:
            raise HTTPException(404, "Character not in conversation")
        return result

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
            await db.add_message(conv_id, "assistant", first_mes,
                                 character_card_id=conv["ai_card_id"])
            ai_data = ai_card["card_data"].get("data", ai_card["card_data"])
            user_data = user_card["card_data"].get("data", user_card["card_data"])
            scenario_desc = (scenario or {}).get("description", "")
            asyncio.create_task(_auto_update_scene_state(
                conv_id, model,
                ai_data.get("name", "Character"), user_data.get("name", "User"),
                ai_data.get("description", ""),
                user_description=user_data.get("description", ""),
                scenario_context=scenario_desc))
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
        # Use messages since last scene state generation, capped at 10
        if last_msg_id is not None:
            new_msgs = [m for m in all_msgs if m["id"] > last_msg_id]
        else:
            new_msgs = all_msgs[-10:]
        if not new_msgs:
            new_msgs = all_msgs[-10:]
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

    # -- Author's Note --

    @app.put("/rp/conversations/{conv_id}/authors-note")
    async def update_authors_note(conv_id: int, req: AuthorsNoteRequest):
        if not await db.update_authors_note(conv_id, req.note, req.depth):
            raise HTTPException(404, "Conversation not found")
        return {"ok": True}

    # -- Summaries --

    @app.get("/rp/conversations/{conv_id}/summaries")
    async def list_summaries(conv_id: int):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        return await db.list_summaries(conv_id)

    @app.post("/rp/conversations/{conv_id}/summarize")
    async def trigger_summary(conv_id: int):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        ai_card = await db.get_card(conv["ai_card_id"])
        user_card = await db.get_card(conv["user_card_id"])
        ai_data = ai_card.get("card_data", {}).get("data", ai_card.get("card_data", {}))
        user_data = user_card.get("card_data", {}).get("data", user_card.get("card_data", {}))
        model = _resolve_model(conv["model"])
        result = await maybe_generate_summary(
            conv_id, _ollama, model,
            char_name=ai_data.get("name", "Character"),
            user_name=user_data.get("name", "User"),
            ai_personality=ai_data.get("description", ""),
            user_description=user_data.get("description", ""),
            resolve_model=_resolve_model,
        )
        if result is None:
            return {"ok": False, "reason": "no overflow — messages fit within budget"}
        return {"ok": True, "summary": result}

    # -- Chat --

    _template_path = Path(__file__).parent / "prompt.md"

    async def _build_pipeline_ctx(conv, messages):
        return await build_pipeline_ctx(
            conv, messages, pipeline=_pipeline, template_path=_template_path)

    async def _budget_ctx(ctx, model, ollama_options):
        return await budget_ctx(ctx, model, ollama_options, ollama=_ollama)

    async def _maybe_summarize(conv_id: int, model: str,
                               ai_name: str, user_name: str, ai_personality: str,
                               user_description: str = "",
                               messages_budget: int = 0):
        """Fire-and-forget summary generation when messages exceed budget."""
        try:
            await maybe_generate_summary(
                conv_id, _ollama, model,
                char_name=ai_name, user_name=user_name,
                ai_personality=ai_personality,
                user_description=user_description,
                resolve_model=_resolve_model,
                messages_budget=messages_budget,
            )
        except Exception as e:
            _log.warning("Summary generation failed for conv %d: %s", conv_id, e)

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
            return

        await db.set_cached_first_message(combo_hash, card_hash, scenario_hash, model, first_mes)
        _log.info("First message cached for combo %s", combo_hash)
        return first_mes

    async def _generate_first_message(conv, ai_card, user_card, scenario):
        """Generate a first message in the character's voice using scenario + card style reference."""
        ai_data = ai_card["card_data"].get("data", ai_card["card_data"])
        user_data = user_card["card_data"].get("data", user_card["card_data"])
        char_name = ai_data.get("name", "Character")
        user_name = user_data.get("name", "User")

        scenario_desc = (scenario or {}).get("description", "")
        style_reference = ai_data.get("first_mes", "")
        description = ai_data.get("description", "")
        personality = ai_data.get("personality", "")

        def _expand_vars(text: str) -> str:
            return (text
                    .replace("{{user}}", user_name)
                    .replace("{{char}}", char_name)
                    .replace("{{character}}", char_name)
                    .replace("${user}", user_name)
                    .replace("${char}", char_name))

        prompt_parts = []
        if description:
            prompt_parts.append(f"Character: {_expand_vars(description)}")
        if personality:
            prompt_parts.append(f"Personality: {_expand_vars(personality)}")

        if scenario_desc:
            prompt_parts.append(
                f"Scenario (follow this EXACTLY — who is where, who arrives, "
                f"who is already present):\n{_expand_vars(scenario_desc)}"
            )
            prompt_parts.append(
                f"Write the opening scene that sets up this scenario. "
                f"Write as {char_name} in third person (e.g. \"{char_name} stepped forward\", "
                f"not \"I stepped forward\")."
            )
        else:
            prompt_parts.append(
                f"Write a natural opening scene where {char_name} and {user_name} encounter each other. "
                f"Write as {char_name} in third person (e.g. \"{char_name} stepped forward\", "
                f"not \"I stepped forward\")."
            )

        prompt_parts.append(
            f"Write ONLY {char_name}'s actions, thoughts, and dialogue. "
            f"Do not write {user_name}'s actions or dialogue. 300-500 words."
        )

        if style_reference:
            prompt_parts.append(
                f"Style reference (match this prose register, voice, and level of detail — "
                f"do NOT copy the content, write a NEW scene for the scenario above):\n{_expand_vars(style_reference)}"
            )

        full_prompt = "\n\n".join(prompt_parts)
        model = _resolve_model(conv["model"])

        result = await asyncio.wait_for(
            _ollama.generate(
                model=model, prompt=full_prompt,
                system=f"You are writing the opening narration for {char_name}. Stay in character.",
                options={"temperature": 1.05, "num_predict": 768, "min_p": 0.1, "repeat_penalty": 1.08, "think": False},
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

    _scene_state_model = "qwen3:14b"

    async def _generate_scene_state(model: str, messages: list[dict], previous_state: str = "",
                                     ai_name: str = "Character", user_name: str = "User",
                                     ai_personality: str = "",
                                     user_description: str = "",
                                     scenario_context: str = "") -> str:
        from .scene_state import build_scene_state_prompt, clean_scene_state_response, validate_scene_state
        prompt = build_scene_state_prompt(messages, previous_state, ai_name, user_name,
                                          ai_personality, user_description=user_description,
                                          scenario_context=scenario_context)
        summary_model = _resolve_model(_scene_state_model) if _resolve_model else model
        try:
            result = await _ollama.generate(
                model=summary_model, prompt=prompt,
                system="Output only the scene state summary. No thinking, no preamble.",
                options={"temperature": 0.2, "num_predict": 800, "think": False},
            )
        except Exception as e:
            _log.error("Scene state generation failed: %s", e)
            return previous_state
        clean = clean_scene_state_response(result)
        return validate_scene_state(clean, previous_state, messages,
                                    character_names=[ai_name, user_name])

    async def _auto_update_scene_state(conv_id: int, model: str,
                                        ai_name: str = "Character", user_name: str = "User",
                                        ai_personality: str = "",
                                        user_description: str = "",
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
            # Slice to only messages since last scene state generation, capped at 10
            if last_msg_id is not None:
                new_msgs = [m for m in all_msgs if m["id"] > last_msg_id]
            else:
                new_msgs = all_msgs[-10:]
            if not new_msgs:
                new_msgs = all_msgs[-10:]
            if not new_msgs:
                return
            latest_msg_id = new_msgs[-1]["id"]
            msg_list = [{"role": m["role"], "content": m["content"]} for m in new_msgs]
            clean = await _generate_scene_state(model, msg_list, previous_state,
                                                ai_name, user_name, ai_personality,
                                                user_description=user_description,
                                                scenario_context=scenario_context)
            await db.update_scene_state(conv_id, clean, latest_msg_id)
            conv_log.log_scene_state(conv_id, previous_state, clean)
        except Exception as e:
            _log.warning("Scene state auto-update failed: %s", e)

    _UNSET = object()

    async def _stream_response(ctx, conv_id, conv, model, chat_messages,
                                ollama_options, user_name,
                                save_role="assistant", prefix_text="",
                                continue_msg_id=None, extra_debug=None,
                                character_card_id=_UNSET):
        debug = {
            "debug_prompt": ctx["system_prompt"],
            "debug_user_prompt": ctx.get("post_prompt", ""),
            "debug_messages": ctx["messages"],
        }
        if ctx.get("_summary"):
            debug["debug_summary"] = ctx["_summary"]
            debug["debug_summary_through"] = ctx.get("_summary_through_sequence", 0)
        if ctx.get("_lorebook_injected"):
            debug["debug_lorebook"] = ctx["_lorebook_injected"]
            debug["debug_lorebook_tokens"] = ctx.get("_lorebook_tokens", 0)
        if extra_debug:
            debug.update(extra_debug)
        yield json.dumps(debug) + "\n"

        tokens = []
        raw = {}
        try:
            async for chunk in _ollama.chat_stream(
                model=model, messages=chat_messages,
                options=ollama_options, stop=[f"{user_name}:", "\n\n\n"],
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
            recent_asst = [m["content"] for m in ctx.get("messages", [])
                           if m.get("role") == "assistant"][-6:]
            post_ctx = {
                "response": response_text, "ai_name": get_ai_name(ctx),
                "_char_pronouns": get_ai_pronouns(ctx),
                "_user_name": get_user_name(ctx),
                "_user_pronouns": get_user_pronouns(ctx),
                "_recent_assistant_messages": recent_asst,
            }
            post_ctx = await _pipeline.run_post(post_ctx)
            full_text = prefix_text + post_ctx["response"] if prefix_text else post_ctx["response"]
            if continue_msg_id:
                await db.update_message(continue_msg_id, full_text)
            else:
                await db.add_message(
                    conv_id, save_role, full_text, raw_response=raw,
                    system_prompt=ctx.get("system_prompt", ""),
                    scene_state=conv.get("scene_state", ""),
                    post_prompt=ctx.get("post_prompt", ""),
                    budget_json=budget_to_json(ctx),
                    prompt_json=chat_messages,
                    character_card_id=conv.get("ai_card_id") if character_card_id is _UNSET else character_card_id,
                )
            conv_log.log_response(conv_id, save_role, post_ctx["response"], raw)
            budget_report = ctx.get("_budget_report")
            msg_budget = budget_report.messages_budget if budget_report else 0
            asyncio.create_task(_auto_update_scene_state(conv_id, model,
                                            get_ai_name(ctx), get_user_name(ctx), get_ai_personality(ctx),
                                            user_description=get_user_description(ctx)))
            asyncio.create_task(_maybe_summarize(conv_id, model,
                                            get_ai_name(ctx), get_user_name(ctx), get_ai_personality(ctx),
                                            user_description=get_user_description(ctx),
                                            messages_budget=msg_budget))
        except Exception as e:
            yield json.dumps({"error": f"Failed to save response: {e}", "done": True}) + "\n"

    async def _generate_for_character(conv_id, conv, char_card, card_names,
                                      model, ollama_options, user_content,
                                      all_char_cards=None):
        """Generate one character's response in a multi-char conversation.

        Yields NDJSON chunks. Saves the message to DB when done.
        """
        messages = await db.get_messages(conv_id)
        ctx = await build_pipeline_ctx_for_character(
            conv, messages, char_card,
            pipeline=_pipeline, template_path=_template_path,
            all_char_cards=all_char_cards)

        card_data = char_card.get("card_data", {}).get("data", char_card.get("card_data", {}))
        char_name = card_data.get("name", "Character")
        char_id = char_card["id"]

        try:
            await _budget_ctx(ctx, model, ollama_options)
        except BudgetError as e:
            yield json.dumps({"error": f"Budget error for {char_name}: {e}", "done": False}) + "\n"
            return

        opts = {**ollama_options, "num_ctx": ctx["_num_ctx"]}
        chat_messages = build_multi_char_messages(ctx, char_id, card_names)
        user_name = get_user_name(ctx)

        tokens = []
        raw = {}
        try:
            async for chunk in _ollama.chat_stream(
                model=model, messages=chat_messages,
                options=opts, stop=[f"{user_name}:", "\n\n\n"],
            ):
                yield json.dumps(chunk) + "\n"
                if chunk.get("done"):
                    raw = chunk
                elif not chunk.get("thinking"):
                    tokens.append(chunk["token"])
        except Exception as e:
            yield json.dumps({"error": str(e), "done": False}) + "\n"
            return

        response_text = "".join(tokens)
        recent_asst = [m["content"] for m in ctx.get("messages", [])
                       if m.get("role") == "assistant"
                       and m.get("_character_card_id") == char_id][-6:]
        post_ctx = {
            "response": response_text, "ai_name": char_name,
            "_char_pronouns": card_data.get("pronouns", ""),
            "_user_name": get_user_name(ctx),
            "_user_pronouns": get_user_pronouns(ctx),
            "_recent_assistant_messages": recent_asst,
        }
        post_ctx = await _pipeline.run_post(post_ctx)
        final_text = post_ctx["response"]

        await db.add_message(
            conv_id, "assistant", final_text, raw_response=raw,
            system_prompt=ctx.get("system_prompt", ""),
            scene_state=conv.get("scene_state", ""),
            post_prompt=ctx.get("post_prompt", ""),
            budget_json=budget_to_json(ctx),
            prompt_json=chat_messages,
            character_card_id=char_id,
        )
        conv_log.log_response(conv_id, "assistant", final_text, raw)

    @app.post("/rp/conversations/{conv_id}/message")
    async def send_message(conv_id: int, req: SendMessageRequest):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")

        characters = await db.get_conversation_characters(conv_id)
        is_multi = len(characters) > 1

        await db.add_message(conv_id, "user", req.content)
        conv_log.log_response(conv_id, "user", req.content)

        if is_multi:
            return await _send_multi_char_message(conv_id, conv, characters, req.content)

        messages = await db.get_messages(conv_id)
        ctx = await _build_pipeline_ctx(conv, messages)

        model = _resolve_model(conv["model"])
        scenario = ctx.get("scenario") or {}
        settings = scenario.get("settings", {})
        ollama_options = scale_num_predict(
            build_ollama_options(settings), req.content)

        # Gather optional injections (research + fewshot)
        research = await research_dispatch(_ollama, req.content)
        fewshot_msgs = await get_fewshot_messages(
            _ollama, ctx["messages"], card_id=conv["ai_card_id"],
        )

        # Budget gate: cap injections so they don't starve conversation history
        alloc = await allocate_injections(
            ctx, model=model, ollama=_ollama,
            num_predict=ollama_options.get("num_predict"),
            research_text=research,
            fewshot_msgs=fewshot_msgs if fewshot_msgs and ctx["messages"] else None,
            model_ctx_override=ollama_options.get("num_ctx"),
        )

        if research and alloc.keep_research:
            _log.info("Injecting research into context (%d chars)", len(research))
            conv_log.log_research(conv_id, req.content, research)
            ctx["post_prompt"] = (
                ctx.get("post_prompt", "")
                + "\n\n[Research notes — weave these facts naturally if relevant, "
                + "don't quote them verbatim or mention looking anything up]\n"
                + research
            )

        if fewshot_msgs and ctx["messages"] and alloc.keep_fewshot:
            n_examples = len(fewshot_msgs) // 2
            _log.info("Injecting %d fewshot examples (vector-matched, system prompt)", n_examples)
            conv_log.log_fewshot(conv_id, n_examples, fewshot_msgs)
            ref_parts = []
            for i in range(0, len(fewshot_msgs), 2):
                user_msg = fewshot_msgs[i]["content"]
                asst_msg = fewshot_msgs[i + 1]["content"]
                ref_parts.append(f"User: {user_msg}\n{get_ai_name(ctx)}: {asst_msg}")
            ctx["system_prompt"] += (
                "\n\nVoice reference (match this tone and style, NOT the scene content"
                " — these are from different scenes):\n"
                + "\n---\n".join(ref_parts)
            )

        ctx["_injection_alloc"] = alloc

        try:
            await _budget_ctx(ctx, model, ollama_options)
        except BudgetError as e:
            err_msg = f"Prompt does not fit model context: {e}"
            async def _err_stream():
                yield json.dumps({
                    "error": err_msg,
                    "done": True,
                }) + "\n"
            return StreamingResponse(
                _err_stream(), media_type="application/x-ndjson",
                status_code=413,
            )

        # Tell Ollama to load the model with its real context window
        ollama_options = {**ollama_options, "num_ctx": ctx["_num_ctx"]}

        chat_messages = build_chat_messages(ctx)
        user_name = get_user_name(ctx)
        conv_log.log_prompt(conv_id, "send_message", model,
                            ctx["system_prompt"], ctx.get("post_prompt", ""),
                            ctx["messages"], ollama_options)

        async def stream():
            debug = {
                "debug_prompt": ctx["system_prompt"],
                "debug_user_prompt": ctx.get("post_prompt", ""),
                "debug_messages": ctx["messages"],
            }
            if ctx.get("_summary"):
                debug["debug_summary"] = ctx["_summary"]
                debug["debug_summary_through"] = ctx.get("_summary_through_sequence", 0)
            yield json.dumps(debug) + "\n"

            cur_messages = list(chat_messages)
            max_tool_rounds = 3
            final_text = ""
            raw = {}

            for _round in range(max_tool_rounds + 1):
                tokens = []
                try:
                    async for chunk in _ollama.chat_stream(
                        model=model, messages=cur_messages,
                        options=ollama_options, stop=[f"{user_name}:", "\n\n\n"],
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
                recent_asst = [m["content"] for m in ctx.get("messages", [])
                               if m.get("role") == "assistant"][-6:]
                post_ctx = {
                    "response": final_text, "ai_name": get_ai_name(ctx),
                    "_char_pronouns": get_ai_pronouns(ctx),
                    "_user_name": get_user_name(ctx),
                    "_user_pronouns": get_user_pronouns(ctx),
                    "_recent_assistant_messages": recent_asst,
                }
                post_ctx = await _pipeline.run_post(post_ctx)
                await db.add_message(
                    conv_id, "assistant", post_ctx["response"], raw_response=raw,
                    system_prompt=ctx.get("system_prompt", ""),
                    scene_state=conv.get("scene_state", ""),
                    post_prompt=ctx.get("post_prompt", ""),
                    budget_json=budget_to_json(ctx),
                    prompt_json=chat_messages,
                    character_card_id=conv["ai_card_id"],
                )
                conv_log.log_response(conv_id, "assistant", post_ctx["response"], raw)
                budget_report = ctx.get("_budget_report")
                msg_budget = budget_report.messages_budget if budget_report else 0
                asyncio.create_task(_auto_update_scene_state(conv_id, model,
                                                get_ai_name(ctx), get_user_name(ctx), get_ai_personality(ctx),
                                                user_description=get_user_description(ctx)))
                asyncio.create_task(_maybe_summarize(conv_id, model,
                                                get_ai_name(ctx), get_user_name(ctx), get_ai_personality(ctx),
                                                user_description=get_user_description(ctx),
                                                messages_budget=msg_budget))
            except Exception as e:
                yield json.dumps({"error": f"Failed to save response: {e}", "done": True}) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    async def _select_turn_order(messages, characters, card_names, user_name):
        """Ask a small model which characters should respond and in what order."""
        name_to_id = {}
        for card_id, name in card_names.items():
            name_to_id[name.lower()] = card_id
        all_names = [card_names[ch["card_id"]] for ch in characters if ch["card_id"] in card_names]

        recent = []
        for m in messages[-8:]:
            role = m["role"]
            content = m["content"]
            char_id = m.get("character_card_id") or m.get("_character_card_id")
            if char_id and char_id in card_names:
                speaker = card_names[char_id]
            elif role == "user":
                speaker = user_name
            else:
                speaker = "Assistant"
            recent.append(f"{speaker}: {content[:200]}")

        system = (
            "You direct a roleplay conversation. Given the recent messages and available characters, "
            "decide which characters should respond next and in what order.\n"
            "Not every character needs to respond every turn — only those who would naturally react.\n"
            "Return ONLY a JSON array of character names, e.g. [\"Riley\", \"Amber\"]\n"
            "Return at least one character. No explanation, just the JSON array."
        )
        prompt_text = (
            f"Available characters: {', '.join(all_names)}\n"
            f"User character: {user_name}\n\n"
            "Recent messages:\n" + "\n".join(recent)
        )

        try:
            selector_model = _resolve_model("qwen3:8b")
            result = await _ollama.chat(
                model=selector_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt_text},
                ],
                options={"temperature": 0.3, "num_predict": 64, "think": False},
            )
            raw_text = result.get("message", {}).get("content", "").strip()
            start = raw_text.find("[")
            end = raw_text.rfind("]")
            if start >= 0 and end > start:
                selected_names = json.loads(raw_text[start:end + 1])
            else:
                selected_names = json.loads(raw_text)

            selected_ids = []
            for name in selected_names:
                card_id = name_to_id.get(name.lower())
                if card_id is not None and card_id not in selected_ids:
                    selected_ids.append(card_id)

            if not selected_ids:
                return characters

            if random.random() < 0.10:
                random.shuffle(selected_ids)
                _log.info("Turn selector: randomized order → %s",
                          [card_names.get(cid) for cid in selected_ids])

            id_set = {ch["card_id"] for ch in characters}
            selected_ids = [cid for cid in selected_ids if cid in id_set]
            if not selected_ids:
                return characters

            id_to_ch = {ch["card_id"]: ch for ch in characters}
            ordered = [id_to_ch[cid] for cid in selected_ids]

            _log.info("Turn selector: %s → %s",
                      [card_names.get(ch["card_id"]) for ch in characters],
                      [card_names.get(ch["card_id"]) for ch in ordered])
            return ordered

        except Exception as e:
            _log.warning("Turn selector failed, using default order: %s", e)
            return characters

    async def _send_multi_char_message(conv_id, conv, characters, user_content):
        """Handle message in a multi-character conversation with dynamic turn order."""
        model = _resolve_model(conv["model"])
        scenario = {}
        if conv["scenario_id"]:
            scenario = await db.get_scenario(conv["scenario_id"]) or {}
        settings = scenario.get("settings", {})
        ollama_options = scale_num_predict(
            build_ollama_options(settings), user_content)

        char_cards = {}
        card_names = {}
        for ch in characters:
            card = await db.get_card(ch["card_id"])
            if card:
                char_cards[ch["card_id"]] = card
                cdata = card.get("card_data", {}).get("data", card.get("card_data", {}))
                card_names[ch["card_id"]] = cdata.get("name", "Character")

        all_cards_ordered = [char_cards[ch["card_id"]] for ch in characters if ch["card_id"] in char_cards]

        messages = await db.get_messages(conv_id)
        user_card = await db.get_card(conv["user_card_id"])
        u_data = user_card["card_data"].get("data", user_card["card_data"]) if user_card else {}
        u_name = u_data.get("name", "User")
        responding = await _select_turn_order(messages, characters, card_names, u_name)

        async def multi_stream():
            yield json.dumps({"multi_character": True, "character_count": len(responding)}) + "\n"

            for ch in responding:
                card_id = ch["card_id"]
                card = char_cards.get(card_id)
                if not card:
                    continue
                name = card_names.get(card_id, "Character")

                yield json.dumps({
                    "character_start": {
                        "card_id": card_id,
                        "name": name,
                        "color": ch.get("color", ""),
                    }
                }) + "\n"

                async for chunk in _generate_for_character(
                    conv_id, conv, card, card_names,
                    model, ollama_options, user_content,
                    all_char_cards=all_cards_ordered,
                ):
                    yield chunk

                yield json.dumps({"character_done": {"card_id": card_id, "name": name}}) + "\n"

            asyncio.create_task(_auto_update_scene_state(
                conv_id, model,
                card_names.get(characters[0]["card_id"], "Character"),
                get_user_name({"user_card": char_cards.get(conv["user_card_id"], await db.get_card(conv["user_card_id"]))}),
                "",
                user_description=""))
            yield json.dumps({"done": True}) + "\n"

        return StreamingResponse(multi_stream(), media_type="application/x-ndjson")

    @app.post("/rp/conversations/{conv_id}/save-partial")
    async def save_partial(conv_id: int, req: SavePartialRequest):
        """Save a partial response when the user hits Stop mid-stream."""
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        content = req.content.strip()
        if not content:
            return {"ok": False}
        role = req.role if req.role in ("assistant", "user") else "assistant"
        await db.add_message(conv_id, role, content)
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
        ollama_options = build_ollama_options(settings)

        try:
            await _budget_ctx(ctx, model, ollama_options)
        except BudgetError as e:
            err_msg = f"Prompt does not fit model context: {e}"
            async def _err_stream():
                yield json.dumps({
                    "error": err_msg,
                    "done": True,
                }) + "\n"
            return StreamingResponse(
                _err_stream(), media_type="application/x-ndjson",
                status_code=413,
            )

        # Tell Ollama to load the model with its real context window
        ollama_options = {**ollama_options, "num_ctx": ctx["_num_ctx"]}

        chat_messages = build_chat_messages(ctx)
        user_name = get_user_name(ctx)
        conv_log.log_prompt(conv_id, "regenerate", model,
                            ctx["system_prompt"], ctx.get("post_prompt", ""),
                            ctx["messages"], ollama_options)

        return StreamingResponse(
            _stream_response(ctx, conv_id, conv, model, chat_messages,
                              ollama_options, user_name),
            media_type="application/x-ndjson")

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
        ollama_options = build_ollama_options(settings)

        try:
            await _budget_ctx(ctx, model, ollama_options)
        except BudgetError as e:
            err_msg = f"Prompt does not fit model context: {e}"
            async def _err_stream():
                yield json.dumps({
                    "error": err_msg,
                    "done": True,
                }) + "\n"
            return StreamingResponse(
                _err_stream(), media_type="application/x-ndjson",
                status_code=413,
            )

        # Tell Ollama to load the model with its real context window
        ollama_options = {**ollama_options, "num_ctx": ctx["_num_ctx"]}

        # For continue: use the last assistant message as priming prefix
        # so the model continues mid-sentence instead of starting fresh.
        prefix_text = ""
        continue_msg_id = None
        budgeted_msgs = ctx["messages"]
        if budgeted_msgs and budgeted_msgs[-1].get("role") == "assistant":
            last_asst = budgeted_msgs[-1]
            prefix_text = last_asst.get("content", "")
            continue_msg_id = last_asst.get("_id")
            ctx["messages"] = budgeted_msgs[:-1]

        chat_messages = build_chat_messages(ctx)
        if prefix_text:
            chat_messages[-1] = {"role": "assistant", "content": prefix_text}

        user_name = get_user_name(ctx)
        conv_log.log_prompt(conv_id, "continue", model,
                            ctx["system_prompt"], ctx.get("post_prompt", ""),
                            ctx["messages"], ollama_options)

        return StreamingResponse(
            _stream_response(ctx, conv_id, conv, model, chat_messages,
                              ollama_options, user_name,
                              prefix_text=prefix_text,
                              continue_msg_id=continue_msg_id),
            media_type="application/x-ndjson")

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

        characters = await db.get_conversation_characters(conv_id)
        is_multi = len(characters) > 1

        if not generating_as_user and is_multi:
            last_user_content = ""
            for m in reversed(messages):
                if m["role"] == "user":
                    last_user_content = m["content"]
                    break
            return await _send_multi_char_message(
                conv_id, conv, characters, last_user_content)

        if generating_as_user:
            orig_ai_card = await db.get_card(conv["ai_card_id"])
            orig_ai_data = orig_ai_card["card_data"].get("data", orig_ai_card["card_data"])
            orig_user_card = await db.get_card(conv["user_card_id"])
            orig_user_data = orig_user_card["card_data"].get("data", orig_user_card["card_data"])
            swapped_conv = dict(conv)
            swapped_conv["user_card_id"] = conv["ai_card_id"]
            swapped_conv["ai_card_id"] = conv["user_card_id"]
            swapped_conv["_scenario_names"] = {
                "char": orig_ai_data.get("name", "Character"),
                "user": orig_user_data.get("name", "User"),
            }
            swapped_messages = []
            for m in messages:
                sm = dict(m)
                sm["role"] = "assistant" if m["role"] == "user" else "user"
                swapped_messages.append(sm)
            ctx = await _build_pipeline_ctx(swapped_conv, swapped_messages)
            user_name_str = orig_user_data.get("name", "User")
            ai_char_names = []
            for ch in characters:
                card = await db.get_card(ch["card_id"])
                if card:
                    cdata = card["card_data"].get("data", card["card_data"])
                    ai_char_names.append(cdata.get("name", "Character"))
            never_write = ", ".join(ai_char_names) if ai_char_names else "the other characters"
            ctx["post_prompt"] = (
                f"Write {user_name_str}'s next action or dialogue. Stay in character as {user_name_str}.\n"
                f"NEVER write {never_write}'s actions, speech, or thoughts.\n"
                "Write 1-2 short paragraphs. Mix action and dialogue.\n"
                "Use first person for actions (e.g. 'I walk over') and direct speech for dialogue.\n"
                "Be reactive to what just happened — don't repeat or restart the scene."
            )
            recent_user = [m["content"][:150] for m in messages if m["role"] == "user"][-3:]
            if recent_user:
                ctx["post_prompt"] += (
                    "\n\nYou already wrote these — write something COMPLETELY DIFFERENT "
                    "(different actions, different words, advance the scene):\n"
                    + "\n---\n".join(recent_user)
                )
            scene_state = ctx.get("scene_state", "")
            if scene_state.strip():
                ctx["post_prompt"] += "\n\n[Current Scene State — do NOT contradict this]\n" + scene_state.strip()
        else:
            ctx = await _build_pipeline_ctx(conv, messages)

        if generating_as_user:
            model = _resolve_model("qwen3:14b")
            ollama_options = {
                "temperature": 0.7, "num_predict": 256, "think": False,
                "repeat_penalty": 1.15, "repeat_last_n": 256,
            }
        else:
            model = _resolve_model(conv["model"])
            scenario = ctx.get("scenario") or {}
            settings = scenario.get("settings", {})
            ollama_options = build_ollama_options(settings)

        try:
            await _budget_ctx(ctx, model, ollama_options)
        except BudgetError as e:
            err_msg = f"Prompt does not fit model context: {e}"
            async def _err_stream():
                yield json.dumps({
                    "error": err_msg,
                    "done": True,
                }) + "\n"
            return StreamingResponse(
                _err_stream(), media_type="application/x-ndjson",
                status_code=413,
            )

        ollama_options = {**ollama_options, "num_ctx": ctx["_num_ctx"]}

        chat_messages = build_chat_messages(ctx)
        if generating_as_user:
            chat_messages.pop()
        user_name = get_user_name(ctx)
        conv_log.log_prompt(conv_id, "auto_reply", model,
                            ctx["system_prompt"], ctx.get("post_prompt", ""),
                            ctx["messages"], ollama_options)

        return StreamingResponse(
            _stream_response(ctx, conv_id, conv, model, chat_messages,
                              ollama_options, user_name,
                              save_role=save_role,
                              extra_debug={"auto_role": save_role},
                              character_card_id=None if generating_as_user else _UNSET),
            media_type="application/x-ndjson")

    # -- Compare (A/B eval) --
    from .eval_routes import setup_eval_routes
    setup_eval_routes(
        app, _ollama, _pipeline, _resolve_model, _template_path,
        _auto_update_scene_state,
    )

    # -- Static files --
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/rp", StaticFiles(directory=str(static_dir), html=True), name="rp-static")
