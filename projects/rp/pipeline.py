import asyncio
import logging
import re
from typing import Callable
from .mcp_client import get_router

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
        if ai_name and ai_name not in scene_state:
            _log.warning("Scene state discarded — references unknown character "
                         "(expected %r, state: %s)", ai_name, scene_state[:120])
            ctx["scene_state"] = ""
        else:
            ctx["post_prompt"] += "\n\n[Current Scene State — do NOT contradict this]\n" + scene_state.strip()

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
When {{user}} is vulnerable, {{char}} does NOT respond like a therapist. Real people fumble, project, say the wrong thing, sit in uncomfortable silence. Emotional conversations are messy, not eloquent."""


STYLE_ITEMS_PER_TURN = 3


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
        "user_pronouns": user_data.get("pronouns", ""),
        "char_pronouns": ai_data.get("pronouns", ""),
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

def clean_response(ctx: dict) -> dict:
    """Strip common LLM artifacts from response."""
    response = ctx.get("response", "")
    response = response.strip()
    # Strip AI name prefix if model echoes it (e.g. "Jessica: ..." or "Jessica Klein: ...")
    ai_name = ctx.get("ai_name", "")
    if ai_name and response.startswith(ai_name):
        after = response[len(ai_name):]
        if after.startswith(": "):
            response = after[2:]
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


def enforce_pronouns(ctx: dict) -> dict:
    """Fix they/them → she/her or he/him when the character has explicit pronouns."""
    pronouns = ctx.get("_char_pronouns", "")
    if not pronouns:
        return ctx

    mapping = _PRONOUN_MAP.get(pronouns.lower().strip())
    if not mapping:
        return ctx

    ai_name = ctx.get("ai_name", "")
    response = ctx.get("response", "")
    if not ai_name or not response:
        return ctx

    sentences = re.split(r'(?<=[.!?…"])\s+', response)
    fixed = []
    name_recent = False
    corrections = 0
    for sent in sentences:
        has_name = ai_name.lower() in sent.lower()
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

    if corrections:
        ctx["response"] = " ".join(fixed)
        ctx["_pronoun_corrections"] = corrections
        _log.info("Fixed %d pronoun(s) for %s (%s)", corrections, ai_name, pronouns)
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
    p.add_pre(assemble_prompt)
    p.add_pre(expand_variables)
    p.add_pre(select_style)
    p.add_pre(inject_tools)
    p.add_post(clean_response)
    p.add_post(enforce_pronouns)
    p.add_post(check_stock_phrases)
    return p
