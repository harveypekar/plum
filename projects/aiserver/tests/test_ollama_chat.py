import json
import sys
from pathlib import Path

import httpx
import pytest

# Allow imports from aiserver directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ollama import OllamaClient


class FakeStreamResponse:
    def __init__(self, lines, status_code=200):
        self.status_code = status_code
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return b"error"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class FakeClient:
    def __init__(self, response):
        self._response = response
        self.last_request = None

    def stream(self, method, url, json=None):
        self._response._request_json = json
        self.last_request = json
        return self._response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_chat_stream_sends_messages(monkeypatch):
    lines = [
        json.dumps({"message": {"content": "Hello"}, "done": False}),
        json.dumps({"message": {"content": " world"}, "done": False}),
        json.dumps({"done": True, "eval_count": 10, "eval_duration": 1_000_000_000}),
    ]
    fake_resp = FakeStreamResponse(lines)
    fake_client = FakeClient(fake_resp)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: fake_client)

    client = OllamaClient()
    messages = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hi"},
    ]

    chunks = []
    async for chunk in client.chat_stream(model="test", messages=messages):
        chunks.append(chunk)

    assert fake_client.last_request["model"] == "test"
    assert fake_client.last_request["messages"] == messages
    assert fake_client.last_request["stream"] is True
    assert "prompt" not in fake_client.last_request
    assert chunks[0] == {"token": "Hello", "thinking": False, "done": False}
    assert chunks[1] == {"token": " world", "thinking": False, "done": False}
    assert chunks[2]["done"] is True
    assert chunks[2]["total_tokens"] == 10


@pytest.mark.asyncio
async def test_chat_stream_with_thinking(monkeypatch):
    lines = [
        json.dumps({"message": {"content": "", "thinking": "Let me think"}, "done": False}),
        json.dumps({"message": {"content": "Answer"}, "done": False}),
        json.dumps({"done": True, "eval_count": 5, "eval_duration": 1_000_000_000}),
    ]
    fake_resp = FakeStreamResponse(lines)
    fake_client = FakeClient(fake_resp)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: fake_client)

    client = OllamaClient()
    messages = [{"role": "user", "content": "Hi"}]

    chunks = []
    async for chunk in client.chat_stream(model="test", messages=messages, options={"think": True}):
        chunks.append(chunk)

    assert fake_client.last_request.get("think") is True
    assert chunks[0] == {"token": "Let me think", "thinking": True, "done": False}
    assert chunks[1] == {"token": "Answer", "thinking": False, "done": False}


@pytest.mark.asyncio
async def test_chat_stream_passes_options_and_stop(monkeypatch):
    lines = [
        json.dumps({"done": True, "eval_count": 0, "eval_duration": 1}),
    ]
    fake_resp = FakeStreamResponse(lines)
    fake_client = FakeClient(fake_resp)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: fake_client)

    client = OllamaClient()
    messages = [{"role": "user", "content": "Hi"}]
    options = {"temperature": 0.8, "repeat_penalty": 1.1}

    chunks = []
    async for chunk in client.chat_stream(
        model="test", messages=messages, options=options, stop=["Valentina:"]
    ):
        chunks.append(chunk)

    assert fake_client.last_request["options"] == {"temperature": 0.8, "repeat_penalty": 1.1}
    assert fake_client.last_request["stop"] == ["Valentina:"]
