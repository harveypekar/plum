"""Download and normalize HuggingFace dating conversation datasets."""

from datasets import load_dataset

from normalize import make_record, write_corpus


def fetch_flirty_dialogue() -> list[dict]:
    """Fetch CanadianGamer/Flirty-Dialogue dataset."""
    print("Fetching CanadianGamer/Flirty-Dialouge...")
    ds = load_dataset("CanadianGamer/Flirty-Dialouge", split="train")
    records = []
    for i, row in enumerate(ds):
        if i == 0:
            print(f"  Columns: {list(row.keys())}")
            print(f"  Sample: {row}")
        messages = []
        for key in row:
            if isinstance(row[key], str) and row[key].strip():
                messages.append({"role": key, "text": row[key].strip()})
        if messages:
            records.append(
                make_record(
                    id=f"flirty-dialogue-{i:06d}",
                    source="huggingface/CanadianGamer/Flirty-Dialouge",
                    platform="synthetic",
                    messages=messages,
                    metadata={"original_format": "dialogue_pair"},
                )
            )
    return records


def fetch_flirty_or_not() -> list[dict]:
    """Fetch ieuniversity/flirty_or_not dataset."""
    print("Fetching ieuniversity/flirty_or_not...")
    ds = load_dataset("ieuniversity/flirty_or_not", split="train")
    records = []
    for i, row in enumerate(ds):
        if i == 0:
            print(f"  Columns: {list(row.keys())}")
            print(f"  Sample: {row}")
        text_col = None
        label_col = None
        for key in row:
            if isinstance(row[key], str) and len(row[key]) > 20:
                text_col = key
            elif key in ("label", "flirty", "is_flirty"):
                label_col = key
        if text_col and row[text_col].strip():
            records.append(
                make_record(
                    id=f"flirty-or-not-{i:06d}",
                    source="huggingface/ieuniversity/flirty_or_not",
                    platform="unknown",
                    messages=[{"role": "A", "text": row[text_col].strip()}],
                    metadata={
                        "label": row.get(label_col) if label_col else None,
                        "original_format": "classification",
                    },
                )
            )
    return records


def main():
    all_records = []
    all_records.extend(fetch_flirty_dialogue())
    all_records.extend(fetch_flirty_or_not())
    write_corpus(all_records, "huggingface.jsonl")


if __name__ == "__main__":
    main()
