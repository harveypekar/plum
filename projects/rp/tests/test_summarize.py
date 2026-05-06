import asyncio
from unittest.mock import AsyncMock, patch

from projects.rp.summarize import (
    SUMMARY_MODEL,
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

    def test_target_tokens_scales_word_limit(self):
        prompt_small = build_summary_prompt(
            messages=_msgs(("user", "test")), target_tokens=600)
        prompt_large = build_summary_prompt(
            messages=_msgs(("user", "test")), target_tokens=4000)
        # Extract the word targets
        assert "420 words" in prompt_small
        assert "2800 words" in prompt_large

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


def _make_long_messages(n):
    """Generate messages with varied content that tokenizes realistically."""
    base = "The character walked through the scene and spoke with feeling about what happened. "
    msgs = []
    for i in range(n):
        content = f"Turn {i}: " + base * 5 + f" End of turn {i}."
        msgs.append(_db_msg("user", content, i * 2 + 1, i * 2 + 1))
        msgs.append(_db_msg("assistant", content, i * 2 + 2, i * 2 + 2))
    return msgs


class TestMaybeGenerateSummary:
    def test_skips_when_below_min_unsummarized(self):
        """No summary when fewer than MIN_UNSUMMARIZED new messages."""
        async def run():
            few_msgs = _make_messages(1)  # 2 messages, below MIN_UNSUMMARIZED
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=few_msgs)
                mock_db.get_latest_summary = AsyncMock(return_value=None)

                ollama = AsyncMock()
                result = await maybe_generate_summary(1, ollama, "test-model",
                                                      messages_budget=100)
                assert result is None
                ollama.generate.assert_not_called()
        asyncio.run(run())

    def test_skips_when_older_messages_fit(self):
        """No summary when older messages fit within available budget."""
        async def run():
            msgs = _make_messages(8)  # 16 messages, recent_window=8 leaves 8 older
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=msgs)
                mock_db.get_latest_summary = AsyncMock(return_value=None)

                ollama = AsyncMock()
                # Large budget — everything fits
                result = await maybe_generate_summary(1, ollama, "test-model",
                                                      messages_budget=120000)
                assert result is None
                ollama.generate.assert_not_called()
        asyncio.run(run())

    def test_generates_when_older_messages_overflow(self):
        """Summary generated when older messages exceed available budget."""
        async def run():
            msgs = _make_long_messages(10)  # 20 long messages
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

                # Small budget forces overflow
                result = await maybe_generate_summary(1, ollama, "test-model",
                                                      char_name="Amber", user_name="Val",
                                                      messages_budget=1200)

                assert result is not None
                ollama.generate.assert_called_once()
                mock_db.save_summary.assert_called_once()
        asyncio.run(run())

    def test_summarizes_only_older_messages(self):
        """Summary covers messages before the recent window, not all messages."""
        async def run():
            msgs = _make_long_messages(10)  # 20 messages
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=msgs)
                mock_db.get_latest_summary = AsyncMock(return_value=None)
                mock_db.save_summary = AsyncMock(return_value={"id": 1})

                ollama = AsyncMock()
                ollama.generate = AsyncMock(return_value="Summary.")

                await maybe_generate_summary(1, ollama, "test-model",
                                              messages_budget=1200)

                call_args = mock_db.save_summary.call_args[1]
                # 20 messages total, RECENT_WINDOW=8, older=12
                # through_sequence should be the last older message
                assert call_args["through_sequence"] == 12
                assert call_args["msg_count"] == 12
        asyncio.run(run())

    def test_includes_previous_summary_in_prompt(self):
        """When extending a summary, the previous summary text is passed."""
        async def run():
            msgs = _make_long_messages(10)
            existing_summary = {
                "summary": "They met at the park.",
                "through_sequence": 4,
                "through_msg_id": 4,
            }
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=msgs)
                mock_db.get_latest_summary = AsyncMock(return_value=existing_summary)
                mock_db.save_summary = AsyncMock(return_value={"id": 2})

                ollama = AsyncMock()
                ollama.generate = AsyncMock(return_value="Extended summary.")

                await maybe_generate_summary(1, ollama, "test-model",
                                              messages_budget=1200)

                call_args = ollama.generate.call_args
                assert "They met at the park" in call_args[1]["prompt"]
        asyncio.run(run())

    def test_target_tokens_scales_with_budget(self):
        """num_predict scales to fill available budget space."""
        async def run():
            msgs = _make_long_messages(10)
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=msgs)
                mock_db.get_latest_summary = AsyncMock(return_value=None)
                mock_db.save_summary = AsyncMock(return_value={"id": 1})

                ollama = AsyncMock()
                ollama.generate = AsyncMock(return_value="Summary.")

                # Budget 1500: available ~852, older ~972 → triggers
                # target = min(852, 8000) = 852 > default 600
                await maybe_generate_summary(1, ollama, "test-model",
                                              messages_budget=1500)

                call_args = ollama.generate.call_args
                num_predict = call_args[1]["options"]["num_predict"]
                assert num_predict > 600
        asyncio.run(run())

    def test_skips_on_empty_llm_response(self):
        """Don't save if the LLM returns empty."""
        async def run():
            msgs = _make_long_messages(10)
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=msgs)
                mock_db.get_latest_summary = AsyncMock(return_value=None)

                ollama = AsyncMock()
                ollama.generate = AsyncMock(return_value="<think>reasoning</think>")

                result = await maybe_generate_summary(1, ollama, "test-model",
                                                      messages_budget=1200)

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

    def test_uses_dedicated_model_when_resolve_model_provided(self):
        """When resolve_model is given, uses SUMMARY_MODEL."""
        async def run():
            msgs = _make_long_messages(10)
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=msgs)
                mock_db.get_latest_summary = AsyncMock(return_value=None)
                mock_db.save_summary = AsyncMock(return_value={"id": 1})

                ollama = AsyncMock()
                ollama.generate = AsyncMock(return_value="Summary text.")

                def fake_resolve(m):
                    return "resolved-" + m

                await maybe_generate_summary(
                    1, ollama, "conv-model",
                    resolve_model=fake_resolve,
                    messages_budget=1200,
                )

                call_args = ollama.generate.call_args
                assert call_args[1]["model"] == f"resolved-{SUMMARY_MODEL}"
        asyncio.run(run())

    def test_falls_back_to_conv_model_without_resolve(self):
        """Without resolve_model, uses the conversation model directly."""
        async def run():
            msgs = _make_long_messages(10)
            with patch("projects.rp.summarize.db") as mock_db:
                mock_db.get_messages = AsyncMock(return_value=msgs)
                mock_db.get_latest_summary = AsyncMock(return_value=None)
                mock_db.save_summary = AsyncMock(return_value={"id": 1})

                ollama = AsyncMock()
                ollama.generate = AsyncMock(return_value="Summary text.")

                await maybe_generate_summary(1, ollama, "conv-model",
                                              messages_budget=1200)

                call_args = ollama.generate.call_args
                assert call_args[1]["model"] == "conv-model"
        asyncio.run(run())
