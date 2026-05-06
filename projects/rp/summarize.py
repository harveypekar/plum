"""Hierarchical conversation summary generation.

Generates rolling summaries that fill available budget space. Instead of
fixed-size 600-token summaries every 10 messages, summaries scale to fill
the space that dropped messages would have occupied. On each overflow,
the previous summary + newly-overflowing messages are re-summarized into
a new summary of the same target size.
"""

import logging

from . import db
from .tokenizer import count_tokens

_log = logging.getLogger("rp.summarize")

SUMMARY_MODEL = "q8"
RECENT_WINDOW = 8
MIN_UNSUMMARIZED = 4


def _target_words(target_tokens: int) -> int:
    """Rough token→word conversion for the prompt instruction."""
    return max(200, int(target_tokens * 0.7))


def build_summary_prompt(messages: list[dict], previous_summary: str = "",
                         char_name: str = "Character", user_name: str = "User",
                         ai_personality: str = "",
                         target_tokens: int = 600) -> str:
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
    word_limit = _target_words(target_tokens)
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
        f"- Target approximately {word_limit} words\n"
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
    resolve_model=None,
    messages_budget: int = 0,
) -> dict | None:
    """Generate a summary when conversation messages exceed available budget.

    Trigger: when unsummarized messages outside the recent window exceed
    the space remaining after the recent window is accounted for.

    The summary targets filling the available space so the model always
    operates with a full context window.
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

    new_msgs = [m for m in messages if m["sequence"] > prev_through_seq]
    if len(new_msgs) < MIN_UNSUMMARIZED:
        return None

    recent = messages[-RECENT_WINDOW:] if len(messages) > RECENT_WINDOW else messages
    recent_tokens = sum(count_tokens(m["content"]) for m in recent)

    if messages_budget <= 0:
        messages_budget = 13000

    available_for_summary = messages_budget - recent_tokens
    if available_for_summary < 400:
        return None

    older = messages[:-RECENT_WINDOW] if len(messages) > RECENT_WINDOW else []
    unsummarized_older = [m for m in older if m["sequence"] > prev_through_seq]

    if not unsummarized_older and not prev_summary:
        return None

    unsummarized_tokens = sum(count_tokens(m["content"]) for m in unsummarized_older)
    prev_summary_tokens = count_tokens(prev_summary) if prev_summary else 0
    total_older_content = unsummarized_tokens + prev_summary_tokens

    if total_older_content <= available_for_summary:
        return None

    target_tokens = min(available_for_summary, 8000)
    target_tokens = max(target_tokens, 400)

    prompt = build_summary_prompt(
        [{"role": m["role"], "content": m["content"]} for m in unsummarized_older],
        previous_summary=prev_summary,
        char_name=char_name,
        user_name=user_name,
        ai_personality=ai_personality,
        target_tokens=target_tokens,
    )

    summary_model = resolve_model(SUMMARY_MODEL) if resolve_model else model
    raw = await ollama.generate(
        model=summary_model, prompt=prompt,
        system="Output only the summary. No thinking, no preamble.",
        options={"temperature": 0.3, "num_predict": target_tokens, "think": False},
    )
    summary = clean_summary_response(raw)
    if not summary:
        _log.warning("Empty summary generated for conv %d", conv_id)
        return None

    last_summarized = unsummarized_older[-1] if unsummarized_older else messages[-RECENT_WINDOW - 1]
    token_estimate = count_tokens(summary)

    saved = await db.save_summary(
        conv_id,
        summary=summary,
        through_msg_id=last_summarized["id"],
        through_sequence=last_summarized["sequence"],
        msg_count=len(unsummarized_older),
        token_estimate=token_estimate,
    )
    _log.info(
        "Generated summary for conv %d (through seq %d, %d msgs, ~%d tokens, target=%d, model=%s)",
        conv_id, last_summarized["sequence"], len(unsummarized_older),
        token_estimate, target_tokens, summary_model,
    )
    return saved
