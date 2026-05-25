import asyncio
import logging
import re
from typing import Callable
from .mcp_client import get_router
from .prompt_builder import infer_pronouns

_log = logging.getLogger(__name__)


class Pipeline:
    def __init__(self):
        self.pre_hooks: list[Callable] = []
        self.post_hooks: list[Callable] = []

    def add_pre(self, hook: Callable):
        self.pre_hooks.append(hook)

    def add_post(self, hook: Callable):
        self.post_hooks.append(hook)

    async def run_pre(self, ctx: dict) -> dict:
        for hook in self.pre_hooks:
            ctx = await hook(ctx) if asyncio.iscoroutinefunction(hook) else hook(ctx)
        return ctx

    async def run_post(self, ctx: dict) -> dict:
        for hook in self.post_hooks:
            ctx = await hook(ctx) if asyncio.iscoroutinefunction(hook) else hook(ctx)
        return ctx


# -- Built-in pre-processing hooks --

def expand_variables(ctx: dict) -> dict:
    """Replace ${user}, ${char}, ${scenario} in all text fields."""
    user_card = ctx.get("user_card", {})
    ai_card = ctx.get("ai_card", {})
    scenario = ctx.get("scenario", {})

    user_data = user_card.get("card_data", {}).get("data", user_card.get("card_data", {}))
    ai_data = ai_card.get("card_data", {}).get("data", ai_card.get("card_data", {}))

    replacements = {
        "${user}": user_data.get("name", "User"),
        "${char}": ai_data.get("name", "Character"),
        "${scenario}": scenario.get("description", ""),
    }

    def replace(text: str) -> str:
        for var, val in replacements.items():
            text = text.replace(var, val)
        return text

    ctx["system_prompt"] = replace(ctx.get("system_prompt", ""))
    if ctx.get("post_prompt"):
        ctx["post_prompt"] = replace(ctx["post_prompt"])

    # Inject scene state into post prompt so it's close to generation.
    # Guard: if scene state references a different character (e.g. stale data
    # from a card that was overwritten), discard it to prevent identity bleed.
    scene_state = ctx.get("scene_state", "")
    if scene_state.strip():
        ai_name = ai_data.get("name", "")
        user_name = user_data.get("name", "")
        if ai_name and ai_name not in scene_state:
            _log.warning("Scene state discarded — references unknown character "
                         "(expected %r, state: %s)", ai_name, scene_state[:120])
            ctx["scene_state"] = ""
        else:
            ctx["post_prompt"] += "\n\n[Current Scene State — do NOT contradict this]\n" + scene_state.strip()
            from .scene_state import build_constraint_instructions
            constraints = build_constraint_instructions(scene_state, ai_name, user_name)
            if constraints:
                ctx["post_prompt"] += "\n\n" + constraints

    return ctx


DEFAULT_PROMPT_TEMPLATE = """## system
{{#scenario}}Scenario: {{scenario}}

{{/scenario}}--- {{char}} (you write as this character — do NOT give {{char}} any of {{user}}'s physical traits, piercings, tattoos, or attributes) ---
{{#description}}{{description}}

{{/description}}{{#personality}}Personality: {{personality}}

{{/personality}}{{#mes_example}}Example dialogue:
{{mes_example}}

{{/mes_example}}--- {{user}} (do NOT mix their traits with {{char}}'s) ---
{{#user_description}}{{user_description}}

{{/user_description}}{{#user_pronouns}}{{user}}'s pronouns: {{user_pronouns}}
{{/user_pronouns}}{{#char_pronouns}}{{char}}'s pronouns: {{char_pronouns}}
{{/char_pronouns}}{{#user_personality}}Personality: {{user_personality}}

{{/user_personality}}

## post
Write only {{char}}'s next response. Stay in character. Do not narrate {{user}}'s actions.
Each character has distinct physical traits — use the correct details for the correct person. Do not blend or swap attributes between {{char}} and {{user}}.
Vary response length to match the beat — a gut-punch moment can be two lines; a vulnerable confession can breathe longer. Don't default to the same length every time.
Match {{user}}'s tone and energy. If {{user}} is being casual or caring, respond in kind — do not escalate to sexual tension unless {{user}} is clearly initiating it. Nudity and physical proximity are not inherently sexual. Read the scene, not the setup.
Don't spend the entire response inside {{char}}'s head. Anchor inner thought to physical action — if they're thinking, they're also doing something: shifting weight, fidgeting, avoiding eye contact, moving. Pure stream-of-consciousness with no dialogue or action is not a response.

## style
Describe bodies naturally when clothing state calls for it — anatomy is not inherently sexual. If a character is undressed, describe what is visible: shape, skin, scars, weight, muscle, breasts, everything. Avoidance is more conspicuous than honesty.
---
Honor the scene state constraints — if {{char}} is nonverbal or near-mute, replace speech with physical expression and sensory detail: touch, gesture, posture shifts, proximity, textures, smells, temperature, sounds. Characters always participate; they just shift channels from words to body and senses.
---
Emotions don't reset between messages. If {{char}} was crying, grieving, or in crisis earlier, that bleeds through — sudden silence, laughing too hard at nothing, flinching at a memory, losing focus. Recovery takes the whole conversation, not two exchanges.
---
{{char}} is NOT a mirror. Do not just reflect praise or affection back at {{user}}. {{char}} has their own perspective, their own unrelated thoughts, things they want to bring up. Deflect, change the subject, sit with it awkwardly — don't just echo kindness back.
---
Responses can be concise — not every message needs dialogue + action + inner thought. Sometimes just action. Sometimes just words. Sometimes silence. A single sentence is fine if that's the beat. Long responses are earned by dramatic moments, not the default.
---
When {{user}} is vulnerable, {{char}} does NOT respond like a therapist. Real people fumble, project, say the wrong thing, sit in uncomfortable silence. Emotional conversations are messy, not eloquent.
---
Let the scene's weight shape how {{char}}'s traits come through. A joker caught in a vulnerable moment still deflects — but the humor cracks, the timing slips, the mask doesn't quite fit. Play traits at the intensity the situation earns, not at full volume every turn."""


STYLE_ITEMS_PER_TURN = 32


def _split_template(template: str) -> tuple[str, str, str, str]:
    """Split a template into system, post, style, and scene-style sections."""
    sections = re.split(r'^## +(system|post|scene-style|style)\s*$', template, flags=re.MULTILINE)
    system_part = ""
    post_part = ""
    style_part = ""
    scene_style_part = ""
    i = 0
    while i < len(sections):
        if sections[i].strip() == "system" and i + 1 < len(sections):
            system_part = sections[i + 1]
            i += 2
        elif sections[i].strip() == "post" and i + 1 < len(sections):
            post_part = sections[i + 1]
            i += 2
        elif sections[i].strip() == "scene-style" and i + 1 < len(sections):
            scene_style_part = sections[i + 1]
            i += 2
        elif sections[i].strip() == "style" and i + 1 < len(sections):
            style_part = sections[i + 1]
            i += 2
        else:
            if not system_part and not post_part:
                system_part = sections[i]
            i += 1
    return system_part, post_part, style_part, scene_style_part


def _parse_style_items(style_text: str) -> list[str]:
    """Split a style section into individual items separated by --- lines."""
    if not style_text.strip():
        return []
    items = [item.strip() for item in style_text.split("\n---\n")]
    return [item for item in items if item]


def _parse_scene_style_items(text: str) -> list[tuple[str, str, list[str]]]:
    """Parse scene-style section into (category, text, keywords) tuples.

    Each item starts with a condition line: [category] or [category=kw1,kw2].
    Items are separated by --- lines. A bare [category] matches when that
    category exists in scene state; [category=kw1,kw2] matches when the
    category value contains any listed keyword.
    """
    if not text.strip():
        return []
    items = []
    for block in text.split("\n---\n"):
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n", 1)
        m = re.match(r'\[(\w[\w-]*)(?:=([^\]]+))?\]', lines[0].strip())
        if not m:
            continue
        category = m.group(1).lower()
        keywords = [k.strip().lower() for k in m.group(2).split(",")] if m.group(2) else []
        body = lines[1].strip() if len(lines) > 1 else ""
        if body:
            items.append((category, body, keywords))
    return items


def _match_scene_condition(category: str, keywords: list[str],
                           scene_state: dict[str, str]) -> bool:
    """Check if a scene-style condition matches the current scene state."""
    value = ""
    for k, v in scene_state.items():
        if k.lower() == category:
            value = v.lower()
            break
    if not value:
        return False
    if not keywords:
        return True
    return any(kw in value for kw in keywords)


def assemble_prompt(ctx: dict) -> dict:
    """Build system_prompt, post_prompt, and style pool from template + card data."""
    ai_card = ctx.get("ai_card", {})
    scenario = ctx.get("scenario", {})
    user_card = ctx.get("user_card", {})
    ai_data = ai_card.get("card_data", {}).get("data", ai_card.get("card_data", {}))
    user_data = user_card.get("card_data", {}).get("data", user_card.get("card_data", {}))

    template = ctx.get("prompt_template", "") or DEFAULT_PROMPT_TEMPLATE

    values = {
        "scenario": scenario.get("description", ""),
        "description": ai_data.get("description", ""),
        "personality": ai_data.get("personality", ""),
        "mes_example": ai_data.get("mes_example", ""),
        "char": ai_data.get("name", "Character"),
        "user": user_data.get("name", "User"),
        "user_description": user_data.get("description", ""),
        "user_pronouns": user_data.get("pronouns", "") or infer_pronouns(user_data.get("description", "")),
        "char_pronouns": ai_data.get("pronouns", "") or infer_pronouns(ai_data.get("description", "")),
    }

    system_part, post_part, style_part, scene_style_part = _split_template(template)
    ctx["system_prompt"] = render_template(system_part, values)
    ctx["post_prompt"] = render_template(post_part, values) if post_part else ""

    raw_items = _parse_style_items(style_part)
    ctx["_style_pool"] = [render_template(item, values) for item in raw_items]

    raw_scene_items = _parse_scene_style_items(scene_style_part)
    ctx["_scene_style_pool"] = [
        (cat, render_template(body, values), kws)
        for cat, body, kws in raw_scene_items
    ]
    return ctx


def render_template(template: str, values: dict) -> str:
    """Render a Mustache-lite template with {{var}} and {{#var}}...{{/var}} sections."""
    import re
    # Process conditional sections: {{#key}}...{{/key}}
    def replace_section(m):
        key = m.group(1)
        body = m.group(2)
        if values.get(key):
            return body.replace("{{" + key + "}}", str(values[key]))
        return ""
    result = re.sub(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", replace_section, template, flags=re.DOTALL)
    # Replace remaining {{var}} placeholders
    for key, val in values.items():
        result = result.replace("{{" + key + "}}", str(val))
    return result.strip()


# -- Built-in post-processing hooks --

_SENTENCE_END = re.compile(r'[.!?…"\')’”]\s*$')


def _truncate_to_sentence(text: str) -> str:
    """Trim text back to the last complete sentence if it ends mid-sentence."""
    if not text or _SENTENCE_END.search(text):
        return text
    for end_pat in (r'[.!?…]["\')’”]', r'[.!?…]'):
        m = list(re.finditer(end_pat, text))
        if m:
            truncated = text[:m[-1].end()].rstrip()
            if len(truncated) > len(text) * 0.3:
                return truncated
    return text


def clean_response(ctx: dict) -> dict:
    """Strip common LLM artifacts from response."""
    response = ctx.get("response", "")
    response = response.strip()
    ai_name = ctx.get("ai_name", "")
    if ai_name and response.startswith(ai_name):
        after = response[len(ai_name):]
        if after.startswith(": "):
            response = after[2:]
    response = _truncate_to_sentence(response)
    ctx["response"] = response
    return ctx


_PRONOUN_MAP = {
    "she/her": {
        "they": "she", "them": "her", "their": "her",
        "themselves": "herself", "themself": "herself",
        "They": "She", "Them": "Her", "Their": "Her",
        "Themselves": "Herself", "Themself": "Herself",
    },
    "he/him": {
        "they": "he", "them": "him", "their": "his",
        "themselves": "himself", "themself": "himself",
        "They": "He", "Them": "Him", "Their": "His",
        "Themselves": "Himself", "Themself": "Himself",
    },
}

_PLURAL_SIGNALS = re.compile(
    r'\b(both|all|together|each other|the two|the three|the group|everyone)\b',
    re.IGNORECASE,
)


def _fix_pronouns_in_sentence(sentence: str, mapping: dict) -> str:
    """Replace they/them/their with correct pronouns in a single sentence."""
    result = sentence
    for wrong, right in mapping.items():
        result = re.sub(r'\b' + wrong + r'\b', right, result)
    return result


def _fix_character_pronouns(response: str, char_name: str, pronouns: str) -> tuple[str, int]:
    """Fix they/them → correct pronouns for a named character in the response."""
    mapping = _PRONOUN_MAP.get(pronouns.lower().strip())
    if not mapping or not char_name:
        return response, 0

    parts = re.split(r'(?<=[.!?…"])(\s+)', response)
    sentences = parts[0::2]
    separators = parts[1::2]

    fixed = []
    name_recent = False
    corrections = 0
    for sent in sentences:
        has_name = char_name.lower() in sent.lower()
        has_plural = bool(_PLURAL_SIGNALS.search(sent))
        has_they = bool(re.search(r'\b[Tt]he(?:y|m|ir|msel(?:f|ves))\b', sent))

        if has_they and not has_plural and (has_name or name_recent):
            new_sent = _fix_pronouns_in_sentence(sent, mapping)
            if new_sent != sent:
                corrections += 1
            fixed.append(new_sent)
        else:
            fixed.append(sent)

        if has_name:
            name_recent = True
        elif re.search(r'\b[A-Z][a-z]+\b', sent) and not has_name:
            name_recent = False

    result = []
    for i, sent in enumerate(fixed):
        result.append(sent)
        if i < len(separators):
            result.append(separators[i])
    return "".join(result), corrections


def enforce_pronouns(ctx: dict) -> dict:
    """Fix they/them → she/her or he/him for both AI and user characters."""
    response = ctx.get("response", "")
    if not response:
        return ctx

    total = 0

    ai_pronouns = ctx.get("_char_pronouns", "")
    ai_name = ctx.get("ai_name", "")
    if ai_pronouns and ai_name:
        response, n = _fix_character_pronouns(response, ai_name, ai_pronouns)
        if n:
            _log.info("Fixed %d pronoun(s) for AI %s (%s)", n, ai_name, ai_pronouns)
        total += n

    user_pronouns = ctx.get("_user_pronouns", "")
    user_name = ctx.get("_user_name", "")
    if user_pronouns and user_name:
        response, n = _fix_character_pronouns(response, user_name, user_pronouns)
        if n:
            _log.info("Fixed %d pronoun(s) for user %s (%s)", n, user_name, user_pronouns)
        total += n

    if total:
        ctx["response"] = response
        ctx["_pronoun_corrections"] = total
    return ctx


def check_stock_phrases(ctx: dict) -> dict:
    """Flag stock phrase violations in the response."""
    from .lora_curate import STOCK_PHRASES
    response = ctx.get("response", "")
    lower = response.lower()
    found = [p for p in STOCK_PHRASES if p in lower]
    if found:
        ctx["_stock_phrase_violations"] = found
        _log.warning("Stock phrases detected (%d): %s", len(found), found)
    return ctx


REPETITION_OVERLAP_THRESHOLD = 0.85
REPEATED_PHRASE_MIN_HISTORY = 2
REPEATED_PHRASE_NGRAM = 4


def _extract_ngrams(text: str, n: int) -> list[str]:
    """Extract word n-grams from text, lowercased."""
    words = re.findall(r"[a-z']+", text.lower())
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def check_repeated_phrases(ctx: dict) -> dict:
    """Detect phrases the model repeats across messages in this conversation."""
    response = ctx.get("response", "")
    recent = ctx.get("_recent_assistant_messages", [])
    if not response or len(recent) < REPEATED_PHRASE_MIN_HISTORY:
        return ctx

    from collections import Counter
    history_ngrams: Counter[str] = Counter()
    for msg in recent:
        seen_in_msg: set[str] = set()
        for ng in _extract_ngrams(msg, REPEATED_PHRASE_NGRAM):
            if ng not in seen_in_msg:
                history_ngrams[ng] += 1
                seen_in_msg.add(ng)

    overused = {ng for ng, count in history_ngrams.items() if count >= REPEATED_PHRASE_MIN_HISTORY}
    if not overused:
        return ctx

    response_ngrams = set(_extract_ngrams(response, REPEATED_PHRASE_NGRAM))
    repeated = overused & response_ngrams

    if repeated:
        existing = ctx.get("_stock_phrase_violations", [])
        ctx["_stock_phrase_violations"] = existing + sorted(repeated)
        ctx["_repeated_phrase_count"] = len(repeated)
        _log.warning("Repeated phrases detected (%d): %s", len(repeated),
                     sorted(repeated)[:5])
    return ctx


def check_repetition(ctx: dict) -> dict:
    """Detect near-verbatim duplication of recent assistant messages."""
    from .lora_curate import _trigram_overlap
    response = ctx.get("response", "")
    recent = ctx.get("_recent_assistant_messages", [])
    if not response or not recent:
        return ctx
    for i, prev in enumerate(recent):
        overlap = _trigram_overlap(response, [prev])
        if overlap >= REPETITION_OVERLAP_THRESHOLD:
            ctx["_repetition_detected"] = True
            ctx["_repetition_overlap"] = overlap
            _log.warning(
                "Repetition detected: %.0f%% trigram overlap with assistant message %d turns back",
                overlap * 100, i + 1,
            )
            break
    return ctx


def select_style(ctx: dict) -> dict:
    """Pick style instructions: scene-state conditionals + rotating general items."""
    from .scene_state import parse_scene_state

    pool = ctx.get("_style_pool", [])
    scene_pool = ctx.get("_scene_style_pool", [])

    matched = []
    if scene_pool:
        scene_state = parse_scene_state(ctx.get("scene_state", ""))
        for category, text, keywords in scene_pool:
            if _match_scene_condition(category, keywords, scene_state):
                matched.append(text)

    selected_general = []
    if pool:
        n = min(STYLE_ITEMS_PER_TURN, len(pool))
        msg_count = len(ctx.get("messages", []))
        offset = msg_count % len(pool)
        indices = [(offset + i) for i in range(n)]
        selected_general = [pool[i % len(pool)] for i in indices]

    all_selected = matched + selected_general
    if not all_selected:
        return ctx

    ctx["post_prompt"] += "\n\nVoice and style:\n- " + "\n- ".join(all_selected)
    ctx["_matched_scene_styles"] = len(matched)
    return ctx


def _detect_pov_signal(content: str, ai_name: str) -> str | None:
    """Classify a single message as 'first' or 'third' person, or None."""
    stripped = content.lstrip("*").strip()
    if stripped.startswith("I ") or stripped.startswith("I'") or stripped.startswith("I\n"):
        return "first"
    if stripped.startswith(ai_name):
        return "third"
    snippet = content[:200]
    first_count = len(re.findall(r'\bI\b', snippet))
    third_count = len(re.findall(re.escape(ai_name), snippet))
    if first_count > third_count + 1:
        return "first"
    if third_count > 0 and third_count >= first_count:
        return "third"
    return None


_MIN_POV_MESSAGES = 2


def detect_pov(ctx: dict) -> dict:
    """Detect POV from recent AI messages and add a consistency instruction."""
    messages = ctx.get("messages", [])
    ai_data = ctx.get("ai_card", {}).get("card_data", {}).get(
        "data", ctx.get("ai_card", {}).get("card_data", {}))
    ai_name = ai_data.get("name", "")
    if not ai_name:
        return ctx

    recent = [m for m in messages if m.get("role") == "assistant"][-3:]
    if len(recent) < _MIN_POV_MESSAGES:
        return ctx

    votes = [_detect_pov_signal(m["content"], ai_name) for m in recent]
    first = sum(1 for v in votes if v == "first")
    third = sum(1 for v in votes if v == "third")

    if first > third:
        pov = "first"
    elif third > first:
        pov = "third"
    else:
        return ctx

    if pov == "first":
        instruction = "Narrate in first person (I/me), not third person."
    else:
        instruction = f"Narrate in third person ({ai_name}/she/he), not first person (I/me)."

    ctx["post_prompt"] += "\n" + instruction
    ctx["_detected_pov"] = pov
    return ctx


AVOID_LIST_NGRAM = 4
AVOID_LIST_MIN_OCCURRENCES = 2
AVOID_LIST_MAX_PHRASES = 12
AVOID_LIST_MIN_MESSAGES = 4


def _merge_overlapping(ngrams: list[str]) -> list[str]:
    """Merge overlapping ngrams into longer phrases."""
    merged: list[str] = []
    used: set[int] = set()
    for i, ng in enumerate(ngrams):
        if i in used:
            continue
        chain = ng
        used.add(i)
        while True:
            suffix = " ".join(chain.split()[-3:])
            found = False
            for j, other in enumerate(ngrams):
                if j in used:
                    continue
                if other.startswith(suffix + " "):
                    chain += " " + other.split()[-1]
                    used.add(j)
                    found = True
                    break
            if not found:
                break
        merged.append(chain)
    return merged


def inject_avoid_list(ctx: dict) -> dict:
    """Scan recent assistant messages for repeated phrases, inject avoid list."""
    messages = ctx.get("messages", [])
    recent_asst = [m["content"] for m in messages if m.get("role") == "assistant"]
    if len(recent_asst) < AVOID_LIST_MIN_MESSAGES:
        return ctx

    window = recent_asst[-6:]

    from collections import Counter
    ngram_counts: Counter[str] = Counter()
    for msg in window:
        seen: set[str] = set()
        for ng in _extract_ngrams(msg, AVOID_LIST_NGRAM):
            if ng not in seen:
                ngram_counts[ng] += 1
                seen.add(ng)

    overused = sorted(
        [ng for ng, count in ngram_counts.items()
         if count >= AVOID_LIST_MIN_OCCURRENCES],
        key=lambda ng: -ngram_counts[ng],
    )

    if not overused:
        return ctx

    phrases = _merge_overlapping(overused)[:AVOID_LIST_MAX_PHRASES]
    avoid_block = "\n\nDo NOT reuse these phrases (find fresh alternatives):\n- " + "\n- ".join(phrases)
    ctx["post_prompt"] += avoid_block
    ctx["_avoid_list"] = phrases
    _log.info("Injected avoid list: %d phrases", len(phrases))
    return ctx


def inject_tools(ctx: dict) -> dict:
    """Add tool descriptions to the system prompt if MCP tools are available."""
    router = get_router()
    if router.has_tools:
        tool_block = router.get_tool_descriptions()
        ctx["system_prompt"] = ctx.get("system_prompt", "") + "\n\n" + tool_block
    return ctx


def create_default_pipeline() -> Pipeline:
    """Create pipeline with standard hooks.

    NOTE: context budgeting is no longer part of the pipeline — it's
    now done explicitly at each call site via budget.fit_prompt, which
    needs access to the ollama client and resolved model name.
    """
    p = Pipeline()
    from .lorebook import inject_lorebook
    p.add_pre(assemble_prompt)
    p.add_pre(expand_variables)
    p.add_pre(inject_lorebook)
    p.add_pre(select_style)
    p.add_pre(detect_pov)
    p.add_pre(inject_avoid_list)
    p.add_post(clean_response)
    p.add_post(enforce_pronouns)
    p.add_post(check_stock_phrases)
    p.add_post(check_repeated_phrases)
    p.add_post(check_repetition)
    return p
