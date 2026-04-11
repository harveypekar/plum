"""Shared test fixtures for the rp test suite."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest


@dataclass
class StubOllama:
    """Stand-in for OllamaClient in unit tests.

    - `num_ctx_map` is what get_num_ctx returns per model.
    - `count_map` lets tests stub the ground-truth count helper by
      registering a dict of {prompt_key: token_count}. Tests that don't
      care about ground-truth counting can leave it empty.
    - `show_calls` records how many times get_num_ctx was called per
      model (for cache-hit tests).
    - `chat_calls` records how many times chat() was called (for the
      ground-truth call counter).
    """

    num_ctx_map: dict[str, int] = field(default_factory=dict)
    count_map: dict[str, int] = field(default_factory=dict)
    show_calls: dict[str, int] = field(default_factory=dict)
    chat_calls: int = 0
    default_count: int = 0
    last_chat_messages: list | None = None

    async def get_num_ctx(self, model: str) -> int:
        self.show_calls[model] = self.show_calls.get(model, 0) + 1
        await asyncio.sleep(0)
        if model not in self.num_ctx_map:
            from aiserver.ollama import OllamaError
            raise OllamaError(f"stub has no num_ctx for model {model!r}")
        return self.num_ctx_map[model]

    async def chat(self, model: str, messages, tools=None, think=False):
        """Stub /api/chat that returns a prompt_eval_count.

        Ground-truth counting calls this with num_predict=0 in options;
        our stub returns count_map[model] or default_count.
        """
        self.chat_calls += 1
        self.last_chat_messages = list(messages)
        count = self.count_map.get(model, self.default_count)
        return {
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "prompt_eval_count": count,
        }


@pytest.fixture
def stub_ollama_factory():
    """Factory that builds a fresh StubOllama with the given config."""
    def _make(**kwargs):
        return StubOllama(**kwargs)
    return _make
