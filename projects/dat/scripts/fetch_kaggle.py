"""Download and normalize Kaggle dating datasets."""

import csv
from pathlib import Path

import kagglehub

from normalize import make_record, write_corpus

DATASETS = {
    "reddit-tinder": "thedevastator/uncovering-online-dating-trends-with-reddit-s-ti",
}


def fetch_reddit_tinder() -> list[dict]:
    """Fetch the Kaggle r/Tinder dataset."""
    print("Fetching Kaggle reddit-tinder dataset...")
    path = kagglehub.dataset_download(DATASETS["reddit-tinder"])
    print(f"  Downloaded to: {path}")

    # List files to understand structure
    dl_path = Path(path)
    csv_files = list(dl_path.rglob("*.csv"))
    print(f"  CSV files found: {[f.name for f in csv_files]}")

    records = []
    for csv_file in csv_files:
        print(f"  Processing {csv_file.name}...")
        with open(csv_file, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            print(f"    Columns: {reader.fieldnames}")
            for i, row in enumerate(reader):
                if i == 0:
                    print(f"    Sample: {dict(list(row.items())[:5])}")
                # Look for text/selftext/body columns (Reddit post content)
                text = ""
                for col in ("selftext", "body", "text", "title"):
                    if col in row and row[col] and row[col].strip() not in ("", "[removed]", "[deleted]"):
                        text = row[col].strip()
                        break
                if not text or len(text) < 20:
                    continue
                metadata = {
                    "subreddit": row.get("subreddit", "tinder"),
                    "original_format": "reddit_post",
                }
                for k in ("score", "num_comments", "created_utc", "link_flair_text"):
                    if k in row and row[k]:
                        metadata[k] = row[k]
                records.append(
                    make_record(
                        id=f"kaggle-tinder-{csv_file.stem}-{i:06d}",
                        source="kaggle/thedevastator/reddit-tinder",
                        platform="reddit",
                        messages=[{"role": "poster", "text": text}],
                        metadata=metadata,
                    )
                )
    return records


def main():
    records = fetch_reddit_tinder()
    write_corpus(records, "kaggle.jsonl")


if __name__ == "__main__":
    main()
