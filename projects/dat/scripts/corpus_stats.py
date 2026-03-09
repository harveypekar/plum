"""Print summary statistics for the corpus."""

import json
from pathlib import Path

from normalize import CORPUS_DIR


def main():
    total = 0
    for jsonl_file in sorted(CORPUS_DIR.glob("*.jsonl")):
        count = 0
        msg_count = 0
        platforms = set()
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                count += 1
                msg_count += len(record.get("messages", []))
                platforms.add(record.get("platform", "unknown"))
        total += count
        print(f"{jsonl_file.name}: {count} records, {msg_count} messages, platforms: {platforms}")
    print(f"\nTotal: {total} records across {len(list(CORPUS_DIR.glob('*.jsonl')))} files")


if __name__ == "__main__":
    main()
