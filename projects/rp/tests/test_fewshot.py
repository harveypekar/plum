import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from projects.aiserver.ollama import OllamaClient, OllamaError


def test_embed_returns_vector():
    """embed() returns the first embedding from Ollama response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp

    with patch("projects.aiserver.ollama.httpx.AsyncClient") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        client = OllamaClient(base_url="http://localhost:11434")
        result = asyncio.run(client.embed("nomic-embed-text", "hello world"))

    assert result == [0.1, 0.2, 0.3]


def test_embed_sends_correct_request():
    """embed() POSTs to /api/embed with model and input fields."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embeddings": [[0.5] * 768]}

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp

    with patch("projects.aiserver.ollama.httpx.AsyncClient") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        client = OllamaClient(base_url="http://localhost:11434")
        asyncio.run(client.embed("nomic-embed-text", "scene context text"))

    mock_client.post.assert_called_once_with(
        "http://localhost:11434/api/embed",
        json={"model": "nomic-embed-text", "input": "scene context text"},
    )


def test_embed_raises_on_non_200():
    """embed() raises OllamaError when Ollama returns a non-200 status."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp

    with patch("projects.aiserver.ollama.httpx.AsyncClient") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        client = OllamaClient(base_url="http://localhost:11434")
        with pytest.raises(OllamaError, match="Ollama embed returned 500"):
            asyncio.run(client.embed("nomic-embed-text", "test"))


def test_embed_uses_custom_base_url():
    """embed() uses the base_url set on the client."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embeddings": [[1.0, 2.0]]}

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp

    with patch("projects.aiserver.ollama.httpx.AsyncClient") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        client = OllamaClient(base_url="http://custom-host:9999")
        asyncio.run(client.embed("nomic-embed-text", "text"))

    mock_client.post.assert_called_once_with(
        "http://custom-host:9999/api/embed",
        json={"model": "nomic-embed-text", "input": "text"},
    )
