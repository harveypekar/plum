import asyncio
from unittest.mock import AsyncMock

from projects.rp.stock_phrases import make_stock_phrase_rewriter, REWRITE_MODEL


def _make_ollama(response_text="Rewritten response here."):
    ollama = AsyncMock()
    ollama.chat = AsyncMock(return_value={
        "message": {"content": response_text},
    })
    return ollama


class TestMakeStockPhraseRewriter:
    def test_no_violations_passes_through(self):
        ollama = _make_ollama()
        hook = make_stock_phrase_rewriter(ollama)
        ctx = {"response": "She smiled.", "ai_name": "Kasa"}
        result = asyncio.run(hook(ctx))
        assert result["response"] == "She smiled."
        ollama.chat.assert_not_called()

    def test_empty_violations_passes_through(self):
        ollama = _make_ollama()
        hook = make_stock_phrase_rewriter(ollama)
        ctx = {
            "response": "She smiled.",
            "ai_name": "Kasa",
            "_stock_phrase_violations": [],
        }
        result = asyncio.run(hook(ctx))
        assert result["response"] == "She smiled."
        ollama.chat.assert_not_called()

    def test_calls_ollama_on_violations(self):
        rewritten = "She felt her stomach drop as the door slammed."
        ollama = _make_ollama(rewritten)
        hook = make_stock_phrase_rewriter(ollama)
        ctx = {
            "response": "Her breath caught in her throat as the door slammed.",
            "ai_name": "Kasa",
            "_stock_phrase_violations": ["breath caught in"],
        }
        result = asyncio.run(hook(ctx))
        assert result["response"] == rewritten
        assert result["_stock_phrases_rewritten"] is True
        ollama.chat.assert_called_once()

    def test_prompt_contains_violations_and_response(self):
        ollama = _make_ollama("Fixed response.")
        hook = make_stock_phrase_rewriter(ollama)
        original = "Her heart pounded in her chest."
        ctx = {
            "response": original,
            "ai_name": "Jess",
            "_stock_phrase_violations": ["heart pounded in"],
        }
        asyncio.run(hook(ctx))
        call_args = ollama.chat.call_args
        prompt = call_args[1]["messages"][0]["content"]
        assert "heart pounded in" in prompt
        assert original in prompt
        assert "Jess" in prompt

    def test_uses_resolve_model(self):
        ollama = _make_ollama("Fixed.")
        def resolve(m):
            return f"resolved-{m}"
        hook = make_stock_phrase_rewriter(ollama, resolve_model=resolve)
        ctx = {
            "response": "Her pulse quickened.",
            "ai_name": "Kasa",
            "_stock_phrase_violations": ["pulse quickened"],
        }
        asyncio.run(hook(ctx))
        call_args = ollama.chat.call_args
        assert call_args[1]["model"] == f"resolved-{REWRITE_MODEL}"

    def test_uses_raw_model_without_resolver(self):
        ollama = _make_ollama("Fixed.")
        hook = make_stock_phrase_rewriter(ollama)
        ctx = {
            "response": "Her pulse quickened.",
            "ai_name": "Kasa",
            "_stock_phrase_violations": ["pulse quickened"],
        }
        asyncio.run(hook(ctx))
        call_args = ollama.chat.call_args
        assert call_args[1]["model"] == REWRITE_MODEL

    def test_keeps_original_on_too_short_rewrite(self):
        ollama = _make_ollama("Short.")
        hook = make_stock_phrase_rewriter(ollama)
        original = "Her breath caught in her throat as she watched the sunset paint the sky in brilliant oranges and deep purples."
        ctx = {
            "response": original,
            "ai_name": "Kasa",
            "_stock_phrase_violations": ["breath caught in"],
        }
        result = asyncio.run(hook(ctx))
        assert result["response"] == original
        assert "_stock_phrases_rewritten" not in result

    def test_keeps_original_on_empty_rewrite(self):
        ollama = _make_ollama("")
        hook = make_stock_phrase_rewriter(ollama)
        original = "Her heart pounded in her chest."
        ctx = {
            "response": original,
            "ai_name": "Kasa",
            "_stock_phrase_violations": ["heart pounded in"],
        }
        result = asyncio.run(hook(ctx))
        assert result["response"] == original

    def test_keeps_original_on_ollama_error(self):
        ollama = AsyncMock()
        ollama.chat = AsyncMock(side_effect=RuntimeError("Ollama down"))
        hook = make_stock_phrase_rewriter(ollama)
        original = "Her pulse raced as she ran."
        ctx = {
            "response": original,
            "ai_name": "Kasa",
            "_stock_phrase_violations": ["pulse raced"],
        }
        result = asyncio.run(hook(ctx))
        assert result["response"] == original
        assert "_stock_phrases_rewritten" not in result

    def test_multiple_violations_listed(self):
        ollama = _make_ollama("She felt her legs weaken and her hands shake.")
        hook = make_stock_phrase_rewriter(ollama)
        ctx = {
            "response": "Her breath caught in her throat and her heart pounded in her chest.",
            "ai_name": "Kasa",
            "_stock_phrase_violations": ["breath caught in", "heart pounded in"],
        }
        result = asyncio.run(hook(ctx))
        call_args = ollama.chat.call_args
        prompt = call_args[1]["messages"][0]["content"]
        assert "breath caught in" in prompt
        assert "heart pounded in" in prompt
        assert result["_stock_phrases_rewritten"] is True
