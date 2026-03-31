import asyncio
from unittest.mock import AsyncMock, patch

from projects.rp.summarize import (
    build_summary_prompt,
    clean_summary_response,
    maybe_generate_summary,
)


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


def _db_msg(role, content, msg_id, sequence):
    return {"role": role, "content": content, "id": msg_id, "sequence": sequence,
            "conversation_id": 1, "raw_response": None, "created_at": "2026-01-01"}


def _make_messages(n):
    """Generate n user/assistant message pairs with sequential ids."""
    msgs = []
    for i in range(n):
        msgs.append(_db_msg("user", f"user msg {i}", i * 2 + 1, i * 2 + 1))
        msgs.append(_db_msg("assistant", f"assistant msg {i}", i * 2 + 2, i * 2 + 2))
    return msgs


class TestMaybeGenerateSummary:
    def test_skips_when_below_threshold(self):
        """No summary generated when fewer than SUMMARY_THRESHOLD messages."""
        async def run():
            few_msgs = _make_messages(3)  # 6 messages, below threshold of 10
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=few_msgs)
                mock_db.get_latest_summary = AsyncMock(return_value=None)

                ollama = AsyncMock()
                result = await maybe_generate_summary(1, ollama, "test-model")

                assert result is None
                ollama.generate.assert_not_called()
        asyncio.run(run())

    def test_generates_when_above_threshold(self):
        """Summary generated when enough unsummarized messages exist."""
        async def run():
            msgs = _make_messages(6)  # 12 messages, above threshold
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=msgs)
                mock_db.get_latest_summary = AsyncMock(return_value=None)
                mock_db.save_summary = AsyncMock(return_value={
                    "id": 1, "conversation_id": 1, "summary": "test summary",
                    "through_msg_id": 12, "through_sequence": 12,
                    "msg_count": 12, "token_estimate": 3,
                })

                ollama = AsyncMock()
                ollama.generate = AsyncMock(return_value="Test summary of conversation.")

                result = await maybe_generate_summary(1, ollama, "test-model",
                                                      char_name="Amber", user_name="Val")

                assert result is not None
                ollama.generate.assert_called_once()
                mock_db.save_summary.assert_called_once()
                call_args = mock_db.save_summary.call_args
                assert call_args[1]["through_msg_id"] == 12
                assert call_args[1]["through_sequence"] == 12
                assert call_args[1]["msg_count"] == 12
        asyncio.run(run())

    def test_only_counts_unsummarized_messages(self):
        """Only messages after the last summary count toward the threshold."""
        async def run():
            msgs = _make_messages(8)  # 16 messages total
            existing_summary = {
                "summary": "Previous summary text.",
                "through_sequence": 10,  # summary covers through sequence 10
                "through_msg_id": 10,
            }
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=msgs)
                mock_db.get_latest_summary = AsyncMock(return_value=existing_summary)

                ollama = AsyncMock()
                # 6 messages after sequence 10 (seqs 11-16), below threshold of 10
                result = await maybe_generate_summary(1, ollama, "test-model")

                assert result is None
                ollama.generate.assert_not_called()
        asyncio.run(run())

    def test_includes_previous_summary_in_prompt(self):
        """When extending a summary, the previous summary text is passed to the prompt."""
        async def run():
            msgs = _make_messages(10)  # 20 messages
            existing_summary = {
                "summary": "They met at the park.",
                "through_sequence": 4,  # only covers first 4
                "through_msg_id": 4,
            }
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=msgs)
                mock_db.get_latest_summary = AsyncMock(return_value=existing_summary)
                mock_db.save_summary = AsyncMock(return_value={"id": 2})

                ollama = AsyncMock()
                ollama.generate = AsyncMock(return_value="Extended summary.")

                await maybe_generate_summary(1, ollama, "test-model")

                # Check that the prompt included the previous summary
                call_args = ollama.generate.call_args
                assert "They met at the park" in call_args[1]["prompt"]
        asyncio.run(run())

    def test_skips_on_empty_llm_response(self):
        """Don't save if the LLM returns empty."""
        async def run():
            msgs = _make_messages(6)
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=msgs)
                mock_db.get_latest_summary = AsyncMock(return_value=None)

                ollama = AsyncMock()
                ollama.generate = AsyncMock(return_value="<think>reasoning</think>")

                result = await maybe_generate_summary(1, ollama, "test-model")

                assert result is None
                mock_db.save_summary.assert_not_called()
        asyncio.run(run())

    def test_empty_conversation(self):
        """No crash on empty conversation."""
        async def run():
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=[])

                result = await maybe_generate_summary(1, AsyncMock(), "test-model")
                assert result is None
        asyncio.run(run())
