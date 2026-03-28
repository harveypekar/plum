"""Conversation summary prompt building and response cleaning."""


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
