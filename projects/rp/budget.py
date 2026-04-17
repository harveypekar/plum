"""Prompt budgeting: fit rp pipeline and lora_generate prompts into model_ctx.

See docs/superpowers/specs/2026-04-07-rp-prompt-budgeting-design.md.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .context import ContextStrategy  # noqa: F401

_log = logging.getLogger(__name__)


class _OllamaLike(Protocol):
    async def get_num_ctx(self, model: str) -> int: ...
    async def chat(self, model, messages, tools=None, think=False): ...
    async def count_generate_prompt(
        self, model: str, prompt: str, system: str | None = None
    ) -> int: ...


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


async def _ollama_count_messages(
    messages: list[dict],
    model: str,
    ollama: _OllamaLike,
) -> int:
    """Ask Ollama for the ground-truth token count of `messages`.

    Calls /api/chat and reads prompt_eval_count from the response.
    Returns 0 if Ollama doesn't surface the field — caller decides
    how to handle a missing value.
    """
    result = await ollama.chat(model=model, messages=messages)
    return int(result.get("prompt_eval_count", 0) or 0)


async def _ollama_count_raw_prompt(
    prompt: str,
    system: str | None,
    model: str,
    ollama: _OllamaLike,
) -> int:
    """Ask Ollama for the ground-truth token count of a /api/generate prompt.

    Chat and generate apply different templates (role markers vs raw),
    so `_ollama_count_messages` would systematically over-count for the
    generate endpoint. Raw-prompt callers (lora_generate) must use this
    helper to match what they actually send.
    """
    return await ollama.count_generate_prompt(model=model, prompt=prompt, system=system)


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
        truncated = original[:target_chars]
    ai_data["mes_example"] = truncated

    # Re-run the prompt assembly chain to rebuild system_prompt/post_prompt.
    from .pipeline import assemble_prompt, expand_variables, inject_tools
    assemble_prompt(ctx)
    expand_variables(ctx)
    inject_tools(ctx)
    return True


def _render_for_count(ctx: dict) -> list[dict]:
    """Build the messages list that would actually be sent to Ollama.

    Must stay in lockstep with routes.py `_build_chat_messages`: system_prompt,
    the budgeted messages, optional post_prompt as a trailing system message,
    and the assistant priming anchor "{ai_name} " that anchors the model's
    voice. Omitting the anchor would systematically undercount prompt_eval_count.
    """
    msgs = [{"role": "system", "content": ctx.get("system_prompt", "")}]
    msgs.extend(ctx.get("messages", []))
    if ctx.get("post_prompt"):
        msgs.append({"role": "system", "content": ctx["post_prompt"]})
    ai_data = ctx.get("ai_card", {}).get("card_data", {}).get(
        "data", ctx.get("ai_card", {}).get("card_data", {})
    )
    ai_name = ai_data.get("name", "Character")
    msgs.append({"role": "assistant", "content": ai_name + " "})
    return msgs


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

    summary_dropped = False
    mes_example_truncated = False
    messages_snapshot = list(ctx.get("messages", []))

    def _current_overhead() -> int:
        return _estimate_tokens(ctx.get("system_prompt", "")) + _estimate_tokens(
            ctx.get("post_prompt", "")
        )

    # Priority 2: delegate to strategy.fit with the corrected budget.
    # The strategy (SlidingWindow / SummaryBuffer) handles greeting
    # protection, oldest-first drop, and summary injection.
    if messages_budget > 0:
        ctx["messages"] = strategy.fit(
            messages_snapshot, messages_budget, ctx=ctx
        )

    # Priority 3: if still over budget, drop the summary (if any) and re-fit
    # from the pre-strategy snapshot so any injected summary message is gone.
    def _current_messages_tokens() -> int:
        return sum(
            _estimate_tokens(m.get("content", ""))
            for m in ctx.get("messages", [])
        )

    if ctx.get("_summary") and _current_messages_tokens() > messages_budget:
        ctx["_summary"] = None
        if messages_budget > 0:
            ctx["messages"] = strategy.fit(
                messages_snapshot, messages_budget, ctx=ctx
            )
        summary_dropped = True
        warnings.append("summary dropped to fit messages budget")

    # Priority 4: if overhead alone exceeds available (or messages_budget <= 0),
    # truncate mes_example and re-run assembly.
    if messages_budget <= 0 or _current_overhead() > available:
        if _truncate_mes_example(ctx):
            mes_example_truncated = True
            warnings.append("mes_example truncated to fit system prompt")
            overhead = _current_overhead()
            messages_budget = available - overhead
            if messages_budget > 0:
                ctx["messages"] = strategy.fit(
                    messages_snapshot, messages_budget, ctx=ctx
                )

    # Ground-truth check: ask Ollama for the real prompt_eval_count.
    actual_tokens: int | None = None
    if ground_truth and messages_budget > 0:
        gt_messages = _render_for_count(ctx)
        actual_tokens = await _ollama_count_messages(gt_messages, model, ollama)

        # If Ollama returned a nonsense value (missing field, zero, negative),
        # discard it and fall back to the estimator. A silent "0 tokens" would
        # otherwise make any prompt appear to fit.
        if actual_tokens <= 0:
            warnings.append(
                f"ollama returned non-positive prompt_eval_count ({actual_tokens}); "
                "falling back to estimator"
            )
            actual_tokens = None
        elif actual_tokens + response_reserve > model_ctx:
            # One more shrink: drop one more oldest non-greeting message and recount.
            if len(ctx.get("messages", [])) > 2:
                ctx["messages"] = [ctx["messages"][0]] + ctx["messages"][2:]
                gt_messages = _render_for_count(ctx)
                actual_tokens = await _ollama_count_messages(gt_messages, model, ollama)
                if actual_tokens <= 0:
                    warnings.append(
                        f"ollama returned non-positive prompt_eval_count on recount "
                        f"({actual_tokens}); falling back to estimator"
                    )
                    actual_tokens = None
            # If still over, let Priority 5 below raise.

    # Priority 5: if after all shrinking the messages still can't fit,
    # raise BudgetError with a populated report.
    #
    # Two failure modes:
    # (a) Total size still exceeds available after all shrink steps.
    # (b) The most recent user message was dropped entirely — a broken
    #     conversation where we have no user turn to respond to.
    final_msg_tokens = _current_messages_tokens()
    final_overhead = _current_overhead()
    last_user_msg = next(
        (m for m in reversed(messages_snapshot) if m.get("role") == "user"),
        None,
    )
    last_user_dropped = last_user_msg is not None and not any(
        m is last_user_msg for m in ctx.get("messages", [])
    )
    effective_total = (
        actual_tokens if actual_tokens is not None
        else final_overhead + final_msg_tokens
    )
    if effective_total + response_reserve > model_ctx or messages_budget <= 0 or last_user_dropped:
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
            actual_tokens=actual_tokens,
            warnings=warnings + ["prompt does not fit after all shrink steps"],
        )
        ctx["_budget_report"] = failing_report
        raise BudgetError(
            f"Prompt does not fit: model_ctx={model_ctx}, reserve={response_reserve}, "
            f"overhead={final_overhead}, messages={final_msg_tokens}. "
            f"The most recent user message may be too long for this model.",
            failing_report,
        )

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
        actual_tokens=actual_tokens,
        warnings=warnings,
    )

    ctx["_num_ctx"] = model_ctx
    ctx["_budget_report"] = report
    return report


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

    Does NOT shrink — single-shot prompts have no safe shrink heuristic.
    If it doesn't fit, raises BudgetError and the caller decides to skip
    that scenario/turn.
    """
    model_ctx = await _get_model_ctx(model, ollama)
    response_reserve = num_predict if num_predict is not None else 1024
    available = model_ctx - response_reserve

    prompt = prompt or ""
    system = system or ""
    overhead = _estimate_tokens(prompt) + _estimate_tokens(system)

    actual_tokens: int | None = None
    warnings: list[str] = []
    if ground_truth:
        # Count via /api/generate to match how lora_generate actually sends
        # the prompt. /api/chat applies role markers that /api/generate
        # doesn't, so counting via chat would systematically over-count.
        actual_tokens = await _ollama_count_raw_prompt(
            prompt, system or None, model, ollama
        )
        # Silent-failure guard: treat non-positive counts as estimator fallback
        # (matches fit_prompt behavior added in Task 8 review).
        if actual_tokens <= 0:
            warnings.append(
                f"ollama returned non-positive prompt_eval_count ({actual_tokens}); "
                "falling back to estimator"
            )
            actual_tokens = None

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
        warnings=warnings,
    )

    if not fits:
        raise BudgetError(
            f"Raw prompt does not fit: model_ctx={model_ctx}, reserve={response_reserve}, "
            f"prompt_tokens={effective_total}.",
            report,
        )
    return prompt, report
