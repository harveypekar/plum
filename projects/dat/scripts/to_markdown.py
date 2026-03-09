"""Convert the JSONL corpus into a single readable markdown file."""

import json
from datetime import datetime, timezone
from pathlib import Path

from normalize import CORPUS_DIR

OUTPUT = CORPUS_DIR.parent / "corpus.md"

# Friendly names for sources
SOURCE_NAMES = {
    "github.jsonl": "Tinder Messages (Flirtation-analysis)",
    "huggingface.jsonl": "HuggingFace Dialogue Datasets",
    "kaggle.jsonl": "r/Tinder (Kaggle)",
    "reddit-tinder.jsonl": "r/Tinder",
    "reddit-hingeapp.jsonl": "r/hingeapp",
    "reddit-bumble.jsonl": "r/Bumble",
    "reddit-onlinedating.jsonl": "r/OnlineDating",
    "reddit-dating_advice.jsonl": "r/dating_advice",
}


def format_metadata(meta: dict) -> str:
    """Format metadata as a compact inline string."""
    parts = []
    if "polarity" in meta:
        parts.append("flirty" if str(meta["polarity"]) == "1" else "not flirty")
    if "label" in meta and meta["label"] is not None:
        parts.append("flirty" if meta["label"] else "not flirty")
    if "score" in meta:
        parts.append(f"score: {meta['score']}")
    if "num_comments" in meta:
        parts.append(f"comments: {meta['num_comments']}")
    if "created_utc" in meta:
        try:
            ts = int(meta["created_utc"])
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            parts.append(dt.strftime("%Y-%m-%d"))
        except (ValueError, TypeError, OSError):
            pass
    return " · ".join(parts)


def format_messages(messages: list[dict]) -> str:
    """Format message list as blockquoted dialogue."""
    lines = []
    for msg in messages:
        role = msg.get("role", "?")
        text = msg.get("text", "")
        # Split embedded dialogue turns (literal \n followed by role markers)
        text = text.replace("\\n", "\n")
        for sub_line in text.split("\n"):
            sub_line = sub_line.strip()
            if not sub_line:
                continue
            # If line starts with a role marker like "B:", format it
            if len(sub_line) > 2 and sub_line[1] == ":" and sub_line[0].isupper():
                r, t = sub_line[0], sub_line[2:].strip()
                lines.append(f"> **{r}:** {t}")
            else:
                lines.append(f"> **{role}:** {sub_line}")
    return "\n>\n".join(lines)


def main():
    total = 0
    sections = []

    for jsonl_file in sorted(CORPUS_DIR.glob("*.jsonl")):
        name = SOURCE_NAMES.get(jsonl_file.name, jsonl_file.stem)
        records = []
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                records.append(json.loads(line))

        entries = []
        for i, rec in enumerate(records):
            meta_str = format_metadata(rec.get("metadata", {}))
            header = f"#### #{i + 1}"
            if meta_str:
                header += f"  [{meta_str}]"
            body = format_messages(rec.get("messages", []))
            entries.append(f"{header}\n\n{body}")

        section = f"## {name} ({len(records)} records)\n\n"
        section += "\n\n---\n\n".join(entries)
        sections.append(section)
        total += len(records)

    header = f"# Dating Conversation Corpus\n\n**{total} records** across {len(sections)} sources.\n\n"
    toc = "## Table of Contents\n\n"
    for jsonl_file in sorted(CORPUS_DIR.glob("*.jsonl")):
        name = SOURCE_NAMES.get(jsonl_file.name, jsonl_file.stem)
        with open(jsonl_file, encoding="utf-8") as f:
            count = sum(1 for _ in f)
        anchor = name.lower().replace(" ", "-").replace("(", "").replace(")", "").replace("/", "")
        toc += f"- [{name}](#{anchor}-{count}-records) ({count})\n"

    doc = header + toc + "\n\n" + "\n\n---\n\n".join(sections) + "\n"

    OUTPUT.write_text(doc, encoding="utf-8")
    size_mb = OUTPUT.stat().st_size / 1024 / 1024
    print(f"Wrote {total} records to {OUTPUT} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
