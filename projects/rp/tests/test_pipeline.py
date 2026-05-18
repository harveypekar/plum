import pytest  # noqa: F401
from projects.rp.pipeline import assemble_prompt, expand_variables, render_template


def _make_ctx(template="", scenario_desc="", ai_desc="", ai_personality="",
              ai_name="Char", user_name="User", user_desc="", messages=None):
    return {
        "user_card": {"card_data": {"data": {"name": user_name, "description": user_desc}}},
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
    assert result["_style_pool"] == []
    assert result["_scene_style_pool"] == []


def test_assemble_with_style_section():
    template = "## system\nSys\n\n## post\nPost\n\n## style\nRule A for {{char}}\n---\nRule B"
    ctx = _make_ctx(template=template, ai_name="Amber")
    result = assemble_prompt(ctx)
    assert result["_style_pool"] == ["Rule A for Amber", "Rule B"]


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
    _split_template, _parse_style_items, _parse_scene_style_items,
    _match_scene_condition, select_style, clean_response,
    check_stock_phrases, enforce_pronouns, detect_pov, _detect_pov_signal,
    Pipeline, STYLE_ITEMS_PER_TURN,
)
from projects.rp.prompt_builder import infer_pronouns  # noqa: E402
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
        sys, post, style, ss = _split_template("## system\nSys content\n\n## post\nPost content")
        assert "Sys content" in sys
        assert "Post content" in post
        assert style == ""
        assert ss == ""

    def test_system_only(self):
        sys, post, style, ss = _split_template("## system\nOnly system")
        assert "Only system" in sys
        assert post == ""
        assert style == ""

    def test_post_only(self):
        sys, post, style, ss = _split_template("## post\nOnly post")
        assert sys == ""
        assert "Only post" in post

    def test_no_markers(self):
        sys, post, style, ss = _split_template("Just plain text")
        assert "Just plain text" in sys
        assert post == ""

    def test_extra_whitespace_in_markers(self):
        sys, post, style, ss = _split_template("##  system\nSys\n\n##  post\nPost")
        assert "Sys" in sys
        assert "Post" in post

    def test_all_three_sections(self):
        tmpl = "## system\nSys\n\n## post\nPost\n\n## style\nStyle A\n---\nStyle B"
        sys, post, style, ss = _split_template(tmpl)
        assert "Sys" in sys
        assert "Post" in post
        assert "Style A" in style
        assert "Style B" in style

    def test_style_without_post(self):
        sys, post, style, ss = _split_template("## system\nSys\n\n## style\nS1\n---\nS2")
        assert "Sys" in sys
        assert post == ""
        assert "S1" in style

    def test_scene_style_section(self):
        tmpl = "## system\nSys\n\n## style\nS1\n\n## scene-style\n[mood=sad]\nBe sad"
        sys, post, style, ss = _split_template(tmpl)
        assert "Sys" in sys
        assert "S1" in style
        assert "[mood=sad]" in ss

    def test_all_four_sections(self):
        tmpl = "## system\nS\n\n## post\nP\n\n## style\nSt\n\n## scene-style\nSS"
        sys, post, style, ss = _split_template(tmpl)
        assert "S" in sys
        assert "P" in post
        assert "St" in style
        assert "SS" in ss


class TestParseStyleItems:
    def test_splits_on_separator(self):
        items = _parse_style_items("Item A\n---\nItem B\n---\nItem C")
        assert items == ["Item A", "Item B", "Item C"]

    def test_empty_string(self):
        assert _parse_style_items("") == []

    def test_single_item(self):
        assert _parse_style_items("Just one rule.") == ["Just one rule."]

    def test_strips_whitespace(self):
        items = _parse_style_items("  A  \n---\n  B  ")
        assert items == ["A", "B"]

    def test_skips_empty_items(self):
        items = _parse_style_items("A\n---\n\n---\nB")
        assert items == ["A", "B"]


class TestSelectStyle:
    def test_appends_to_post_prompt(self):
        ctx = {
            "post_prompt": "Core rules.",
            "_style_pool": ["Style A", "Style B", "Style C", "Style D"],
            "messages": [{"role": "user", "content": "hi"}],
        }
        select_style(ctx)
        assert "Core rules." in ctx["post_prompt"]
        assert "Voice and style:" in ctx["post_prompt"]

    def test_selects_correct_count(self):
        pool = [f"Item {i}" for i in range(12)]
        ctx = {"post_prompt": "", "_style_pool": pool, "messages": []}
        select_style(ctx)
        selected = [item for item in pool if item in ctx["post_prompt"]]
        assert len(selected) == min(STYLE_ITEMS_PER_TURN, len(pool))

    def test_rotates_with_message_count(self):
        pool = [f"Item {i}" for i in range(60)]
        results = []
        for n_msgs in range(6):
            ctx = {"post_prompt": "", "_style_pool": list(pool),
                   "messages": [{}] * n_msgs}
            select_style(ctx)
            selected = [item for item in pool if item in ctx["post_prompt"]]
            results.append(selected)
        # Different message counts should produce different selections
        assert len(set(tuple(r) for r in results)) > 1

    def test_no_pool_leaves_post_unchanged(self):
        ctx = {"post_prompt": "Original.", "_style_pool": [], "messages": []}
        select_style(ctx)
        assert ctx["post_prompt"] == "Original."

    def test_no_pool_key_leaves_post_unchanged(self):
        ctx = {"post_prompt": "Original.", "messages": []}
        select_style(ctx)
        assert ctx["post_prompt"] == "Original."

    def test_small_pool_uses_all(self):
        ctx = {"post_prompt": "", "_style_pool": ["Only one"], "messages": []}
        select_style(ctx)
        assert "Only one" in ctx["post_prompt"]


class TestParseSceneStyleItems:
    def test_basic_condition(self):
        items = _parse_scene_style_items("[restraints]\nShow the limitation.")
        assert len(items) == 1
        assert items[0] == ("restraints", "Show the limitation.", [])

    def test_condition_with_keywords(self):
        items = _parse_scene_style_items("[mood=grieving,crying]\nDon't soften it.")
        assert len(items) == 1
        assert items[0][0] == "mood"
        assert items[0][2] == ["grieving", "crying"]

    def test_multiple_items(self):
        text = "[restraints]\nItem A\n---\n[mood=sad]\nItem B"
        items = _parse_scene_style_items(text)
        assert len(items) == 2
        assert items[0][0] == "restraints"
        assert items[1][0] == "mood"

    def test_empty_string(self):
        assert _parse_scene_style_items("") == []

    def test_skips_items_without_condition(self):
        text = "No condition here\n---\n[mood]\nHas condition"
        items = _parse_scene_style_items(text)
        assert len(items) == 1
        assert items[0][0] == "mood"

    def test_skips_condition_without_body(self):
        items = _parse_scene_style_items("[restraints]")
        assert items == []

    def test_hyphenated_category(self):
        items = _parse_scene_style_items("[scene-mood]\nText here")
        assert items[0][0] == "scene-mood"


class TestMatchSceneCondition:
    def test_category_exists(self):
        assert _match_scene_condition("restraints", [], {"Restraints": "wrists bound"})

    def test_category_missing(self):
        assert not _match_scene_condition("restraints", [], {"Location": "kitchen"})

    def test_keyword_match(self):
        assert _match_scene_condition("mood", ["grieving", "crying"],
                                      {"Mood": "Amber is grieving silently"})

    def test_keyword_no_match(self):
        assert not _match_scene_condition("mood", ["grieving", "crying"],
                                          {"Mood": "calm and relaxed"})

    def test_case_insensitive_category(self):
        assert _match_scene_condition("restraints", [], {"RESTRAINTS": "tied"})

    def test_case_insensitive_value(self):
        assert _match_scene_condition("mood", ["crying"],
                                      {"Mood": "CRYING loudly"})

    def test_empty_scene_state(self):
        assert not _match_scene_condition("mood", [], {})

    def test_partial_keyword_match(self):
        assert _match_scene_condition("voice", ["whisper"],
                                      {"Voice": "barely whispering"})


class TestSelectStyleWithSceneState:
    def test_scene_items_included_when_matching(self):
        ctx = {
            "post_prompt": "",
            "_style_pool": ["General A", "General B", "General C"],
            "_scene_style_pool": [("restraints", "Show limitation", [])],
            "scene_state": "Restraints: wrists bound\nMood: calm",
            "messages": [],
        }
        select_style(ctx)
        assert "Show limitation" in ctx["post_prompt"]
        assert ctx["_matched_scene_styles"] == 1

    def test_scene_items_excluded_when_not_matching(self):
        ctx = {
            "post_prompt": "",
            "_style_pool": ["General A", "General B", "General C"],
            "_scene_style_pool": [("restraints", "Show limitation", [])],
            "scene_state": "Location: kitchen\nMood: calm",
            "messages": [],
        }
        select_style(ctx)
        assert "Show limitation" not in ctx["post_prompt"]
        assert ctx["_matched_scene_styles"] == 0

    def test_keyword_filtered_scene_items(self):
        ctx = {
            "post_prompt": "",
            "_style_pool": ["Gen"],
            "_scene_style_pool": [("mood", "Acute distress", ["grieving", "crying"])],
            "scene_state": "Mood: Amber is grieving",
            "messages": [],
        }
        select_style(ctx)
        assert "Acute distress" in ctx["post_prompt"]

    def test_keyword_filtered_scene_items_no_match(self):
        ctx = {
            "post_prompt": "",
            "_style_pool": ["Gen"],
            "_scene_style_pool": [("mood", "Acute distress", ["grieving", "crying"])],
            "scene_state": "Mood: calm",
            "messages": [],
        }
        select_style(ctx)
        assert "Acute distress" not in ctx["post_prompt"]

    def test_scene_items_added_alongside_general(self):
        ctx = {
            "post_prompt": "",
            "_style_pool": ["Gen A", "Gen B", "Gen C", "Gen D"],
            "_scene_style_pool": [("restraints", "Restraint rule", [])],
            "scene_state": "Restraints: tied",
            "messages": [],
        }
        select_style(ctx)
        assert "Restraint rule" in ctx["post_prompt"]
        general_count = sum(1 for g in ["Gen A", "Gen B", "Gen C", "Gen D"]
                           if g in ctx["post_prompt"])
        assert general_count == min(STYLE_ITEMS_PER_TURN, 4)

    def test_no_scene_pool_works_like_before(self):
        ctx = {
            "post_prompt": "",
            "_style_pool": ["A", "B", "C"],
            "scene_state": "Restraints: tied",
            "messages": [],
        }
        select_style(ctx)
        assert "Voice and style:" in ctx["post_prompt"]

    def test_empty_scene_state_no_scene_items(self):
        ctx = {
            "post_prompt": "",
            "_style_pool": ["Gen"],
            "_scene_style_pool": [("restraints", "Show it", [])],
            "scene_state": "",
            "messages": [],
        }
        select_style(ctx)
        assert "Show it" not in ctx["post_prompt"]

    def test_multiple_scene_items_can_match(self):
        ctx = {
            "post_prompt": "",
            "_style_pool": ["Gen"],
            "_scene_style_pool": [
                ("restraints", "Restraint rule", []),
                ("mood", "Mood rule", ["crying"]),
                ("voice", "Voice rule", ["mute"]),
            ],
            "scene_state": "Restraints: bound\nMood: crying\nVoice: soft",
            "messages": [],
        }
        select_style(ctx)
        assert "Restraint rule" in ctx["post_prompt"]
        assert "Mood rule" in ctx["post_prompt"]
        assert "Voice rule" not in ctx["post_prompt"]
        assert ctx["_matched_scene_styles"] == 2


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


class TestCheckStockPhrases:
    def test_detects_violations(self):
        ctx = {"response": "Her heart pounded in her chest as she looked away."}
        check_stock_phrases(ctx)
        assert "heart pounded in" in ctx["_stock_phrase_violations"]

    def test_no_violations(self):
        ctx = {"response": "She turned away, fingers tight on the mug."}
        check_stock_phrases(ctx)
        assert "_stock_phrase_violations" not in ctx

    def test_multiple_violations(self):
        ctx = {"response": "Her breath caught in her throat. Her pulse quickened."}
        check_stock_phrases(ctx)
        assert len(ctx["_stock_phrase_violations"]) == 2

    def test_case_insensitive(self):
        ctx = {"response": "Her HEART POUNDED IN her chest."}
        check_stock_phrases(ctx)
        assert len(ctx["_stock_phrase_violations"]) == 1


class TestEnforcePronouns:
    def test_fixes_they_to_she(self):
        ctx = {
            "response": "Kasa looked up. They smiled softly.",
            "ai_name": "Kasa",
            "_char_pronouns": "she/her",
        }
        result = enforce_pronouns(ctx)
        assert "She smiled softly" in result["response"]
        assert result["_pronoun_corrections"] == 1

    def test_fixes_them_to_her(self):
        ctx = {
            "response": "Kasa stepped forward and Val reached for them.",
            "ai_name": "Kasa",
            "_char_pronouns": "she/her",
        }
        result = enforce_pronouns(ctx)
        assert "reached for her" in result["response"]

    def test_fixes_their_to_her(self):
        ctx = {
            "response": "Kasa tucked their hair behind their ear.",
            "ai_name": "Kasa",
            "_char_pronouns": "she/her",
        }
        result = enforce_pronouns(ctx)
        assert "her hair" in result["response"]
        assert "her ear" in result["response"]

    def test_fixes_he_him(self):
        ctx = {
            "response": "Marcus crossed the room. They sat down heavily.",
            "ai_name": "Marcus",
            "_char_pronouns": "he/him",
        }
        result = enforce_pronouns(ctx)
        assert "He sat down" in result["response"]

    def test_no_fix_without_pronouns(self):
        ctx = {
            "response": "Kasa looked up. They smiled.",
            "ai_name": "Kasa",
            "_char_pronouns": "",
        }
        result = enforce_pronouns(ctx)
        assert "They smiled" in result["response"]
        assert "_pronoun_corrections" not in result

    def test_no_fix_for_they_them_character(self):
        ctx = {
            "response": "River smiled. They waved goodbye.",
            "ai_name": "River",
            "_char_pronouns": "they/them",
        }
        result = enforce_pronouns(ctx)
        assert "They waved" in result["response"]
        assert "_pronoun_corrections" not in result

    def test_skips_plural_context(self):
        ctx = {
            "response": "Kasa and Val looked at each other. They both laughed.",
            "ai_name": "Kasa",
            "_char_pronouns": "she/her",
        }
        result = enforce_pronouns(ctx)
        assert "They both" in result["response"]

    def test_skips_sentences_without_name_context(self):
        ctx = {
            "response": "The crowd dispersed. They headed home.",
            "ai_name": "Kasa",
            "_char_pronouns": "she/her",
        }
        result = enforce_pronouns(ctx)
        assert "They headed home" in result["response"]

    def test_fixes_continuation_after_name(self):
        ctx = {
            "response": "Kasa stood up slowly. They brushed off their jeans.",
            "ai_name": "Kasa",
            "_char_pronouns": "she/her",
        }
        result = enforce_pronouns(ctx)
        assert "She brushed off her jeans" in result["response"]

    def test_preserves_case_at_sentence_start(self):
        ctx = {
            "response": "Kasa waited. They fidgeted with the hem.",
            "ai_name": "Kasa",
            "_char_pronouns": "she/her",
        }
        result = enforce_pronouns(ctx)
        assert "She fidgeted" in result["response"]

    def test_no_change_when_no_misgendering(self):
        ctx = {
            "response": "Kasa smiled. She tucked her hair back.",
            "ai_name": "Kasa",
            "_char_pronouns": "she/her",
        }
        result = enforce_pronouns(ctx)
        assert result["response"] == "Kasa smiled. She tucked her hair back."
        assert "_pronoun_corrections" not in result


class TestInferPronouns:
    def test_woman_infers_she_her(self):
        assert infer_pronouns("Valentina is a short woman in her early thirties.") == "she/her"

    def test_man_infers_he_him(self):
        assert infer_pronouns("Marcus is a tall man with broad shoulders.") == "he/him"

    def test_female_signals(self):
        assert infer_pronouns("A girl from the countryside, she grew up on a farm.") == "she/her"

    def test_male_signals(self):
        assert infer_pronouns("The boy had always dreamed of adventure. He left home at 16.") == "he/him"

    def test_no_signal_returns_empty(self):
        assert infer_pronouns("A mysterious figure cloaked in shadow.") == ""

    def test_empty_description(self):
        assert infer_pronouns("") == ""

    def test_only_first_200_chars(self):
        desc = "A mysterious figure. " * 20 + "She is actually a woman."
        assert infer_pronouns(desc) == ""

    def test_mixed_signals_majority_wins(self):
        assert infer_pronouns("She is a woman, daughter of a king and wife of a prince.") == "she/her"


class TestEnforcePronounsUserCharacter:
    def test_fixes_user_character_they_to_she(self):
        ctx = {
            "response": "I looked up at Valentina. Their eyes were red from crying.",
            "ai_name": "Amber",
            "_char_pronouns": "she/her",
            "_user_name": "Valentina",
            "_user_pronouns": "she/her",
        }
        result = enforce_pronouns(ctx)
        assert "Her eyes were red" in result["response"]

    def test_fixes_user_character_them_to_her(self):
        ctx = {
            "response": "Valentina pulled me close. I leaned into them gratefully.",
            "ai_name": "Amber",
            "_char_pronouns": "she/her",
            "_user_name": "Valentina",
            "_user_pronouns": "she/her",
        }
        result = enforce_pronouns(ctx)
        assert "leaned into her" in result["response"]

    def test_no_fix_without_user_pronouns(self):
        ctx = {
            "response": "Valentina smiled. They waved.",
            "ai_name": "Amber",
            "_char_pronouns": "she/her",
            "_user_name": "Valentina",
            "_user_pronouns": "",
        }
        result = enforce_pronouns(ctx)
        assert "They waved" in result["response"]

    def test_both_characters_fixed(self):
        ctx = {
            "response": "Amber sighed. They looked at Valentina. They smiled back.",
            "ai_name": "Amber",
            "_char_pronouns": "she/her",
            "_user_name": "Valentina",
            "_user_pronouns": "she/her",
        }
        result = enforce_pronouns(ctx)
        assert "She looked at Valentina" in result["response"]
        assert "She smiled back" in result["response"]

    def test_skips_plural_for_user_character(self):
        ctx = {
            "response": "Valentina and I looked at each other. They both laughed.",
            "ai_name": "Amber",
            "_char_pronouns": "she/her",
            "_user_name": "Valentina",
            "_user_pronouns": "she/her",
        }
        result = enforce_pronouns(ctx)
        assert "They both" in result["response"]


class TestDetectPovSignal:
    def test_first_person_I_start(self):
        assert _detect_pov_signal("I looked up at Valentina.", "Amber") == "first"

    def test_first_person_asterisk_I(self):
        assert _detect_pov_signal("*I sighed heavily.*", "Amber") == "first"

    def test_third_person_name_start(self):
        assert _detect_pov_signal("Amber sighed heavily.", "Amber") == "third"

    def test_third_person_asterisk_name(self):
        assert _detect_pov_signal("*Amber sighed heavily.*", "Amber") == "third"

    def test_ambiguous_returns_none(self):
        assert _detect_pov_signal("The room was dark.", "Amber") is None

    def test_first_person_by_count(self):
        assert _detect_pov_signal("Well, I think I should go. I'm tired.", "Amber") == "first"

    def test_third_person_by_count(self):
        assert _detect_pov_signal("\"Hello,\" Amber said. Amber looked away.", "Amber") == "third"


class TestDetectPov:
    def _make_pov_ctx(self, messages, ai_name="Amber"):
        return {
            "ai_card": {"card_data": {"data": {"name": ai_name}}},
            "messages": messages,
            "post_prompt": "Write next response.",
        }

    def test_detects_first_person(self):
        msgs = [
            {"role": "assistant", "content": "I looked at her."},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "I smiled back."},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "*I shrugged.* 'Fine.'"},
        ]
        ctx = self._make_pov_ctx(msgs)
        result = detect_pov(ctx)
        assert result["_detected_pov"] == "first"
        assert "first person" in result["post_prompt"]

    def test_detects_third_person(self):
        msgs = [
            {"role": "assistant", "content": "*Amber looked at her.*"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "*Amber smiled back.*"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "Amber shrugged. 'Fine.'"},
        ]
        ctx = self._make_pov_ctx(msgs)
        result = detect_pov(ctx)
        assert result["_detected_pov"] == "third"
        assert "third person" in result["post_prompt"]

    def test_no_detection_on_tie(self):
        msgs = [
            {"role": "assistant", "content": "I sighed."},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "*Amber looked up.*"},
        ]
        ctx = self._make_pov_ctx(msgs)
        result = detect_pov(ctx)
        assert "_detected_pov" not in result

    def test_no_detection_with_few_messages(self):
        msgs = [
            {"role": "assistant", "content": "I sighed."},
        ]
        ctx = self._make_pov_ctx(msgs)
        result = detect_pov(ctx)
        assert "_detected_pov" not in result

    def test_no_detection_without_ai_name(self):
        ctx = {
            "ai_card": {"card_data": {"data": {}}},
            "messages": [
                {"role": "assistant", "content": "I sighed."},
                {"role": "assistant", "content": "I looked up."},
            ],
            "post_prompt": "",
        }
        result = detect_pov(ctx)
        assert "_detected_pov" not in result

    def test_only_counts_assistant_messages(self):
        msgs = [
            {"role": "user", "content": "Amber walked in."},
            {"role": "assistant", "content": "I sighed."},
            {"role": "user", "content": "Amber sat down."},
            {"role": "assistant", "content": "*I looked up.*"},
        ]
        ctx = self._make_pov_ctx(msgs)
        result = detect_pov(ctx)
        assert result["_detected_pov"] == "first"


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

    def test_default_template_includes_trait_modulation(self):
        ctx = _make_ctx(template="", ai_name="Amber")
        result = assemble_prompt(ctx)
        assert any("intensity the situation earns" in item for item in result["_style_pool"])

    def test_inferred_pronouns_appear_in_system_prompt(self):
        ctx = _make_ctx(
            template="",
            ai_name="Amber",
            ai_desc="Amber is a tall woman with red hair.",
            user_name="Val",
            user_desc="Val is a short woman with dark curly hair.",
        )
        result = assemble_prompt(ctx)
        assert "she/her" in result["system_prompt"]


class TestCheckRepetition:
    def test_flags_verbatim_duplication(self):
        from rp.pipeline import check_repetition
        prev = "She sighs and leans against the wall, picking at a thread on her sleeve."
        ctx = {
            "response": prev,
            "_recent_assistant_messages": [prev],
        }
        result = check_repetition(ctx)
        assert result.get("_repetition_detected") is True
        assert result["_repetition_overlap"] >= 0.85

    def test_ignores_dissimilar_responses(self):
        from rp.pipeline import check_repetition
        ctx = {
            "response": "She laughed and grabbed the beer off the counter.",
            "_recent_assistant_messages": [
                "The rain hammered against the window as she stared outside.",
            ],
        }
        result = check_repetition(ctx)
        assert "_repetition_detected" not in result

    def test_no_crash_without_recent_messages(self):
        from rp.pipeline import check_repetition
        ctx = {"response": "Hello world."}
        result = check_repetition(ctx)
        assert "_repetition_detected" not in result


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
