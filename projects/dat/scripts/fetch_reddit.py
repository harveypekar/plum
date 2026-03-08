"""Download and normalize Reddit dating subreddit posts via Arctic Shift API.

Saves incrementally — one JSONL per subreddit, appends on resume.
Tracks last cursor in a .cursor file to support resuming after interruption.
"""

import json
import time

import requests

from normalize import CORPUS_DIR, make_record

API_BASE = "https://arctic-shift.photon-reddit.com/api"

TARGET_SUBREDDITS = ["Tinder", "hingeapp", "Bumble", "OnlineDating", "dating_advice"]

CONVERSATION_KEYWORDS = [
    "conversation", "convo", "chat", "message", "opener",
    "replied", "said", "texted", "matched", "she said", "he said",
    "her:", "him:", "me:", "them:",
]

DEFAULT_MAX_PER_SUB = 2000
MAX_RETRIES = 3


def has_conversation_content(text: str) -> bool:
    """Check if post text likely contains conversation content."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in CONVERSATION_KEYWORDS)


def load_cursor(subreddit: str) -> str | None:
    """Load saved pagination cursor for a subreddit."""
    cursor_file = CORPUS_DIR / f".cursor-{subreddit.lower()}"
    if cursor_file.exists():
        return cursor_file.read_text().strip() or None
    return None


def save_cursor(subreddit: str, cursor: str):
    """Save pagination cursor for resume."""
    cursor_file = CORPUS_DIR / f".cursor-{subreddit.lower()}"
    cursor_file.write_text(cursor)


def count_existing(subreddit: str) -> int:
    """Count existing records in the output file."""
    out_path = CORPUS_DIR / f"reddit-{subreddit.lower()}.jsonl"
    if not out_path.exists():
        return 0
    with open(out_path, encoding="utf-8") as f:
        return sum(1 for _ in f)


def fetch_subreddit(subreddit: str, max_posts: int = DEFAULT_MAX_PER_SUB):
    """Fetch posts from a subreddit, appending to JSONL incrementally."""
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CORPUS_DIR / f"reddit-{subreddit.lower()}.jsonl"

    existing = count_existing(subreddit)
    after = load_cursor(subreddit)

    if after and existing > 0:
        print(f"Resuming r/{subreddit} from cursor {after} ({existing} existing records)")
    else:
        print(f"Fetching r/{subreddit} from scratch...")

    target = existing + max_posts
    total = existing
    page = 0

    with open(out_path, "a", encoding="utf-8") as f:
        while total < target:
            params = {
                "subreddit": subreddit,
                "limit": 100,
                "sort": "asc",
            }
            if after:
                params["after"] = after

            # Retry with backoff
            data = None
            for attempt in range(MAX_RETRIES):
                try:
                    resp = requests.get(f"{API_BASE}/posts/search", params=params, timeout=30)
                    resp.raise_for_status()
                    data = resp.json().get("data", [])
                    break
                except requests.RequestException as e:
                    if attempt < MAX_RETRIES - 1:
                        wait = 2 ** (attempt + 1)
                        print(f"  Error: {e}, retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"  Failed after {MAX_RETRIES} retries: {e}")
                        print(f"  r/{subreddit}: {total} records saved (interrupted)")
                        return total

            if not data:
                break

            page += 1
            batch = 0
            for post in data:
                text = post.get("selftext", "") or ""
                title = post.get("title", "") or ""
                if text in ("[removed]", "[deleted]", ""):
                    text = ""

                full_text = f"{title}\n\n{text}".strip() if text else title.strip()
                if len(full_text) < 50:
                    continue

                if not has_conversation_content(full_text):
                    continue

                metadata = {
                    "subreddit": subreddit.lower(),
                    "original_format": "reddit_post",
                }
                for k in ("score", "num_comments", "created_utc", "link_flair_text", "id"):
                    val = post.get(k)
                    if val is not None:
                        metadata[k] = val

                record = make_record(
                    id=f"arctic-{post.get('id', total)}",
                    source="arctic-shift.photon-reddit.com",
                    platform="reddit",
                    messages=[{"role": "poster", "text": full_text}],
                    metadata=metadata,
                )
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                total += 1
                batch += 1

            # Save cursor after each page
            after = data[-1].get("created_utc")
            save_cursor(subreddit, str(after))

            if page % 10 == 0:
                print(f"  r/{subreddit}: {total} matching posts, page {page}...")
                f.flush()

            time.sleep(0.5)

    print(f"  r/{subreddit}: {total} total matching posts")
    return total


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch Reddit dating subreddit posts")
    parser.add_argument("subreddits", nargs="*", default=TARGET_SUBREDDITS,
                        help="Subreddits to fetch (default: all)")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_PER_SUB,
                        help=f"Max new posts per subreddit (default: {DEFAULT_MAX_PER_SUB})")
    args = parser.parse_args()

    grand_total = 0
    for sub in args.subreddits:
        grand_total += fetch_subreddit(sub, max_posts=args.max)
    print(f"\nDone. {grand_total} total records across {len(args.subreddits)} subreddits.")


if __name__ == "__main__":
    main()
