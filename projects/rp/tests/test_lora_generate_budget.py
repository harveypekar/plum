"""Tests for lora_generate.py integration with budget.fit_raw_prompt."""

import pytest
from unittest.mock import AsyncMock

from projects.rp import lora_generate
from projects.rp.budget import BudgetError, BudgetReport


def _report(model_ctx=8192):
    return BudgetReport(
        model="m", model_ctx=model_ctx, response_reserve=500,
        available=model_ctx - 500, overhead=100, messages_budget=0,
        messages_kept=0, messages_dropped=0,
        summary_dropped=False, mes_example_truncated=False,
        estimator_tokens=100, actual_tokens=100, warnings=[],
    )


class TestGenerateScenariosBudgetSkip:
    @pytest.mark.asyncio
    async def test_budget_error_skips_category(self, monkeypatch):
        """If fit_raw_prompt raises for one category, that category is
        skipped but generate_scenarios returns scenarios from the others."""
        ollama = AsyncMock()
        ollama.get_num_ctx = AsyncMock(return_value=8192)
        ollama.generate = AsyncMock(return_value='["s1.", "s2.", "s3."]')
        ollama.chat = AsyncMock(return_value={"prompt_eval_count": 100, "done": True})

        call_count = {"n": 0}

        async def _fake_fit_raw_prompt(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise BudgetError("too big", _report(500))
            return kwargs["prompt"], _report()

        monkeypatch.setattr(lora_generate, "fit_raw_prompt", _fake_fit_raw_prompt)

        ai_card = {"data": {"name": "Ann", "description": "x", "personality": "y"}}
        user_card = {"data": {"name": "Bea", "description": "z"}}
        scenarios = await lora_generate.generate_scenarios(
            ollama, "m", ai_card, user_card, num_per_category=3
        )
        # 8 categories * 3 scenarios each = 24, minus 3 from skipped = 21
        assert len(scenarios) == 21


class TestGenerateUserMessageBudgetError:
    @pytest.mark.asyncio
    async def test_returns_empty_on_budget_error(self, monkeypatch):
        """BudgetError in generate_user_message returns '' so the existing
        'empty message' branch in generate_conversation stops the turn."""
        ollama = AsyncMock()

        async def _fake_fit(**kwargs):
            raise BudgetError("too big", _report(500))

        monkeypatch.setattr(lora_generate, "fit_raw_prompt", _fake_fit)

        context = {
            "char_name": "Ann", "user_name": "Bea",
            "user_personality": "p", "scenario": "s", "history": [],
        }
        result = await lora_generate.generate_user_message(ollama, "m", context)
        assert result == ""
