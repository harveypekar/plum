"""Prompt assembly and context budgeting extracted from routes.py.

Pure functions for building chat messages, extracting card data, and
preparing the pipeline context. Functions that need external services
(db, ollama, pipeline) take them as explicit parameters.
"""

import logging
from dataclasses import asdict
from pathlib import Path

from . import db
from .budget import fit_prompt, BudgetError, BudgetReport
from .context import get_strategy
from .tokenizer import count_tokens

_log = logging.getLogger("rp.prompt_builder")

CHAT_DEFAULTS = {
    "num_predict": 768,
    "num_ctx": 16384,
    "temperature": 1.05,
    "repeat_penalty": 1.08,
    "min_p": 0.1,
}


def get_ai_name(ctx: dict) -> str:
    ai_data = ctx.get("ai_card", {}).get("card_data", {}).get(
        "data", ctx.get("ai_card", {}).get("card_data", {}))
    return ai_data.get("name", "Character")


def get_user_name(ctx: dict) -> str:
    user_data = ctx.get("user_card", {}).get("card_data", {}).get(
        "data", ctx.get("user_card", {}).get("card_data", {}))
    return user_data.get("name", "User")


def get_ai_personality(ctx: dict) -> str:
    ai_data = ctx.get("ai_card", {}).get("card_data", {}).get(
        "data", ctx.get("ai_card", {}).get("card_data", {}))
    return ai_data.get("description", "")


def build_ollama_options(settings: dict) -> dict:
    opts = dict(CHAT_DEFAULTS)
    for k, v in settings.items():
        if k not in ("max_context_tokens", "model"):
            opts[k] = v
    return opts


def scale_num_predict(opts: dict, user_message: str) -> dict:
    user_tokens = count_tokens(user_message)
    scaled = max(256, min(1024, user_tokens * 2))
    return {**opts, "num_predict": scaled}


def build_chat_messages(ctx: dict) -> list[dict]:
    chat_messages = [{"role": "system", "content": ctx["system_prompt"]}]
    chat_messages.extend(ctx["messages"])
    if ctx.get("post_prompt"):
        chat_messages.append({"role": "system", "content": ctx["post_prompt"]})
    ai_name = get_ai_name(ctx)
    chat_messages.append({"role": "assistant", "content": ai_name + " "})
    return chat_messages


def budget_to_json(ctx: dict) -> dict | None:
    report = ctx.get("_budget_report")
    if not isinstance(report, BudgetReport):
        return None
    result = asdict(report)
    alloc = ctx.get("_injection_alloc")
    if alloc is not None:
        result["injection"] = asdict(alloc)
    return result


async def build_pipeline_ctx(conv, messages, *, pipeline, template_path: Path):
    """Load cards, scenario, template and run pipeline pre-hooks."""
    user_card = await db.get_card(conv["user_card_id"])
    ai_card = await db.get_card(conv["ai_card_id"])
    scenario = await db.get_scenario(conv["scenario_id"]) if conv["scenario_id"] else {}
    scenario = scenario or {}

    prompt_template = ""
    if template_path.exists():
        prompt_template = template_path.read_text()

    msg_dicts = []
    for m in messages:
        d = {"role": m["role"], "content": m["content"]}
        d["_sequence"] = m.get("sequence", 0)
        msg_dicts.append(d)

    ctx = {
        "user_card": user_card,
        "ai_card": ai_card,
        "scenario": scenario,
        "messages": msg_dicts,
        "system_prompt": "",
        "post_prompt": "",
        "scene_state": conv.get("scene_state", ""),
        "prompt_template": prompt_template,
    }

    summary_row = await db.get_latest_summary(conv["id"])
    if summary_row:
        ctx["_summary"] = summary_row["summary"]
        ctx["_summary_through_sequence"] = summary_row["through_sequence"]

    return await pipeline.run_pre(ctx)


async def budget_ctx(ctx, model, ollama_options, *, ollama):
    """Run fit_prompt with SummaryBuffer strategy.

    Raises BudgetError on failure — callers handle the response.
    """
    strategy = get_strategy("summary_buffer")
    num_predict = ollama_options.get("num_predict")
    try:
        return await fit_prompt(
            ctx, model=model, ollama=ollama,
            strategy=strategy, num_predict=num_predict,
            ground_truth=True,
            model_ctx_override=ollama_options.get("num_ctx"),
        )
    except BudgetError as e:
        _log.warning("Budget error for model=%s: %s", model, e)
        raise
