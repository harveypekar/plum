# Prompt Budgeting for rp + lora_generate

**Status:** Design approved
**Date:** 2026-04-07
**Branch:** `prompt-budgeting`

## Problem

The rp runtime pipeline and `lora_generate.py` both assemble prompts that can silently overflow the model's context window. The current budgeting logic in `projects/rp/pipeline.py:apply_context_strategy` has three gaps:

1. It budgets only `messages`, not the system prompt, tool descriptions, `post_prompt`, or `scene_state`. A fat `mes_example` plus injected tool descriptions can add 2–3k tokens that nobody counts.
2. The budget value is a hardcoded-per-scenario `max_context_tokens` (default 6144) that bears no relation to the model's actual context window.
3. No headroom is reserved for the response. Ollama's generation can get cut off mid-token.

`lora_generate.py` bypasses the pipeline entirely and has no budgeting at all.

The runtime fallout is degraded generation quality when the effective window shrinks to whatever Ollama silently truncates to. The lora_generate fallout is worse: synthetic runs can fail mid-job on oversized scenarios.

## Goals

- Every prompt sent to Ollama by rp runtime chat and `lora_generate.py` fits within `model_ctx - response_reserve`, verified by ground-truth token count.
- The budget is derived from the model's real context length (via `/api/show`), not a hardcoded scenario setting.
- Ollama is told to load the model with its full `num_ctx`, so the runtime window matches what we budgeted for.
- When a prompt is over budget, a deterministic shrink policy drops the least-valuable content first and protects character identity + most-recent user turn.
- When even the minimum prompt doesn't fit, callers get a typed error with a diagnostic report rather than a silent truncation.

## Non-goals

- Replacing the `len(text) // 4` estimator with a real client-side tokenizer (e.g., `tiktoken`, HF `AutoTokenizer`). The estimator + one ground-truth Ollama call per request is sufficient.
- Per-request budget overrides from scenario settings. `max_context_tokens` is deprecated; the model's real context window is the single source of truth.
- TTL caching of `/api/show` results. Cache lives for the process lifetime; aiserver restart picks up model reloads.
- Budgeting for eval scripts, fewshot retrieval, or the summarizer. (Future work.)

## Architecture

### New module: `projects/rp/budget.py`

Single shared module used by both the rp runtime pipeline and `lora_generate.py`.

#### Public API

```python
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
    available: int              # model_ctx - response_reserve
    overhead: int               # system_prompt + post_prompt (estimator)
    messages_budget: int        # available - overhead
    messages_kept: int
    messages_dropped: int
    summary_dropped: bool
    mes_example_truncated: bool
    estimator_tokens: int
    actual_tokens: int | None   # from ground-truth Ollama call, if run
    warnings: list[str]

async def fit_prompt(
    ctx: dict,
    *,
    model: str,
    ollama: "OllamaClient",
    strategy: "ContextStrategy",
    num_predict: int | None = None,
    ground_truth: bool = True,
) -> BudgetReport:
    """Mutate ctx so the assembled prompt fits model_ctx - response_reserve.

    Runs the active context strategy against a corrected messages budget
    (model_ctx - response_reserve - system/post overhead), performs an
    optional ground-truth token count via Ollama, and applies the shrink
    policy if still over.

    Sets ctx["_num_ctx"] = model_ctx so the caller can pass num_ctx in
    Ollama options.

    Raises BudgetError (with a populated BudgetReport) if the minimum
    viable prompt (system + first message + most-recent user message)
    does not fit.
    """

async def fit_raw_prompt(
    *,
    prompt: str,
    system: str | None,
    model: str,
    ollama: "OllamaClient",
    num_predict: int | None = None,
    ground_truth: bool = True,
) -> tuple[str, BudgetReport]:
    """Budget a single-shot raw prompt (used by lora_generate).

    Returns the (possibly unchanged) prompt and a BudgetReport. Raises
    BudgetError if the prompt + system + response_reserve exceed model_ctx.
    lora_generate catches this and skips the scenario.
    """
```

#### Module state

```python
_ctx_cache: dict[str, int] = {}
_ctx_locks: dict[str, asyncio.Lock] = {}

async def _get_model_ctx(model: str, ollama: "OllamaClient") -> int:
    """Return cached num_ctx for model, fetching once on first use."""
```

One `/api/show` call per model per process lifetime. Per-model `asyncio.Lock` prevents concurrent first-use from issuing duplicate requests.

### New method: `OllamaClient.get_num_ctx`

Added to `projects/aiserver/ollama.py`:

```python
async def get_num_ctx(self, model: str) -> int:
    """Return effective context length for a model via /api/show.

    Prefers parameters.num_ctx (the runtime-loaded window) and falls
    back to model_info['<arch>.context_length'] (the architectural max
    from the GGUF file). Raises OllamaError if neither is present.
    """
```

Rationale for placement: it's a general Ollama capability, not rp-specific. `budget.py` calls it; aiserver stats/dashboard code can reuse it.

### Integration points

**Runtime pipeline (`projects/rp/pipeline.py`)**

`create_default_pipeline()` removes `apply_context_strategy` from the pre-chain. The pipeline stays a pure prompt-assembly chain: `assemble_prompt → expand_variables → inject_tools`. No Ollama or model dependency leaks into the pipeline.

`apply_context_strategy` is deleted (the caller invokes `fit_prompt` directly — see below).

**Runtime call sites (`projects/rp/routes.py`)**

`_build_pipeline_ctx` currently ends with `return await _pipeline.run_pre(ctx)`. After this change, routes.py calls `fit_prompt` explicitly after `run_pre`, where `_ollama` and the resolved model name are already in scope:

```python
ctx = await _build_pipeline_ctx(conv, messages)
strategy = get_strategy(
    conv.get("scenario_settings", {}).get("context_strategy", "summary_buffer")
)
report = await fit_prompt(
    ctx,
    model=resolved_model,
    ollama=_ollama,
    strategy=strategy,
    num_predict=request_options.get("num_predict"),
)
ctx["_budget_report"] = report
```

This happens at each of the ~5 `_build_pipeline_ctx` call sites in `routes.py` (message send, regenerate, swap, etc.). A small helper wraps the `fit_prompt` call to avoid duplication.

The Ollama call sites then merge `ctx["_num_ctx"]` into the options dict:

```python
options = {**request_options, "num_ctx": ctx["_num_ctx"]}
```

This tells Ollama to load the model with its full context window. First request after aiserver start triggers a model reload (slow for large models); subsequent requests are fast. An INFO log line is emitted on the first reload for observability.

**lora_generate (`projects/rp/lora_generate.py`)**

Each of `generate_scenarios`, `generate_user_message`, `generate_assistant_message` wraps its Ollama call in `fit_raw_prompt`. On `BudgetError`:

- `generate_scenarios`: log a warning with the category and character pair, skip that category, continue the run.
- `generate_user_message` / `generate_assistant_message`: log a warning with the conversation index and turn, return `None`, which the existing control flow already interprets as "stop this conversation" (see `lora_generate.py:354`).

The overall run continues — one oversized scenario does not abort a multi-hour job.

### Data flow (per request)

```
1. Pipeline pre-hooks run as today:
   assemble_prompt → expand_variables → inject_tools
   ctx now has: system_prompt (with tools appended), post_prompt (with
   scene_state appended), raw messages from DB.

2. routes.py calls fit_prompt(ctx, model=..., ollama=..., strategy=..., num_predict=...):

   2a. model_ctx = await _get_model_ctx(model, ollama)
       - Cache hit: return immediately.
       - Cache miss: acquire per-model lock, call ollama.get_num_ctx,
         cache, return. Concurrent callers on the same model wait on
         the lock and see the cached value.

   2b. response_reserve = num_predict if num_predict is not None else 1024
       available = model_ctx - response_reserve

   2c. Count overhead with estimator:
         overhead = count(system_prompt) + count(post_prompt)
       messages_budget = available - overhead

   2d. If messages_budget <= 0:
       Try shrink-policy step 4 (mes_example truncation).
       If still <= 0, raise BudgetError.

   2e. ctx["messages"] = strategy.fit(messages, messages_budget, ctx=ctx)
       SlidingWindow / SummaryBuffer are unchanged — they just get a
       correctly-computed budget.

   2f. Ground-truth check (if ground_truth=True):
         full_prompt = render(system_prompt, messages, post_prompt)
         actual = await _ollama_count(full_prompt, model)
       If actual + response_reserve > model_ctx:
         apply shrink policy, re-count once more.
         If still over, raise BudgetError.

   2g. ctx["_num_ctx"] = model_ctx
       Return BudgetReport.

3. routes.py proceeds to generation, merging ctx["_num_ctx"] into
   the Ollama options dict.
```

#### Why the estimator drives shrinking but ground-truth verifies

- The estimator is good enough to pick *which* messages to drop (relative sizing is accurate).
- Ground-truth is the real contract: "did this actually fit in the model's window?"
- One ground-truth call per request (~50–150ms local). Not cheap but small vs. generation time.
- Ground-truth checking *every* shrink iteration would be 3–5 calls per turn — too expensive. Estimator drives the loop; ground-truth is the safety net.
- If ground-truth says "still over," at most one additional shrink + recount is performed, then `BudgetError`. The estimator is empirically accurate enough that this second recount almost never fails.

### Ground-truth counting mechanism

```python
async def _ollama_count(prompt: str, model: str, ollama: "OllamaClient") -> int:
    """Return prompt_eval_count for the given prompt.

    Calls /api/generate with num_predict=0, stream=false. The response's
    prompt_eval_count is Ollama's real token count using the model's
    tokenizer.
    """
```

This is added to `budget.py` rather than `OllamaClient` because its only purpose is budgeting — it's not a general Ollama capability, and keeping it local avoids adding a narrow method to the shared client.

## Shrink policy (priority order)

Each step is one operation; after each, re-measure and stop as soon as the prompt fits.

### Priority 1 — Always protected, never touched

- Character description
- Character personality
- `post_prompt` (instruction tail)
- `scene_state`
- Tool descriptions
- First message (greeting)
- Most recent user message

### Priority 2 — Drop oldest messages

Handled inside the active `ContextStrategy.fit()` call. `SlidingWindow` and `SummaryBuffer` already drop oldest-first and protect the greeting. `budget.py` just passes them the correct budget.

### Priority 3 — Drop the injected summary

Only applies when `SummaryBuffer` is active and a summary was added. A summary is a lossy compression of history; if all droppable history is already gone and we still don't fit, the summary is the next-cheapest thing to lose.

Implementation: after strategy.fit, if still over, clear `ctx["_summary"]` and re-run strategy.fit.

### Priority 4 — Truncate `mes_example`

The only Priority 1 → shrinkable promotion. `mes_example` is typically the biggest and most redundant field on a character card (full example dialogues, often 500–2000 tokens).

Truncation rule: keep the first N lines such that the resulting `mes_example` is max(25% of original tokens, 200 tokens). Re-run `assemble_prompt` with the truncated value, re-measure.

Mark `report.mes_example_truncated = True` and add a warning to `report.warnings`.

### Priority 5 — Nothing left to shrink

Raise `BudgetError` with the populated `BudgetReport`. Callers decide:

- Runtime pipeline: return an error to the user. The message is explicit ("This turn does not fit in the model's context. The most recent user message alone is {N} tokens, model context is {M}.") so the user knows what to do (shorten input or switch models).
- `lora_generate`: log at WARNING, skip this scenario/turn, continue the run.

### Most-recent user message protection

If a user pastes a 20k-token wall of text into an 8k-context model, we raise `BudgetError` immediately rather than silently dropping it. The user must know their message did not fit, not receive a reply to a truncated version of what they said.

## `num_ctx` propagation

Ollama's `num_ctx` at load time defaults to **2048** unless passed in the `options` block. Even if `/api/show` reports that a model supports 32k, if nobody loaded it with `num_ctx: 32768`, the running model only sees 2048 tokens.

Fix: `fit_prompt` sets `ctx["_num_ctx"] = model_ctx`. All callers merge this into the options dict on their Ollama calls:

```python
options = {**request_options, "num_ctx": ctx["_num_ctx"]}
```

Consequences:

- First request after aiserver start triggers a model reload into the larger context. Slow for large models (tens of seconds for 70B). Subsequent requests are fast.
- Log at INFO on the first reload: `"Loading {model} with num_ctx={n}"`.
- No thrashing: the same model always receives the same `num_ctx` (both pulled from `/api/show`), so concurrent scenarios using the same model don't cause reloads.
- `lora_generate` call sites also pass `num_ctx` — this is important because lora_generate can run for hours and any thrashing would be expensive.

## Error handling

### `BudgetError`

Raised by `fit_prompt` and `fit_raw_prompt` when the minimum viable prompt does not fit. Carries a populated `BudgetReport` for diagnostics.

Callers:

- **Runtime pipeline** (`routes.py`): catch, return HTTP 413 (Payload Too Large) with a user-facing message built from the report. The streaming response, if already started, sends a final error chunk.
- **lora_generate**: catch, log at WARNING with `report.model`, `report.overhead`, `report.estimator_tokens`, skip the current scenario/turn, continue.

### Degraded scenarios (not errors)

Anything handled by shrink policy steps 2–4 is logged but does not raise. The `BudgetReport` carries flags (`summary_dropped`, `mes_example_truncated`, `messages_dropped > 0`) and a `warnings` list. Callers can log or surface these as desired.

### Ollama unreachable during `_get_model_ctx`

Propagate the underlying `OllamaError`. No attempt to fall back to a hardcoded default — if we can't learn the model's context, we can't safely budget.

## Testing

### Unit tests — `projects/rp/tests/test_budget.py`

All mocked, no network. Fast, runs on every commit.

- `fit_prompt` with `ground_truth=False`:
  - Happy path: small context, everything fits, nothing dropped.
  - Messages exceed budget: oldest dropped, first message + most-recent user message protected.
  - System prompt alone exceeds `available`: Priority 4 (mes_example truncation) fires.
  - Even truncated mes_example doesn't fit: `BudgetError` raised with populated report.
  - Each shrink priority level: force conditions and assert the `BudgetReport` flag for that level is set.
- `fit_prompt` with `ground_truth=True` and mocked `_ollama_count`:
  - Estimator says "fits" but ground-truth says "over": one additional shrink + recount succeeds.
  - Estimator says "fits" but ground-truth says "over" twice: `BudgetError`.
- `_get_model_ctx` caching:
  - First call hits the mock once.
  - Second call returns from cache without hitting the mock.
  - Concurrent first calls via `asyncio.gather(*[_get_model_ctx(m, o) for _ in range(10)])` only hit the mock once.
- `response_reserve` logic: `None` → 1024, explicit value → honored verbatim.
- `OllamaClient.get_num_ctx`:
  - Prefers `parameters.num_ctx` from `/api/show`.
  - Falls back to `model_info['<arch>.context_length']`.
  - Raises `OllamaError` when neither is present.
  - Three fixture `/api/show` responses cover these cases.

### Integration tests — `projects/rp/tests/test_budget_integration.py`

Marked `@pytest.mark.integration`. Skipped in default test runs (`pytest -m "not integration"`); opt-in for local verification.

- Ground-truth check with a small real model: assemble a known prompt, call `fit_prompt(ground_truth=True)`, assert `actual_tokens` is within 5% of the estimator.
- `num_ctx` propagation: send an oversized prompt through `fit_prompt`, verify `BudgetError` fires rather than Ollama silently truncating.

### Regression tests

- Existing `test_context.py` tests for `SlidingWindow` and `SummaryBuffer` stay unchanged — the strategies are unmodified.
- One new equivalence test: given an empty system prompt, `fit_prompt` produces the same `messages` list as the old `apply_context_strategy` pathway did (smoke test that replacing the hook didn't break message-fitting).

### `lora_generate` tests

- Monkey-patch `ollama.generate` with a counter.
- Force `fit_raw_prompt` to raise `BudgetError` on a specific scenario.
- Assert: (a) the oversized scenario is skipped with a warning log, (b) the overall run continues and produces output for non-oversized scenarios, (c) the counter shows the skipped scenario never triggered the underlying `ollama.generate` call.

### Explicitly NOT tested

- Exact token counts from the estimator (it's a heuristic; ground-truth is the contract).
- Ollama's own context-truncation behavior (that's Ollama's job).
- Every possible shrink priority combination (the order is linear; each level has one dedicated test).

## Migration / compatibility

- `max_context_tokens` in scenario settings is deprecated. Code no longer reads it. Existing scenarios with the field set continue to work (the field is ignored, not rejected). A cleanup migration to remove the column is out of scope for this change.
- `apply_context_strategy` is deleted. Any external code referencing it would break — a repo-wide grep confirms there are no such references outside `pipeline.py` itself.
- `ContextStrategy` and its subclasses are unchanged. They remain the mechanism for choosing *which* messages to drop.
- Tests that construct a pipeline without an `OllamaClient` will need to inject a stub. A helper `make_test_ollama(num_ctx=8192)` will be added to `tests/conftest.py`.

## Open questions

None at spec-approval time.

## References

- `projects/rp/pipeline.py:172-180` — current `apply_context_strategy` being replaced
- `projects/rp/context.py` — `SlidingWindow` and `SummaryBuffer` (unchanged by this work)
- `projects/aiserver/ollama.py` — `OllamaClient` (adds `get_num_ctx` method)
- `projects/rp/lora_generate.py:182-239` — `generate_scenarios` (gets `fit_raw_prompt` integration)
- `projects/rp/lora_generate.py:244-325` — `generate_user_message` / `generate_assistant_message` (get `fit_raw_prompt` integration)
- Ollama API: `POST /api/show` returns `parameters` and `model_info` fields used by `get_num_ctx`
- Ollama API: `POST /api/generate` with `num_predict: 0` returns `prompt_eval_count` used by `_ollama_count`
