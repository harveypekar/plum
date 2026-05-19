"""Prompt assembly and context budgeting extracted from routes.py.

Pure functions for building chat messages, extracting card data, and
preparing the pipeline context. Functions that need external services
(db, ollama, pipeline) take them as explicit parameters.
"""

import logging
import re
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
    "temperature": 1.1,
    "repeat_penalty": 1.08,
    "repeat_last_n": 512,
    "frequency_penalty": 0.1,
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


_FEMALE_SIGNALS = re.compile(
    r'\b(woman|female|girl|lady|she|daughter|mother|wife|girlfriend|sister)\b',
    re.IGNORECASE,
)
_MALE_SIGNALS = re.compile(
    r'\b(man|male|boy|guy|he|son|father|husband|boyfriend|brother)\b',
    re.IGNORECASE,
)


def infer_pronouns(description: str) -> str:
    """Infer she/her or he/him from the first 200 chars of a card description."""
    text = description[:200]
    female = len(_FEMALE_SIGNALS.findall(text))
    male = len(_MALE_SIGNALS.findall(text))
    if female > male:
        return "she/her"
    if male > female:
        return "he/him"
    return ""


def get_ai_pronouns(ctx: dict) -> str:
    ai_data = ctx.get("ai_card", {}).get("card_data", {}).get(
        "data", ctx.get("ai_card", {}).get("card_data", {}))
    return ai_data.get("pronouns", "") or infer_pronouns(ai_data.get("description", ""))


def get_user_pronouns(ctx: dict) -> str:
    user_data = ctx.get("user_card", {}).get("card_data", {}).get(
        "data", ctx.get("user_card", {}).get("card_data", {}))
    return user_data.get("pronouns", "") or infer_pronouns(user_data.get("description", ""))


def get_ai_personality(ctx: dict) -> str:
    ai_data = ctx.get("ai_card", {}).get("card_data", {}).get(
        "data", ctx.get("ai_card", {}).get("card_data", {}))
    return ai_data.get("description", "")


def get_user_description(ctx: dict) -> str:
    user_data = ctx.get("user_card", {}).get("card_data", {}).get(
        "data", ctx.get("user_card", {}).get("card_data", {}))
    return user_data.get("description", "")


def build_ollama_options(settings: dict) -> dict:
    opts = dict(CHAT_DEFAULTS)
    for k, v in settings.items():
        if k not in ("max_context_tokens", "model"):
            opts[k] = v
    return opts


def scale_num_predict(opts: dict, user_message: str) -> dict:
    base = opts.get("num_predict", CHAT_DEFAULTS["num_predict"])
    user_tokens = count_tokens(user_message)
    scaled = max(512, min(base, user_tokens * 3))
    return {**opts, "num_predict": scaled}


def build_chat_messages(ctx: dict) -> list[dict]:
    chat_messages = [{"role": "system", "content": ctx["system_prompt"]}]

    messages = list(ctx["messages"])
    authors_note = ctx.get("authors_note", "")
    if authors_note:
        depth = ctx.get("authors_note_depth", 4)
        insert_idx = max(0, len(messages) - depth)
        note_msg = {"role": "system", "content": f"[Author's Note: {authors_note}]"}
        messages.insert(insert_idx, note_msg)

    chat_messages.extend(messages)
    if ctx.get("post_prompt"):
        chat_messages.append({"role": "system", "content": ctx["post_prompt"]})
    ai_name = get_ai_name(ctx)
    pronouns = get_ai_pronouns(ctx)
    if pronouns:
        anchor = f"{ai_name} [{pronouns}] "
    else:
        anchor = ai_name + " "
    chat_messages.append({"role": "assistant", "content": anchor})
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
        if "id" in m:
            d["_id"] = m["id"]
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
        "authors_note": conv.get("authors_note", ""),
        "authors_note_depth": conv.get("authors_note_depth", 4),
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
