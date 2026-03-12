import pytest
from projects.rp.pipeline import assemble_prompt, expand_variables, render_template


def _make_ctx(template="", scenario_desc="", ai_desc="", ai_personality="", ai_name="Char", user_name="User", messages=None):
    return {
        "user_card": {"card_data": {"data": {"name": user_name}}},
        "ai_card": {"card_data": {"data": {
            "name": ai_name,
            "description": ai_desc,
            "personality": ai_personality,
            "mes_example": "",
        }}},
        "scenario": {"description": scenario_desc},
        "messages": messages or [],
        "system_prompt": "",
        "prompt_template": template,
    }


def test_assemble_splits_system_and_post():
    template = "## system\nYou are {{char}}.\n\n## post\nStay in character."
    ctx = _make_ctx(template=template, ai_name="Jessica")
    result = assemble_prompt(ctx)
    assert result["system_prompt"] == "You are Jessica."
    assert result["post_prompt"] == "Stay in character."


def test_assemble_no_post_section():
    template = "## system\nYou are {{char}}."
    ctx = _make_ctx(template=template, ai_name="Jessica")
    result = assemble_prompt(ctx)
    assert result["system_prompt"] == "You are Jessica."
    assert result["post_prompt"] == ""


def test_assemble_messages_untouched():
    template = "## system\nHello\n\n## post\nBye"
    msgs = [{"role": "assistant", "content": "Hi"}, {"role": "user", "content": "Hey"}]
    ctx = _make_ctx(template=template, messages=msgs)
    result = assemble_prompt(ctx)
    assert result["messages"] == msgs


def test_assemble_no_mes_history_variable():
    template = "## system\n{{mes_history}}"
    msgs = [{"role": "user", "content": "test"}]
    ctx = _make_ctx(template=template, messages=msgs)
    result = assemble_prompt(ctx)
    assert "test" not in result["system_prompt"]


def test_expand_variables_includes_post_prompt():
    ctx = {
        "user_card": {"card_data": {"data": {"name": "Val"}}},
        "ai_card": {"card_data": {"data": {"name": "Jess"}}},
        "scenario": {"description": "park scene"},
        "system_prompt": "You are ${char}.",
        "post_prompt": "Write ${char}'s reply. Don't narrate ${user}.",
    }
    result = expand_variables(ctx)
    assert result["post_prompt"] == "Write Jess's reply. Don't narrate Val."


def test_default_template_has_system_and_post():
    ctx = _make_ctx(template="", ai_name="Jessica", ai_desc="A painter", scenario_desc="In a park")
    result = assemble_prompt(ctx)
    assert "Jessica" in result["system_prompt"] or "painter" in result["system_prompt"]
    assert result["post_prompt"]
