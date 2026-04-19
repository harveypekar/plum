"""Tests for the DB-based per-message evaluator."""

from projects.rp.eval.evaluators.message import (
    build_context_for_message,
    get_scoreable_messages,
)


class TestBuildContext:
    def test_builds_context_from_message_row(self):
        msg = {
            "id": 100,
            "conversation_id": 5,
            "role": "assistant",
            "content": "She kicked the door open.",
            "system_prompt": "You are Amber. Be sarcastic.",
            "scene_state": "Living room. Night.",
            "post_prompt": "",
            "sequence": 4,
        }
        history = [
            {"role": "user", "content": "Come in", "sequence": 1},
            {"role": "assistant", "content": "Ugh, fine.", "sequence": 2},
            {"role": "user", "content": "Sit down", "sequence": 3},
        ]
        ctx = build_context_for_message(msg, history)
        assert ctx["system_prompt"] == "You are Amber. Be sarcastic."
        assert ctx["scene_state"] == "Living room. Night."
        assert ctx["assistant_message"] == "She kicked the door open."
        assert ctx["user_message"] == "Sit down"
        assert "Ugh, fine." in ctx["conversation_history"]

    def test_user_message_is_last_user_in_history(self):
        msg = {
            "id": 100,
            "conversation_id": 5,
            "role": "assistant",
            "content": "Response here",
            "system_prompt": "sys",
            "scene_state": "",
            "post_prompt": "",
            "sequence": 6,
        }
        history = [
            {"role": "user", "content": "first", "sequence": 1},
            {"role": "assistant", "content": "reply", "sequence": 2},
            {"role": "user", "content": "second", "sequence": 3},
            {"role": "assistant", "content": "reply2", "sequence": 4},
            {"role": "user", "content": "third", "sequence": 5},
        ]
        ctx = build_context_for_message(msg, history)
        assert ctx["user_message"] == "third"


class TestGetScoreableMessages:
    def test_filters_to_assistant_with_system_prompt(self):
        messages = [
            {"id": 1, "role": "user", "content": "hi", "system_prompt": None, "sequence": 1},
            {"id": 2, "role": "assistant", "content": "hey", "system_prompt": "sys", "sequence": 2},
            {"id": 3, "role": "assistant", "content": "no ctx", "system_prompt": None, "sequence": 3},
        ]
        result = get_scoreable_messages(messages)
        assert len(result) == 1
        assert result[0]["id"] == 2

    def test_empty_input(self):
        assert get_scoreable_messages([]) == []
