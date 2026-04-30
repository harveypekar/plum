import logging

from . import db
from .lora_curate import _count_stock_phrases, _trigram_overlap

_log = logging.getLogger(__name__)

EMBED_MODEL = "nomic-embed-text"

DRIFT_STOCK_THRESHOLD = 1
DRIFT_OVERLAP_THRESHOLD = 0.25


def voice_is_drifting(messages: list[dict]) -> bool:
    """Check whether recent assistant messages show voice quality degradation.

    Returns True (inject fewshot) when stock phrases or self-repetition appear,
    False (skip fewshot) when the voice is strong.
    """
    recent = [m["content"] for m in messages if m["role"] == "assistant"][-3:]
    if len(recent) < 3:
        return True

    latest = recent[-1]
    if _count_stock_phrases(latest) >= DRIFT_STOCK_THRESHOLD:
        return True
    if _trigram_overlap(latest, recent[:-1]) > DRIFT_OVERLAP_THRESHOLD:
        return True
    return False


async def get_fewshot_messages(ollama, messages: list[dict],
                               card_id: int | None = None) -> list[dict]:
    """Retrieve few-shot examples by writing-style similarity.

    Embeds the last assistant message only (not user+assistant) so vector
    similarity matches writing voice rather than scene topic.  Skips
    retrieval entirely when recent messages show strong, consistent voice.

    Returns a flat list of alternating user/assistant message dicts, or [] on
    any failure (never blocks RP generation).
    """
    try:
        if len(messages) < 2 or card_id is None:
            return []

        if not voice_is_drifting(messages):
            _log.debug("Voice is strong — skipping fewshot injection")
            return []

        last_assistant = next(
            (m["content"] for m in reversed(messages) if m["role"] == "assistant"), None
        )
        if last_assistant is None:
            return []

        embedding = await ollama.embed(EMBED_MODEL, last_assistant)

        examples = await db.search_fewshot_examples(embedding, card_id, limit=2)

        if not examples:
            return []

        fewshot_msgs = []
        for ex in examples:
            fewshot_msgs.append({"role": "user", "content": ex["user_message"]})
            fewshot_msgs.append({"role": "assistant", "content": ex["assistant_message"]})
        return fewshot_msgs

    except Exception as e:
        _log.warning("Fewshot retrieval failed: %s", e)
        return []
