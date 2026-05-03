from projects.rp.scene_state import (
    build_scene_state_prompt,
    clean_scene_state_response,
    parse_scene_state,
    validate_scene_state,
    _extract_content_words,
    _has_evidence,
)


def _msgs(*pairs):
    """Shorthand: _msgs(("user", "hi"), ("assistant", "hello"))"""
    return [{"role": r, "content": c} for r, c in pairs]


class TestBuildSceneStatePrompt:
    def test_update_instruction_for_multi_message(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "I wave"), ("assistant", "She waves back")),
        )
        assert "UPDATE" in prompt
        assert "INITIAL" not in prompt

    def test_initial_instruction_for_single_message(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "Hello")),
            previous_state="",
        )
        assert "INITIAL" in prompt
        assert "UPDATE" not in prompt

    def test_update_instruction_when_previous_state_exists(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "Hello")),
            previous_state="Location: park",
        )
        assert "UPDATE" in prompt
        assert "INITIAL" not in prompt

    def test_scenario_context_included(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            scenario_context="A fantasy tavern at midnight",
        )
        assert "Scenario context: A fantasy tavern at midnight" in prompt

    def test_no_scenario_context_no_section(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            scenario_context="",
        )
        assert "Scenario context:" not in prompt

    def test_previous_state_included(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            previous_state="Location: kitchen\nMood: calm",
        )
        assert "PREVIOUS SCENE STATE" in prompt
        assert "Location: kitchen" in prompt

    def test_no_previous_state_no_section(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            previous_state="",
        )
        assert "PREVIOUS SCENE STATE" not in prompt

    def test_personality_hint_truncated(self):
        long_personality = "X" * 300
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            ai_personality=long_personality,
            ai_name="Sol",
        )
        assert "Sol's personality:" in prompt
        assert len(prompt.split("Sol's personality:")[1].split("\n")[0]) <= 210

    def test_no_personality_no_hint(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            ai_personality="",
        )
        # "personality" should not appear before the format section
        before_format = prompt.split("Format")[0]
        assert "personality:" not in before_format.lower()

    def test_character_names_in_prompt(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "hi")),
            ai_name="Jessica",
            user_name="Val",
        )
        assert "Jessica (AI)" in prompt
        assert "Val (user)" in prompt

    def test_messages_appear_in_history(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "I sit down"), ("assistant", "She looks over")),
        )
        assert "user: I sit down" in prompt
        assert "assistant: She looks over" in prompt

    def test_format_categories_present(self):
        prompt = build_scene_state_prompt(messages=_msgs(("user", "test")))
        for cat in ["Location:", "Clothing:", "Restraints:", "Position:", "Props:", "Mood:"]:
            assert cat in prompt


class TestCleanSceneStateResponse:
    def test_strips_whitespace(self):
        assert clean_scene_state_response("  Location: park  ") == "Location: park"

    def test_removes_think_tags(self):
        raw = "<think>reasoning here</think>Location: park"
        assert clean_scene_state_response(raw) == "Location: park"

    def test_removes_none_lines(self):
        raw = "Location: park\nRestraints: none\nMood: calm"
        result = clean_scene_state_response(raw)
        assert "Location: park" in result
        assert "Mood: calm" in result
        assert "Restraints" not in result

    def test_removes_na_lines(self):
        raw = "Location: park\nProps: n/a"
        result = clean_scene_state_response(raw)
        assert "Props" not in result

    def test_removes_empty_value_lines(self):
        raw = "Location: park\nRestraints: \nMood: calm"
        result = clean_scene_state_response(raw)
        assert "Restraints" not in result

    def test_keeps_non_category_lines(self):
        raw = "Location: park\nSome extra context"
        result = clean_scene_state_response(raw)
        assert "Some extra context" in result

    def test_empty_input(self):
        assert clean_scene_state_response("") == ""

    def test_only_think_tags(self):
        assert clean_scene_state_response("<think>blah</think>") == ""

    def test_preserves_restraint_with_detail(self):
        raw = "Restraints: wrists behind back — no free hand use"
        result = clean_scene_state_response(raw)
        assert "wrists behind back" in result


class TestParseSceneState:
    def test_basic_parsing(self):
        state = "Location: kitchen\nClothing: red dress\nMood: calm"
        parsed = parse_scene_state(state)
        assert parsed == {"Location": "kitchen", "Clothing": "red dress", "Mood": "calm"}

    def test_empty_string(self):
        assert parse_scene_state("") == {}

    def test_preserves_category_casing(self):
        parsed = parse_scene_state("Location: park\nPROPS: candles")
        assert "Location" in parsed
        assert "PROPS" in parsed

    def test_colon_in_value(self):
        parsed = parse_scene_state("Position: sitting across from each other: at the table")
        assert parsed["Position"] == "sitting across from each other: at the table"


class TestExtractContentWords:
    def test_removes_stopwords(self):
        words = _extract_content_words("the cat is on the mat")
        assert "the" not in words
        assert "cat" in words
        assert "mat" in words

    def test_removes_short_words(self):
        words = _extract_content_words("go up in at")
        assert len(words) == 0

    def test_lowercase(self):
        words = _extract_content_words("Big ANGRY Dog")
        assert "big" in words
        assert "angry" in words
        assert "dog" in words


class TestHasEvidence:
    def test_exact_match(self):
        assert _has_evidence({"naked"}, {"naked", "then", "walked"})

    def test_no_match(self):
        assert not _has_evidence({"candles", "wine"}, {"dinner", "talking", "smiled"})

    def test_substring_match(self):
        assert _has_evidence({"undress"}, {"undressed", "slowly"})

    def test_reverse_substring(self):
        assert _has_evidence({"unbuttoned"}, {"unbutton", "shirt"})

    def test_short_words_skip_substring(self):
        assert not _has_evidence({"red"}, {"bored", "covered"})


class TestValidateSceneState:
    def test_no_previous_state_returns_unmodified(self):
        new = "Location: park\nClothing: naked"
        result = validate_scene_state(new, "", _msgs(("user", "hello")))
        assert result == new

    def test_unchanged_categories_kept(self):
        old = "Location: kitchen\nMood: calm"
        new = "Location: kitchen\nMood: tense"
        result = validate_scene_state(new, old, _msgs(("user", "test")))
        assert "Location: kitchen" in result

    def test_clothing_hallucination_reverted(self):
        old = "Location: kitchen\nClothing: red dress"
        new = "Location: kitchen\nClothing: naked"
        msgs = _msgs(("user", "I talk about dinner"), ("assistant", "She smiles and nods"))
        result = validate_scene_state(new, old, msgs)
        assert "Clothing: red dress" in result

    def test_clothing_change_with_evidence_kept(self):
        old = "Location: bedroom\nClothing: pajamas"
        new = "Location: bedroom\nClothing: naked"
        msgs = _msgs(("user", "She slowly undresses"),
                      ("assistant", "She slips out of her pajamas, now naked"))
        result = validate_scene_state(new, old, msgs)
        assert "naked" in result

    def test_prop_hallucination_reverted(self):
        old = "Location: park\nProps: picnic blanket"
        new = "Location: park\nProps: candles and wine glasses"
        msgs = _msgs(("user", "We sit on the blanket"), ("assistant", "She stretches out"))
        result = validate_scene_state(new, old, msgs)
        assert "picnic blanket" in result
        assert "candles" not in result

    def test_prop_change_with_evidence_kept(self):
        old = "Location: park\nProps: picnic blanket"
        new = "Location: park\nProps: picnic blanket, guitar"
        msgs = _msgs(("user", "I pull out my guitar"))
        result = validate_scene_state(new, old, msgs)
        assert "guitar" in result

    def test_mood_always_kept(self):
        old = "Mood: calm"
        new = "Mood: electrified with anticipation"
        msgs = _msgs(("user", "I wave"))
        result = validate_scene_state(new, old, msgs)
        assert "electrified" in result

    def test_voice_always_kept(self):
        old = "Voice: soft"
        new = "Voice: sharp and clipped"
        msgs = _msgs(("user", "I wave"))
        result = validate_scene_state(new, old, msgs)
        assert "sharp" in result

    def test_location_hallucination_reverted(self):
        old = "Location: kitchen\nClothing: jeans"
        new = "Location: bedroom\nClothing: jeans"
        msgs = _msgs(("user", "I grab a glass of water"))
        result = validate_scene_state(new, old, msgs)
        assert "Location: kitchen" in result

    def test_location_change_with_evidence_kept(self):
        old = "Location: kitchen"
        new = "Location: bedroom"
        msgs = _msgs(("user", "Let's go to the bedroom"),
                      ("assistant", "She follows you into the bedroom"))
        result = validate_scene_state(new, old, msgs)
        assert "Location: bedroom" in result

    def test_new_category_without_evidence_dropped(self):
        old = "Location: kitchen"
        new = "Location: kitchen\nRestraints: wrists tied behind back"
        msgs = _msgs(("user", "I pour some coffee"))
        result = validate_scene_state(new, old, msgs)
        assert "Restraints" not in result

    def test_new_category_with_evidence_kept(self):
        old = "Location: kitchen"
        new = "Location: kitchen\nRestraints: wrists tied behind back"
        msgs = _msgs(("user", "I tie her wrists behind her back"))
        result = validate_scene_state(new, old, msgs)
        assert "wrists" in result

    def test_substring_evidence_supports_change(self):
        old = "Clothing: blouse and skirt"
        new = "Clothing: unbuttoned blouse and skirt"
        msgs = _msgs(("assistant", "She slowly unbuttons her blouse"))
        result = validate_scene_state(new, old, msgs)
        assert "unbuttoned" in result

    def test_rewording_without_new_content_kept(self):
        old = "Position: sitting on the sofa"
        new = "Position: seated on the sofa"
        msgs = _msgs(("user", "I smile at her"))
        result = validate_scene_state(new, old, msgs)
        assert "seated" in result or "sitting" in result

    def test_multiple_categories_mixed(self):
        old = "Location: park\nClothing: sundress\nMood: happy"
        new = "Location: park\nClothing: bikini\nMood: flirty"
        msgs = _msgs(("user", "The sun is nice today"))
        result = validate_scene_state(new, old, msgs)
        assert "sundress" in result
        assert "flirty" in result
        assert "bikini" not in result
