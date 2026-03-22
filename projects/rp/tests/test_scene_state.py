from projects.rp.scene_state import build_scene_state_prompt, clean_scene_state_response


def _msgs(*pairs):
    """Shorthand: _msgs(("user", "hi"), ("assistant", "hello"))"""
    return [{"role": r, "content": c} for r, c in pairs]


class TestBuildSceneStatePrompt:
    def test_update_instruction_always_present(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "I wave"), ("assistant", "She waves back")),
        )
        assert "UPDATE" in prompt

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
        for cat in ["Location:", "Clothing:", "Restraints:", "Position:", "Props:", "Mood:", "Voice:"]:
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
