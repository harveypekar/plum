"""Download and normalize Reddit dating subreddit posts via Arctic Shift API."""

import time

import requests

from normalize import make_record, write_corpus

API_BASE = "https://arctic-shift.photon-reddit.com/api"

TARGET_SUBREDDITS = ["Tinder", "hingeapp", "Bumble", "OnlineDating", "dating_advice"]

CONVERSATION_KEYWORDS = [
    "conversation", "convo", "chat", "message", "opener",
    "replied", "said", "texted", "matched", "she said", "he said",
    "her:", "him:", "me:", "them:",
]

MAX_POSTS_PER_SUB = 10000


def has_conversation_content(text: str) -> bool:
    """Check if post text likely contains conversation content."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in CONVERSATION_KEYWORDS)


def fetch_subreddit(subreddit: str) -> list[dict]:
    """Fetch posts from a subreddit via Arctic Shift API, paginating by date."""
    print(f"Fetching r/{subreddit}...")
    records = []
    after = None  # pagination cursor (created_utc)
    page = 0

    while len(records) < MAX_POSTS_PER_SUB:
        params = {
            "subreddit": subreddit,
            "limit": 100,
            "sort": "asc",
        }
        if after:
            params["after"] = after

        resp = requests.get(f"{API_BASE}/posts/search", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        if not data:
            break

        page += 1
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

            records.append(
                make_record(
                    id=f"arctic-{post.get('id', len(records))}",
                    source="arctic-shift.photon-reddit.com",
                    platform="reddit",
                    messages=[{"role": "poster", "text": full_text}],
                    metadata=metadata,
                )
            )

        # Paginate using the last post's created_utc
        after = data[-1].get("created_utc")
        if page % 10 == 0:
            print(f"  r/{subreddit}: {len(records)} matching posts, page {page}...")

        # Be polite to the API
        time.sleep(0.5)

    print(f"  r/{subreddit}: {len(records)} total matching posts")
    return records


def main():
    import sys

    # Accept optional subreddit filter: python fetch_reddit.py Tinder hingeapp
    subs = sys.argv[1:] if len(sys.argv) > 1 else TARGET_SUBREDDITS

    for sub in subs:
        records = fetch_subreddit(sub)
        write_corpus(records, f"reddit-{sub.lower()}.jsonl")


if __name__ == "__main__":
    main()
