"""Compare / A/B eval endpoints extracted from routes.py."""

import asyncio
import copy
import logging
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, HTTPException

from . import db
from .models import CompareRequest, SelectCandidateRequest
from .budget import BudgetError, allocate_injections
from .research import research_dispatch
from .fewshot import get_fewshot_messages
from .prompt_builder import (
    get_ai_name, get_user_name, get_ai_personality, get_ai_pronouns,
    build_chat_messages, build_ollama_options, scale_num_predict,
    budget_to_json, build_pipeline_ctx, budget_ctx,
)
from . import conv_log

_log = logging.getLogger("rp.eval_routes")


def setup_eval_routes(
    app: FastAPI,
    ollama,
    pipeline,
    resolve_model: Callable,
    template_path: Path,
    auto_update_scene_state: Callable,
):
    """Register compare/eval endpoints on the FastAPI app."""

    async def _build_ctx(conv, messages):
        return await build_pipeline_ctx(
            conv, messages, pipeline=pipeline, template_path=template_path)

    async def _budget(ctx, model, ollama_options):
        return await budget_ctx(ctx, model, ollama_options, ollama=ollama)

    @app.post("/rp/conversations/{conv_id}/compare")
    async def compare_message(conv_id: int, req: CompareRequest):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")

        await db.add_message(conv_id, "user", req.content)
        conv_log.log_response(conv_id, "user", req.content)

        messages = await db.get_messages(conv_id)
        next_seq = max((m["sequence"] for m in messages), default=0) + 1

        eval_set = await db.create_eval_set(conv_id, next_seq)

        base_ctx = await _build_ctx(conv, messages)
        base_model = resolve_model(conv["model"])
        scenario = base_ctx.get("scenario") or {}
        settings = scenario.get("settings", {})
        base_ollama_options = scale_num_predict(
            build_ollama_options(settings), req.content)

        research = await research_dispatch(ollama, req.content)
        fewshot_msgs = await get_fewshot_messages(
            ollama, base_ctx["messages"], card_id=conv["ai_card_id"],
        )

        alloc = await allocate_injections(
            base_ctx, model=base_model, ollama=ollama,
            num_predict=base_ollama_options.get("num_predict"),
            research_text=research,
            fewshot_msgs=fewshot_msgs if fewshot_msgs and base_ctx["messages"] else None,
            model_ctx_override=base_ollama_options.get("num_ctx"),
        )

        if research and alloc.keep_research:
            base_ctx["post_prompt"] = (
                base_ctx.get("post_prompt", "")
                + "\n\n[Research notes — weave these facts naturally if relevant, "
                + "don't quote them verbatim or mention looking anything up]\n"
                + research
            )

        if fewshot_msgs and base_ctx["messages"] and alloc.keep_fewshot:
            base_ctx["messages"] = [base_ctx["messages"][0]] + fewshot_msgs + base_ctx["messages"][1:]

        base_ctx["_injection_alloc"] = alloc

        async def generate_candidate(cfg, candidate_row):
            ctx = copy.deepcopy(base_ctx)
            model = resolve_model(cfg.model) if cfg.model else base_model
            ollama_options = dict(base_ollama_options)
            if cfg.temperature is not None:
                ollama_options["temperature"] = cfg.temperature
            if cfg.num_predict is not None:
                ollama_options["num_predict"] = cfg.num_predict

            try:
                await _budget(ctx, model, ollama_options)
            except BudgetError as e:
                await db.update_eval_candidate(
                    candidate_row["id"],
                    content=f"[budget error: {e}]",
                )
                return

            ollama_options = {**ollama_options, "num_ctx": ctx["_num_ctx"]}
            chat_messages = build_chat_messages(ctx)
            user_name = get_user_name(ctx)

            tokens = []
            raw = {}
            try:
                async for chunk in ollama.chat_stream(
                    model=model, messages=chat_messages,
                    options=ollama_options, stop=[f"{user_name}:"],
                ):
                    if chunk.get("done"):
                        raw = chunk
                    elif not chunk.get("thinking"):
                        tokens.append(chunk["token"])
            except Exception as e:
                await db.update_eval_candidate(
                    candidate_row["id"],
                    content=f"[generation error: {e}]",
                )
                return

            response_text = "".join(tokens)
            post_ctx = {"response": response_text, "ai_name": get_ai_name(ctx), "_char_pronouns": get_ai_pronouns(ctx)}
            post_ctx = await pipeline.run_post(post_ctx)
            await db.update_eval_candidate(
                candidate_row["id"],
                content=post_ctx["response"],
                raw_response=raw,
                prompt_json=chat_messages,
                budget_json=budget_to_json(ctx),
            )

        tasks = []
        for cfg in req.configs:
            label = cfg.label or cfg.model or "default"
            model_name = cfg.model or conv["model"]
            config_dict = cfg.model_dump(exclude_none=True)
            candidate_row = await db.add_eval_candidate(
                eval_set["id"], label, model_name, config_dict,
            )
            tasks.append(generate_candidate(cfg, candidate_row))

        await asyncio.gather(*tasks)

        candidates = await db.get_eval_candidates(eval_set["id"])
        return {
            "eval_set_id": eval_set["id"],
            "conversation_id": conv_id,
            "sequence": next_seq,
            "candidates": candidates,
        }

    @app.post("/rp/eval-sets/{eval_set_id}/select")
    async def select_candidate(eval_set_id: int, req: SelectCandidateRequest):
        eval_set = await db.get_eval_set(eval_set_id)
        if not eval_set:
            raise HTTPException(404, "Eval set not found")

        candidates = await db.get_eval_candidates(eval_set_id)
        winner = next((c for c in candidates if c["id"] == req.candidate_id), None)
        if not winner:
            raise HTTPException(404, "Candidate not found in this eval set")

        conv_id = eval_set["conversation_id"]
        conv = await db.get_conversation(conv_id)

        await db.add_message(
            conv_id, "assistant", winner["content"],
            raw_response=winner.get("raw_response"),
            system_prompt=None,
            scene_state=conv.get("scene_state", ""),
            post_prompt=None,
            budget_json=winner.get("budget_json"),
            prompt_json=winner.get("prompt_json"),
        )
        await db.select_eval_candidate(
            eval_set_id, req.candidate_id,
            preference_tags=req.preference_tags,
        )

        asyncio.create_task(auto_update_scene_state(
            conv_id, conv["model"],
            get_ai_name({"ai_card": await db.get_card(conv["ai_card_id"])}),
            get_user_name({"user_card": await db.get_card(conv["user_card_id"])}),
            get_ai_personality({"ai_card": await db.get_card(conv["ai_card_id"])}),
        ))

        return {
            "ok": True,
            "eval_set_id": eval_set_id,
            "selected_candidate_id": req.candidate_id,
            "content": winner["content"],
        }

    @app.get("/rp/eval-sets/{eval_set_id}")
    async def get_eval_set_detail(eval_set_id: int):
        eval_set = await db.get_eval_set(eval_set_id)
        if not eval_set:
            raise HTTPException(404, "Eval set not found")
        candidates = await db.get_eval_candidates(eval_set_id)
        return {"eval_set": eval_set, "candidates": candidates}

    @app.get("/rp/conversations/{conv_id}/eval-sets")
    async def list_eval_sets(conv_id: int):
        sets = await db.get_eval_sets_for_conversation(conv_id)
        return sets
