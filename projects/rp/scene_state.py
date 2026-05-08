"""Scene state prompt building, response cleaning, and hallucination validation."""

import logging
import re

_log = logging.getLogger("rp.scene_state")

_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "out",
    "off", "over", "under", "again", "then", "once", "here", "there",
    "when", "where", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "just", "and", "but", "or",
    "if", "while", "that", "this", "these", "those", "it", "its",
    "her", "his", "they", "them", "their", "she", "he", "him", "we",
    "us", "our", "you", "your", "my", "me", "currently", "right",
    "now", "still", "also", "about", "up", "down",
})

_SKIP_VALIDATION = frozenset({"mood", "voice"})

_STRIP_CATEGORIES = frozenset({"personality", "character", "background", "description"})

_PLACEHOLDER_PATTERNS = frozenset({
    "not described", "not mentioned", "not specified", "not stated",
    "unknown", "unclear", "n/a", "none",
})


def _first_sentence(text: str) -> str:
    """Extract the first sentence from a description, capped at 120 chars."""
    if not text:
        return ""
    end = text.find(". ")
    if end == -1:
        end = text.find(".\n")
    if end == -1:
        end = len(text)
    return text[:min(end + 1, 120)].strip()


def build_scene_state_prompt(messages: list[dict], previous_state: str = "",
                              ai_name: str = "Character", user_name: str = "User",
                              ai_personality: str = "",
                              user_description: str = "",
                              scenario_context: str = "") -> str:
    """Build the prompt sent to the LLM to generate/update scene state."""
    history = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    prev_section = ""
    if previous_state.strip():
        prev_section = (
            "PREVIOUS SCENE STATE (carry forward anything not contradicted by new messages):\n"
            f"{previous_state.strip()}\n\n"
        )
    char_hints = []
    if ai_personality:
        char_hints.append(f"{ai_name}: {_first_sentence(ai_personality)}")
    if user_description:
        char_hints.append(f"{user_name}: {_first_sentence(user_description)}")
    char_section = ""
    if char_hints:
        char_section = "\n".join(char_hints) + "\n\n"
    scenario_section = ""
    if scenario_context.strip():
        scenario_section = f"Scenario context: {scenario_context.strip()}\n\n"
    initial = not previous_state.strip() and len(messages) <= 1
    if initial:
        instruction = (
            "This is the opening of a new scene. Establish the INITIAL scene state "
            "based on the scenario context and first message below.\n\n"
        )
    else:
        instruction = (
            "Below are the most recent messages. UPDATE the scene state based on what changed.\n"
            "Keep everything from the previous state that still holds true. "
            "Only change what the new messages contradict or add.\n\n"
        )
    clothing_instruction = (
        "For EACH character's clothing: if that character's clothing is not explicitly described in the messages, write 'not described'. "
        "Do NOT copy one character's clothing to the other. Do NOT guess.\n"
        if initial else
        "If a character's clothing is not mentioned in the new messages, carry forward from the previous state unchanged.\n"
    )
    return (
        f"{prev_section}"
        f"{char_section}"
        f"{scenario_section}"
        f"{instruction}"
        f"Characters: {ai_name} (AI) and {user_name} (user).\n\n"
        "Format — one short line per category:\n"
        "Location: (where are they right now)\n"
        f"{ai_name}'s clothing: (what {ai_name} is wearing RIGHT NOW — track removals: if they undressed, write 'naked')\n"
        f"{user_name}'s clothing: (what {user_name} is wearing RIGHT NOW — track removals: if they undressed, write 'naked')\n"
        "Restraints: (describe the specific tie/pattern AND what it practically limits — e.g. 'wrists behind back — no free hand use' — or 'none')\n"
        "Position: (posture, who is where, physical contact)\n"
        "Props: (objects currently in play)\n"
        "Mood: (what characters feel right now — use neutral terms; avoid sexually-charged words like 'charged' or 'electric' unless characters are explicitly intimate)\n"
        "ONLY state facts explicitly shown or described in the messages. Do NOT invent or assume details not present.\n"
        f"{clothing_instruction}"
        "No narration, no story, no explanation. Just the current facts.\n\n"
        f"Recent messages:\n{history}"
    )


def clean_scene_state_response(raw: str) -> str:
    """Clean up LLM scene state output: strip think tags, remove empty/none lines,
    and remove non-scene categories the LLM may parrot from the prompt."""
    clean = raw.strip()
    if "<think>" in clean:
        clean = clean.split("</think>")[-1].strip()
    lines = []
    for line in clean.splitlines():
        if ":" in line:
            cat = line.split(":", 1)[0].strip()
            cat_key = cat.lower().split("'s ")[-1] if "'s " in cat.lower() else cat.lower()
            if cat_key in _STRIP_CATEGORIES:
                continue
            value = line.split(":", 1)[1].strip().lower()
            if value and value != "none" and value != "n/a":
                lines.append(line)
        elif line.strip():
            lines.append(line)
    return "\n".join(lines)


def parse_scene_state(state: str) -> dict[str, str]:
    """Parse scene state text into {category_label: value} dict."""
    result: dict[str, str] = {}
    for line in state.strip().splitlines():
        if ":" in line:
            cat, val = line.split(":", 1)
            key = cat.strip()
            if key:
                result[key] = val.strip()
    return result


def _extract_content_words(text: str) -> set[str]:
    """Extract meaningful words (3+ chars, no stopwords) from text."""
    return {w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in _STOPWORDS}


def _has_evidence(new_words: set[str], msg_words: set[str]) -> bool:
    """Check if any new word has a match in message words.

    Matches on: exact equality, substring containment (4+ chars),
    or shared prefix of 6+ chars (handles conjugation like unbuttons/unbuttoned).
    """
    if new_words & msg_words:
        return True
    for nw in new_words:
        if len(nw) < 4:
            continue
        for mw in msg_words:
            if len(mw) < 4:
                continue
            if nw in mw or mw in nw:
                return True
            if len(nw) >= 5 and len(mw) >= 5:
                prefix = min(len(nw), len(mw), 6)
                if nw[:prefix] == mw[:prefix]:
                    return True
    return False


def validate_scene_state(
    new_state: str,
    previous_state: str,
    messages: list[dict],
) -> str:
    """Revert scene state categories that changed without evidence in messages."""
    if not previous_state.strip():
        if not parse_scene_state(new_state):
            _log.info("Initial scene state has no valid categories, returning empty")
            return ""
        return new_state

    if not new_state.strip():
        _log.info("Empty scene state response, keeping previous state")
        return previous_state

    new = parse_scene_state(new_state)
    if not new:
        _log.info("No valid categories in scene state response, keeping previous state")
        return previous_state

    old = parse_scene_state(previous_state)

    msg_text = " ".join(m.get("content", "") for m in messages)
    msg_words = _extract_content_words(msg_text)

    validated: dict[str, str] = {}

    for cat, new_val in new.items():
        cat_key = cat.lower()
        if cat_key in _SKIP_VALIDATION:
            validated[cat] = new_val
            continue

        old_val = old.get(cat, "")
        if not old_val:
            for ok, ov in old.items():
                if ok.lower() == cat_key:
                    old_val = ov
                    break

        if new_val.lower() == old_val.lower():
            validated[cat] = new_val
            continue

        if old_val and new_val.lower().strip() in _PLACEHOLDER_PATTERNS:
            _log.info(
                "Reverted scene state [%s]: %r -> %r (placeholder regression)",
                cat, old_val, new_val,
            )
            validated[cat] = old_val
            continue

        new_words = _extract_content_words(new_val)
        old_words = _extract_content_words(old_val) if old_val else set()
        added_words = new_words - old_words

        if not added_words or _has_evidence(added_words, msg_words):
            validated[cat] = new_val
        else:
            _log.info(
                "Reverted scene state [%s]: %r -> %r (no evidence; words: %s)",
                cat, old_val, new_val, added_words,
            )
            if old_val:
                validated[cat] = old_val

    _fix_discarded_clothing(validated)
    return "\n".join(f"{cat}: {val}" for cat, val in validated.items())


def _fix_discarded_clothing(state: dict[str, str]) -> None:
    """Remove items from clothing lines if they appear as 'discarded' in props."""
    props_val = ""
    for cat, val in state.items():
        if cat.lower() == "props":
            props_val = val.lower()
            break
    if not props_val:
        return

    discarded = set()
    for part in re.findall(r"discarded\s+([a-z][a-z\s]*?)(?:,|$)", props_val):
        discarded.update(w for w in part.strip().split() if len(w) >= 3)

    if not discarded:
        return

    for cat in list(state.keys()):
        if "clothing" not in cat.lower():
            continue
        val = state[cat]
        val_lower = val.lower()
        if any(d in val_lower for d in discarded):
            cleaned_parts = []
            for item in re.split(r",\s*|;\s*|\s+and\s+", val):
                item_lower = item.strip().lower()
                if not any(d in item_lower for d in discarded):
                    cleaned_parts.append(item.strip())
            if cleaned_parts:
                state[cat] = ", ".join(cleaned_parts)
            else:
                state[cat] = "naked"
            if state[cat].lower() != val_lower:
                _log.info(
                    "Fixed clothing [%s]: %r -> %r (items listed as discarded in props)",
                    cat, val, state[cat],
                )
