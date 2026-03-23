import asyncio
import logging
from typing import Callable
from .context import get_strategy
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

    # Inject scene state into post prompt so it's close to generation
    scene_state = ctx.get("scene_state", "")
    if scene_state.strip():
        ctx["post_prompt"] += "\n\n[Current Scene State — do NOT contradict this]\n" + scene_state.strip()

    return ctx


DEFAULT_PROMPT_TEMPLATE = """## system
{{#scenario}}Scenario: {{scenario}}

{{/scenario}}--- {{char}} (you write as this character) ---
{{#description}}{{description}}

{{/description}}{{#personality}}Personality: {{personality}}

{{/personality}}{{#mes_example}}Example dialogue:
{{mes_example}}

{{/mes_example}}--- {{user}} (do NOT mix their traits with {{char}}'s) ---
{{#user_description}}{{user_description}}

{{/user_description}}{{#user_personality}}Personality: {{user_personality}}

{{/user_personality}}

## post
Write only {{char}}'s next response. Stay in character. Do not narrate {{user}}'s actions.
Each character has distinct physical traits — use the correct details for the correct person. Do not blend or swap attributes between {{char}} and {{user}}.
Vary response length to match the beat — a gut-punch moment can be two lines; a vulnerable confession can breathe longer. Don't default to the same length every time.
Describe bodies naturally when clothing state calls for it — anatomy is not inherently sexual. If a character is undressed, describe what is visible: shape, skin, scars, weight, muscle, breasts, everything. Avoidance is more conspicuous than honesty.
Honor the scene state constraints — if {{char}} is nonverbal or near-mute, replace speech with physical expression and sensory detail: touch, gesture, posture shifts, proximity, textures, smells, temperature, sounds. Characters always participate; they just shift channels from words to body and senses.
Emotions don't reset between messages. If {{char}} was crying, grieving, or in crisis earlier, that bleeds through — sudden silence, laughing too hard at nothing, flinching at a memory, losing focus. Recovery takes the whole conversation, not two exchanges.
{{char}} is NOT a mirror. Do not just reflect praise or affection back at {{user}}. {{char}} has their own perspective, their own unrelated thoughts, things they want to bring up. Deflect, change the subject, sit with it awkwardly — don't just echo kindness back.
Vary the shape of responses. Not every message needs dialogue + action + inner thought. Sometimes just action. Sometimes just words. Sometimes silence. A single sentence is fine if that's the beat.
When {{user}} is vulnerable, {{char}} does NOT respond like a therapist. Real people fumble, project, say the wrong thing, sit in uncomfortable silence. Emotional conversations are messy, not eloquent."""


def _split_template(template: str) -> tuple[str, str]:
    """Split a template into system and post sections."""
    import re
    sections = re.split(r'^## +(system|post)\s*$', template, flags=re.MULTILINE)
    system_part = ""
    post_part = ""
    i = 0
    while i < len(sections):
        if sections[i].strip() == "system" and i + 1 < len(sections):
            system_part = sections[i + 1]
            i += 2
        elif sections[i].strip() == "post" and i + 1 < len(sections):
            post_part = sections[i + 1]
            i += 2
        else:
            if not system_part and not post_part:
                system_part = sections[i]
            i += 1
    return system_part, post_part


def assemble_prompt(ctx: dict) -> dict:
    """Build system_prompt and post_prompt from template + character card data."""
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
    }

    system_part, post_part = _split_template(template)
    ctx["system_prompt"] = render_template(system_part, values)
    ctx["post_prompt"] = render_template(post_part, values) if post_part else ""
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


def apply_context_strategy(ctx: dict) -> dict:
    """Fit messages within token budget using the active strategy."""
    settings = ctx.get("scenario", {}).get("settings", {})
    strategy_name = settings.get("context_strategy", "sliding_window")
    max_tokens = settings.get("max_context_tokens", 6144)

    strategy = get_strategy(strategy_name)
    ctx["messages"] = strategy.fit(ctx["messages"], max_tokens)
    return ctx


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


def inject_tools(ctx: dict) -> dict:
    """Add tool descriptions to the system prompt if MCP tools are available."""
    router = get_router()
    if router.has_tools:
        tool_block = router.get_tool_descriptions()
        ctx["system_prompt"] = ctx.get("system_prompt", "") + "\n\n" + tool_block
    return ctx


def create_default_pipeline() -> Pipeline:
    """Create pipeline with standard hooks."""
    p = Pipeline()
    p.add_pre(assemble_prompt)
    p.add_pre(expand_variables)
    p.add_pre(inject_tools)
    p.add_pre(apply_context_strategy)
    p.add_post(clean_response)
    return p
