"""Tests for eval_routes.py — compare/select/list endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
import httpx

from .test_routes import (
    FakeDB, IntegrationStubOllama, _async_noop, _coro_returning,
    _seed_conversation,
)
from projects.rp import db
from fastapi import FastAPI


@pytest.fixture
def fake_db():
    return FakeDB()


@pytest.fixture
def stub_ollama():
    return IntegrationStubOllama()


@pytest.fixture
def app(fake_db, stub_ollama, monkeypatch):
    _app = FastAPI()

    for name in dir(fake_db):
        if not name.startswith("_") and callable(getattr(fake_db, name)):
            if hasattr(db, name):
                monkeypatch.setattr(db, name, getattr(fake_db, name))

    monkeypatch.setattr(db, "init_schema", _async_noop)
    monkeypatch.setattr(db, "close", _async_noop)

    from projects.rp import research, fewshot, conv_log
    monkeypatch.setattr(research, "research_dispatch", _coro_returning(None))
    monkeypatch.setattr(fewshot, "get_fewshot_messages", _coro_returning([]))
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


class TestCompare:
    @pytest.mark.asyncio
    async def test_compare_returns_candidates(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        resp = await client.post(f"/rp/conversations/{conv['id']}/compare", json={
            "content": "Hello",
            "configs": [
                {"label": "A"},
                {"label": "B"},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == conv["id"]
        assert len(data["candidates"]) == 2
        labels = {c["label"] for c in data["candidates"]}
        assert labels == {"A", "B"}

    @pytest.mark.asyncio
    async def test_compare_saves_user_message(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        await client.post(f"/rp/conversations/{conv['id']}/compare", json={
            "content": "Test message",
            "configs": [{"label": "A"}],
        })
        msgs = await fake_db.get_messages(conv["id"])
        user_msgs = [m for m in msgs if m["role"] == "user"]
        assert len(user_msgs) == 1
        assert user_msgs[0]["content"] == "Test message"

    @pytest.mark.asyncio
    async def test_compare_candidates_have_content(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        resp = await client.post(f"/rp/conversations/{conv['id']}/compare", json={
            "content": "Hi",
            "configs": [{"label": "A"}],
        })
        data = resp.json()
        assert data["candidates"][0]["content"] == "Hello world"

    @pytest.mark.asyncio
    async def test_compare_conversation_not_found(self, client):
        resp = await client.post("/rp/conversations/999/compare", json={
            "content": "Hi",
            "configs": [{"label": "A"}],
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_compare_with_custom_config(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        resp = await client.post(f"/rp/conversations/{conv['id']}/compare", json={
            "content": "Hi",
            "configs": [
                {"label": "warm", "temperature": 1.5},
                {"label": "cool", "temperature": 0.3},
            ],
        })
        data = resp.json()
        assert len(data["candidates"]) == 2


class TestSelectCandidate:
    @pytest.mark.asyncio
    async def test_select_saves_message(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        compare_resp = await client.post(
            f"/rp/conversations/{conv['id']}/compare",
            json={"content": "Hi", "configs": [{"label": "A"}, {"label": "B"}]},
        )
        candidates = compare_resp.json()["candidates"]
        winner_id = candidates[0]["id"]
        eval_set_id = compare_resp.json()["eval_set_id"]

        resp = await client.post(f"/rp/eval-sets/{eval_set_id}/select", json={
            "candidate_id": winner_id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["selected_candidate_id"] == winner_id

        msgs = await fake_db.get_messages(conv["id"])
        asst_msgs = [m for m in msgs if m["role"] == "assistant"]
        assert len(asst_msgs) == 1

    @pytest.mark.asyncio
    async def test_select_with_preference_tags(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        compare_resp = await client.post(
            f"/rp/conversations/{conv['id']}/compare",
            json={"content": "Hi", "configs": [{"label": "A"}]},
        )
        cand_id = compare_resp.json()["candidates"][0]["id"]
        eval_set_id = compare_resp.json()["eval_set_id"]

        resp = await client.post(f"/rp/eval-sets/{eval_set_id}/select", json={
            "candidate_id": cand_id,
            "preference_tags": ["vivid", "in-character"],
        })
        assert resp.status_code == 200
        es = await fake_db.get_eval_set(eval_set_id)
        assert es["preference_tags"] == ["vivid", "in-character"]

    @pytest.mark.asyncio
    async def test_select_eval_set_not_found(self, client):
        resp = await client.post("/rp/eval-sets/999/select", json={
            "candidate_id": 1,
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_select_candidate_not_found(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        compare_resp = await client.post(
            f"/rp/conversations/{conv['id']}/compare",
            json={"content": "Hi", "configs": [{"label": "A"}]},
        )
        eval_set_id = compare_resp.json()["eval_set_id"]
        resp = await client.post(f"/rp/eval-sets/{eval_set_id}/select", json={
            "candidate_id": 99999,
        })
        assert resp.status_code == 404


class TestEvalSetEndpoints:
    @pytest.mark.asyncio
    async def test_get_eval_set_detail(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        compare_resp = await client.post(
            f"/rp/conversations/{conv['id']}/compare",
            json={"content": "Hi", "configs": [{"label": "X"}]},
        )
        eval_set_id = compare_resp.json()["eval_set_id"]

        resp = await client.get(f"/rp/eval-sets/{eval_set_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["eval_set"]["id"] == eval_set_id
        assert len(data["candidates"]) == 1

    @pytest.mark.asyncio
    async def test_get_eval_set_not_found(self, client):
        resp = await client.get("/rp/eval-sets/999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_eval_sets_for_conversation(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        await client.post(
            f"/rp/conversations/{conv['id']}/compare",
            json={"content": "First", "configs": [{"label": "A"}]},
        )
        await client.post(
            f"/rp/conversations/{conv['id']}/compare",
            json={"content": "Second", "configs": [{"label": "B"}]},
        )

        resp = await client.get(f"/rp/conversations/{conv['id']}/eval-sets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_eval_sets_empty(self, client, fake_db):
        _, _, conv = await _seed_conversation(fake_db)
        resp = await client.get(f"/rp/conversations/{conv['id']}/eval-sets")
        assert resp.status_code == 200
        assert resp.json() == []
