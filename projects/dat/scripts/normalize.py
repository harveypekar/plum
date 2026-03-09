"""Shared normalization utilities for the dating corpus."""

import json
from pathlib import Path
from typing import Any

CORPUS_DIR = Path(__file__).parent.parent / "corpus"
RAW_DIR = Path(__file__).parent.parent / "raw"

SCHEMA = {
    "type": "object",
    "required": ["id", "source", "platform", "messages"],
    "properties": {
        "id": {"type": "string"},
        "source": {"type": "string"},
        "platform": {"type": "string"},
        "messages": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["role", "text"],
                "properties": {
                    "role": {"type": "string"},
                    "text": {"type": "string"},
                },
            },
        },
        "metadata": {"type": "object"},
    },
}


def write_corpus(records: list[dict[str, Any]], filename: str) -> Path:
    """Write normalized records to a JSONL file in corpus/."""
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CORPUS_DIR / filename
    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    print(f"Wrote {count} records to {out_path}")
    return out_path


def make_record(
    id: str,
    source: str,
    platform: str,
    messages: list[dict[str, str]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a corpus record dict."""
    record = {
        "id": id,
        "source": source,
        "platform": platform,
        "messages": messages,
    }
    if metadata:
        record["metadata"] = metadata
    return record
