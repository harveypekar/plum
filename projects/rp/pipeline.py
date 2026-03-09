import asyncio
from typing import Callable
from .context import get_strategy


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
    return ctx


DEFAULT_PROMPT_TEMPLATE = """{{#scenario}}Scenario: {{scenario}}

{{/scenario}}{{#description}}Character: {{description}}

{{/description}}{{#personality}}Personality: {{personality}}

{{/personality}}{{#mes_example}}Example dialogue:
{{mes_example}}{{/mes_example}}"""


def assemble_prompt(ctx: dict) -> dict:
    """Build system prompt from scenario + character card data."""
    ai_card = ctx.get("ai_card", {})
    scenario = ctx.get("scenario", {})
    user_card = ctx.get("user_card", {})
    ai_data = ai_card.get("card_data", {}).get("data", ai_card.get("card_data", {}))
    user_data = user_card.get("card_data", {}).get("data", user_card.get("card_data", {}))

    # Use template from context (loaded by routes), fall back to default
    template = ctx.get("prompt_template", "") or DEFAULT_PROMPT_TEMPLATE

    values = {
        "scenario": scenario.get("description", ""),
        "description": ai_data.get("description", ""),
        "personality": ai_data.get("personality", ""),
        "mes_example": ai_data.get("mes_example", ""),
        "char": ai_data.get("name", "Character"),
        "user": user_data.get("name", "User"),
    }

    ctx["system_prompt"] = render_template(template, values)
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
    max_tokens = settings.get("max_context_tokens", 2048)

    strategy = get_strategy(strategy_name)
    ctx["messages"] = strategy.fit(ctx["messages"], max_tokens)
    return ctx


# -- Built-in post-processing hooks --

def clean_response(ctx: dict) -> dict:
    """Strip common LLM artifacts from response."""
    response = ctx.get("response", "")
    ctx["response"] = response.strip()
    return ctx


def create_default_pipeline() -> Pipeline:
    """Create pipeline with standard hooks."""
    p = Pipeline()
    p.add_pre(assemble_prompt)
    p.add_pre(expand_variables)
    p.add_pre(apply_context_strategy)
    p.add_post(clean_response)
    return p
