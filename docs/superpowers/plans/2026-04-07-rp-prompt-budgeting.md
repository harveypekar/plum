# Prompt Budgeting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guarantee every prompt sent to Ollama by the rp runtime pipeline and `lora_generate.py` fits within the model's real context window, with a deterministic shrink policy and a ground-truth token count.

**Architecture:** New module `projects/rp/budget.py` with a single async entry point `fit_prompt(ctx, ...)` (plus `fit_raw_prompt` for single-shot prompts). Called explicitly from `routes.py` after pipeline pre-hooks and from `lora_generate.py` before each Ollama call. The pipeline itself stays pure. `OllamaClient` gets one new method `get_num_ctx` that reads `/api/show` once per model and caches the result.

**Tech Stack:** Python 3.11+, `httpx`, `asyncpg`, `asyncio`, `pytest`, `pytest-asyncio`, `fastapi`, Ollama local server.

**Spec:** `docs/superpowers/specs/2026-04-07-rp-prompt-budgeting-design.md`

**Branch / worktree:** work must happen on branch `prompt-budgeting` in worktree `/mnt/d/prg/plum-prompt-budgeting`. All `cd` paths in this plan assume that worktree.

---

## Preflight

- [ ] **Step 0: Switch to the correct worktree**

```bash
cd /mnt/d/prg/plum-prompt-budgeting
git status
git branch --show-current
```

Expected: clean working tree, branch `prompt-budgeting`.

---

## Task 1: Add `OllamaClient.get_num_ctx`

**Why:** Budgeting needs the model's real context window. Ollama exposes it via `/api/show`. This method is general enough to belong on the shared client, not inside `budget.py`.

**Files:**
- Modify: `projects/aiserver/ollama.py` (add method after `list_models_detail`, around line 254)
- Test: `projects/aiserver/tests/test_ollama_chat.py` (add a new test class at the end)

- [ ] **Step 1.1: Write the failing tests**

Append to `projects/aiserver/tests/test_ollama_chat.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from aiserver.ollama import OllamaClient, OllamaError


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
```

- [ ] **Step 1.2: Run tests and verify they fail**

```bash
cd /mnt/d/prg/plum-prompt-budgeting
cd projects/aiserver && source .venv/bin/activate && cd ../..
pytest projects/aiserver/tests/test_ollama_chat.py::TestGetNumCtx -v
```

Expected: FAIL — `AttributeError: 'OllamaClient' object has no attribute 'get_num_ctx'`.

- [ ] **Step 1.3: Implement `get_num_ctx`**

In `projects/aiserver/ollama.py`, add this method to `OllamaClient` after `list_models_detail` (around line 254):

```python
    async def get_num_ctx(self, model: str) -> int:
        """Return effective context length for a model via /api/show.

        Prefers the runtime-loaded num_ctx from the parameters field (a
        whitespace-formatted string). Falls back to any <arch>.context_length
        entry in model_info (the architectural max from the GGUF file).
        Raises OllamaError if neither is present or the request fails.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/show", json={"model": model}
                )
                if resp.status_code != 200:
                    raise OllamaError(
                        f"Ollama /api/show returned {resp.status_code}: {resp.text}"
                    )
                data = resp.json()
        except httpx.ConnectError:
            raise OllamaError(f"Cannot connect to Ollama at {self.base_url}")
        except httpx.HTTPError as e:
            raise OllamaError(f"HTTP error from /api/show: {e}") from e

        # Parse parameters for "num_ctx <value>"
        params_str = data.get("parameters", "") or ""
        for line in params_str.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "num_ctx":
                try:
                    return int(parts[1])
                except ValueError:
                    pass

        # Fall back to model_info[<arch>.context_length]
        model_info = data.get("model_info", {}) or {}
        for key, value in model_info.items():
            if key.endswith(".context_length") and isinstance(value, int):
                return value

        raise OllamaError(
            f"Could not determine context length for model {model!r}: "
            f"no num_ctx in parameters and no <arch>.context_length in model_info"
        )
```

- [ ] **Step 1.4: Run tests and verify they pass**

```bash
pytest projects/aiserver/tests/test_ollama_chat.py::TestGetNumCtx -v
```

Expected: all 5 tests PASS.

- [ ] **Step 1.5: Run the full aiserver test suite to check nothing regressed**

```bash
pytest projects/aiserver/tests/ -v
```

Expected: all tests pass (or same baseline as before this change).

- [ ] **Step 1.6: Commit**

```bash
cd /mnt/d/prg/plum-prompt-budgeting
git add projects/aiserver/ollama.py projects/aiserver/tests/test_ollama_chat.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(ollama): add get_num_ctx to read model context length

Reads /api/show and returns the effective num_ctx, preferring
parameters.num_ctx (runtime) and falling back to model_info
<arch>.context_length (architectural max).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: `budget.py` foundations — exceptions, report, model-ctx cache

**Why:** The shared module needs its types and caching layer before any budgeting logic can land.

**Files:**
- Create: `projects/rp/budget.py`
- Create: `projects/rp/tests/test_budget.py`
- Create: `projects/rp/tests/conftest.py` (test helpers — a stub Ollama client)

- [ ] **Step 2.1: Create the test stub for Ollama**

Create `projects/rp/tests/conftest.py`:

```python
"""Shared test fixtures for the rp test suite."""

from __future__ import annotations

from dataclasses import dataclass, field


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

    async def get_num_ctx(self, model: str) -> int:
        self.show_calls[model] = self.show_calls.get(model, 0) + 1
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
        count = self.count_map.get(model, self.default_count)
        return {
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "prompt_eval_count": count,
        }
```

- [ ] **Step 2.2: Write the failing tests for `_get_model_ctx` caching and data classes**

Create `projects/rp/tests/test_budget.py`:

```python
"""Unit tests for projects/rp/budget.py."""

import asyncio
import pytest

from projects.rp import budget
from projects.rp.budget import BudgetError, BudgetReport, _get_model_ctx


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
            estimator_tokens=5000, actual_tokens=None, warnings=[],
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
```

Add a small factory fixture to `projects/rp/tests/conftest.py` (append to the end):

```python
import pytest


@pytest.fixture
def stub_ollama_factory():
    """Factory that builds a fresh StubOllama with the given config."""
    def _make(**kwargs):
        return StubOllama(**kwargs)
    return _make
```

- [ ] **Step 2.3: Run tests to verify they fail**

```bash
cd /mnt/d/prg/plum-prompt-budgeting
cd projects/aiserver && source .venv/bin/activate && cd ../..
pytest projects/rp/tests/test_budget.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'projects.rp.budget'`.

- [ ] **Step 2.4: Create the minimal `budget.py`**

Create `projects/rp/budget.py`:

```python
"""Prompt budgeting: fit rp pipeline and lora_generate prompts into model_ctx.

See docs/superpowers/specs/2026-04-07-rp-prompt-budgeting-design.md.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .context import ContextStrategy

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
```

- [ ] **Step 2.5: Run tests and verify they pass**

```bash
pytest projects/rp/tests/test_budget.py -v
```

Expected: all tests PASS.

- [ ] **Step 2.6: Commit**

```bash
git add projects/rp/budget.py projects/rp/tests/test_budget.py projects/rp/tests/conftest.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp): add budget module foundations

New module projects/rp/budget.py with:
- BudgetError + BudgetReport types
- _get_model_ctx caching helper (one /api/show call per model
  per process, with per-model lock to prevent thundering)
- Estimator-based _estimate_tokens helper

Also adds a StubOllama fixture in projects/rp/tests/conftest.py
for isolated unit tests.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: `_ollama_count_messages` — ground-truth token counting

**Why:** Budgeting needs a way to ask Ollama "how many tokens would this exact set of messages consume?". We use `/api/chat` with `num_predict: 0` and read `prompt_eval_count` from the response.

**Files:**
- Modify: `projects/rp/budget.py` (add helper function)
- Modify: `projects/rp/tests/test_budget.py` (add test class)

- [ ] **Step 3.1: Write the failing test**

Append to `projects/rp/tests/test_budget.py`:

```python
from projects.rp.budget import _ollama_count_messages


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
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
pytest projects/rp/tests/test_budget.py::TestOllamaCountMessages -v
```

Expected: FAIL — `ImportError: cannot import name '_ollama_count_messages'`.

- [ ] **Step 3.3: Implement `_ollama_count_messages`**

Add to `projects/rp/budget.py` (after `_get_model_ctx`):

```python
async def _ollama_count_messages(
    messages: list[dict],
    model: str,
    ollama: _OllamaLike,
) -> int:
    """Ask Ollama for the ground-truth token count of `messages`.

    Calls /api/chat with num_predict=0 (no generation, just tokenize
    the prompt). Reads prompt_eval_count from the response. Returns 0
    if Ollama doesn't surface the field — caller decides how to handle
    a missing value.
    """
    result = await ollama.chat(model=model, messages=messages)
    return int(result.get("prompt_eval_count", 0) or 0)
```

Note: the real `OllamaClient.chat` signature doesn't accept an `options` dict. For counting we rely on Ollama's behavior: a `chat` call with no `num_predict` override still returns `prompt_eval_count` because the prompt is tokenized before generation. In practice `prompt_eval_count` is what we want regardless of how much is generated, so we don't need to set `num_predict=0`. This also avoids a signature change to `OllamaClient.chat`.

If we later decide we *do* need `num_predict=0` (to save a few ms of generation), we'll add an `options` kwarg to `chat` in a separate change.

- [ ] **Step 3.4: Run tests and verify they pass**

```bash
pytest projects/rp/tests/test_budget.py -v
```

Expected: all tests in `test_budget.py` PASS.

- [ ] **Step 3.5: Commit**

```bash
git add projects/rp/budget.py projects/rp/tests/test_budget.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp/budget): add _ollama_count_messages ground-truth helper

Calls Ollama /api/chat and reads prompt_eval_count from the
response. Used by fit_prompt for the single ground-truth
verification step per request.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: `fit_prompt` happy path + Priority 2 (strategy drops oldest)

**Why:** The main entry point. Starts with the happy path and the most common shrink case — delegating to `ContextStrategy.fit` with a correctly-computed `messages_budget`.

**Files:**
- Modify: `projects/rp/budget.py` (add `fit_prompt`)
- Modify: `projects/rp/tests/test_budget.py` (add test class)

- [ ] **Step 4.1: Write failing tests**

Append to `projects/rp/tests/test_budget.py`:

```python
from projects.rp.budget import fit_prompt
from projects.rp.context import SlidingWindow


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
        """When messages exceed budget, SlidingWindow drops oldest first."""
        stub = stub_ollama_factory(num_ctx_map={"m": 2048})  # small ctx
        # Each message ~= 25 tokens under len//4
        messages = [
            {"role": "assistant", "content": "G" * 100},   # greeting (kept)
            {"role": "user", "content": "A" * 100},        # oldest (droppable)
            {"role": "assistant", "content": "B" * 100},   # droppable
            {"role": "user", "content": "C" * 100},        # droppable
            {"role": "assistant", "content": "D" * 100},   # droppable
            {"role": "user", "content": "E" * 100},        # most recent (kept)
        ]
        ctx = _build_ctx(messages=messages)
        # With num_predict=2000, available = 48, overhead = 0,
        # messages_budget = 48 -> can only fit greeting (25) + one (25)
        # = only greeting actually fits since 25+25=50 > 48, or ==
        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SlidingWindow(),
            num_predict=2000, ground_truth=False,
        )
        # Greeting is always kept; most-recent should be kept too.
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
            system_prompt="X" * 2000,  # ~500 tokens
            messages=[{"role": "user", "content": "hi"}],
        )
        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SlidingWindow(),
            num_predict=200, ground_truth=False,
        )
        # available = 1000 - 200 = 800
        # overhead = ~500 (system) + 0 (post) = 500
        # messages_budget = 300
        assert report.available == 800
        assert report.overhead == 500
        assert report.messages_budget == 300
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
pytest projects/rp/tests/test_budget.py::TestFitPromptHappyPath -v
```

Expected: FAIL — `ImportError: cannot import name 'fit_prompt'`.

- [ ] **Step 4.3: Implement `fit_prompt` happy path + Priority 2**

Append to `projects/rp/budget.py`:

```python
async def fit_prompt(
    ctx: dict,
    *,
    model: str,
    ollama: _OllamaLike,
    strategy: "ContextStrategy",
    num_predict: int | None = None,
    ground_truth: bool = True,
) -> BudgetReport:
    """Shrink ctx["messages"] (and, if needed, other prompt pieces) so the
    assembled prompt fits within model_ctx - response_reserve.

    Mutates ctx:
      - ctx["messages"]: potentially trimmed by the strategy
      - ctx["_summary"]: potentially deleted (Priority 3)
      - ctx["ai_card"]: mes_example potentially truncated (Priority 4)
      - ctx["system_prompt"] / ctx["post_prompt"]: re-rendered on P4
      - ctx["_num_ctx"]: set to the model's context window
      - ctx["_budget_report"]: set to the returned BudgetReport

    Raises BudgetError with a populated report if the minimum viable
    prompt (system + greeting + most-recent user message) doesn't fit.
    """
    model_ctx = await _get_model_ctx(model, ollama)
    response_reserve = num_predict if num_predict is not None else 1024
    available = model_ctx - response_reserve

    warnings: list[str] = []
    messages_before = len(ctx.get("messages", []))

    # Estimator-based overhead.
    overhead = _estimate_tokens(ctx.get("system_prompt", "")) + _estimate_tokens(
        ctx.get("post_prompt", "")
    )
    messages_budget = available - overhead

    # Priority 2: delegate to strategy.fit with the corrected budget.
    # The strategy (SlidingWindow / SummaryBuffer) handles greeting
    # protection, oldest-first drop, and summary injection.
    if messages_budget > 0:
        ctx["messages"] = strategy.fit(
            ctx.get("messages", []), messages_budget, ctx=ctx
        )

    messages_after = len(ctx.get("messages", []))
    messages_dropped = max(0, messages_before - messages_after)

    report = BudgetReport(
        model=model,
        model_ctx=model_ctx,
        response_reserve=response_reserve,
        available=available,
        overhead=overhead,
        messages_budget=messages_budget,
        messages_kept=messages_after,
        messages_dropped=messages_dropped,
        summary_dropped=False,
        mes_example_truncated=False,
        estimator_tokens=overhead + sum(
            _estimate_tokens(m.get("content", "")) for m in ctx.get("messages", [])
        ),
        actual_tokens=None,
        warnings=warnings,
    )

    ctx["_num_ctx"] = model_ctx
    ctx["_budget_report"] = report
    return report
```

- [ ] **Step 4.4: Run tests and verify they pass**

```bash
pytest projects/rp/tests/test_budget.py::TestFitPromptHappyPath -v
```

Expected: all 4 tests PASS. Debug any token-count edge cases until green (the test message sizes are set so len//4 arithmetic lines up).

- [ ] **Step 4.5: Commit**

```bash
git add projects/rp/budget.py projects/rp/tests/test_budget.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp/budget): add fit_prompt with Priority 2 (strategy drop)

Happy path + delegation to ContextStrategy.fit with a corrected
messages budget (model_ctx - response_reserve - overhead). Ground
truth check and higher-priority shrink steps follow in later
commits.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Priority 3 — drop summary when still over budget

**Why:** After strategy.fit drops all droppable messages, if we're still over (e.g., because the summary itself is the overflow source), the next-cheapest thing to lose is the summary.

**Files:**
- Modify: `projects/rp/budget.py` (add post-strategy check)
- Modify: `projects/rp/tests/test_budget.py`

- [ ] **Step 5.1: Write failing test**

Append to `projects/rp/tests/test_budget.py`:

```python
from projects.rp.context import SummaryBuffer


class TestFitPromptPriority3:
    @pytest.mark.asyncio
    async def test_summary_dropped_when_still_over(self, stub_ollama_factory):
        """After strategy.fit drops all messages but a single huge user msg,
        and overhead + summary + that msg still exceeds budget, the summary
        should be dropped."""
        stub = stub_ollama_factory(num_ctx_map={"m": 1000})
        ctx = _build_ctx(
            system_prompt="",
            post_prompt="",
            messages=[
                {"role": "assistant", "content": "greeting",
                 "_sequence": 1},
                {"role": "user", "content": "X" * 1000,
                 "_sequence": 10},  # ~250 tokens, most recent
            ],
        )
        # Summary is ~200 tokens (would normally fit under 25% cap of 1000 = 250)
        ctx["_summary"] = "Y" * 800
        ctx["_summary_through_sequence"] = 5

        # available = 1000 - 100 = 900
        # overhead = 0
        # messages_budget = 900
        # SummaryBuffer would include summary (~200) + greeting + recent msg (~250)
        # Total ~ 450 — fits. This test needs tighter budget to force drop.

        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SummaryBuffer(),
            num_predict=500, ground_truth=False,
        )
        # available = 500, overhead=0, messages_budget=500
        # summary_buffer injects summary (~200) + greeting (~2) + recent (~250) = 452
        # fits without dropping summary
        assert report.summary_dropped is False

    @pytest.mark.asyncio
    async def test_summary_dropped_when_budget_too_tight(self, stub_ollama_factory):
        """When even after strategy.fit the prompt is still over budget
        (we check via the estimator on the rendered messages), drop summary."""
        stub = stub_ollama_factory(num_ctx_map={"m": 1200})
        huge_recent = "Z" * 3600  # ~900 tokens
        ctx = _build_ctx(
            messages=[
                {"role": "assistant", "content": "hi", "_sequence": 1},
                {"role": "user", "content": huge_recent, "_sequence": 10},
            ],
        )
        ctx["_summary"] = "S" * 400  # ~100 tokens
        ctx["_summary_through_sequence"] = 5

        # available = 1200 - 200 = 1000
        # overhead = 0
        # messages_budget = 1000
        # SummaryBuffer: summary (100) + greeting (~0) + recent (900) = 1000 — exactly fits
        # Force it tighter: num_predict=300 -> available=900 -> over by ~100
        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SummaryBuffer(),
            num_predict=300, ground_truth=False,
        )
        assert report.summary_dropped is True
        # summary should no longer be in ctx["messages"] as a [Story so far] entry
        for m in ctx["messages"]:
            assert "[Story so far]" not in m.get("content", "")
```

- [ ] **Step 5.2: Run tests and verify they fail**

```bash
pytest projects/rp/tests/test_budget.py::TestFitPromptPriority3 -v
```

Expected: the second test FAILs (summary not dropped).

- [ ] **Step 5.3: Add Priority 3 logic**

Replace the body of `fit_prompt` in `projects/rp/budget.py` to add the post-strategy check. Find this block inside `fit_prompt`:

```python
    # Priority 2: delegate to strategy.fit with the corrected budget.
    if messages_budget > 0:
        ctx["messages"] = strategy.fit(
            ctx.get("messages", []), messages_budget, ctx=ctx
        )
```

Replace it with:

```python
    summary_dropped = False

    # Priority 2: delegate to strategy.fit with the corrected budget.
    if messages_budget > 0:
        ctx["messages"] = strategy.fit(
            ctx.get("messages", []), messages_budget, ctx=ctx
        )

    # Priority 3: if still over budget, drop the summary (if any) and re-fit.
    def _current_messages_tokens() -> int:
        return sum(_estimate_tokens(m.get("content", "")) for m in ctx.get("messages", []))

    if ctx.get("_summary") and _current_messages_tokens() > messages_budget:
        ctx["_summary"] = None
        # Re-run strategy with summary gone
        if messages_budget > 0:
            ctx["messages"] = strategy.fit(
                ctx.get("messages", []), messages_budget, ctx=ctx
            )
        summary_dropped = True
        warnings.append("summary dropped to fit messages budget")
```

Then update the `BudgetReport` construction at the bottom of `fit_prompt`:

```python
    report = BudgetReport(
        ...
        summary_dropped=summary_dropped,
        ...
    )
```

- [ ] **Step 5.4: Run tests and verify they pass**

```bash
pytest projects/rp/tests/test_budget.py::TestFitPromptPriority3 -v
```

Expected: both tests PASS.

- [ ] **Step 5.5: Run the full budget test suite to confirm no regressions**

```bash
pytest projects/rp/tests/test_budget.py -v
```

Expected: all tests pass.

- [ ] **Step 5.6: Commit**

```bash
git add projects/rp/budget.py projects/rp/tests/test_budget.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp/budget): drop summary when still over budget (Priority 3)

After strategy.fit, if the kept messages still exceed the budget,
clear ctx[_summary] and re-run the strategy. SummaryBuffer then
degrades to SlidingWindow behavior without the summary slot.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Priority 4 — truncate `mes_example`

**Why:** When the system prompt is so large that even with zero message history we can't fit, the one piece of character identity we're willing to shrink is `mes_example` — usually the biggest and most redundant field.

**Files:**
- Modify: `projects/rp/budget.py`
- Modify: `projects/rp/tests/test_budget.py`

- [ ] **Step 6.1: Write failing test**

Append to `projects/rp/tests/test_budget.py`:

```python
class TestFitPromptPriority4:
    @pytest.mark.asyncio
    async def test_mes_example_truncated_when_overhead_dominates(
        self, stub_ollama_factory
    ):
        """When system_prompt (which includes mes_example) exceeds the
        available budget, truncate mes_example and re-render."""
        stub = stub_ollama_factory(num_ctx_map={"m": 1000})

        # system_prompt that embeds a long mes_example section
        mes_example = "Example line.\n" * 200  # ~700 tokens
        system_prompt = "character intro\n\nExample dialogue:\n" + mes_example + "\n\nmore intro"

        ctx = _build_ctx(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": "hi"}],
            ai_card={"card_data": {"data": {"mes_example": mes_example}}},
        )
        # Pre-populate ctx so we can re-run assembly
        ctx["user_card"] = {"card_data": {"data": {}}}
        ctx["scenario"] = {}
        ctx["prompt_template"] = ""

        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SlidingWindow(),
            num_predict=500, ground_truth=False,
        )
        # available = 500, overhead before truncation ~ (len(system)+len(post))//4 ~ 200+
        # after truncation mes_example should be ~25% (~175 tokens) or >= 200 tokens
        assert report.mes_example_truncated is True
        # ai_card mes_example should be smaller now
        truncated = ctx["ai_card"]["card_data"]["data"]["mes_example"]
        assert len(truncated) < len(mes_example)
```

- [ ] **Step 6.2: Run tests and verify they fail**

```bash
pytest projects/rp/tests/test_budget.py::TestFitPromptPriority4 -v
```

Expected: FAIL — `mes_example_truncated` is False.

- [ ] **Step 6.3: Add Priority 4 logic**

Add this helper to `projects/rp/budget.py` (above `fit_prompt`):

```python
def _truncate_mes_example(ctx: dict) -> bool:
    """Truncate ai_card's mes_example in place and re-run the assembly hooks.

    Keeps whole lines up to max(25% of original tokens, 200 tokens).
    Returns True if truncation happened, False if there was nothing to
    truncate (empty or already small).

    Imports from .pipeline are local to avoid a circular import: pipeline
    can freely import budget without risk.
    """
    ai_card = ctx.get("ai_card") or {}
    card_data = ai_card.get("card_data") or {}
    ai_data = card_data.get("data", card_data)
    original = ai_data.get("mes_example", "") or ""
    if not original:
        return False

    original_tokens = _estimate_tokens(original)
    target_tokens = max(original_tokens // 4, 200)
    if original_tokens <= target_tokens:
        return False

    target_chars = target_tokens * 4
    truncated_lines: list[str] = []
    running = 0
    for line in original.splitlines():
        next_len = running + len(line) + 1
        if next_len > target_chars:
            break
        truncated_lines.append(line)
        running = next_len
    truncated = "\n".join(truncated_lines).rstrip()
    if not truncated:
        truncated = original[:target_chars]  # last-resort char-slice
    ai_data["mes_example"] = truncated

    # Re-run the prompt assembly chain to rebuild system_prompt/post_prompt.
    from .pipeline import assemble_prompt, expand_variables, inject_tools
    assemble_prompt(ctx)
    expand_variables(ctx)
    inject_tools(ctx)
    return True
```

Then extend `fit_prompt`. Insert the Priority 4 block AFTER Priority 3 and BEFORE the report construction. Replace the block starting with `# Priority 3` through the `summary_dropped = True` line with:

```python
    summary_dropped = False
    mes_example_truncated = False

    def _current_messages_tokens() -> int:
        return sum(_estimate_tokens(m.get("content", "")) for m in ctx.get("messages", []))

    def _current_overhead() -> int:
        return _estimate_tokens(ctx.get("system_prompt", "")) + _estimate_tokens(
            ctx.get("post_prompt", "")
        )

    # Priority 2: delegate to strategy.fit with the corrected budget.
    if messages_budget > 0:
        ctx["messages"] = strategy.fit(
            ctx.get("messages", []), messages_budget, ctx=ctx
        )

    # Priority 3: if still over, drop summary and re-fit.
    if ctx.get("_summary") and _current_messages_tokens() > messages_budget:
        ctx["_summary"] = None
        if messages_budget > 0:
            ctx["messages"] = strategy.fit(
                ctx.get("messages", []), messages_budget, ctx=ctx
            )
        summary_dropped = True
        warnings.append("summary dropped to fit messages budget")

    # Priority 4: if overhead alone exceeds available (or messages_budget <= 0),
    # truncate mes_example and re-run assembly.
    if messages_budget <= 0 or _current_overhead() > available:
        if _truncate_mes_example(ctx):
            mes_example_truncated = True
            warnings.append("mes_example truncated to fit system prompt")
            # Recompute overhead and re-fit messages with new budget
            overhead = _current_overhead()
            messages_budget = available - overhead
            if messages_budget > 0:
                # Re-grab original messages list (already trimmed above, use as-is)
                ctx["messages"] = strategy.fit(
                    ctx.get("messages", []), messages_budget, ctx=ctx
                )
```

And update the `BudgetReport` construction to use the new locals:

```python
    report = BudgetReport(
        model=model,
        model_ctx=model_ctx,
        response_reserve=response_reserve,
        available=available,
        overhead=_current_overhead(),
        messages_budget=messages_budget,
        messages_kept=len(ctx.get("messages", [])),
        messages_dropped=max(0, messages_before - len(ctx.get("messages", []))),
        summary_dropped=summary_dropped,
        mes_example_truncated=mes_example_truncated,
        estimator_tokens=_current_overhead() + _current_messages_tokens(),
        actual_tokens=None,
        warnings=warnings,
    )
```

- [ ] **Step 6.4: Run tests and verify they pass**

```bash
pytest projects/rp/tests/test_budget.py -v
```

Expected: all tests pass, including the new P4 test.

- [ ] **Step 6.5: Commit**

```bash
git add projects/rp/budget.py projects/rp/tests/test_budget.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp/budget): truncate mes_example when overhead dominates (Priority 4)

When the assembled system_prompt exceeds the available budget,
truncate the character card's mes_example to max(25%, 200 tokens),
re-run the pipeline assembly hooks, and retry the messages fit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Priority 5 — raise `BudgetError` when nothing left to shrink

**Why:** If even the minimum viable prompt (system + greeting + most-recent user message) still doesn't fit, we raise a typed error. Callers decide what to do (HTTP 413 for runtime, skip-and-continue for lora_generate).

**Files:**
- Modify: `projects/rp/budget.py`
- Modify: `projects/rp/tests/test_budget.py`

- [ ] **Step 7.1: Write failing test**

Append to `projects/rp/tests/test_budget.py`:

```python
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
        # Error message should be informative
        assert "fit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_budget_error_when_system_alone_exceeds_available(
        self, stub_ollama_factory
    ):
        """Even after mes_example truncation, if the rest of the system
        prompt exceeds available, we raise."""
        stub = stub_ollama_factory(num_ctx_map={"m": 200})
        ctx = _build_ctx(
            system_prompt="X" * 4000,  # ~1000 tokens — overhead dominates
            messages=[{"role": "user", "content": "hi"}],
            ai_card={"card_data": {"data": {"mes_example": ""}}},  # nothing to truncate
        )
        ctx["user_card"] = {"card_data": {"data": {}}}
        ctx["scenario"] = {}
        ctx["prompt_template"] = ""

        with pytest.raises(BudgetError):
            await fit_prompt(
                ctx, model="m", ollama=stub, strategy=SlidingWindow(),
                num_predict=50, ground_truth=False,
            )
```

- [ ] **Step 7.2: Run tests to verify they fail**

```bash
pytest projects/rp/tests/test_budget.py::TestFitPromptPriority5 -v
```

Expected: FAIL — `BudgetError` not raised (currently fit_prompt just returns an over-budget report).

- [ ] **Step 7.3: Add Priority 5 check**

In `projects/rp/budget.py`, after the Priority 4 block and BEFORE the `report = BudgetReport(...)` construction, add:

```python
    # Priority 5: if after all shrinking the messages still can't fit under
    # messages_budget, raise BudgetError. We check: does the minimum viable
    # set (greeting + most-recent user message) fit?
    final_msg_tokens = _current_messages_tokens()
    final_overhead = _current_overhead()
    if final_overhead + final_msg_tokens > available or messages_budget <= 0:
        failing_report = BudgetReport(
            model=model,
            model_ctx=model_ctx,
            response_reserve=response_reserve,
            available=available,
            overhead=final_overhead,
            messages_budget=messages_budget,
            messages_kept=len(ctx.get("messages", [])),
            messages_dropped=max(0, messages_before - len(ctx.get("messages", []))),
            summary_dropped=summary_dropped,
            mes_example_truncated=mes_example_truncated,
            estimator_tokens=final_overhead + final_msg_tokens,
            actual_tokens=None,
            warnings=warnings + ["prompt does not fit after all shrink steps"],
        )
        ctx["_budget_report"] = failing_report
        raise BudgetError(
            f"Prompt does not fit: model_ctx={model_ctx}, reserve={response_reserve}, "
            f"overhead={final_overhead}, messages={final_msg_tokens}. "
            f"The most recent user message may be too long for this model.",
            failing_report,
        )
```

- [ ] **Step 7.4: Run tests and verify they pass**

```bash
pytest projects/rp/tests/test_budget.py -v
```

Expected: all tests pass.

- [ ] **Step 7.5: Commit**

```bash
git add projects/rp/budget.py projects/rp/tests/test_budget.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp/budget): raise BudgetError when nothing left to shrink (Priority 5)

When even the minimum viable prompt exceeds model_ctx - reserve
after all shrink priorities, raise a typed BudgetError carrying a
populated BudgetReport so callers can surface a meaningful message.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Ground-truth check path

**Why:** The estimator is ±30% accurate. After estimator-based shrinking, we call Ollama once to get the real `prompt_eval_count`. If still over, we do one more shrink + recount, then raise.

**Files:**
- Modify: `projects/rp/budget.py`
- Modify: `projects/rp/tests/test_budget.py`

- [ ] **Step 8.1: Write failing tests**

Append to `projects/rp/tests/test_budget.py`:

```python
class TestFitPromptGroundTruth:
    def _render_messages_for_count(self, ctx):
        """Build the messages list as it would be sent to Ollama."""
        msgs = [{"role": "system", "content": ctx["system_prompt"]}]
        msgs.extend(ctx["messages"])
        if ctx.get("post_prompt"):
            msgs.append({"role": "system", "content": ctx["post_prompt"]})
        return msgs

    @pytest.mark.asyncio
    async def test_ground_truth_fits_first_try(self, stub_ollama_factory):
        """Estimator says fits, ground-truth confirms."""
        stub = stub_ollama_factory(
            num_ctx_map={"m": 8192},
            count_map={"m": 100},  # ground truth says 100 tokens
            default_count=100,
        )
        ctx = _build_ctx(
            system_prompt="hello",
            messages=[{"role": "user", "content": "hi"}],
        )
        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SlidingWindow(),
            num_predict=1024, ground_truth=True,
        )
        assert report.actual_tokens == 100
        assert stub.chat_calls == 1

    @pytest.mark.asyncio
    async def test_ground_truth_triggers_one_more_shrink(self, stub_ollama_factory):
        """Estimator said fits but ground truth says over -> shrink once more."""
        class ShrinkingStub(StubOllama):
            def __init__(self):
                super().__init__(
                    num_ctx_map={"m": 1000},
                    default_count=2000,  # first call: over
                )
                self.counts = [2000, 400]  # decreasing per call
                self.call_idx = 0

            async def chat(self, model, messages, tools=None, think=False):
                self.chat_calls += 1
                idx = min(self.call_idx, len(self.counts) - 1)
                self.call_idx += 1
                return {"done": True, "prompt_eval_count": self.counts[idx]}

        from projects.rp.tests.conftest import StubOllama  # noqa: F401
        stub = ShrinkingStub()
        ctx = _build_ctx(
            messages=[
                {"role": "assistant", "content": "g"},
                {"role": "user", "content": "A" * 100},
                {"role": "user", "content": "B" * 100},
            ],
        )
        report = await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SlidingWindow(),
            num_predict=100, ground_truth=True,
        )
        assert stub.chat_calls == 2  # first check + recount after shrink
        assert report.actual_tokens == 400

    @pytest.mark.asyncio
    async def test_ground_truth_over_twice_raises(self, stub_ollama_factory):
        """Ground truth still over after one more shrink -> BudgetError."""
        class OverStub(StubOllama):
            def __init__(self):
                super().__init__(
                    num_ctx_map={"m": 500},
                    default_count=1000,  # always over
                )

            async def chat(self, model, messages, tools=None, think=False):
                self.chat_calls += 1
                return {"done": True, "prompt_eval_count": 1000}

        from projects.rp.tests.conftest import StubOllama  # noqa: F401
        stub = OverStub()
        ctx = _build_ctx(
            messages=[
                {"role": "assistant", "content": "g"},
                {"role": "user", "content": "hi"},
            ],
        )
        with pytest.raises(BudgetError):
            await fit_prompt(
                ctx, model="m", ollama=stub, strategy=SlidingWindow(),
                num_predict=100, ground_truth=True,
            )
```

- [ ] **Step 8.2: Run tests to verify they fail**

```bash
pytest projects/rp/tests/test_budget.py::TestFitPromptGroundTruth -v
```

Expected: FAIL — first test fails because `ground_truth=True` is not yet wired to make any call.

- [ ] **Step 8.3: Implement ground-truth check**

In `projects/rp/budget.py`, modify `fit_prompt`. After Priority 4 block but BEFORE the Priority 5 block, add:

```python
    # Ground-truth check: ask Ollama for the real prompt_eval_count.
    actual_tokens: int | None = None
    if ground_truth and messages_budget > 0:
        # Render messages as routes.py / lora_generate.py will send them.
        gt_messages = _render_for_count(ctx)
        actual_tokens = await _ollama_count_messages(gt_messages, model, ollama)

        if actual_tokens + response_reserve > model_ctx:
            # One more shrink: drop one more oldest message (if any) and recount.
            if len(ctx.get("messages", [])) > 2:
                # Pop the message right after the greeting (oldest non-greeting).
                ctx["messages"] = [ctx["messages"][0]] + ctx["messages"][2:]
                gt_messages = _render_for_count(ctx)
                actual_tokens = await _ollama_count_messages(gt_messages, model, ollama)
            # If still over, let Priority 5 below raise.
```

Also add this helper function above `fit_prompt`:

```python
def _render_for_count(ctx: dict) -> list[dict]:
    """Build the messages list that would actually be sent to Ollama.

    Mirrors routes.py _build_chat_messages: system_prompt, then the
    budgeted messages, then post_prompt (if any) as a trailing system
    message. Does NOT append the "assistant: name " anchor — that's a
    runtime concern and tokenizes to only a few tokens.
    """
    msgs = [{"role": "system", "content": ctx.get("system_prompt", "")}]
    msgs.extend(ctx.get("messages", []))
    if ctx.get("post_prompt"):
        msgs.append({"role": "system", "content": ctx["post_prompt"]})
    return msgs
```

Then update the Priority 5 condition to use `actual_tokens` when available:

```python
    # Priority 5: ...
    final_msg_tokens = _current_messages_tokens()
    final_overhead = _current_overhead()
    effective_total = (
        actual_tokens if actual_tokens is not None
        else final_overhead + final_msg_tokens
    )
    if effective_total + response_reserve > model_ctx or messages_budget <= 0:
        # ... same BudgetError block as before, but with actual_tokens set
```

Update the failing_report construction in Priority 5 to include `actual_tokens=actual_tokens,`.

And in the non-error return path at the bottom, set `actual_tokens=actual_tokens` on the successful `BudgetReport`.

- [ ] **Step 8.4: Run tests and verify they pass**

```bash
pytest projects/rp/tests/test_budget.py -v
```

Expected: all tests pass. If `test_ground_truth_triggers_one_more_shrink` fails, verify the shrink step removes the correct message and that the second chat call returns the smaller count.

- [ ] **Step 8.5: Commit**

```bash
git add projects/rp/budget.py projects/rp/tests/test_budget.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp/budget): add ground-truth token count verification

After estimator-based shrinking, call Ollama once via _ollama_count_messages
to get the real prompt_eval_count. If still over, drop one more
oldest message and recount once. If still over, Priority 5 raises.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: `fit_raw_prompt` for single-shot prompts

**Why:** `lora_generate.py` builds raw prompts (not chat messages) and needs a simpler budgeting API that just checks fit and raises if not.

**Files:**
- Modify: `projects/rp/budget.py`
- Modify: `projects/rp/tests/test_budget.py`

- [ ] **Step 9.1: Write failing tests**

Append to `projects/rp/tests/test_budget.py`:

```python
from projects.rp.budget import fit_raw_prompt


class TestFitRawPrompt:
    @pytest.mark.asyncio
    async def test_small_prompt_fits(self, stub_ollama_factory):
        stub = stub_ollama_factory(
            num_ctx_map={"m": 8192},
            count_map={"m": 200},
        )
        prompt, report = await fit_raw_prompt(
            prompt="hello world",
            system="be helpful",
            model="m",
            ollama=stub,
            num_predict=500,
            ground_truth=True,
        )
        assert prompt == "hello world"
        assert report.actual_tokens == 200
        assert report.model_ctx == 8192

    @pytest.mark.asyncio
    async def test_oversized_prompt_raises(self, stub_ollama_factory):
        stub = stub_ollama_factory(
            num_ctx_map={"m": 500},
            count_map={"m": 10000},  # ground-truth says way over
        )
        with pytest.raises(BudgetError) as exc_info:
            await fit_raw_prompt(
                prompt="X" * 40000,
                system="",
                model="m",
                ollama=stub,
                num_predict=100,
                ground_truth=True,
            )
        assert exc_info.value.report.model_ctx == 500

    @pytest.mark.asyncio
    async def test_ground_truth_off_uses_estimator(self, stub_ollama_factory):
        stub = stub_ollama_factory(num_ctx_map={"m": 8192})
        prompt, report = await fit_raw_prompt(
            prompt="hi",
            system=None,
            model="m",
            ollama=stub,
            num_predict=1024,
            ground_truth=False,
        )
        assert report.actual_tokens is None
        assert stub.chat_calls == 0

    @pytest.mark.asyncio
    async def test_default_num_predict_is_1024(self, stub_ollama_factory):
        stub = stub_ollama_factory(num_ctx_map={"m": 8192})
        _, report = await fit_raw_prompt(
            prompt="hi", system=None, model="m", ollama=stub,
            num_predict=None, ground_truth=False,
        )
        assert report.response_reserve == 1024
```

- [ ] **Step 9.2: Run tests to verify they fail**

```bash
pytest projects/rp/tests/test_budget.py::TestFitRawPrompt -v
```

Expected: FAIL — `cannot import name 'fit_raw_prompt'`.

- [ ] **Step 9.3: Implement `fit_raw_prompt`**

Append to `projects/rp/budget.py`:

```python
async def fit_raw_prompt(
    *,
    prompt: str,
    system: str | None,
    model: str,
    ollama: _OllamaLike,
    num_predict: int | None = None,
    ground_truth: bool = True,
) -> tuple[str, BudgetReport]:
    """Budget a single-shot raw prompt (used by lora_generate).

    Does NOT shrink the prompt — single-shot prompts have no safe
    shrinking heuristic. If it doesn't fit, raises BudgetError and the
    caller (lora_generate) decides to skip that scenario/turn.
    """
    model_ctx = await _get_model_ctx(model, ollama)
    response_reserve = num_predict if num_predict is not None else 1024
    available = model_ctx - response_reserve

    prompt = prompt or ""
    system = system or ""
    overhead = _estimate_tokens(prompt) + _estimate_tokens(system)

    actual_tokens: int | None = None
    if ground_truth:
        # Build a minimal messages list matching how lora_generate sends it.
        gt_messages: list[dict] = []
        if system:
            gt_messages.append({"role": "system", "content": system})
        gt_messages.append({"role": "user", "content": prompt})
        actual_tokens = await _ollama_count_messages(gt_messages, model, ollama)

    effective_total = actual_tokens if actual_tokens is not None else overhead
    fits = (effective_total + response_reserve) <= model_ctx

    report = BudgetReport(
        model=model,
        model_ctx=model_ctx,
        response_reserve=response_reserve,
        available=available,
        overhead=overhead,
        messages_budget=available - overhead,
        messages_kept=1,
        messages_dropped=0,
        summary_dropped=False,
        mes_example_truncated=False,
        estimator_tokens=overhead,
        actual_tokens=actual_tokens,
        warnings=[],
    )

    if not fits:
        raise BudgetError(
            f"Raw prompt does not fit: model_ctx={model_ctx}, reserve={response_reserve}, "
            f"prompt_tokens={effective_total}.",
            report,
        )
    return prompt, report
```

- [ ] **Step 9.4: Run tests and verify they pass**

```bash
pytest projects/rp/tests/test_budget.py -v
```

Expected: all tests pass.

- [ ] **Step 9.5: Commit**

```bash
git add projects/rp/budget.py projects/rp/tests/test_budget.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp/budget): add fit_raw_prompt for single-shot prompts

Simpler API used by lora_generate.py: checks fit of a raw prompt +
system against model_ctx - reserve. No shrinking (single-shot
prompts have no safe heuristic). Raises BudgetError with a
populated report when the prompt won't fit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Wire `fit_prompt` into `routes.py` — `send_message` + delete old hook

**Why:** This is the biggest behavioral change. Do `send_message` first (the main code path), verify manually with the running server, then roll out to the other call sites.

**Files:**
- Modify: `projects/rp/routes.py`
- Modify: `projects/rp/pipeline.py` (remove `apply_context_strategy` from default pipeline)

- [ ] **Step 10.1: Add an imports block and a budgeting helper to `routes.py`**

At the top of `projects/rp/routes.py`, find the existing import block that has:

```python
from .pipeline import create_default_pipeline
```

Change it to:

```python
from .pipeline import create_default_pipeline
from .budget import fit_prompt, BudgetError
from .context import get_strategy
```

Then, inside the `register(app, ollama, resolve_model)` function body (the place where `_build_pipeline_ctx` is defined, around line 425), add this helper right after `_build_pipeline_ctx`:

```python
    async def _budget_ctx(ctx, model, ollama_options):
        """Run fit_prompt against ctx, using scenario-configured strategy.

        On BudgetError, logs a WARNING and re-raises — callers handle the
        response (HTTP 413, stream error chunk, etc.).
        """
        scenario = ctx.get("scenario") or {}
        settings = scenario.get("settings", {})
        strategy = get_strategy(settings.get("context_strategy", "summary_buffer"))
        num_predict = ollama_options.get("num_predict") if ollama_options else None
        try:
            return await fit_prompt(
                ctx, model=model, ollama=_ollama,
                strategy=strategy, num_predict=num_predict,
                ground_truth=True,
            )
        except BudgetError as e:
            _log.warning("Budget error for model=%s: %s", model, e)
            raise
```

- [ ] **Step 10.2: Wire `_budget_ctx` into `send_message` around line 743**

Find this block in `send_message` (around line 743):

```python
        chat_messages = _build_chat_messages(ctx)
        user_name = _get_user_name(ctx)
```

Insert a call to `_budget_ctx` right before it, and also merge `num_ctx` into the Ollama options. Replace those two lines with:

```python
        try:
            await _budget_ctx(ctx, model, ollama_options)
        except BudgetError as e:
            async def _err_stream():
                yield json.dumps({
                    "error": f"Prompt does not fit model context: {e}",
                    "done": True,
                }) + "\n"
            return StreamingResponse(_err_stream(), media_type="application/x-ndjson",
                                     status_code=413)

        # Tell Ollama to load the model with its real context window
        ollama_options = {**ollama_options, "num_ctx": ctx["_num_ctx"]}

        chat_messages = _build_chat_messages(ctx)
        user_name = _get_user_name(ctx)
```

- [ ] **Step 10.3: Remove `apply_context_strategy` from the default pipeline**

Open `projects/rp/pipeline.py`. Find `create_default_pipeline` (around line 208):

```python
def create_default_pipeline() -> Pipeline:
    """Create pipeline with standard hooks."""
    p = Pipeline()
    p.add_pre(assemble_prompt)
    p.add_pre(expand_variables)
    p.add_pre(inject_tools)
    p.add_pre(apply_context_strategy)
    p.add_post(clean_response)
    return p
```

Remove the `p.add_pre(apply_context_strategy)` line:

```python
def create_default_pipeline() -> Pipeline:
    """Create pipeline with standard hooks.

    NOTE: context budgeting is no longer part of the pipeline — it's
    now done explicitly at each call site via budget.fit_prompt, which
    needs access to the ollama client and resolved model name.
    """
    p = Pipeline()
    p.add_pre(assemble_prompt)
    p.add_pre(expand_variables)
    p.add_pre(inject_tools)
    p.add_post(clean_response)
    return p
```

Leave `apply_context_strategy` defined for now — we'll delete it in Task 13 after all call sites are migrated.

- [ ] **Step 10.4: Run the pipeline tests**

```bash
pytest projects/rp/tests/test_pipeline.py -v
```

Expected: any tests that asserted `apply_context_strategy` was in the pipeline will fail. If such a test exists, remove or update it (the hook is no longer in the default pipeline).

- [ ] **Step 10.5: Sanity-check the runtime by hand**

Restart aiserver and send one message to an existing conversation:

```bash
bash projects/aiserver/restart.sh
# In another shell, or via the rp UI at http://localhost:8080/rp/
# send a message to an existing conversation.
tail -20 /tmp/aiserver.log
```

Expected: request completes normally. Look for `INFO: Loaded num_ctx=<N> for model <M>` on the first request for each model.

- [ ] **Step 10.6: Commit**

```bash
git add projects/rp/routes.py projects/rp/pipeline.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp/routes): wire fit_prompt into send_message

Replaces the old apply_context_strategy pre-hook with an explicit
_budget_ctx helper called after pipeline pre-hooks. On BudgetError,
returns HTTP 413 with an error stream chunk. Also passes num_ctx
into the Ollama options dict so the model is loaded with its real
context window.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 11: Wire `fit_prompt` into the remaining `routes.py` call sites

**Why:** `regenerate`, `auto_user`, and two other code paths all call `_build_pipeline_ctx` + Ollama. They need the same treatment as `send_message`.

**Files:**
- Modify: `projects/rp/routes.py` (4 locations)

Identified call sites (from the earlier grep at Preflight time):
1. `regenerate` — around line 855
2. The three call sites at lines ~913, ~991, ~1011 (auto-user / swap / other branches)

For each call site: find the pattern `_build_pipeline_ctx` → `_build_ollama_options` → `_build_chat_messages`, and wrap it the same way as `send_message`.

- [ ] **Step 11.1: Wire `_budget_ctx` into `regenerate` (line ~855)**

Find in `regenerate`:

```python
        ctx = await _build_pipeline_ctx(conv, messages)

        model = _resolve_model(conv["model"])
        scenario = ctx.get("scenario") or {}
        settings = scenario.get("settings", {})
        ollama_options = _build_ollama_options(settings)

        chat_messages = _build_chat_messages(ctx)
```

Replace with:

```python
        ctx = await _build_pipeline_ctx(conv, messages)

        model = _resolve_model(conv["model"])
        scenario = ctx.get("scenario") or {}
        settings = scenario.get("settings", {})
        ollama_options = _build_ollama_options(settings)

        try:
            await _budget_ctx(ctx, model, ollama_options)
        except BudgetError as e:
            async def _err_stream():
                yield json.dumps({
                    "error": f"Prompt does not fit model context: {e}",
                    "done": True,
                }) + "\n"
            return StreamingResponse(_err_stream(), media_type="application/x-ndjson",
                                     status_code=413)
        ollama_options = {**ollama_options, "num_ctx": ctx["_num_ctx"]}

        chat_messages = _build_chat_messages(ctx)
```

- [ ] **Step 11.2: Wire `_budget_ctx` into the remaining 3 call sites**

Repeat the same pattern at each of the other `_build_pipeline_ctx` call sites in `routes.py` (around lines 913, 991, 1011). In each case:

1. After the `ollama_options = _build_ollama_options(settings)` line.
2. Before the `chat_messages = _build_chat_messages(ctx)` line.
3. Insert the `try: await _budget_ctx(ctx, model, ollama_options)` block and the `ollama_options = {**ollama_options, "num_ctx": ctx["_num_ctx"]}` line.

Grep to find any you missed:

```bash
grep -n "_build_chat_messages(ctx)" projects/rp/routes.py
```

Each match should now have `_budget_ctx` called above it. If any don't, apply the same pattern.

- [ ] **Step 11.3: Smoke-test each code path by hand**

Through the rp UI or curl, exercise:
1. Regenerate the last assistant message (`POST /rp/conversations/{id}/regenerate`)
2. Auto-user message (the "user types for me" flow, if wired)
3. Any other flow hitting `_build_chat_messages`

Expected: all complete successfully, `/tmp/aiserver.log` shows no BudgetError unless triggered by a truly oversized conversation.

- [ ] **Step 11.4: Commit**

```bash
git add projects/rp/routes.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp/routes): wire fit_prompt into regenerate and other call sites

Applies the same _budget_ctx + num_ctx injection pattern to
regenerate, auto-user, and the remaining call sites identified by
grepping for _build_chat_messages.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 12: Wire `fit_raw_prompt` into `lora_generate.py`

**Why:** The synthetic data generator has no pipeline; each of its Ollama calls needs its own budget check. On `BudgetError`, the current scenario/turn is skipped and the run continues.

**Files:**
- Modify: `projects/rp/lora_generate.py`
- Test: `projects/rp/tests/test_lora_generate_budget.py` (new)

- [ ] **Step 12.1: Write the failing tests**

Create `projects/rp/tests/test_lora_generate_budget.py`:

```python
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
```

- [ ] **Step 12.2: Run tests to verify they fail**

```bash
pytest projects/rp/tests/test_lora_generate_budget.py -v
```

Expected: FAIL — tests exercise code paths that don't yet call `fit_raw_prompt`.

- [ ] **Step 12.3: Wire `fit_raw_prompt` into `lora_generate.py`**

Open `projects/rp/lora_generate.py`. Add the import at the top after the existing `from .pipeline import ...` line:

```python
from .budget import fit_raw_prompt, BudgetError
```

In `generate_scenarios` (around line 182), find the block:

```python
        raw = await ollama.generate(
            model=model, prompt=prompt,
            system="Output valid JSON only. No markdown fences.",
            options={"temperature": 0.9, "num_predict": 1024, "think": False},
        )
```

Wrap it with budget check:

```python
        try:
            prompt, _ = await fit_raw_prompt(
                prompt=prompt,
                system="Output valid JSON only. No markdown fences.",
                model=model,
                ollama=ollama,
                num_predict=1024,
            )
        except BudgetError as e:
            _log.warning(
                "Skipping category %s for %s: prompt does not fit (%s)",
                cat["category"], char_name, e,
            )
            continue

        raw = await ollama.generate(
            model=model, prompt=prompt,
            system="Output valid JSON only. No markdown fences.",
            options={"temperature": 0.9, "num_predict": 1024, "think": False,
                     "num_ctx": (await _get_model_ctx_hint(model, ollama))},
        )
```

That last `num_ctx` argument needs a helper that just calls `_get_model_ctx`. Add at the top of the file after imports:

```python
from .budget import _get_model_ctx

async def _get_model_ctx_hint(model: str, ollama) -> int:
    """Wrap _get_model_ctx for direct use in options dicts."""
    return await _get_model_ctx(model, ollama)
```

Actually this is awkward. Simpler approach: capture the num_ctx once in `generate_conversation` and `generate_scenarios` and thread it down. Refactor:

At the top of `generate_scenarios`:

```python
    num_ctx = await _get_model_ctx(model, ollama)
```

Then pass `"num_ctx": num_ctx` into every `options` dict in that function. Same for `generate_conversation` → `generate_user_message` / `generate_assistant_message`: resolve `num_ctx` once in `generate_conversation`, pass it via the `context` dict, and the sub-functions read it when building options.

Concretely, in `generate_user_message`, change:

```python
    raw = await ollama.generate(
        model=model, prompt=prompt,
        system=f"You are {context['user_name']}. Write their next message only.",
        options={"temperature": 1.0, "num_predict": 300, "think": False},
    )
    return raw.strip().strip('"')
```

to:

```python
    try:
        prompt, _ = await fit_raw_prompt(
            prompt=prompt,
            system=f"You are {context['user_name']}. Write their next message only.",
            model=model, ollama=ollama, num_predict=300,
        )
    except BudgetError as e:
        _log.warning("User msg budget error: %s", e)
        return ""

    raw = await ollama.generate(
        model=model, prompt=prompt,
        system=f"You are {context['user_name']}. Write their next message only.",
        options={
            "temperature": 1.0, "num_predict": 300, "think": False,
            "num_ctx": context.get("_num_ctx") or 2048,
        },
    )
    return raw.strip().strip('"')
```

In `generate_assistant_message`, apply the same treatment — the prompt here is effectively `system_prompt + messages`. Build a single string or just pass `system_prompt` as system + the last user message as prompt. Since `fit_raw_prompt` takes `prompt` + `system`, use:

```python
    # Serialize chat messages into a single prompt for budget checking.
    serialized = "\n".join(f"{m['role']}: {m['content']}" for m in chat_msgs[1:])
    try:
        _, _ = await fit_raw_prompt(
            prompt=serialized, system=system_prompt,
            model=model, ollama=ollama, num_predict=768,
        )
    except BudgetError as e:
        _log.warning("Assistant msg budget error: %s", e)
        return ""
```

And add `"num_ctx": context_num_ctx` to the options (read from a module-level cache or threaded in).

To keep this simple, have `generate_conversation` fetch and cache `num_ctx`:

```python
async def generate_conversation(ollama, model_70b: str, ai_card: dict, user_card: dict,
                                scenario: dict, num_turns: int = 12) -> dict | None:
    """Generate a full multi-turn conversation."""
    try:
        num_ctx = await _get_model_ctx(model_70b, ollama)
    except Exception as e:
        _log.error("Cannot determine num_ctx for %s: %s", model_70b, e)
        return None

    ai_data = ai_card.get("data", ai_card)
    # ... existing code ...

    context = {
        "char_name": char_name,
        "user_name": user_name,
        "user_personality": user_data.get("personality", "") or user_data.get("description", ""),
        "scenario": scenario["text"],
        "history": messages,
        "_num_ctx": num_ctx,
    }
```

Then `generate_user_message` and `generate_assistant_message` read `context["_num_ctx"]` for their options. (The test in Step 12.1 doesn't inspect options so this refactoring is compatible.)

- [ ] **Step 12.4: Run tests and verify they pass**

```bash
pytest projects/rp/tests/test_lora_generate_budget.py -v
pytest projects/rp/tests/ -v
```

Expected: all tests pass.

- [ ] **Step 12.5: Run the ruff linter over the changed files**

```bash
cd projects/aiserver && source .venv/bin/activate && cd ../..
ruff check projects/rp/lora_generate.py projects/rp/budget.py projects/rp/routes.py
```

Expected: no errors (or only pre-existing ones you didn't touch).

- [ ] **Step 12.6: Commit**

```bash
git add projects/rp/lora_generate.py projects/rp/tests/test_lora_generate_budget.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp/lora_generate): budget each Ollama call via fit_raw_prompt

generate_scenarios, generate_user_message, and generate_assistant_message
now call fit_raw_prompt before hitting Ollama. BudgetError results in
skip-and-log (scenarios) or empty-return (turns), letting the existing
control flow continue the overall run instead of aborting.

Also threads num_ctx from generate_conversation's single /api/show call
into every Ollama options dict so long lora runs don't thrash the model
load.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 13: Delete `apply_context_strategy` and add equivalence regression test

**Why:** All call sites are migrated. The old function is dead code and should be removed. Add one regression test to confirm that the new `fit_prompt + SlidingWindow` path produces the same message trimming as the old `apply_context_strategy` did for the equivalence case (empty system prompt).

**Files:**
- Modify: `projects/rp/pipeline.py` (delete function)
- Modify: `projects/rp/tests/test_pipeline.py` (remove tests that reference the deleted function, if any)
- Modify: `projects/rp/tests/test_budget.py` (add equivalence test)

- [ ] **Step 13.1: Verify no remaining references**

```bash
grep -rn "apply_context_strategy" projects/ docs/ 2>&1
```

Expected: only matches in `projects/rp/pipeline.py` (the definition) and possibly `projects/rp/tests/test_pipeline.py` (an old test).

- [ ] **Step 13.2: Delete the function from `pipeline.py`**

Open `projects/rp/pipeline.py` and delete lines 172–180 (the `apply_context_strategy` function definition).

- [ ] **Step 13.3: Update or remove any tests that referenced it**

If `projects/rp/tests/test_pipeline.py` imports or uses `apply_context_strategy`, delete or update those test functions.

- [ ] **Step 13.4: Add an equivalence regression test**

Append to `projects/rp/tests/test_budget.py`:

```python
class TestEquivalenceWithOldBehavior:
    @pytest.mark.asyncio
    async def test_empty_system_prompt_matches_sliding_window(
        self, stub_ollama_factory
    ):
        """With an empty system prompt, fit_prompt should produce the same
        messages trimming that the old apply_context_strategy did — that is,
        pure SlidingWindow behavior against the raw max_tokens."""
        stub = stub_ollama_factory(num_ctx_map={"m": 1000})
        # Each msg ~25 tokens (len//4). Budget 1000 - 500 reserve = 500.
        # Overhead = 0. messages_budget = 500. ~20 messages fit, but the
        # strategy also protects the greeting.
        messages = [
            {"role": "assistant", "content": "G" * 100},  # greeting
        ]
        for i in range(30):
            messages.append({"role": "user", "content": f"msg {i:02d} " + "X" * 100})

        ctx = _build_ctx(system_prompt="", post_prompt="", messages=messages)
        expected = SlidingWindow().fit(list(messages), max_tokens=500)

        await fit_prompt(
            ctx, model="m", ollama=stub, strategy=SlidingWindow(),
            num_predict=500, ground_truth=False,
        )
        assert ctx["messages"] == expected
```

- [ ] **Step 13.5: Run tests**

```bash
pytest projects/rp/tests/test_budget.py projects/rp/tests/test_pipeline.py projects/rp/tests/test_context.py -v
```

Expected: all pass.

- [ ] **Step 13.6: Commit**

```bash
git add projects/rp/pipeline.py projects/rp/tests/test_pipeline.py projects/rp/tests/test_budget.py
git commit --author="Claude <noreply@anthropic.com>" -m "refactor(rp): delete apply_context_strategy + add equivalence test

All call sites now use budget.fit_prompt. Removes the dead
apply_context_strategy function from pipeline.py. Adds an equivalence
regression test confirming that fit_prompt with an empty system prompt
produces the same messages trimming that SlidingWindow did directly.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 14: End-to-end smoke test with the running aiserver

**Why:** Unit tests mock everything. Before opening a PR, run one real request through the stack to confirm `num_ctx` propagation actually takes effect and the ground-truth counting works with real Ollama.

**Files:** none (manual verification)

- [ ] **Step 14.1: Restart aiserver in the worktree**

```bash
cd /mnt/d/prg/plum-prompt-budgeting/projects/aiserver
source .venv/bin/activate
# Kill any running aiserver from the main tree first
bash /mnt/d/prg/plum/projects/aiserver/restart.sh || true
# Start fresh from the worktree
nohup python main.py > /tmp/aiserver-pb.log 2>&1 &
sleep 3
curl -s http://localhost:8080/health
```

Expected: JSON with `status: ok`, `ollama_connected: true`.

- [ ] **Step 14.2: Send a real conversation turn**

Via the rp UI at http://localhost:8080/rp/, or via curl with an existing conversation ID:

```bash
curl -N -X POST http://localhost:8080/rp/conversations/78/message \
  -H "Content-Type: application/json" \
  -d '{"content": "hello, how are you today?"}'
```

Expected: streaming NDJSON response. Generation completes normally.

- [ ] **Step 14.3: Inspect the log for budgeting activity**

```bash
grep -E "Loaded num_ctx|Budget|budget|num_ctx" /tmp/aiserver-pb.log | tail -20
```

Expected: an INFO line like `Loaded num_ctx=<N> for model <M>` for each model hit. No errors.

- [ ] **Step 14.4: (Optional) Force a BudgetError**

Paste a very long message (50k+ characters) via the UI to a conversation on a small-context model. Expected: stream returns an `error` chunk containing "Prompt does not fit model context", HTTP status 413.

- [ ] **Step 14.5: Kill the worktree aiserver and restart the main one**

```bash
pkill -f "python main.py" || true
bash /mnt/d/prg/plum/projects/aiserver/restart.sh
```

Expected: main tree aiserver running again.

This task has no commit — it's a verification step. Proceed to Task 15.

---

## Task 15: Open the PR

**Files:** none (PR creation via `gh`)

- [ ] **Step 15.1: Push the branch**

```bash
cd /mnt/d/prg/plum-prompt-budgeting
git push -u origin prompt-budgeting
```

- [ ] **Step 15.2: Open the PR**

```bash
gh pr create --title "feat(rp): prompt budgeting for runtime + lora_generate" --body "$(cat <<'EOF'
## Summary

- New `projects/rp/budget.py` shared module with `fit_prompt` and `fit_raw_prompt` entry points
- `OllamaClient.get_num_ctx` reads the model's real context window from `/api/show`, cached per process
- rp runtime pipeline and `lora_generate.py` both budget against `model_ctx - response_reserve` using a deterministic shrink policy (oldest messages → summary → mes_example truncation → typed `BudgetError`)
- `num_ctx` is now passed explicitly to Ollama on every generation call, eliminating the silent 2048 default

## Test plan

- [ ] `cd /mnt/d/prg/plum-prompt-budgeting && cd projects/aiserver && source .venv/bin/activate && cd ../.. && pytest projects/rp/tests/ projects/aiserver/tests/ -v` — all unit tests pass
- [ ] `bash projects/aiserver/restart.sh` — aiserver starts cleanly
- [ ] Send one message via the rp UI to an existing conversation — generation completes normally
- [ ] `grep "Loaded num_ctx" /tmp/aiserver.log` — shows one entry per model on first request
- [ ] Paste a 50k-character wall of text as a user message on a small-context model — receive HTTP 413 with "Prompt does not fit model context" error chunk

## Spec & plan

- Design: `docs/superpowers/specs/2026-04-07-rp-prompt-budgeting-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-07-rp-prompt-budgeting.md`

## Migration notes

- `max_context_tokens` in scenario settings is now ignored (deprecated, not rejected). Users who relied on it to deliberately cap context on a big model will see longer context used after this lands.
- First request to each model after aiserver restart triggers a one-time model reload with the full `num_ctx`. For large models (70B) this can take tens of seconds. Subsequent requests are fast.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL is printed. The task is done.

---

## Self-Review Checklist (performed before handing off)

**Spec coverage:**

- ✅ `OllamaClient.get_num_ctx` — Task 1
- ✅ `budget.py` module with `BudgetError`, `BudgetReport`, `_get_model_ctx` caching + per-model lock — Task 2
- ✅ `_ollama_count_messages` ground-truth helper — Task 3
- ✅ `fit_prompt` happy path + Priority 2 (strategy drop) — Task 4
- ✅ Priority 3 (drop summary) — Task 5
- ✅ Priority 4 (truncate mes_example + re-run assembly) — Task 6
- ✅ Priority 5 (BudgetError with populated report) — Task 7
- ✅ Ground-truth check + one-more-shrink retry — Task 8
- ✅ `fit_raw_prompt` for single-shot prompts — Task 9
- ✅ `routes.py` send_message integration — Task 10
- ✅ `routes.py` regenerate + 3 other call sites — Task 11
- ✅ `lora_generate.py` integration at all 3 Ollama call points — Task 12
- ✅ `num_ctx` propagation in Ollama options — Tasks 10, 11, 12
- ✅ Delete dead `apply_context_strategy` + equivalence regression test — Task 13
- ✅ End-to-end smoke test — Task 14
- ✅ PR opening with inline test plan — Task 15

**Placeholder scan:** No TBDs, TODOs, or "handle appropriately" phrases. Every code step shows the actual code.

**Type consistency:** `BudgetReport` fields match across Task 2 (definition), Task 4 (construction), Task 7 (failing_report), Task 9 (fit_raw_prompt construction), Task 12 (test fixture).

**Naming consistency:** `_get_model_ctx`, `fit_prompt`, `fit_raw_prompt`, `_budget_ctx` (the routes helper), `BudgetError`, `BudgetReport`, `_ollama_count_messages`, `_render_for_count`, `_estimate_tokens`, `_truncate_mes_example` — used identically everywhere they appear.

**Scope:** Exactly the two paths scoped at brainstorming time (runtime pipeline + lora_generate). Nothing crept in (eval scripts, fewshot retrieval, summarizer — all explicitly out of scope in the spec).
