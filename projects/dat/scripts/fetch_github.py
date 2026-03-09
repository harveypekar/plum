"""Download and normalize GitHub-hosted dating datasets."""

import csv
import io
from pathlib import Path

import requests

from normalize import RAW_DIR, make_record, write_corpus

FLIRTATION_ANALYSIS_URLS = {
    "all": "https://raw.githubusercontent.com/alyssafrndz/Flirtation-analysis/main/flirting_rated.csv",
}


def fetch_flirtation_analysis() -> list[dict]:
    """Fetch Flirtation-analysis CSVs from GitHub."""
    records = []
    for split, url in FLIRTATION_ANALYSIS_URLS.items():
        print(f"Fetching flirtation-analysis/{split}...")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        # Save raw
        raw_dir = RAW_DIR / "flirtation-analysis"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{split}.csv"
        raw_path.write_text(resp.text, encoding="utf-8")

        # Parse CSV — inspect header first
        reader = csv.DictReader(io.StringIO(resp.text))
        print(f"  Columns: {reader.fieldnames}")
        for i, row in enumerate(reader):
            if i == 0:
                print(f"  Sample: {row}")
            # Find the text column (longest string value)
            text_col = max(
                (k for k in row if isinstance(row[k], str)),
                key=lambda k: len(row[k]),
                default=None,
            )
            if text_col and row[text_col].strip():
                metadata = {
                    "split": split,
                    "original_format": "labeled_message",
                }
                # Capture any label/rating columns
                for k, v in row.items():
                    if k != text_col:
                        metadata[k] = v
                records.append(
                    make_record(
                        id=f"flirtation-{split}-{i:06d}",
                        source="github/alyssafrndz/Flirtation-analysis",
                        platform="tinder",
                        messages=[{"role": "A", "text": row[text_col].strip()}],
                        metadata=metadata,
                    )
                )
    return records


def main():
    records = fetch_flirtation_analysis()
    write_corpus(records, "github.jsonl")


if __name__ == "__main__":
    main()
