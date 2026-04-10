"""Unit tests for projects/rp/budget.py."""

import asyncio
import pytest

from projects.rp import budget
from projects.rp.budget import BudgetError, BudgetReport, _get_model_ctx, _ollama_count_messages, fit_prompt
from projects.rp.context import SlidingWindow, SummaryBuffer


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


def _build_ctx(system_prompt="", post_prompt="", messages=None, ai_card=None):
    """Build a minimal ctx dict for fit_prompt tests."""
    return {
        "system_prompt": system_prompt,
        "post_prompt": post_prompt,
        "messages": messages or [],
        "ai_card": ai_card or {"card_data": {"data": {"mes_example": ""}}},
    }


class TestFitPromptHappyPath:
    @pytest.mark.asyncio
    async def test_everything_fits_no_shrink(self, stub_ollama_factory):
        stub = stub_ollama_factory(num_ctx_map={"m": 8192})
        ctx = _build_ctx(
            system_prompt="system",  # ~1 token
            post_prompt="post",       # ~1 token
            messages=[
                {"role": "assistant", "content": "greeting"},
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
        )
        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SlidingWindow(),
            num_predict=512, ground_truth=False,
        )
        assert len(ctx["messages"]) == 3
        assert report.model == "m"
        assert report.model_ctx == 8192
        assert report.response_reserve == 512
        assert report.available == 8192 - 512
        assert report.messages_kept == 3
        assert report.messages_dropped == 0
        assert report.summary_dropped is False
        assert report.mes_example_truncated is False
        assert ctx["_num_ctx"] == 8192
        assert ctx["_budget_report"] is report

    @pytest.mark.asyncio
    async def test_default_response_reserve_is_1024(self, stub_ollama_factory):
        stub = stub_ollama_factory(num_ctx_map={"m": 8192})
        ctx = _build_ctx(messages=[{"role": "user", "content": "hi"}])
        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SlidingWindow(),
            num_predict=None, ground_truth=False,
        )
        assert report.response_reserve == 1024

    @pytest.mark.asyncio
    async def test_priority_2_drops_oldest_messages(self, stub_ollama_factory):
        """When messages exceed budget, SlidingWindow drops oldest first.

        Budget math:
          available = 2048 - 1900 = 148 tokens
          overhead = 0 (no system/post prompt)
          messages_budget = 148
          Each message = len("X"*100) // 4 = 25 tokens

        SlidingWindow keeps greeting (25t) then fills from newest:
          E(25), D(25), C(25), B(25) = 100t total -> 25+100=125 <= 148
          A: 125+25=150 > 148 -> break
        Result: G (greeting) + B, C, D, E kept; A (oldest) dropped.
        """
        stub = stub_ollama_factory(num_ctx_map={"m": 2048})
        messages = [
            {"role": "assistant", "content": "G" * 100},   # greeting (kept)
            {"role": "user", "content": "A" * 100},        # oldest (droppable)
            {"role": "assistant", "content": "B" * 100},
            {"role": "user", "content": "C" * 100},
            {"role": "assistant", "content": "D" * 100},
            {"role": "user", "content": "E" * 100},        # most recent (kept)
        ]
        ctx = _build_ctx(messages=messages)
        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SlidingWindow(),
            num_predict=1900, ground_truth=False,
        )
        contents = [m["content"] for m in ctx["messages"]]
        assert "G" * 100 in contents  # greeting
        assert "E" * 100 in contents  # most recent
        assert "A" * 100 not in contents  # oldest dropped
        assert report.messages_dropped > 0

    @pytest.mark.asyncio
    async def test_overhead_counted_against_budget(self, stub_ollama_factory):
        """Large system_prompt should reduce messages_budget accordingly."""
        stub = stub_ollama_factory(num_ctx_map={"m": 1000})
        ctx = _build_ctx(
            system_prompt="X" * 2000,
            messages=[{"role": "user", "content": "hi"}],
        )
        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SlidingWindow(),
            num_predict=200, ground_truth=False,
        )
        # available = 1000 - 200 = 800
        # overhead = len("X"*2000)//4 = 500 (system) + 0 (post) = 500
        # messages_budget = 300
        assert report.available == 800
        assert report.overhead == 500
        assert report.messages_budget == 300


class TestFitPromptPriority3:
    @pytest.mark.asyncio
    async def test_summary_kept_when_it_fits(self, stub_ollama_factory):
        """Happy case: summary fits within budget, should not be dropped."""
        stub = stub_ollama_factory(num_ctx_map={"m": 1000})
        ctx = _build_ctx(
            system_prompt="",
            post_prompt="",
            messages=[
                {"role": "assistant", "content": "greeting", "_sequence": 1},
                {"role": "user", "content": "X" * 1000, "_sequence": 10},
            ],
        )
        ctx["_summary"] = "Y" * 800
        ctx["_summary_through_sequence"] = 5

        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SummaryBuffer(),
            num_predict=500, ground_truth=False,
        )
        assert report.summary_dropped is False

    @pytest.mark.asyncio
    async def test_summary_dropped_when_budget_too_tight(self, stub_ollama_factory):
        """When even after strategy.fit the prompt is still over budget
        (we check via the estimator on the rendered messages), drop summary.

        Budget math (4-chars-per-token estimator):
          model_ctx=1200, num_predict=300 -> available=900, messages_budget=900
          summary "S"*400 -> 100 tokens; cap = 900*0.25 = 225; 100 <= 225, injected.
          budget_for_recent = 900 - 0 (greeting "hi"=2 chars=0t) - 100 = 800
          recent "Z"*3200 -> 800 tokens; 800 <= 800, kept by strategy.
          Injected msg = "[Story so far]\\n" + "S"*400 = 415 chars = 103 tokens.
          Post-strategy total = 103 + 0 + 800 = 903 > 900 -> Priority 3 fires.
        """
        stub = stub_ollama_factory(num_ctx_map={"m": 1200})
        # 800 tokens exactly fills recent budget; "[Story so far]\\n" prefix (3t) pushes total over
        huge_recent = "Z" * 3200  # 800 tokens
        ctx = _build_ctx(
            messages=[
                {"role": "assistant", "content": "hi", "_sequence": 1},
                {"role": "user", "content": huge_recent, "_sequence": 10},
            ],
        )
        ctx["_summary"] = "S" * 400  # 100 tokens, within 25% cap
        ctx["_summary_through_sequence"] = 5

        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SummaryBuffer(),
            num_predict=300, ground_truth=False,
        )
        assert report.summary_dropped is True
        for m in ctx["messages"]:
            assert "[Story so far]" not in m.get("content", "")


class TestFitPromptPriority4:
    @pytest.mark.asyncio
    async def test_mes_example_truncated_when_overhead_dominates(
        self, stub_ollama_factory
    ):
        """When system_prompt (which includes mes_example) exceeds the
        available budget, truncate mes_example and re-render.

        Uses a minimal template (system section only, no post) so that after
        truncation the re-assembled overhead fits within available.
        Budget math:
          model_ctx=1000, num_predict=500 -> available=500
          mes_example = "Example line.\\n" * 200 = 2800 chars = 700 tokens
          template "## system\\n{{mes_example}}" -> system_prompt = mes_example (~700t)
          initial overhead = 700 > 500 -> P4 fires
          after truncation: target = max(700//4, 200) = 200 tokens -> ~800 chars
          re-assembled overhead ~200t <= 500 -> P5 does not fire
        """
        stub = stub_ollama_factory(num_ctx_map={"m": 1000})

        mes_example = "Example line.\n" * 200

        ctx = _build_ctx(
            system_prompt=mes_example,  # initial system_prompt includes mes_example
            messages=[{"role": "user", "content": "hi"}],
            ai_card={"card_data": {"data": {"mes_example": mes_example}}},
        )
        ctx["user_card"] = {"card_data": {"data": {}}}
        ctx["scenario"] = {}
        # Minimal template: system section only, no post — keeps overhead low after re-assembly
        ctx["prompt_template"] = "## system\n{{mes_example}}"

        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SlidingWindow(),
            num_predict=500, ground_truth=False,
        )
        assert report.mes_example_truncated is True
        truncated = ctx["ai_card"]["card_data"]["data"]["mes_example"]
        assert len(truncated) < len(mes_example)


class TestFitPromptPriority5:
    @pytest.mark.asyncio
    async def test_budget_error_when_single_user_message_too_big(
        self, stub_ollama_factory
    ):
        """A user message larger than model_ctx on its own can't be shrunk."""
        stub = stub_ollama_factory(num_ctx_map={"m": 500})
        huge = "X" * 20000  # ~5000 tokens
        ctx = _build_ctx(
            messages=[
                {"role": "assistant", "content": "greeting"},
                {"role": "user", "content": huge},
            ],
        )
        with pytest.raises(BudgetError) as exc_info:
            await fit_prompt(
                ctx, model="m", ollama=stub, strategy=SlidingWindow(),
                num_predict=100, ground_truth=False,
            )
        report = exc_info.value.report
        assert report.model == "m"
        assert report.model_ctx == 500
        assert "fit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_budget_error_when_system_alone_exceeds_available(
        self, stub_ollama_factory
    ):
        """Even after mes_example truncation, if the rest of the system
        prompt exceeds available, we raise."""
        stub = stub_ollama_factory(num_ctx_map={"m": 200})
        ctx = _build_ctx(
            system_prompt="X" * 4000,
            messages=[{"role": "user", "content": "hi"}],
            ai_card={"card_data": {"data": {"mes_example": ""}}},
        )
        ctx["user_card"] = {"card_data": {"data": {}}}
        ctx["scenario"] = {}
        ctx["prompt_template"] = ""

        with pytest.raises(BudgetError):
            await fit_prompt(
                ctx, model="m", ollama=stub, strategy=SlidingWindow(),
                num_predict=50, ground_truth=False,
            )
