"""Download and normalize the labsensacional sexting dataset from GitHub.

Source: https://github.com/labsensacional/sexting-dataset
~546 lines of He:/She: dialogue. We split on greeting patterns to find
conversation boundaries.
"""

import re

import requests

from normalize import RAW_DIR, make_record, write_corpus

DATASET_URL = "https://raw.githubusercontent.com/labsensacional/sexting-dataset/master/sexting_dataset.txt"

# Patterns that suggest a new conversation is starting
GREETING_PATTERN = re.compile(
    r"^(He|She):\s*(Hey|Hello|Hi |What's up|Heyy|Sup )",
    re.IGNORECASE,
)


def parse_conversations(text: str) -> list[list[dict[str, str]]]:
    """Split He:/She: dialogue into conversations at greeting boundaries."""
    lines = text.strip().split("\n")
    conversations = []
    current = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if this line starts a new conversation
        if GREETING_PATTERN.match(line) and current:
            conversations.append(current)
            current = []

        # Parse He:/She: prefix
        match = re.match(r"^(He|She):\s*(.+)", line, re.IGNORECASE)
        if match:
            role = match.group(1).capitalize()
            text_content = match.group(2).strip()
            if text_content:
                current.append({"role": role, "text": text_content})

    if current:
        conversations.append(current)

    return conversations


def main():
    print("Fetching sexting dataset...")
    resp = requests.get(DATASET_URL, timeout=30)
    resp.raise_for_status()

    # Save raw
    raw_dir = RAW_DIR / "sexting-dataset"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "sexting_dataset.txt"
    raw_path.write_text(resp.text, encoding="utf-8")

    conversations = parse_conversations(resp.text)
    print(f"  Parsed {len(conversations)} conversations")

    records = []
    for i, convo in enumerate(conversations):
        if len(convo) < 2:
            continue
        records.append(
            make_record(
                id=f"sexting-{i:06d}",
                source="github/labsensacional/sexting-dataset",
                platform="unknown",
                messages=convo,
                metadata={"original_format": "text", "content_warning": "sexual"},
            )
        )

    print(f"  {len(records)} multi-turn conversations")
    write_corpus(records, "sexting.jsonl")


if __name__ == "__main__":
    main()
