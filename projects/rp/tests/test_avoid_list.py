"""Tests for inject_avoid_list: phrase repetition + dialect detection."""

from projects.rp.pipeline import inject_avoid_list, _detect_dialect


def _ctx_with_assistant_messages(messages: list[str]) -> dict:
    return {
        "messages": [{"role": "assistant", "content": m} for m in messages],
        "post_prompt": "",
    }


class TestAvoidListThreshold:
    def test_kicks_in_after_two_messages(self):
        ctx = _ctx_with_assistant_messages([
            "Her tongue darted out to wet suddenly dry lips as she shifted.",
            "Her tongue darted out to wet suddenly dry lips nervously.",
        ])
        result = inject_avoid_list(ctx)
        assert result.get("_avoid_list"), "Should detect repeats after 2 messages"

    def test_no_injection_with_one_message(self):
        ctx = _ctx_with_assistant_messages([
            "Her tongue darted out to wet suddenly dry lips as she shifted.",
        ])
        result = inject_avoid_list(ctx)
        assert not result.get("_avoid_list")

    def test_no_injection_when_no_repeats(self):
        ctx = _ctx_with_assistant_messages([
            "She walked to the window and looked outside.",
            "The coffee was cold but she drank it anyway.",
        ])
        result = inject_avoid_list(ctx)
        assert not result.get("_avoid_list")


class TestShortNgrams:
    def test_catches_three_word_repeats(self):
        ctx = _ctx_with_assistant_messages([
            "Her hazel eyes widened as she looked at him.",
            "Her hazel eyes sparkled with mischief.",
            "Her hazel eyes narrowed suspiciously.",
        ])
        result = inject_avoid_list(ctx)
        assert result.get("_avoid_list")
        joined = " ".join(result["_avoid_list"])
        assert "hazel eyes" in joined


class TestDialectDetection:
    def test_detects_dialect_in_single_message(self):
        ctx = _ctx_with_assistant_messages([
            "Whaddya say, newbie? Gonna show me whatcha got?",
        ])
        result = inject_avoid_list(ctx)
        assert result.get("_dialect_violations")
        assert "whaddya" in result["_dialect_violations"]
        assert "gonna" in result["_dialect_violations"]

    def test_dialect_injected_into_post_prompt(self):
        ctx = _ctx_with_assistant_messages([
            "Well ain't that somethin'. Gonna be a wild ride, y'know?",
        ])
        result = inject_avoid_list(ctx)
        assert "dialect" in result["post_prompt"].lower() or "phonetic" in result["post_prompt"].lower()

    def test_no_dialect_for_clean_text(self):
        ctx = _ctx_with_assistant_messages([
            "She smiled and turned to face the window.",
        ])
        result = inject_avoid_list(ctx)
        assert not result.get("_dialect_violations")

    def test_detect_dialect_helper(self):
        words = _detect_dialect(["Gonna be thinkin' about whatcha said"])
        assert "gonna" in words
        assert "thinkin'" in words
        assert "whatcha" in words


class TestCombined:
    def test_both_phrases_and_dialect(self):
        ctx = _ctx_with_assistant_messages([
            "Her tongue darted out to wet suddenly dry lips. Gonna be fun, ain't it?",
            "Her tongue darted out to wet suddenly dry lips. Whatcha thinkin'?",
        ])
        result = inject_avoid_list(ctx)
        assert result.get("_avoid_list")
        assert result.get("_dialect_violations")
        assert "Do NOT reuse" in result["post_prompt"]
        assert "dialect" in result["post_prompt"].lower() or "phonetic" in result["post_prompt"].lower()
