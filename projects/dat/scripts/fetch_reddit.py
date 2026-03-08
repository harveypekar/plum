"""Download and normalize Reddit dating subreddit posts via Pushshift/HF."""

from datasets import load_dataset

from normalize import make_record, write_corpus

TARGET_SUBREDDITS = {"tinder", "hingeapp", "bumble", "onlinedating", "dating_advice"}

# Keywords suggesting the post contains a conversation
CONVERSATION_KEYWORDS = [
    "conversation", "convo", "chat", "message", "opener",
    "replied", "said", "texted", "matched", "she said", "he said",
    "her:", "him:", "me:", "them:",
]

MAX_POSTS = 50000  # cap to avoid very long downloads


def has_conversation_content(text: str) -> bool:
    """Check if post text likely contains conversation content."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in CONVERSATION_KEYWORDS)


def fetch_pushshift_dating() -> list[dict]:
    """Stream Pushshift Reddit data, filtering for dating subreddits."""
    print("Streaming Pushshift Reddit submissions...")
    print(f"  Target subreddits: {TARGET_SUBREDDITS}")
    print(f"  Max posts: {MAX_POSTS}")

    # Stream to avoid downloading the entire dataset
    ds = load_dataset(
        "fddemarco/pushshift-reddit",
        "submissions",
        split="train",
        streaming=True,
    )

    records = []
    seen = 0
    for row in ds:
        subreddit = (row.get("subreddit") or "").lower()
        if subreddit not in TARGET_SUBREDDITS:
            continue

        text = row.get("selftext", "") or ""
        title = row.get("title", "") or ""
        if text in ("[removed]", "[deleted]", ""):
            text = ""

        full_text = f"{title}\n\n{text}".strip() if text else title.strip()
        if len(full_text) < 50:
            continue

        if not has_conversation_content(full_text):
            continue

        seen += 1
        if seen % 1000 == 0:
            print(f"  Found {seen} posts...")

        metadata = {
            "subreddit": subreddit,
            "original_format": "reddit_post",
        }
        for k in ("score", "num_comments", "created_utc", "link_flair_text", "id"):
            if k in row and row[k]:
                metadata[k] = row[k]

        records.append(
            make_record(
                id=f"pushshift-{row.get('id', seen)}",
                source="huggingface/fddemarco/pushshift-reddit",
                platform="reddit",
                messages=[{"role": "poster", "text": full_text}],
                metadata=metadata,
            )
        )

        if len(records) >= MAX_POSTS:
            print(f"  Reached {MAX_POSTS} cap, stopping.")
            break

    return records


def main():
    records = fetch_pushshift_dating()
    write_corpus(records, "reddit.jsonl")


if __name__ == "__main__":
    main()
