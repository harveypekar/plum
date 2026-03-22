"""Scene state prompt building and response cleaning — extracted for testability."""


def build_scene_state_prompt(messages: list[dict], previous_state: str = "",
                              ai_name: str = "Character", user_name: str = "User",
                              ai_personality: str = "") -> str:
    """Build the prompt sent to the LLM to generate/update scene state."""
    history = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    prev_section = ""
    if previous_state.strip():
        prev_section = (
            "PREVIOUS SCENE STATE (carry forward anything not contradicted by new messages):\n"
            f"{previous_state.strip()}\n\n"
        )
    personality_hint = ""
    if ai_personality:
        short = ai_personality[:200].rsplit(" ", 1)[0]
        personality_hint = f"{ai_name}'s personality: {short}\n\n"
    return (
        f"{prev_section}"
        f"{personality_hint}"
        "Below are the most recent messages. UPDATE the scene state based on what changed.\n"
        "Keep everything from the previous state that still holds true. "
        "Only change what the new messages contradict or add.\n\n"
        f"Characters: {ai_name} (AI) and {user_name} (user).\n\n"
        "Format — one short line per category:\n"
        "Location: (where are they right now)\n"
        f"Clothing: (what {ai_name} and {user_name} are currently wearing — be specific, or 'fully naked' if they undressed)\n"
        "Restraints: (describe the specific tie/pattern for each bound character — e.g. 'chest harness in red jute, wrists behind back' — or 'none')\n"
        "Position: (posture, who is where, physical contact)\n"
        "Props: (objects currently in play)\n"
        "Mood: (emotional atmosphere right now)\n"
        f"Voice: (for each character: 1-2 words describing how they CURRENTLY sound — ground this in {ai_name}'s personality, not generic descriptors)\n\n"
        "No narration, no story, no explanation. Just the current facts.\n\n"
        f"Recent messages:\n{history}"
    )


def clean_scene_state_response(raw: str) -> str:
    """Clean up LLM scene state output: strip think tags, remove empty/none lines."""
    clean = raw.strip()
    if "<think>" in clean:
        clean = clean.split("</think>")[-1].strip()
    lines = []
    for line in clean.splitlines():
        if ":" in line:
            value = line.split(":", 1)[1].strip().lower()
            if value and value != "none" and value != "n/a":
                lines.append(line)
        elif line.strip():
            lines.append(line)
    return "\n".join(lines)
