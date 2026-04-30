import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from projects.aiserver.ollama import OllamaClient, OllamaError
import projects.rp.db as db
from projects.rp.fewshot import get_fewshot_messages, voice_is_drifting


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
        result = asyncio.run(db.search_fewshot_examples(embedding, card_id=5, limit=1))

    assert result == [row_dict]
    mock_pool.fetch.assert_called_once()
    call_args = mock_pool.fetch.call_args
    # Embedding should be passed as a string
    assert call_args[0][1] == "[0.1,0.2,0.3]"
    assert call_args[0][2] == 1
    assert call_args[0][3] == 5


def test_search_fewshot_examples_embedding_format():
    """search_fewshot_examples() converts float list to pgvector string format."""
    mock_pool = _make_pool(fetch_return=[])

    with patch.object(db, "get_pool", AsyncMock(return_value=mock_pool)):
        asyncio.run(db.search_fewshot_examples([1.0, -0.5, 0.0], card_id=3, limit=2))

    call_args = mock_pool.fetch.call_args[0]
    assert call_args[1] == "[1.0,-0.5,0.0]"
    assert call_args[2] == 2
    assert call_args[3] == 3


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
            card_id=5,
            scene_context="forest",
            user_message="hello",
            assistant_message="world",
            embedding=[0.1, 0.2],
            model="qwen3:8b",
            token_estimate=100,
        ))

    assert result == fake_row
    mock_pool.fetchrow.assert_called_once()
    call_args = mock_pool.fetchrow.call_args[0]
    # 1st positional arg is card_id, 5th is the embedding string
    assert call_args[1] == 5
    assert call_args[5] == "[0.1,0.2]"
    assert call_args[6] == "qwen3:8b"


def test_add_fewshot_example_embedding_format():
    """add_fewshot_example() converts embedding list to pgvector string."""
    fake_row = {
        "id": 1, "scene_context": "s", "user_message": "u",
        "assistant_message": "a", "token_estimate": 0,
        "active": True, "created_at": "2026-01-01",
    }
    mock_pool = _make_pool(fetchrow_return=fake_row)

    with patch.object(db, "get_pool", AsyncMock(return_value=mock_pool)):
        asyncio.run(db.add_fewshot_example(
            card_id=1, scene_context="s", user_message="u",
            assistant_message="a", embedding=[0.5, 0.25, 0.75],
            model="test", token_estimate=0,
        ))

    call_args = mock_pool.fetchrow.call_args[0]
    assert call_args[5] == "[0.5,0.25,0.75]"


def test_count_fewshot_examples_returns_int():
    """count_fewshot_examples() returns the integer from pool.fetchval."""
    mock_pool = _make_pool(fetchval_return=7)

    with patch.object(db, "get_pool", AsyncMock(return_value=mock_pool)):
        result = asyncio.run(db.count_fewshot_examples())

    assert result == 7
    mock_pool.fetchval.assert_called_once_with(
        "SELECT COUNT(*) FROM rp_fewshot_examples WHERE active"
    )


def test_count_fewshot_examples_with_card_id():
    """count_fewshot_examples(card_id) filters by card."""
    mock_pool = _make_pool(fetchval_return=3)

    with patch.object(db, "get_pool", AsyncMock(return_value=mock_pool)):
        result = asyncio.run(db.count_fewshot_examples(card_id=5))

    assert result == 3
    mock_pool.fetchval.assert_called_once_with(
        "SELECT COUNT(*) FROM rp_fewshot_examples WHERE active AND card_id = $1",
        5,
    )


def test_count_fewshot_examples_zero():
    """count_fewshot_examples() returns 0 when there are no active examples."""
    mock_pool = _make_pool(fetchval_return=0)

    with patch.object(db, "get_pool", AsyncMock(return_value=mock_pool)):
        result = asyncio.run(db.count_fewshot_examples())

    assert result == 0


# -- voice_is_drifting --


class TestVoiceIsDrifting:
    def test_fewer_than_three_messages_assumes_drift(self):
        msgs = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello there"},
        ]
        assert voice_is_drifting(msgs) is True

    def test_no_assistant_messages_assumes_drift(self):
        msgs = [
            {"role": "user", "content": "Hi"},
            {"role": "user", "content": "Hello"},
        ]
        assert voice_is_drifting(msgs) is True

    def test_clean_voice_returns_false(self):
        msgs = [
            {"role": "user", "content": "What are you doing?"},
            {"role": "assistant", "content": "She glanced up from the workbench, wiping grease from her fingers."},
            {"role": "user", "content": "Can I help?"},
            {"role": "assistant", "content": "A small smile tugged at her lips as she handed over the wrench."},
            {"role": "user", "content": "Like this?"},
            {"role": "assistant", "content": "She watched his clumsy grip and stepped closer to adjust his hold."},
        ]
        assert voice_is_drifting(msgs) is False

    def test_stock_phrase_triggers_drift(self):
        msgs = [
            {"role": "user", "content": "What happened?"},
            {"role": "assistant", "content": "She looked away, uncertain."},
            {"role": "user", "content": "Tell me."},
            {"role": "assistant", "content": "A quiet sigh escaped her."},
            {"role": "user", "content": "Please."},
            {"role": "assistant", "content": "Her breath caught in her throat and her heart pounded in her chest."},
        ]
        assert voice_is_drifting(msgs) is True

    def test_high_trigram_overlap_triggers_drift(self):
        repeated = "She crossed her arms and leaned against the wall watching him carefully"
        msgs = [
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": repeated + " with narrow eyes."},
            {"role": "user", "content": "B"},
            {"role": "assistant", "content": repeated + " with a frown."},
            {"role": "user", "content": "C"},
            {"role": "assistant", "content": repeated + " with suspicion."},
        ]
        assert voice_is_drifting(msgs) is True

    def test_only_counts_assistant_messages(self):
        msgs = [
            {"role": "user", "content": "Her breath caught in her throat"},
            {"role": "assistant", "content": "She nodded slowly, considering the question."},
            {"role": "user", "content": "Her heart pounded in her chest"},
            {"role": "assistant", "content": "The rain drummed against the window as she spoke."},
            {"role": "user", "content": "Electricity coursed through her veins"},
            {"role": "assistant", "content": "She set down her cup and met his gaze steadily."},
        ]
        assert voice_is_drifting(msgs) is False


# -- fewshot.py: get_fewshot_messages --


def _make_ollama(embedding=None):
    """Return a mock OllamaClient with embed() as an AsyncMock."""
    ollama = AsyncMock()
    ollama.embed = AsyncMock(return_value=embedding or [0.1, 0.2, 0.3])
    return ollama


def test_get_fewshot_messages_returns_pairs():
    """get_fewshot_messages() returns correct user/assistant message pairs."""
    ollama = _make_ollama()
    messages = [
        {"role": "user", "content": "Hello there"},
        {"role": "assistant", "content": "Greetings, traveller"},
    ]
    examples = [
        {"user_message": "Good day", "assistant_message": "Good day to you too"},
        {"user_message": "Farewell", "assistant_message": "Until we meet again"},
    ]

    with patch("projects.rp.fewshot.voice_is_drifting", return_value=True), \
         patch("projects.rp.db.search_fewshot_examples", AsyncMock(return_value=examples)):
        result = asyncio.run(get_fewshot_messages(ollama, messages, card_id=5))

    assert result == [
        {"role": "user", "content": "Good day"},
        {"role": "assistant", "content": "Good day to you too"},
        {"role": "user", "content": "Farewell"},
        {"role": "assistant", "content": "Until we meet again"},
    ]


def test_get_fewshot_messages_no_card_id():
    """get_fewshot_messages() returns [] when card_id is None."""
    ollama = _make_ollama()
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]

    result = asyncio.run(get_fewshot_messages(ollama, messages, card_id=None))

    assert result == []
    ollama.embed.assert_not_called()


def test_get_fewshot_messages_too_few_messages():
    """get_fewshot_messages() returns [] when conversation has fewer than 2 messages."""
    ollama = _make_ollama()

    result_zero = asyncio.run(get_fewshot_messages(ollama, [], card_id=5))
    result_one = asyncio.run(get_fewshot_messages(ollama, [{"role": "user", "content": "hi"}], card_id=5))

    assert result_zero == []
    assert result_one == []
    ollama.embed.assert_not_called()


def test_get_fewshot_messages_no_results():
    """get_fewshot_messages() returns [] when DB returns no examples."""
    ollama = _make_ollama()
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]

    with patch("projects.rp.fewshot.voice_is_drifting", return_value=True), \
         patch("projects.rp.db.search_fewshot_examples", AsyncMock(return_value=[])):
        result = asyncio.run(get_fewshot_messages(ollama, messages, card_id=5))

    assert result == []


def test_get_fewshot_messages_error_returns_empty():
    """get_fewshot_messages() returns [] and does not propagate when embed() raises."""
    ollama = AsyncMock()
    ollama.embed = AsyncMock(side_effect=RuntimeError("Ollama is down"))
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]

    with patch("projects.rp.fewshot.voice_is_drifting", return_value=True):
        result = asyncio.run(get_fewshot_messages(ollama, messages, card_id=5))

    assert result == []


def test_get_fewshot_messages_embeds_assistant_only():
    """get_fewshot_messages() embeds only the last assistant message for style matching."""
    ollama = _make_ollama()
    messages = [
        {"role": "user", "content": "First user message"},
        {"role": "assistant", "content": "First assistant response"},
        {"role": "user", "content": "Second user message"},
        {"role": "assistant", "content": "Second assistant response"},
    ]

    with patch("projects.rp.fewshot.voice_is_drifting", return_value=True), \
         patch("projects.rp.db.search_fewshot_examples", AsyncMock(return_value=[])):
        asyncio.run(get_fewshot_messages(ollama, messages, card_id=5))

    ollama.embed.assert_called_once_with("nomic-embed-text", "Second assistant response")


def test_get_fewshot_messages_skips_when_voice_strong():
    """get_fewshot_messages() returns [] without calling embed when voice is strong."""
    ollama = _make_ollama()
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]

    with patch("projects.rp.fewshot.voice_is_drifting", return_value=False):
        result = asyncio.run(get_fewshot_messages(ollama, messages, card_id=5))

    assert result == []
    ollama.embed.assert_not_called()


def test_get_fewshot_messages_proceeds_when_voice_drifting():
    """get_fewshot_messages() proceeds to retrieval when voice is drifting."""
    ollama = _make_ollama()
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    examples = [
        {"user_message": "Hey", "assistant_message": "Greetings"},
    ]

    with patch("projects.rp.fewshot.voice_is_drifting", return_value=True), \
         patch("projects.rp.db.search_fewshot_examples", AsyncMock(return_value=examples)):
        result = asyncio.run(get_fewshot_messages(ollama, messages, card_id=5))

    assert len(result) == 2
    ollama.embed.assert_called_once()
