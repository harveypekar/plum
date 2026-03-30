"""Conversation summary generation, prompt building, and response cleaning.

Generates rolling summaries of conversation history so the SummaryBuffer
context strategy can inject them instead of losing older messages entirely.
"""

import logging

from . import db

_log = logging.getLogger("rp.summarize")

SUMMARY_THRESHOLD = 10  # unsummarized messages before triggering


def build_summary_prompt(messages: list[dict], previous_summary: str = "",
                         char_name: str = "Character", user_name: str = "User",
                         ai_personality: str = "") -> str:
    """Build the prompt sent to the LLM to generate/update a rolling conversation summary."""
    history = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    prev_section = ""
    if previous_summary.strip():
        prev_section = (
            "PREVIOUS SUMMARY (update and extend this — keep everything still relevant, "
            "revise anything the new messages change):\n"
            f"{previous_summary.strip()}\n\n"
        )
    personality_hint = ""
    if ai_personality:
        short = ai_personality[:200].rsplit(" ", 1)[0]
        personality_hint = f"{char_name}'s personality: {short}\n\n"
    return (
        f"{prev_section}"
        f"{personality_hint}"
        "Update the story summary based on the new messages below. Preserve:\n"
        "- Key plot events and decisions (what actually happened)\n"
        f"- Emotional trajectory (how {char_name}'s feelings evolved, not just current mood)\n"
        f"- Relationship dynamics between {char_name} and {user_name} (trust, tension, intimacy, conflict)\n"
        f"- Character voice notes (distinctive phrases or mannerisms {char_name} used)\n"
        "- Persistent physical changes (injuries, clothing changes, location shifts)\n"
        "- Promises, plans, unresolved tensions\n"
        f"- What {char_name} wants, what they're avoiding, what they haven't said\n\n"
        "Rules:\n"
        "- Present tense\n"
        "- Be specific — quote distinctive phrases when they matter\n"
        "- Track the emotional arc, not just events\n"
        "- Keep under 400 words\n"
        "- Do NOT narrate or continue the story — just summarize what happened\n\n"
        f"New messages:\n{history}"
    )


def clean_summary_response(raw: str) -> str:
    """Clean up LLM summary output: strip think tags, trim whitespace."""
    clean = raw.strip()
    if "<think>" in clean:
        clean = clean.split("</think>")[-1].strip()
    return clean


async def maybe_generate_summary(
    conv_id: int,
    ollama,
    model: str,
    char_name: str = "Character",
    user_name: str = "User",
    ai_personality: str = "",
) -> dict | None:
    """Generate a summary if enough unsummarized messages have accumulated.

    Returns the saved summary row, or None if no summary was needed.
    """
    messages = await db.get_messages(conv_id)
    if not messages:
        return None

    existing = await db.get_latest_summary(conv_id)
    prev_summary = ""
    prev_through_seq = 0

    if existing:
        prev_summary = existing["summary"]
        prev_through_seq = existing["through_sequence"]

    # Filter to messages after the last summary
    new_msgs = [m for m in messages if m["sequence"] > prev_through_seq]
    if len(new_msgs) < SUMMARY_THRESHOLD:
        return None

    prompt = build_summary_prompt(
        [{"role": m["role"], "content": m["content"]} for m in new_msgs],
        previous_summary=prev_summary,
        char_name=char_name,
        user_name=user_name,
        ai_personality=ai_personality,
    )

    raw = await ollama.generate(
        model=model, prompt=prompt,
        system="Output only the summary. No thinking, no preamble.",
        options={"temperature": 0.3, "num_predict": 600, "think": False},
    )
    summary = clean_summary_response(raw)
    if not summary:
        _log.warning("Empty summary generated for conv %d", conv_id)
        return None

    last_msg = new_msgs[-1]
    token_estimate = len(summary) // 4

    saved = await db.save_summary(
        conv_id,
        summary=summary,
        through_msg_id=last_msg["id"],
        through_sequence=last_msg["sequence"],
        msg_count=len(new_msgs),
        token_estimate=token_estimate,
    )
    _log.info("Generated summary for conv %d (through seq %d, %d msgs, ~%d tokens)",
              conv_id, last_msg["sequence"], len(new_msgs), token_estimate)
    return saved
