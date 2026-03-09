"""Download and normalize romance-adjacent conversations from EmpatheticDialogues.

Source: https://huggingface.co/datasets/facebook/empathetic_dialogues
Downloads the CSV directly since the HF dataset script is deprecated.
Filters to emotions related to dating/romance/attraction.
"""

import csv
import io
import tarfile

import requests

from normalize import RAW_DIR, make_record, write_corpus

# Facebook's original GitHub download script writes CSVs
# We use the raw data URL from the facebookresearch repo
DATA_URL = "https://dl.fbaipublicfiles.com/parlai/empatheticdialogues/empatheticdialogues.tar.gz"

# Emotions relevant to dating context (broad)
ROMANCE_EMOTIONS = {
    "caring", "confident", "content",
    "excited", "faithful", "grateful",
    "hopeful", "impressed", "joyful",
    "lonely", "nostalgic", "proud",
    "sentimental", "surprised", "trusting",
    "jealous", "embarrassed", "anxious",
    "nervous", "devastated", "disappointed",
}

# Strictly romance-related
STRICT_ROMANCE = {
    "caring", "faithful", "jealous",
    "lonely", "sentimental", "nostalgic",
}


def main():
    print("Fetching EmpatheticDialogues...")
    resp = requests.get(DATA_URL, timeout=120)
    resp.raise_for_status()

    # Save and extract raw
    raw_dir = RAW_DIR / "empathetic-dialogues"
    raw_dir.mkdir(parents=True, exist_ok=True)
    tar_path = raw_dir / "empatheticdialogues.tar.gz"
    tar_path.write_bytes(resp.content)
    print(f"  Downloaded {len(resp.content) / 1024 / 1024:.1f} MB")

    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(raw_dir)
        names = tar.getnames()
    print(f"  Extracted: {names}")

    # Find train.csv
    train_path = None
    for name in names:
        if "train" in name and name.endswith(".csv"):
            train_path = raw_dir / name
            break
    if not train_path or not train_path.exists():
        print(f"  ERROR: train.csv not found in {names}")
        return

    train_text = train_path.read_text(encoding="utf-8")
    print(f"  Train file: {len(train_text) / 1024:.0f} KB")

    # Parse CSV
    reader = csv.DictReader(io.StringIO(train_text))
    print(f"  Columns: {reader.fieldnames}")

    # Group by conversation ID
    convos = {}
    for row in reader:
        conv_id = row.get("conv_id", "")
        context = row.get("context", "").strip()

        if conv_id not in convos:
            convos[conv_id] = {
                "emotion": context,
                "situation": row.get("prompt", row.get("situation", "")),
                "utterances": [],
            }

        speaker_idx = int(row.get("speaker_idx", 0))
        speaker = "listener" if speaker_idx == 1 else "speaker"
        text = row.get("utterance", "").strip()
        text = text.replace("_comma_", ",")
        if text:
            convos[conv_id]["utterances"].append({"role": speaker, "text": text})

    print(f"  {len(convos)} total conversations")

    # Filter for romance-relevant emotions
    romance_convos = {
        k: v for k, v in convos.items()
        if v["emotion"].lower().strip() in ROMANCE_EMOTIONS
    }
    print(f"  {len(romance_convos)} romance-adjacent conversations")

    records = []
    for conv_id, convo in romance_convos.items():
        if len(convo["utterances"]) < 2:
            continue
        records.append(
            make_record(
                id=f"empathetic-{conv_id}",
                source="huggingface/facebook/empathetic_dialogues",
                platform="crowdsourced",
                messages=convo["utterances"],
                metadata={
                    "emotion": convo["emotion"],
                    "situation": convo["situation"],
                    "original_format": "dialogue",
                    "romance_strict": convo["emotion"].lower().strip() in STRICT_ROMANCE,
                },
            )
        )

    print(f"  {len(records)} multi-turn records")
    write_corpus(records, "empathetic-romance.jsonl")


if __name__ == "__main__":
    main()
