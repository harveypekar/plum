import json
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

# Allow imports from aiserver directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ollama import OllamaClient, OllamaError


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


class TestGetNumCtx:
    @pytest.mark.asyncio
    async def test_prefers_parameters_num_ctx(self):
        client = OllamaClient("http://localhost:11434")
        show_response = {
            "parameters": "num_ctx                        32768\ntemperature                    0.8",
            "model_info": {"llama.context_length": 131072},
        }
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = lambda: show_response
            result = await client.get_num_ctx("mymodel")
        assert result == 32768

    @pytest.mark.asyncio
    async def test_falls_back_to_model_info_context_length(self):
        client = OllamaClient("http://localhost:11434")
        show_response = {
            "parameters": "temperature                    0.8",
            "model_info": {"llama.context_length": 8192},
        }
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = lambda: show_response
            result = await client.get_num_ctx("mymodel")
        assert result == 8192

    @pytest.mark.asyncio
    async def test_tries_any_arch_context_length(self):
        """model_info keys look like <arch>.context_length — e.g. qwen2.context_length."""
        client = OllamaClient("http://localhost:11434")
        show_response = {
            "parameters": "",
            "model_info": {"qwen2.context_length": 4096, "general.architecture": "qwen2"},
        }
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = lambda: show_response
            result = await client.get_num_ctx("mymodel")
        assert result == 4096

    @pytest.mark.asyncio
    async def test_raises_when_neither_present(self):
        client = OllamaClient("http://localhost:11434")
        show_response = {"parameters": "temperature 0.8", "model_info": {}}
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = lambda: show_response
            with pytest.raises(OllamaError, match="context length"):
                await client.get_num_ctx("mymodel")

    @pytest.mark.asyncio
    async def test_raises_on_show_http_error(self):
        client = OllamaClient("http://localhost:11434")
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value.status_code = 404
            mock_post.return_value.text = "model not found"
            with pytest.raises(OllamaError):
                await client.get_num_ctx("nope")
