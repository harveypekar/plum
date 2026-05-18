from projects.rp.scene_state import (
    build_scene_state_prompt,
    clean_scene_state_response,
    parse_scene_state,
    validate_scene_state,
    _extract_content_words,
    _fix_discarded_clothing,
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

    def test_initial_uses_not_described_instruction(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "Hello")),
            previous_state="",
        )
        assert "write 'not described'" in prompt.lower()

    def test_update_uses_carry_forward_instruction(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "I wave"), ("assistant", "She waves")),
        )
        assert "carry forward" in prompt.lower()
        assert "write 'not described'" not in prompt.lower()

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
        assert "Sol:" in prompt
        sol_line = [ln for ln in prompt.splitlines() if ln.startswith("Sol:")][0]
        assert len(sol_line) <= 130

    def test_no_personality_no_hint(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            ai_personality="",
        )
        before_format = prompt.split("Format")[0]
        assert "Characters:" not in before_format or "AI" in before_format

    def test_user_description_included(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            user_name="Valentina",
            user_description="Valentina is a short woman in her early thirties. She has dark skin.",
        )
        assert "Valentina:" in prompt
        assert "short woman" in prompt

    def test_both_descriptions_included(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            ai_name="Amber",
            ai_personality="Amber has long wavy chestnut hair. She is warm.",
            user_name="Val",
            user_description="Val is a short woman. She has piercings.",
        )
        assert "Amber:" in prompt
        assert "Val:" in prompt

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
        for cat in ["Location:", "'s clothing:", "Restraints:", "Position:", "Props:", "Mood:"]:
            assert cat in prompt

    def test_mood_line_warns_against_sexual_terms(self):
        prompt = build_scene_state_prompt(messages=_msgs(("user", "test")))
        mood_line = [ln for ln in prompt.splitlines() if ln.startswith("Mood:")][0]
        assert "neutral" in mood_line.lower()
        assert "charged" in mood_line.lower()

    def test_per_character_clothing_lines(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            ai_name="Amber",
            user_name="Val",
        )
        assert "Amber's clothing:" in prompt
        assert "Val's clothing:" in prompt
        assert "Clothing:" not in prompt.split("Format")[1].split("Restraints")[0].replace("Amber's clothing", "").replace("Val's clothing", "")


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

    def test_strips_personality_line(self):
        raw = "Location: park\nAmber's personality: warm and caring\nMood: calm"
        result = clean_scene_state_response(raw)
        assert "Location: park" in result
        assert "Mood: calm" in result
        assert "personality" not in result.lower()

    def test_strips_character_and_description_lines(self):
        raw = "Location: park\nCharacter: tall and strong\nDescription: blue eyes"
        result = clean_scene_state_response(raw)
        assert "Location: park" in result
        assert "Character" not in result
        assert "Description" not in result

    def test_strips_background_line(self):
        raw = "Location: park\nBackground: grew up in Italy"
        result = clean_scene_state_response(raw)
        assert "Background" not in result


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

    def test_placeholder_regression_reverted(self):
        old = "Location: park\nClothing: oversized t-shirt, dry socks"
        new = "Location: park\nClothing: not described"
        msgs = _msgs(("user", "she smiled at him"))
        result = validate_scene_state(new, old, msgs)
        assert "oversized t-shirt" in result
        assert "not described" not in result

    def test_placeholder_regression_variants(self):
        for placeholder in ["not mentioned", "not specified", "unknown", "unclear", "n/a", "none"]:
            old = "Clothing: red dress\nLocation: cafe"
            new = f"Clothing: {placeholder}\nLocation: cafe"
            msgs = _msgs(("user", "she sipped coffee"))
            result = validate_scene_state(new, old, msgs)
            assert "red dress" in result, f"Failed to revert placeholder '{placeholder}'"

    def test_empty_new_state_keeps_previous(self):
        old = "Location: park\nClothing: sundress\nMood: happy"
        msgs = _msgs(("user", "hello"))
        result = validate_scene_state("", old, msgs)
        assert result == old

    def test_whitespace_new_state_keeps_previous(self):
        old = "Location: park\nClothing: sundress"
        msgs = _msgs(("user", "hello"))
        result = validate_scene_state("  \n  ", old, msgs)
        assert result == old

    def test_placeholder_without_previous_value_dropped(self):
        old = "Location: park"
        new = "Location: park\nClothing: not described"
        msgs = _msgs(("user", "they walked"))
        result = validate_scene_state(new, old, msgs)
        assert "not described" not in result

    def test_narrative_response_keeps_previous(self):
        old = "Location: park\nClothing: sundress\nMood: happy"
        narrative = "She looked up at the sky and smiled warmly at him."
        msgs = _msgs(("user", "hello"))
        result = validate_scene_state(narrative, old, msgs)
        assert result == old

    def test_initial_narrative_returns_empty(self):
        narrative = "She walked into the room and looked around nervously."
        msgs = _msgs(("user", "hello"))
        result = validate_scene_state(narrative, "", msgs)
        assert result == ""

    def test_discarded_items_removed_from_clothing(self):
        old = "Amber's clothing: tank top\nProps: discarded tank top"
        new = "Amber's clothing: tank top and jeans\nProps: discarded tank top, discarded jeans"
        msgs = _msgs(("user", "she took off her jeans"))
        result = validate_scene_state(new, old, msgs)
        assert "jeans" not in result.split("clothing")[1].split("\n")[0]
        assert "Props" in result

    def test_all_items_discarded_becomes_naked(self):
        state = {
            "Amber's clothing": "tank top and jeans",
            "Props": "discarded tank top, discarded jeans",
        }
        _fix_discarded_clothing(state)
        assert state["Amber's clothing"] == "naked"

    def test_partial_discard_keeps_remaining(self):
        state = {
            "Amber's clothing": "tank top, jeans, boots",
            "Props": "discarded jeans",
        }
        _fix_discarded_clothing(state)
        assert "jeans" not in state["Amber's clothing"]
        assert "tank top" in state["Amber's clothing"]
        assert "boots" in state["Amber's clothing"]

    def test_no_props_no_change(self):
        state = {"Amber's clothing": "tank top and jeans"}
        _fix_discarded_clothing(state)
        assert state["Amber's clothing"] == "tank top and jeans"

    def test_no_discarded_no_change(self):
        state = {
            "Amber's clothing": "tank top",
            "Props": "candles, rope",
        }
        _fix_discarded_clothing(state)
        assert state["Amber's clothing"] == "tank top"


class TestBuildConstraintInstructions:
    def test_restraints_generate_constraint(self):
        from rp.scene_state import build_constraint_instructions
        state = "Location: bedroom\nRestraints: wrists bound behind back — no free hand use"
        result = build_constraint_instructions(state)
        assert "PHYSICAL CONSTRAINT" in result
        assert "wrists bound behind back" in result

    def test_naked_generates_body_instruction(self):
        from rp.scene_state import build_constraint_instructions
        state = "Amber's clothing: naked\nVal's clothing: hoodie"
        result = build_constraint_instructions(state)
        assert "Amber is naked" in result
        assert "Val" not in result

    def test_none_restraints_ignored(self):
        from rp.scene_state import build_constraint_instructions
        state = "Restraints: none\nLocation: park"
        result = build_constraint_instructions(state)
        assert "CONSTRAINT" not in result

    def test_position_generates_instruction(self):
        from rp.scene_state import build_constraint_instructions
        state = "Position: Amber face down on bed, Val sitting beside her"
        result = build_constraint_instructions(state)
        assert "POSITION" in result
        assert "face down" in result

    def test_empty_state_returns_empty(self):
        from rp.scene_state import build_constraint_instructions
        assert build_constraint_instructions("") == ""

    def test_combined_constraints(self):
        from rp.scene_state import build_constraint_instructions
        state = (
            "Restraints: hogtied — wrists and ankles bound, face down\n"
            "Amber's clothing: naked\n"
            "Position: face down on bed"
        )
        result = build_constraint_instructions(state)
        assert "PHYSICAL CONSTRAINT" in result
        assert "naked" in result
        assert "POSITION" in result
