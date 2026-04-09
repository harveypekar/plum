"""Unit tests for projects/rp/budget.py."""

import asyncio
import pytest

from projects.rp import budget
from projects.rp.budget import BudgetError, BudgetReport, _get_model_ctx, _ollama_count_messages


@pytest.fixture(autouse=True)
def _clear_budget_cache():
    """Ensure each test sees a fresh module-level cache."""
    budget._ctx_cache.clear()
    budget._ctx_locks.clear()
    yield
    budget._ctx_cache.clear()
    budget._ctx_locks.clear()


class TestBudgetReport:
    def test_fields_have_sensible_defaults(self):
        report = BudgetReport(
            model="m", model_ctx=8192, response_reserve=1024,
            available=7168, overhead=500, messages_budget=6668,
            messages_kept=10, messages_dropped=0,
            summary_dropped=False, mes_example_truncated=False,
            estimator_tokens=5000, actual_tokens=None,
        )
        assert report.model == "m"
        assert report.warnings == []

    def test_budget_error_carries_report(self):
        report = BudgetReport(
            model="m", model_ctx=1024, response_reserve=1024,
            available=0, overhead=0, messages_budget=0,
            messages_kept=0, messages_dropped=0,
            summary_dropped=False, mes_example_truncated=False,
            estimator_tokens=0, actual_tokens=None, warnings=[],
        )
        err = BudgetError("doesn't fit", report)
        assert err.report is report
        assert str(err) == "doesn't fit"


class TestGetModelCtx:
    @pytest.mark.asyncio
    async def test_first_call_fetches_from_ollama(self, stub_ollama_factory):
        stub = stub_ollama_factory(num_ctx_map={"modelA": 8192})
        result = await _get_model_ctx("modelA", stub)
        assert result == 8192
        assert stub.show_calls["modelA"] == 1

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self, stub_ollama_factory):
        stub = stub_ollama_factory(num_ctx_map={"modelA": 8192})
        await _get_model_ctx("modelA", stub)
        await _get_model_ctx("modelA", stub)
        assert stub.show_calls["modelA"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_first_calls_only_fetch_once(self, stub_ollama_factory):
        stub = stub_ollama_factory(num_ctx_map={"modelA": 8192})
        results = await asyncio.gather(*[
            _get_model_ctx("modelA", stub) for _ in range(10)
        ])
        assert all(r == 8192 for r in results)
        assert stub.show_calls["modelA"] == 1

    @pytest.mark.asyncio
    async def test_different_models_cached_independently(self, stub_ollama_factory):
        stub = stub_ollama_factory(num_ctx_map={"A": 8192, "B": 32768})
        assert await _get_model_ctx("A", stub) == 8192
        assert await _get_model_ctx("B", stub) == 32768
        assert stub.show_calls == {"A": 1, "B": 1}


class TestOllamaCountMessages:
    @pytest.mark.asyncio
    async def test_returns_prompt_eval_count(self, stub_ollama_factory):
        stub = stub_ollama_factory(count_map={"modelA": 1234})
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hi"},
        ]
        count = await _ollama_count_messages(messages, "modelA", stub)
        assert count == 1234
        assert stub.chat_calls == 1

    @pytest.mark.asyncio
    async def test_returns_zero_when_missing(self, stub_ollama_factory):
        """If Ollama doesn't return prompt_eval_count, return 0 and let caller
        decide. Never silently inflate or deflate."""
        stub = stub_ollama_factory(count_map={})  # default_count=0
        count = await _ollama_count_messages([{"role": "user", "content": "x"}], "modelA", stub)
        assert count == 0
