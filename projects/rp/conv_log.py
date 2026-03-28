"""Conversation pipeline logger.

Appends structured events to projects/rp/log.txt with global sequence numbers
so the entire pipeline can be replayed: prompts, responses, scene state updates,
research injections, fewshot matches.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

_log_path = Path(__file__).parent / "log.txt"
_seq = 0
_lock = Lock()


def _next_seq() -> int:
    global _seq
    with _lock:
        _seq += 1
        return _seq


def _write(event: str, conv_id: int, data: dict):
    seq = _next_seq()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "seq": seq,
        "ts": ts,
        "event": event,
        "conv_id": conv_id,
        **data,
    }
    line = json.dumps(entry, ensure_ascii=False)
    with _lock:
        with open(_log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def log_prompt(conv_id: int, endpoint: str, model: str,
               system_prompt: str, post_prompt: str,
               messages: list[dict], ollama_options: dict | None = None):
    """Log the complete prompt sent to the model."""
    _write("prompt", conv_id, {
        "endpoint": endpoint,
        "model": model,
        "system_prompt": system_prompt,
        "post_prompt": post_prompt,
        "messages": messages,
        "ollama_options": ollama_options or {},
    })


def log_response(conv_id: int, role: str, content: str,
                 raw_stats: dict | None = None):
    """Log the saved response after post-processing."""
    _write("response", conv_id, {
        "role": role,
        "content": content,
        "raw_stats": _extract_stats(raw_stats) if raw_stats else {},
    })


def log_scene_state(conv_id: int, previous: str, updated: str):
    """Log a scene state update."""
    _write("scene_state", conv_id, {
        "previous": previous,
        "updated": updated,
    })


def log_research(conv_id: int, query: str, result: str):
    """Log research injection."""
    _write("research", conv_id, {
        "query": query,
        "result": result,
    })


def log_fewshot(conv_id: int, count: int, examples: list[dict] | None = None):
    """Log fewshot example injection."""
    _write("fewshot", conv_id, {
        "count": count,
        "examples": examples or [],
    })


def _extract_stats(raw: dict) -> dict:
    """Pull useful stats from Ollama's done chunk."""
    keys = ["total_duration", "load_duration", "prompt_eval_count",
            "prompt_eval_duration", "eval_count", "eval_duration"]
    return {k: raw[k] for k in keys if k in raw}
