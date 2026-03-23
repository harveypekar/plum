import logging

from . import db

_log = logging.getLogger(__name__)

EMBED_MODEL = "nomic-embed-text"


async def get_fewshot_messages(ollama, messages: list[dict]) -> list[dict]:
    """Retrieve few-shot example messages based on vector similarity to the current conversation.

    Returns a flat list of alternating user/assistant message dicts, or [] on
    any failure (never blocks RP generation).
    """
    try:
        if len(messages) < 2:
            return []

        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), None
        )
        last_assistant = next(
            (m["content"] for m in reversed(messages) if m["role"] == "assistant"), None
        )

        if last_user is None or last_assistant is None:
            return []

        scene_summary = f"{last_user}\n{last_assistant}"

        embedding = await ollama.embed(EMBED_MODEL, scene_summary)

        examples = await db.search_fewshot_examples(embedding, limit=2)

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
