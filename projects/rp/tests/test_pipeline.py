import pytest  # noqa: F401
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


from projects.rp.pipeline import (  # noqa: E402
    _split_template, clean_response, Pipeline,
)
import asyncio  # noqa: E402


class TestRenderTemplate:
    def test_simple_substitution(self):
        assert render_template("Hello {{name}}", {"name": "World"}) == "Hello World"

    def test_conditional_section_truthy(self):
        result = render_template("{{#name}}Hi {{name}}{{/name}}", {"name": "Val"})
        assert result == "Hi Val"

    def test_conditional_section_falsy(self):
        result = render_template("{{#name}}Hi {{name}}{{/name}}", {"name": ""})
        assert result == ""

    def test_conditional_section_missing(self):
        result = render_template("{{#name}}Hi {{name}}{{/name}}", {})
        assert result == ""

    def test_multiple_sections(self):
        tmpl = "{{#a}}A:{{a}}{{/a}} {{#b}}B:{{b}}{{/b}}"
        result = render_template(tmpl, {"a": "1", "b": ""})
        assert "A:1" in result
        assert "B:" not in result

    def test_nested_var_in_section(self):
        tmpl = "{{#desc}}Character: {{desc}}\n{{/desc}}{{#user}}Player: {{user}}{{/user}}"
        result = render_template(tmpl, {"desc": "tall", "user": "Val"})
        assert "Character: tall" in result
        assert "Player: Val" in result

    def test_unreferenced_var_left_alone(self):
        result = render_template("{{unknown}} stays", {})
        assert "{{unknown}}" in result

    def test_empty_template(self):
        assert render_template("", {"name": "x"}) == ""

    def test_multiline_section(self):
        tmpl = "{{#bio}}Bio:\n{{bio}}\nEnd{{/bio}}"
        result = render_template(tmpl, {"bio": "A brave warrior"})
        assert "Bio:\nA brave warrior\nEnd" in result


class TestSplitTemplate:
    def test_system_and_post(self):
        sys, post = _split_template("## system\nSys content\n\n## post\nPost content")
        assert "Sys content" in sys
        assert "Post content" in post

    def test_system_only(self):
        sys, post = _split_template("## system\nOnly system")
        assert "Only system" in sys
        assert post == ""

    def test_post_only(self):
        sys, post = _split_template("## post\nOnly post")
        assert sys == ""
        assert "Only post" in post

    def test_no_markers(self):
        sys, post = _split_template("Just plain text")
        assert "Just plain text" in sys
        assert post == ""

    def test_extra_whitespace_in_markers(self):
        sys, post = _split_template("##  system\nSys\n\n##  post\nPost")
        assert "Sys" in sys
        assert "Post" in post


class TestExpandVariables:
    def _ctx(self, system="", post="", scene_state="",
             user_name="User", ai_name="Char", scenario_desc=""):
        return {
            "user_card": {"card_data": {"data": {"name": user_name}}},
            "ai_card": {"card_data": {"data": {"name": ai_name}}},
            "scenario": {"description": scenario_desc},
            "system_prompt": system,
            "post_prompt": post,
            "scene_state": scene_state,
        }

    def test_replaces_user_and_char(self):
        ctx = self._ctx(system="Hi ${user} and ${char}", user_name="Val", ai_name="Jess")
        result = expand_variables(ctx)
        assert result["system_prompt"] == "Hi Val and Jess"

    def test_replaces_scenario(self):
        ctx = self._ctx(system="Scene: ${scenario}", scenario_desc="a park")
        result = expand_variables(ctx)
        assert result["system_prompt"] == "Scene: a park"

    def test_scene_state_injected_into_post(self):
        ctx = self._ctx(post="Stay in character.", scene_state="Location: park\nMood: Char is tense")
        result = expand_variables(ctx)
        assert "Current Scene State" in result["post_prompt"]
        assert "Location: park" in result["post_prompt"]

    def test_empty_scene_state_not_injected(self):
        ctx = self._ctx(post="Stay in character.", scene_state="")
        result = expand_variables(ctx)
        assert "Scene State" not in result["post_prompt"]

    def test_whitespace_only_scene_state_not_injected(self):
        ctx = self._ctx(post="Stay in character.", scene_state="   \n  ")
        result = expand_variables(ctx)
        assert "Scene State" not in result["post_prompt"]

    def test_empty_post_prompt_still_gets_scene_state(self):
        ctx = self._ctx(system="${char} says hi", post="", ai_name="Jess",
                        scene_state="Location: X\nArc: Jess is cautious")
        result = expand_variables(ctx)
        assert result["system_prompt"] == "Jess says hi"
        assert "Location: X" in result["post_prompt"]

    def test_scene_state_discarded_if_wrong_character(self):
        ctx = self._ctx(ai_name="Amber",
                        scene_state="Location: park\nArc: Valentina is nervous")
        result = expand_variables(ctx)
        assert result["scene_state"] == ""
        assert "Scene State" not in result.get("post_prompt", "")


class TestCleanResponse:
    def test_strips_whitespace(self):
        ctx = {"response": "  hello  ", "ai_name": ""}
        assert clean_response(ctx)["response"] == "hello"

    def test_strips_ai_name_prefix(self):
        ctx = {"response": "Jessica: She smiled.", "ai_name": "Jessica"}
        assert clean_response(ctx)["response"] == "She smiled."

    def test_strips_full_name_prefix(self):
        ctx = {"response": "Jessica Klein: She smiled.", "ai_name": "Jessica Klein"}
        assert clean_response(ctx)["response"] == "She smiled."

    def test_no_strip_when_name_is_substring(self):
        ctx = {"response": "Jessica smiled.", "ai_name": "Jessica"}
        assert clean_response(ctx)["response"] == "Jessica smiled."

    def test_no_ai_name(self):
        ctx = {"response": "Hello", "ai_name": ""}
        assert clean_response(ctx)["response"] == "Hello"

    def test_empty_response(self):
        ctx = {"response": "", "ai_name": "Test"}
        assert clean_response(ctx)["response"] == ""


class TestDefaultTemplate:
    def test_default_template_renders_with_full_card(self):
        ctx = _make_ctx(
            template="",
            ai_name="Jessica",
            ai_desc="A painter from Berlin",
            ai_personality="Thoughtful and reserved",
            scenario_desc="Meeting at a gallery",
            user_name="Val",
        )
        ctx["user_card"]["card_data"]["data"]["description"] = "An art collector"
        result = assemble_prompt(ctx)
        # char name appears in post_prompt (DEFAULT_PROMPT_TEMPLATE post section)
        assert "Jessica" in result["post_prompt"]
        assert "painter" in result["system_prompt"]
        assert "gallery" in result["system_prompt"]
        assert result["post_prompt"]

    def test_default_template_omits_empty_sections(self):
        ctx = _make_ctx(template="", ai_name="Sol", ai_desc="", scenario_desc="")
        result = assemble_prompt(ctx)
        assert "Scenario:" not in result["system_prompt"]


class TestPipelineClass:
    def test_pre_hooks_run_in_order(self):
        p = Pipeline()
        log = []
        p.add_pre(lambda ctx: (log.append("a"), ctx)[1])
        p.add_pre(lambda ctx: (log.append("b"), ctx)[1])
        asyncio.run(p.run_pre({}))
        assert log == ["a", "b"]

    def test_post_hooks_run_in_order(self):
        p = Pipeline()
        log = []
        p.add_post(lambda ctx: (log.append("x"), ctx)[1])
        p.add_post(lambda ctx: (log.append("y"), ctx)[1])
        asyncio.run(p.run_post({}))
        assert log == ["x", "y"]

    def test_async_hook(self):
        p = Pipeline()

        async def async_hook(ctx):
            ctx["async_ran"] = True
            return ctx

        p.add_pre(async_hook)
        result = asyncio.run(p.run_pre({}))
        assert result["async_ran"] is True
