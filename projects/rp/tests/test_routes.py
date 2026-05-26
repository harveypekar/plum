"""Integration tests for RP FastAPI routes.

Exercises actual HTTP endpoints via httpx AsyncClient with an in-memory
fake DB and stub Ollama. Tests request validation, response formatting,
status codes, streaming NDJSON, and route wiring.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from projects.rp import db


# ---------------------------------------------------------------------------
# Fake DB — in-memory store that replaces asyncpg-backed db module functions
# ---------------------------------------------------------------------------

class FakeDB:
    """In-memory store mimicking rp.db functions."""

    def __init__(self):
        self.cards: dict[int, dict] = {}
        self.avatars: dict[int, bytes] = {}
        self.scenarios: dict[int, dict] = {}
        self.conversations: dict[int, dict] = {}
        self.messages: dict[int, dict] = {}
        self.eval_sets: dict[int, dict] = {}
        self.eval_candidates: dict[int, dict] = {}
        self.conv_characters: list[dict] = []
        self._next = {"card": 1, "scenario": 1, "conv": 1, "msg": 1,
                       "eval_set": 1, "eval_cand": 1, "conv_char": 1}

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _id(self, kind: str) -> int:
        val = self._next[kind]
        self._next[kind] += 1
        return val

    # -- Cards --

    async def list_cards(self) -> list[dict]:
        return sorted(self.cards.values(), key=lambda c: c["id"])

    async def get_card(self, card_id: int) -> dict | None:
        return self.cards.get(card_id)

    async def find_card_by_name(self, name: str) -> dict | None:
        for c in self.cards.values():
            if c["name"] == name:
                return c
        return None

    async def create_card(self, name: str, card_data: dict,
                          avatar: bytes | None = None) -> dict:
        cid = self._id("card")
        now = self._now()
        card = {
            "id": cid, "name": name, "card_data": card_data,
            "has_avatar": avatar is not None,
            "created_at": now, "updated_at": now,
        }
        self.cards[cid] = card
        if avatar:
            self.avatars[cid] = avatar
        return card

    async def update_card(self, card_id: int, name: str, card_data: dict,
                          avatar: bytes | None = None) -> dict | None:
        if card_id not in self.cards:
            return None
        self.cards[card_id].update(
            name=name, card_data=card_data, updated_at=self._now())
        if avatar is not None:
            self.avatars[card_id] = avatar
            self.cards[card_id]["has_avatar"] = True
        return self.cards[card_id]

    async def delete_card(self, card_id: int) -> bool:
        return self.cards.pop(card_id, None) is not None

    async def get_card_avatar(self, card_id: int) -> bytes | None:
        return self.avatars.get(card_id)

    async def set_card_avatar(self, card_id: int, avatar: bytes) -> bool:
        if card_id not in self.cards:
            return False
        self.avatars[card_id] = avatar
        self.cards[card_id]["has_avatar"] = True
        return True

    # -- Scenarios --

    async def list_scenarios(self) -> list[dict]:
        return sorted(self.scenarios.values(), key=lambda s: s["id"])

    async def get_scenario(self, scenario_id: int) -> dict | None:
        return self.scenarios.get(scenario_id)

    async def find_scenario_by_name(self, name: str) -> dict | None:
        for s in self.scenarios.values():
            if s["name"] == name:
                return s
        return None

    async def create_scenario(self, name: str, description: str,
                              settings: dict,
                              first_message: str = "") -> dict:
        sid = self._id("scenario")
        now = self._now()
        scenario = {
            "id": sid, "name": name, "description": description,
            "first_message": first_message, "settings": settings,
            "created_at": now, "updated_at": now,
        }
        self.scenarios[sid] = scenario
        return scenario

    async def update_scenario(self, scenario_id: int, name: str,
                              description: str, settings: dict,
                              first_message: str = "") -> dict | None:
        if scenario_id not in self.scenarios:
            return None
        self.scenarios[scenario_id].update(
            name=name, description=description, settings=settings,
            first_message=first_message, updated_at=self._now())
        return self.scenarios[scenario_id]

    async def delete_scenario(self, scenario_id: int) -> bool:
        return self.scenarios.pop(scenario_id, None) is not None

    # -- Conversations --

    async def list_conversations(self) -> list[dict]:
        result = []
        for c in sorted(self.conversations.values(), key=lambda c: c["id"]):
            cc = dict(c)
            cc["character_count"] = len([ch for ch in self.conv_characters
                                          if ch["conversation_id"] == c["id"]])
            result.append(cc)
        return result

    async def create_conversation(self, user_card_id: int, ai_card_id: int,
                                  scenario_id: int | None,
                                  model: str) -> dict:
        cid = self._id("conv")
        now = self._now()
        conv = {
            "id": cid, "user_card_id": user_card_id,
            "ai_card_id": ai_card_id, "scenario_id": scenario_id,
            "model": model, "scene_state": "", "scene_state_msg_id": None,
            "category": "user", "authors_note": "", "authors_note_depth": 4,
            "created_at": now, "updated_at": now,
        }
        self.conversations[cid] = conv
        return conv

    async def get_conversation(self, conv_id: int) -> dict | None:
        return self.conversations.get(conv_id)

    async def delete_conversation(self, conv_id: int) -> bool:
        if conv_id not in self.conversations:
            return False
        del self.conversations[conv_id]
        self.messages = {
            k: v for k, v in self.messages.items()
            if v["conversation_id"] != conv_id
        }
        return True

    async def get_conversation_characters(self, conv_id: int) -> list[dict]:
        return [c for c in self.conv_characters if c["conversation_id"] == conv_id]

    async def add_conversation_character(self, conv_id: int, card_id: int,
                                          color: str = "", generation_order: int = 0) -> dict:
        cid = self._id("conv_char")
        entry = {
            "id": cid, "conversation_id": conv_id, "card_id": card_id,
            "color": color, "generation_order": generation_order,
            "card_name": "", "created_at": self._now(),
        }
        card = self.cards.get(card_id)
        if card:
            cd = card.get("card_data", {}).get("data", card.get("card_data", {}))
            entry["card_name"] = cd.get("name", card.get("name", ""))
        self.conv_characters.append(entry)
        return entry

    async def remove_conversation_character(self, conv_id: int, card_id: int) -> bool:
        before = len(self.conv_characters)
        self.conv_characters = [c for c in self.conv_characters
                                 if not (c["conversation_id"] == conv_id and c["card_id"] == card_id)]
        return len(self.conv_characters) < before

    async def update_conversation_character(self, conv_id: int, card_id: int, **kwargs) -> dict | None:
        for c in self.conv_characters:
            if c["conversation_id"] == conv_id and c["card_id"] == card_id:
                c.update(kwargs)
                return c
        return None

    async def delete_all_messages(self, conv_id: int):
        self.messages = {
            k: v for k, v in self.messages.items()
            if v["conversation_id"] != conv_id
        }

    async def update_scene_state(self, conv_id: int, scene_state: str,
                                 msg_id: int | None = None) -> bool:
        if conv_id not in self.conversations:
            return False
        self.conversations[conv_id]["scene_state"] = scene_state
        if msg_id is not None:
            self.conversations[conv_id]["scene_state_msg_id"] = msg_id
        return True

    # -- Messages --

    async def get_messages(self, conv_id: int) -> list[dict]:
        return sorted(
            [m for m in self.messages.values()
             if m["conversation_id"] == conv_id],
            key=lambda m: m["sequence"],
        )

    async def add_message(self, conv_id: int, role: str, content: str,
                          raw_response=None, system_prompt: str | None = None,
                          scene_state: str | None = None,
                          post_prompt: str | None = None,
                          budget_json=None, prompt_json=None,
                          character_card_id: int | None = None) -> dict:
        mid = self._id("msg")
        existing = [m for m in self.messages.values()
                    if m["conversation_id"] == conv_id]
        seq = max((m["sequence"] for m in existing), default=0) + 1
        msg = {
            "id": mid, "conversation_id": conv_id, "role": role,
            "content": content, "raw_response": raw_response,
            "sequence": seq, "character_card_id": character_card_id,
            "created_at": self._now(),
        }
        self.messages[mid] = msg
        return msg

    async def update_message(self, msg_id: int, content: str) -> dict | None:
        if msg_id not in self.messages:
            return None
        self.messages[msg_id]["content"] = content
        return self.messages[msg_id]

    async def delete_message(self, msg_id: int) -> bool:
        return self.messages.pop(msg_id, None) is not None

    # -- Summaries (stubs) --

    async def get_latest_summary(self, conv_id: int) -> dict | None:
        return None

    async def list_summaries(self, conv_id: int) -> list[dict]:
        return []

    # -- Eval sets --

    async def create_eval_set(self, conv_id: int, sequence: int) -> dict:
        eid = self._id("eval_set")
        es = {
            "id": eid, "conversation_id": conv_id, "sequence": sequence,
            "selected_id": None, "preference_tags": [],
            "created_at": self._now(),
        }
        self.eval_sets[eid] = es
        return es

    async def add_eval_candidate(self, eval_set_id: int, label: str,
                                  model: str, config: dict,
                                  prompt_json=None, budget_json=None,
                                  content: str = "",
                                  raw_response=None) -> dict:
        cid = self._id("eval_cand")
        cand = {
            "id": cid, "eval_set_id": eval_set_id, "label": label,
            "model": model, "config": config, "content": content,
            "raw_response": raw_response, "prompt_json": prompt_json,
            "budget_json": budget_json, "created_at": self._now(),
        }
        self.eval_candidates[cid] = cand
        return cand

    async def update_eval_candidate(self, candidate_id: int, content: str,
                                     raw_response=None, prompt_json=None,
                                     budget_json=None) -> dict:
        cand = self.eval_candidates[candidate_id]
        cand.update(content=content, raw_response=raw_response,
                    prompt_json=prompt_json, budget_json=budget_json)
        return cand

    async def select_eval_candidate(self, eval_set_id: int, candidate_id: int,
                                     preference_tags=None) -> dict:
        es = self.eval_sets[eval_set_id]
        es["selected_id"] = candidate_id
        es["preference_tags"] = preference_tags or []
        return es

    async def get_eval_set(self, eval_set_id: int) -> dict | None:
        return self.eval_sets.get(eval_set_id)

    async def get_eval_candidates(self, eval_set_id: int) -> list[dict]:
        return sorted(
            [c for c in self.eval_candidates.values()
             if c["eval_set_id"] == eval_set_id],
            key=lambda c: c["id"],
        )

    async def get_eval_sets_for_conversation(self, conv_id: int) -> list[dict]:
        return sorted(
            [es for es in self.eval_sets.values()
             if es["conversation_id"] == conv_id],
            key=lambda es: es["sequence"],
        )

    # -- First message cache (stubs) --

    async def get_cached_first_message(self, *args) -> str | None:
        return None

    async def set_cached_first_message(self, *args):
        pass

    # -- Lorebook (stubs) --

    async def get_lorebook_for_card(self, card_id: int):
        return None

    async def get_or_create_lorebook(self, card_id, **kw):
        return None

    async def get_lorebook_entries(self, lorebook_id):
        return []


# ---------------------------------------------------------------------------
# Stub Ollama — extends conftest StubOllama with generate + chat_stream
# ---------------------------------------------------------------------------

class IntegrationStubOllama:
    """Ollama stub supporting generate() and chat_stream() for route tests."""

    def __init__(self, num_ctx: int = 8192):
        self._num_ctx = num_ctx
        self.generate_response = "stub response"
        self.chat_stream_tokens = ["Hello", " world"]

    async def get_num_ctx(self, model: str) -> int:
        return self._num_ctx

    async def chat(self, model, messages, tools=None, think=False, options=None):
        return {
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "prompt_eval_count": 100,
        }

    async def chat_stream(self, model, messages, options=None, stop=None):
        for tok in self.chat_stream_tokens:
            yield {"token": tok, "thinking": False, "done": False}
        yield {
            "token": "", "done": True,
            "total_tokens": len(self.chat_stream_tokens),
            "tokens_per_second": 50.0,
        }

    async def generate(self, model, prompt, system=None, options=None):
        self.last_generate_prompt = prompt
        return self.generate_response

    async def count_generate_prompt(self, model, prompt, system=None):
        return 100


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_db():
    return FakeDB()


@pytest.fixture
def stub_ollama():
    return IntegrationStubOllama()


@pytest.fixture
def app(fake_db, stub_ollama, monkeypatch):
    """Create a FastAPI app with RP routes, backed by in-memory fakes."""
    _app = FastAPI()

    # Patch db module functions to use FakeDB
    for name in dir(fake_db):
        if not name.startswith("_") and callable(getattr(fake_db, name)):
            if hasattr(db, name):
                monkeypatch.setattr(db, name, getattr(fake_db, name))

    # Stub out init_schema and close (no real DB)
    monkeypatch.setattr(db, "init_schema", _async_noop)
    monkeypatch.setattr(db, "close", _async_noop)

    # Stub out research, fewshot, MCP, and conv_log to avoid side effects
    from projects.rp import research, fewshot, conv_log
    monkeypatch.setattr(research, "research_dispatch",
                        _coro_returning(None))
    monkeypatch.setattr(fewshot, "get_fewshot_messages",
                        _coro_returning([]))

    monkeypatch.setattr(conv_log, "log_response", lambda *a, **kw: None)
    monkeypatch.setattr(conv_log, "log_prompt", lambda *a, **kw: None)
    monkeypatch.setattr(conv_log, "log_research", lambda *a, **kw: None)
    monkeypatch.setattr(conv_log, "log_fewshot", lambda *a, **kw: None)
    monkeypatch.setattr(conv_log, "log_scene_state", lambda *a, **kw: None)

    from projects.rp.routes import setup
    setup(_app, stub_ollama)

    return _app


@pytest_asyncio.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport,
                                 base_url="http://test") as c:
        yield c


async def _async_noop(*args, **kwargs):
    pass


def _coro_returning(value):
    async def _inner(*args, **kwargs):
        return value
    return _inner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_cards(fake_db) -> tuple[dict, dict]:
    """Create user + AI cards and return them."""
    user = await fake_db.create_card("User", {"data": {"name": "Val"}})
    ai = await fake_db.create_card("Alice", {
        "data": {
            "name": "Alice", "description": "A test character",
            "personality": "Friendly", "first_mes": "",
            "mes_example": "",
        }
    })
    return user, ai


async def _seed_conversation(fake_db, model="test-model") -> tuple[dict, dict, dict]:
    """Create cards + conversation, return (user_card, ai_card, conv)."""
    user, ai = await _seed_cards(fake_db)
    conv = await fake_db.create_conversation(user["id"], ai["id"], None, model)
    return user, ai, conv


# ---------------------------------------------------------------------------
# Card CRUD
# ---------------------------------------------------------------------------

class TestCards:
    @pytest.mark.asyncio
    async def test_list_cards_empty(self, client):
        resp = await client.get("/rp/cards")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_create_and_get_card(self, client):
        resp = await client.post("/rp/cards", json={
            "name": "Alice", "card_data": {"data": {"name": "Alice"}}
        })
        assert resp.status_code == 200
        card = resp.json()
        assert card["name"] == "Alice"
        assert card["id"] >= 1

        resp2 = await client.get(f"/rp/cards/{card['id']}")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_get_card_not_found(self, client):
        resp = await client.get("/rp/cards/9999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_card(self, client):
        create = await client.post("/rp/cards", json={
            "name": "Bob", "card_data": {}
        })
        card_id = create.json()["id"]

        resp = await client.put(f"/rp/cards/{card_id}", json={
            "name": "Bobby", "card_data": {"data": {"name": "Bobby"}}
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Bobby"

    @pytest.mark.asyncio
    async def test_update_card_not_found(self, client):
        resp = await client.put("/rp/cards/9999", json={
            "name": "X", "card_data": {}
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_card(self, client):
        create = await client.post("/rp/cards", json={
            "name": "Temp", "card_data": {}
        })
        card_id = create.json()["id"]

        resp = await client.delete(f"/rp/cards/{card_id}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        resp2 = await client.get(f"/rp/cards/{card_id}")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_card_not_found(self, client):
        resp = await client.delete("/rp/cards/9999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_cards_returns_created(self, client):
        await client.post("/rp/cards", json={"name": "A", "card_data": {}})
        await client.post("/rp/cards", json={"name": "B", "card_data": {}})
        resp = await client.get("/rp/cards")
        assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# Scenario CRUD
# ---------------------------------------------------------------------------

class TestScenarios:
    @pytest.mark.asyncio
    async def test_create_and_get_scenario(self, client):
        resp = await client.post("/rp/scenarios", json={
            "name": "Coffee Shop", "description": "Meet at a cafe",
            "settings": {}
        })
        assert resp.status_code == 200
        scenario = resp.json()
        assert scenario["name"] == "Coffee Shop"

        resp2 = await client.get(f"/rp/scenarios/{scenario['id']}")
        assert resp2.status_code == 200

    @pytest.mark.asyncio
    async def test_update_scenario(self, client):
        create = await client.post("/rp/scenarios", json={
            "name": "Park", "description": "A walk", "settings": {}
        })
        sid = create.json()["id"]

        resp = await client.put(f"/rp/scenarios/{sid}", json={
            "name": "Park (evening)", "description": "An evening walk",
            "settings": {"temperature": 0.8}
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Park (evening)"

    @pytest.mark.asyncio
    async def test_delete_scenario(self, client):
        create = await client.post("/rp/scenarios", json={
            "name": "Temp", "description": "", "settings": {}
        })
        sid = create.json()["id"]
        resp = await client.delete(f"/rp/scenarios/{sid}")
        assert resp.status_code == 200

        resp2 = await client.get(f"/rp/scenarios/{sid}")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_scenario_not_found(self, client):
        assert (await client.get("/rp/scenarios/9999")).status_code == 404
        assert (await client.put("/rp/scenarios/9999", json={
            "name": "X", "description": "", "settings": {}
        })).status_code == 404
        assert (await client.delete("/rp/scenarios/9999")).status_code == 404


# ---------------------------------------------------------------------------
# Conversation CRUD
# ---------------------------------------------------------------------------

class TestConversations:
    @pytest.mark.asyncio
    async def test_create_conversation(self, client, fake_db):
        user, ai = await _seed_cards(fake_db)
        resp = await client.post("/rp/conversations", json={
            "user_card_id": user["id"],
            "ai_card_id": ai["id"],
            "model": "test-model",
        })
        assert resp.status_code == 200
        conv = resp.json()
        assert conv["user_card_id"] == user["id"]
        assert conv["ai_card_id"] == ai["id"]
        assert conv["model"] == "test-model"

    @pytest.mark.asyncio
    async def test_create_conversation_card_not_found(self, client, fake_db):
        user = await fake_db.create_card("User", {})
        resp = await client.post("/rp/conversations", json={
            "user_card_id": user["id"],
            "ai_card_id": 9999,
            "model": "test-model",
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_conversation_detail(self, client, fake_db):
        user, ai, conv = await _seed_conversation(fake_db)
        resp = await client.get(f"/rp/conversations/{conv['id']}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["conversation"]["id"] == conv["id"]
        assert detail["user_card"]["id"] == user["id"]
        assert detail["ai_card"]["id"] == ai["id"]
        assert isinstance(detail["messages"], list)

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, client):
        resp = await client.get("/rp/conversations/9999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_conversation(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        resp = await client.delete(f"/rp/conversations/{conv['id']}")
        assert resp.status_code == 200

        resp2 = await client.get(f"/rp/conversations/{conv['id']}")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_list_conversations(self, client, fake_db):
        await _seed_conversation(fake_db)
        resp = await client.get("/rp/conversations")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_greeting_prompt_excludes_card_system_prompt(
        self, client, fake_db, stub_ollama,
    ):
        card_system = "You are writing a roleplay where you are Alice. SYSTEM_SENTINEL"
        scenario_text = "Alice visits Bob's apartment. Alice rings the doorbell."
        user = await fake_db.create_card("Bob", {"data": {"name": "Bob"}})
        ai = await fake_db.create_card("Alice", {
            "data": {
                "name": "Alice",
                "description": "A test character",
                "personality": "Friendly",
                "system_prompt": card_system,
                "first_mes": "",
                "mes_example": "",
            }
        })
        scenario = await fake_db.create_scenario(
            "Test", scenario_text, {}, first_message="",
        )
        stub_ollama.generate_response = "Alice stood at the door."

        await client.post("/rp/conversations", json={
            "user_card_id": user["id"],
            "ai_card_id": ai["id"],
            "scenario_id": scenario["id"],
            "model": "test-model",
        })

        prompt = stub_ollama.last_generate_prompt
        assert "SYSTEM_SENTINEL" not in prompt
        assert scenario_text in prompt
        assert "EXACTLY" in prompt


# ---------------------------------------------------------------------------
# Scene State
# ---------------------------------------------------------------------------

class TestSceneState:
    @pytest.mark.asyncio
    async def test_update_scene_state(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        resp = await client.put(
            f"/rp/conversations/{conv['id']}/scene-state",
            json={"scene_state": "Location: kitchen\nMood: calm"}
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert fake_db.conversations[conv["id"]]["scene_state"] == \
            "Location: kitchen\nMood: calm"

    @pytest.mark.asyncio
    async def test_update_scene_state_not_found(self, client):
        resp = await client.put(
            "/rp/conversations/9999/scene-state",
            json={"scene_state": "test"}
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_scene_state_persists_across_gets(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        await client.put(
            f"/rp/conversations/{conv['id']}/scene-state",
            json={"scene_state": "Location: park"}
        )
        resp = await client.get(f"/rp/conversations/{conv['id']}")
        assert resp.json()["conversation"]["scene_state"] == "Location: park"


# ---------------------------------------------------------------------------
# Messages — edit, delete
# ---------------------------------------------------------------------------

class TestMessages:
    @pytest.mark.asyncio
    async def test_edit_message(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        msg = await fake_db.add_message(conv["id"], "user", "original")
        resp = await client.put(f"/rp/messages/{msg['id']}", json={
            "content": "edited"
        })
        assert resp.status_code == 200
        assert resp.json()["content"] == "edited"

    @pytest.mark.asyncio
    async def test_edit_message_not_found(self, client):
        resp = await client.put("/rp/messages/9999", json={"content": "x"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_message(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        msg = await fake_db.add_message(conv["id"], "user", "to delete")
        resp = await client.delete(f"/rp/messages/{msg['id']}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_message_not_found(self, client):
        resp = await client.delete("/rp/messages/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Send Message — streaming NDJSON
# ---------------------------------------------------------------------------

class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_streams_ndjson(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        await fake_db.add_message(conv["id"], "assistant", "Hello!")

        resp = await client.post(
            f"/rp/conversations/{conv['id']}/message",
            json={"content": "Hi there"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith(
            "application/x-ndjson")

        lines = [ln for ln in resp.text.strip().split("\n") if ln.strip()]
        assert len(lines) >= 2

        first = json.loads(lines[0])
        assert "debug_prompt" in first

        last = json.loads(lines[-1])
        assert last.get("done") is True

    @pytest.mark.asyncio
    async def test_send_message_conversation_not_found(self, client):
        resp = await client.post(
            "/rp/conversations/9999/message",
            json={"content": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_send_message_saves_user_message(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        await client.post(
            f"/rp/conversations/{conv['id']}/message",
            json={"content": "Hello from user"},
        )
        msgs = await fake_db.get_messages(conv["id"])
        user_msgs = [m for m in msgs if m["role"] == "user"]
        assert any(m["content"] == "Hello from user" for m in user_msgs)

    @pytest.mark.asyncio
    async def test_send_message_tokens_in_stream(self, client, fake_db,
                                                  stub_ollama):
        stub_ollama.chat_stream_tokens = ["Once", " upon", " a", " time"]
        _, _, conv = await _seed_conversation(fake_db)
        await fake_db.add_message(conv["id"], "assistant", "Hello!")

        resp = await client.post(
            f"/rp/conversations/{conv['id']}/message",
            json={"content": "Tell me a story"},
        )
        lines = [json.loads(ln) for ln in resp.text.strip().split("\n")
                 if ln.strip()]
        tokens = [c["token"] for c in lines
                  if "token" in c and not c.get("done")]
        assert tokens == ["Once", " upon", " a", " time"]


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

class TestSummaries:
    @pytest.mark.asyncio
    async def test_list_summaries_empty(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        resp = await client.get(
            f"/rp/conversations/{conv['id']}/summaries")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_summaries_not_found(self, client):
        resp = await client.get("/rp/conversations/9999/summaries")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Save Partial
# ---------------------------------------------------------------------------

class TestSavePartial:
    @pytest.mark.asyncio
    async def test_save_partial(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        resp = await client.post(
            f"/rp/conversations/{conv['id']}/save-partial",
            json={"content": "partial response text"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        msgs = await fake_db.get_messages(conv["id"])
        assert any(m["content"] == "partial response text" for m in msgs)

    @pytest.mark.asyncio
    async def test_save_partial_empty(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        resp = await client.post(
            f"/rp/conversations/{conv['id']}/save-partial",
            json={"content": "  "},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

    @pytest.mark.asyncio
    async def test_save_partial_not_found(self, client):
        resp = await client.post(
            "/rp/conversations/9999/save-partial",
            json={"content": "test"},
        )
        assert resp.status_code == 404
