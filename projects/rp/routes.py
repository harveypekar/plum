import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from . import db
from .cards import parse_card_png, export_card_png, extract_name
from .models import (
    CardCreate, CardResponse, ScenarioCreate, ScenarioResponse,
    ConversationCreate, ConversationResponse, ConversationDetailResponse,
    MessageResponse, SendMessageRequest, EditMessageRequest,
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
        return await db.create_card(name, card_data, avatar=avatar)

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

    # -- Scenarios --

    @app.get("/rp/scenarios", response_model=list[ScenarioResponse])
    async def list_scenarios():
        return await db.list_scenarios()

    @app.post("/rp/scenarios", response_model=ScenarioResponse)
    async def create_scenario(scenario: ScenarioCreate):
        return await db.create_scenario(scenario.name, scenario.description, scenario.settings)

    @app.get("/rp/scenarios/{scenario_id}", response_model=ScenarioResponse)
    async def get_scenario(scenario_id: int):
        s = await db.get_scenario(scenario_id)
        if not s:
            raise HTTPException(404, "Scenario not found")
        return s

    @app.put("/rp/scenarios/{scenario_id}", response_model=ScenarioResponse)
    async def update_scenario(scenario_id: int, scenario: ScenarioCreate):
        result = await db.update_scenario(scenario_id, scenario.name, scenario.description, scenario.settings)
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
        # Add first message from AI card if it has one
        ai_card = await db.get_card(conv.ai_card_id)
        ai_data = ai_card["card_data"].get("data", ai_card["card_data"])
        first_mes = ai_data.get("first_mes", "")
        if first_mes:
            # Expand variables in first message
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

    # -- Chat --

    @app.post("/rp/conversations/{conv_id}/message")
    async def send_message(conv_id: int, req: SendMessageRequest):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")

        # Save user message
        await db.add_message(conv_id, "user", req.content)

        # Load context
        user_card = await db.get_card(conv["user_card_id"])
        ai_card = await db.get_card(conv["ai_card_id"])
        scenario = await db.get_scenario(conv["scenario_id"]) if conv["scenario_id"] else {}
        messages = await db.get_messages(conv_id)

        # Build pipeline context
        ctx = {
            "user_card": user_card,
            "ai_card": ai_card,
            "scenario": scenario or {},
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "system_prompt": "",
        }
        ctx = await _pipeline.run_pre(ctx)

        # Build prompt from last user message
        prompt = ctx["messages"][-1]["content"] if ctx["messages"] else req.content
        system = ctx["system_prompt"]

        # Resolve model
        model = _resolve_model(conv["model"])

        # Stream from Ollama
        async def stream():
            tokens = []
            raw = {}
            try:
                async for chunk in _ollama.generate_stream(
                    model=model, prompt=prompt, system=system,
                ):
                    yield json.dumps(chunk) + "\n"
                    if chunk.get("done"):
                        raw = chunk
                    elif not chunk.get("thinking"):
                        tokens.append(chunk["token"])
            except Exception as e:
                yield json.dumps({"error": str(e), "done": True}) + "\n"
                return

            # Save AI response
            try:
                response_text = "".join(tokens)
                post_ctx = {"response": response_text}
                post_ctx = await _pipeline.run_post(post_ctx)
                await db.add_message(conv_id, "assistant", post_ctx["response"], raw_response=raw)
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
        # Re-run as if user just sent their last message
        conv = await db.get_conversation(conv_id)
        user_card = await db.get_card(conv["user_card_id"])
        ai_card = await db.get_card(conv["ai_card_id"])
        scenario = await db.get_scenario(conv["scenario_id"]) if conv["scenario_id"] else {}
        messages = await db.get_messages(conv_id)

        ctx = {
            "user_card": user_card,
            "ai_card": ai_card,
            "scenario": scenario or {},
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "system_prompt": "",
        }
        ctx = await _pipeline.run_pre(ctx)
        # Find last user message for the prompt
        user_msgs = [m for m in ctx["messages"] if m["role"] == "user"]
        prompt = user_msgs[-1]["content"] if user_msgs else ""
        system = ctx["system_prompt"]
        model = _resolve_model(conv["model"])

        async def stream():
            tokens = []
            raw = {}
            try:
                async for chunk in _ollama.generate_stream(
                    model=model, prompt=prompt, system=system,
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
                post_ctx = {"response": response_text}
                post_ctx = await _pipeline.run_post(post_ctx)
                await db.add_message(conv_id, "assistant", post_ctx["response"], raw_response=raw)
            except Exception as e:
                yield json.dumps({"error": f"Failed to save response: {e}", "done": True}) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    # -- Static files --
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/rp", StaticFiles(directory=str(static_dir), html=True), name="rp-static")
