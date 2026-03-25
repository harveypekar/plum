from projects.rp.summarize import build_summary_prompt, clean_summary_response


def _msgs(*pairs):
    """Shorthand: _msgs(("user", "hi"), ("assistant", "hello"))"""
    return [{"role": r, "content": c} for r, c in pairs]


class TestBuildSummaryPrompt:
    def test_messages_appear_in_history(self):
        prompt = build_summary_prompt(
            messages=_msgs(("user", "I sit down"), ("assistant", "She looks over")),
        )
        assert "user: I sit down" in prompt
        assert "assistant: She looks over" in prompt

    def test_previous_summary_included(self):
        prompt = build_summary_prompt(
            messages=_msgs(("user", "test")),
            previous_summary="They met at the park. She was nervous.",
        )
        assert "PREVIOUS SUMMARY" in prompt
        assert "They met at the park" in prompt

    def test_no_previous_summary_no_section(self):
        prompt = build_summary_prompt(
            messages=_msgs(("user", "test")),
            previous_summary="",
        )
        assert "PREVIOUS SUMMARY" not in prompt

    def test_character_names_in_prompt(self):
        prompt = build_summary_prompt(
            messages=_msgs(("user", "hi")),
            char_name="Amber",
            user_name="Val",
        )
        assert "Amber" in prompt
        assert "Val" in prompt

    def test_personality_hint_truncated(self):
        long_personality = "X" * 300
        prompt = build_summary_prompt(
            messages=_msgs(("user", "test")),
            ai_personality=long_personality,
            char_name="Sol",
        )
        assert "Sol's personality:" in prompt
        # Truncated to ~200 chars
        hint_line = [line for line in prompt.split("\n") if "Sol's personality:" in line][0]
        assert len(hint_line) < 250

    def test_no_personality_no_hint(self):
        prompt = build_summary_prompt(
            messages=_msgs(("user", "test")),
            ai_personality="",
        )
        assert "personality:" not in prompt.split("Update")[0].lower()

    def test_preservation_rules_present(self):
        prompt = build_summary_prompt(messages=_msgs(("user", "test")))
        assert "Emotional trajectory" in prompt
        assert "Relationship dynamics" in prompt
        assert "Character voice notes" in prompt
        assert "under 400 words" in prompt

    def test_present_tense_instruction(self):
        prompt = build_summary_prompt(messages=_msgs(("user", "test")))
        assert "Present tense" in prompt


class TestCleanSummaryResponse:
    def test_strips_whitespace(self):
        assert clean_summary_response("  summary text  ") == "summary text"

    def test_removes_think_tags(self):
        raw = "<think>reasoning here</think>The story begins at the cafe."
        assert clean_summary_response(raw) == "The story begins at the cafe."

    def test_empty_input(self):
        assert clean_summary_response("") == ""

    def test_only_think_tags(self):
        assert clean_summary_response("<think>blah</think>") == ""

    def test_preserves_multiline_summary(self):
        raw = "Line one.\nLine two.\nLine three."
        result = clean_summary_response(raw)
        assert "Line one." in result
        assert "Line two." in result
        assert "Line three." in result

    def test_handles_nested_think_tags(self):
        raw = "<think>outer<think>inner</think>still thinking</think>Actual summary."
        result = clean_summary_response(raw)
        assert result == "Actual summary."
