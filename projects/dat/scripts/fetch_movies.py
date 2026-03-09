"""Download and normalize romance conversations from Cornell Movie-Dialogs Corpus.

Source: https://www.cs.cornell.edu/~cristian/Cornell_Movie-Dialogs_Corpus.html
Filters to romance genre films only.
"""

import io
import re
import zipfile
from collections import defaultdict

import requests

from normalize import RAW_DIR, make_record, write_corpus

CORPUS_URL = "http://www.cs.cornell.edu/~cristian/data/cornell_movie_dialogs_corpus.zip"

ROMANCE_GENRES = {"romance", "romantic comedy", "rom-com"}


def main():
    print("Fetching Cornell Movie-Dialogs Corpus...")
    resp = requests.get(CORPUS_URL, timeout=60)
    resp.raise_for_status()

    # Save raw
    raw_dir = RAW_DIR / "cornell-movie-dialogs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "corpus.zip"
    raw_path.write_bytes(resp.content)
    print(f"  Saved raw to {raw_path} ({len(resp.content) / 1024 / 1024:.1f} MB)")

    # Extract and parse
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    file_list = z.namelist()
    print(f"  Files in zip: {[f.split('/')[-1] for f in file_list if f.endswith('.txt')]}")

    # Find the right files (path prefix varies)
    def find_file(suffix):
        for f in file_list:
            if f.endswith(suffix):
                return f
        return None

    # Parse movie metadata to find romance movies
    meta_file = find_file("movie_titles_metadata.txt")
    if not meta_file:
        print("  ERROR: movie_titles_metadata.txt not found")
        return

    romance_movie_ids = set()
    meta_text = z.read(meta_file).decode("latin-1")
    for line in meta_text.strip().split("\n"):
        parts = line.split(" +++$+++ ")
        if len(parts) >= 6:
            movie_id = parts[0].strip()
            genres_str = parts[5].strip().lower()
            # Parse genre list like "['romance', 'drama']"
            genres = set(re.findall(r"'(\w[\w\s-]*)'", genres_str))
            if genres & ROMANCE_GENRES:
                romance_movie_ids.add(movie_id)

    print(f"  Found {len(romance_movie_ids)} romance movies")

    # Parse lines (individual utterances)
    lines_file = find_file("movie_lines.txt")
    if not lines_file:
        print("  ERROR: movie_lines.txt not found")
        return

    lines_text = z.read(lines_file).decode("latin-1")
    line_map = {}  # line_id -> {"character": ..., "text": ..., "movie_id": ...}
    for line in lines_text.strip().split("\n"):
        parts = line.split(" +++$+++ ")
        if len(parts) >= 5:
            line_id = parts[0].strip()
            char_id = parts[1].strip()
            movie_id = parts[2].strip()
            char_name = parts[3].strip()
            text = parts[4].strip()
            if movie_id in romance_movie_ids and text:
                line_map[line_id] = {
                    "character": char_name,
                    "text": text,
                    "movie_id": movie_id,
                }

    print(f"  {len(line_map)} lines from romance movies")

    # Parse conversations (sequences of line IDs)
    convos_file = find_file("movie_conversations.txt")
    if not convos_file:
        print("  ERROR: movie_conversations.txt not found")
        return

    convos_text = z.read(convos_file).decode("latin-1")
    records = []
    for line in convos_text.strip().split("\n"):
        parts = line.split(" +++$+++ ")
        if len(parts) >= 4:
            movie_id = parts[2].strip()
            if movie_id not in romance_movie_ids:
                continue
            # Parse line ID list like "['L1', 'L2', 'L3']"
            line_ids = re.findall(r"'(L\d+)'", parts[3])
            messages = []
            for lid in line_ids:
                if lid in line_map:
                    entry = line_map[lid]
                    messages.append({
                        "role": entry["character"],
                        "text": entry["text"],
                    })
            if len(messages) >= 2:
                records.append(
                    make_record(
                        id=f"cornell-romance-{len(records):06d}",
                        source="cornell-movie-dialogs-corpus",
                        platform="movie",
                        messages=messages,
                        metadata={
                            "movie_id": movie_id,
                            "genre": "romance",
                            "original_format": "movie_script",
                        },
                    )
                )

    print(f"  {len(records)} romance conversations")
    write_corpus(records, "movies-romance.jsonl")


if __name__ == "__main__":
    main()
