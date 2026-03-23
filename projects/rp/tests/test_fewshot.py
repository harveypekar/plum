import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from projects.aiserver.ollama import OllamaClient, OllamaError
import projects.rp.db as db


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


# -- DB: Few-shot examples --

def _make_pool(fetch_return=None, fetchrow_return=None, fetchval_return=None):
    """Build a mock asyncpg pool with configurable return values."""
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=fetch_return or [])
    pool.fetchrow = AsyncMock(return_value=fetchrow_return)
    pool.fetchval = AsyncMock(return_value=fetchval_return)
    return pool


def test_search_fewshot_examples_returns_list():
    """search_fewshot_examples() returns a list of dicts from pool.fetch."""
    fake_row = MagicMock()
    fake_row.__iter__ = MagicMock(return_value=iter([
        ("id", 1), ("scene_context", "ctx"), ("user_message", "hi"),
        ("assistant_message", "hello"), ("token_estimate", 50), ("similarity", 0.92),
    ]))
    fake_row.keys = MagicMock(return_value=["id", "scene_context", "user_message",
                                             "assistant_message", "token_estimate", "similarity"])
    # Use a plain dict so dict(r) works without fuss
    row_dict = {
        "id": 1, "scene_context": "ctx", "user_message": "hi",
        "assistant_message": "hello", "token_estimate": 50, "similarity": 0.92,
    }

    mock_pool = _make_pool(fetch_return=[row_dict])

    with patch.object(db, "get_pool", AsyncMock(return_value=mock_pool)):
        embedding = [0.1, 0.2, 0.3]
        result = asyncio.run(db.search_fewshot_examples(embedding, limit=1))

    assert result == [row_dict]
    mock_pool.fetch.assert_called_once()
    call_args = mock_pool.fetch.call_args
    # Embedding should be passed as a string
    assert call_args[0][1] == "[0.1,0.2,0.3]"
    assert call_args[0][2] == 1


def test_search_fewshot_examples_embedding_format():
    """search_fewshot_examples() converts float list to pgvector string format."""
    mock_pool = _make_pool(fetch_return=[])

    with patch.object(db, "get_pool", AsyncMock(return_value=mock_pool)):
        asyncio.run(db.search_fewshot_examples([1.0, -0.5, 0.0], limit=2))

    call_args = mock_pool.fetch.call_args[0]
    assert call_args[1] == "[1.0,-0.5,0.0]"
    assert call_args[2] == 2


def test_add_fewshot_example_returns_dict():
    """add_fewshot_example() returns a dict with the inserted row fields."""
    fake_row = {
        "id": 42, "scene_context": "forest", "user_message": "hello",
        "assistant_message": "world", "token_estimate": 100,
        "active": True, "created_at": "2026-01-01 00:00:00+00",
    }

    mock_pool = _make_pool(fetchrow_return=fake_row)

    with patch.object(db, "get_pool", AsyncMock(return_value=mock_pool)):
        result = asyncio.run(db.add_fewshot_example(
            scene_context="forest",
            user_message="hello",
            assistant_message="world",
            embedding=[0.1, 0.2],
            token_estimate=100,
        ))

    assert result == fake_row
    mock_pool.fetchrow.assert_called_once()
    call_args = mock_pool.fetchrow.call_args[0]
    # 4th positional arg (index 4) is the embedding string
    assert call_args[4] == "[0.1,0.2]"


def test_add_fewshot_example_embedding_format():
    """add_fewshot_example() converts embedding list to pgvector string."""
    fake_row = {
        "id": 1, "scene_context": "s", "user_message": "u",
        "assistant_message": "a", "token_estimate": 0,
        "active": True, "created_at": "2026-01-01",
    }
    mock_pool = _make_pool(fetchrow_return=fake_row)

    with patch.object(db, "get_pool", AsyncMock(return_value=mock_pool)):
        asyncio.run(db.add_fewshot_example("s", "u", "a", [0.5, 0.25, 0.75], 0))

    call_args = mock_pool.fetchrow.call_args[0]
    assert call_args[4] == "[0.5,0.25,0.75]"


def test_count_fewshot_examples_returns_int():
    """count_fewshot_examples() returns the integer from pool.fetchval."""
    mock_pool = _make_pool(fetchval_return=7)

    with patch.object(db, "get_pool", AsyncMock(return_value=mock_pool)):
        result = asyncio.run(db.count_fewshot_examples())

    assert result == 7
    mock_pool.fetchval.assert_called_once_with(
        "SELECT COUNT(*) FROM rp_fewshot_examples WHERE active"
    )


def test_count_fewshot_examples_zero():
    """count_fewshot_examples() returns 0 when there are no active examples."""
    mock_pool = _make_pool(fetchval_return=0)

    with patch.object(db, "get_pool", AsyncMock(return_value=mock_pool)):
        result = asyncio.run(db.count_fewshot_examples())

    assert result == 0
