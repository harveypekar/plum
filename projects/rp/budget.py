"""Prompt budgeting: fit rp pipeline and lora_generate prompts into model_ctx.

See docs/superpowers/specs/2026-04-07-rp-prompt-budgeting-design.md.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Protocol

_log = logging.getLogger(__name__)


class _OllamaLike(Protocol):
    async def get_num_ctx(self, model: str) -> int: ...
    async def chat(self, model, messages, tools=None, think=False): ...


# Module-level cache: model name -> num_ctx. Populated on first use per model.
_ctx_cache: dict[str, int] = {}
_ctx_locks: dict[str, asyncio.Lock] = {}


class BudgetError(Exception):
    """Raised when the minimum viable prompt exceeds model_ctx - response_reserve."""

    def __init__(self, message: str, report: "BudgetReport"):
        super().__init__(message)
        self.report = report


@dataclass
class BudgetReport:
    model: str
    model_ctx: int
    response_reserve: int
    available: int              # model_ctx - reserve
    overhead: int               # system_prompt + post_prompt (estimator)
    messages_budget: int        # available - overhead
    messages_kept: int
    messages_dropped: int
    summary_dropped: bool
    mes_example_truncated: bool
    estimator_tokens: int
    actual_tokens: int | None
    warnings: list[str] = field(default_factory=list)


def _estimate_tokens(text: str) -> int:
    """Rough token count: ~4 chars per token. Cheap, used for iterative shrinking."""
    return len(text) // 4


async def _get_model_ctx(model: str, ollama: _OllamaLike) -> int:
    """Return cached num_ctx for `model`, fetching once on first use.

    Uses a per-model asyncio.Lock so concurrent first-use calls don't
    issue duplicate /api/show requests.
    """
    cached = _ctx_cache.get(model)
    if cached is not None:
        return cached

    lock = _ctx_locks.setdefault(model, asyncio.Lock())
    async with lock:
        cached = _ctx_cache.get(model)
        if cached is not None:
            return cached
        num_ctx = await ollama.get_num_ctx(model)
        _ctx_cache[model] = num_ctx
        _log.info("Loaded num_ctx=%d for model %s", num_ctx, model)
        return num_ctx
