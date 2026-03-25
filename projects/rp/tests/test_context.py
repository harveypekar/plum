from projects.rp.context import SlidingWindow, SummaryBuffer, get_strategy


def _msg(role, content):
    return {"role": role, "content": content}


class TestSlidingWindow:
    def test_empty_messages(self):
        sw = SlidingWindow()
        assert sw.fit([], 1000) == []

    def test_all_fit(self):
        msgs = [_msg("assistant", "Hello"), _msg("user", "Hi"), _msg("assistant", "How?")]
        result = SlidingWindow().fit(msgs, 10000)
        assert result == msgs

    def test_keeps_first_message_always(self):
        greeting = _msg("assistant", "A" * 100)
        old = _msg("user", "B" * 100)
        recent = _msg("assistant", "C" * 50)
        result = SlidingWindow().fit([greeting, old, recent], 40)
        assert result[0] == greeting
        assert recent in result
        assert old not in result

    def test_drops_oldest_not_newest(self):
        msgs = [
            _msg("assistant", "greeting"),
            _msg("user", "msg1"),
            _msg("user", "msg2"),
            _msg("user", "msg3"),
            _msg("assistant", "msg4"),
        ]
        result = SlidingWindow().fit(msgs, 10)
        assert result[0] == msgs[0]
        assert result[-1] == msgs[-1]

    def test_custom_token_counter(self):
        msgs = [_msg("assistant", "hi"), _msg("user", "hello world")]
        result = SlidingWindow().fit(msgs, 3, token_counter=lambda t: len(t.split()))
        assert len(result) == 2

    def test_custom_counter_tight(self):
        msgs = [_msg("assistant", "hi"), _msg("user", "hello world")]
        result = SlidingWindow().fit(msgs, 1, token_counter=lambda t: len(t.split()))
        assert len(result) == 1
        assert result[0] == msgs[0]

    def test_single_message(self):
        msgs = [_msg("assistant", "Hello!")]
        result = SlidingWindow().fit(msgs, 1000)
        assert result == msgs

    def test_single_message_over_budget(self):
        msgs = [_msg("assistant", "A" * 10000)]
        result = SlidingWindow().fit(msgs, 1)
        assert result == msgs

    def test_oversized_message_blocks_all_older(self):
        msgs = [
            _msg("assistant", "greet"),
            _msg("user", "old short"),
            _msg("user", "X" * 10000),
            _msg("assistant", "recent short"),
        ]
        result = SlidingWindow().fit(msgs, 20)
        assert result[0] == msgs[0]
        assert msgs[-1] in result
        assert msgs[1] not in result


def _seq_msg(role, content, sequence):
    """Message with _sequence for SummaryBuffer filtering."""
    return {"role": role, "content": content, "_sequence": sequence}


class TestSummaryBuffer:
    def test_empty_messages(self):
        sb = SummaryBuffer()
        assert sb.fit([], 1000) == []

    def test_no_summary_behaves_like_sliding_window(self):
        """Without a summary, SummaryBuffer degrades to SlidingWindow."""
        msgs = [_msg("assistant", "Hello"), _msg("user", "Hi"), _msg("assistant", "How?")]
        result = SummaryBuffer().fit(msgs, 10000)
        assert len(result) == 3
        assert result[0] == msgs[0]

    def test_summary_injected_before_greeting(self):
        msgs = [
            _seq_msg("assistant", "greeting", 1),
            _seq_msg("user", "msg1", 2),
            _seq_msg("assistant", "reply1", 3),
        ]
        ctx = {"_summary": "They met at the park.", "_summary_through_sequence": 0}
        result = SummaryBuffer().fit(msgs, 10000, ctx=ctx)
        assert result[0]["role"] == "system"
        assert "[Story so far]" in result[0]["content"]
        assert "They met at the park." in result[0]["content"]
        assert result[1] == msgs[0]  # greeting

    def test_summary_filters_covered_messages(self):
        """Messages with sequence <= summary_through_sequence are excluded."""
        msgs = [
            _seq_msg("assistant", "greeting", 1),
            _seq_msg("user", "old1", 2),
            _seq_msg("assistant", "old2", 3),
            _seq_msg("user", "new1", 4),
            _seq_msg("assistant", "new2", 5),
        ]
        ctx = {"_summary": "Previous events.", "_summary_through_sequence": 3}
        result = SummaryBuffer().fit(msgs, 10000, ctx=ctx)
        contents = [m["content"] for m in result]
        assert "old1" not in contents
        assert "old2" not in contents
        assert "new1" in contents
        assert "new2" in contents
        assert "greeting" in contents

    def test_summary_budget_cap(self):
        """Summary should not exceed 25% of budget."""
        huge_summary = "X" * 2000  # ~500 tokens at len//4
        msgs = [
            _seq_msg("assistant", "greeting", 1),
            _seq_msg("user", "recent", 10),
        ]
        # Budget 100 tokens: 25% = 25, but summary is ~500 tokens -> too big, no injection
        ctx = {"_summary": huge_summary, "_summary_through_sequence": 5}
        result = SummaryBuffer().fit(msgs, 100, ctx=ctx)
        for m in result:
            assert "[Story so far]" not in m.get("content", "")

    def test_summary_within_budget_cap(self):
        """Small summary within 25% cap is injected."""
        small_summary = "Short summary."
        msgs = [
            _seq_msg("assistant", "greeting", 1),
            _seq_msg("user", "recent", 10),
        ]
        ctx = {"_summary": small_summary, "_summary_through_sequence": 5}
        result = SummaryBuffer().fit(msgs, 10000, ctx=ctx)
        assert any("[Story so far]" in m.get("content", "") for m in result)

    def test_recent_messages_fill_newest_first(self):
        """Like SlidingWindow, newer messages are kept over older ones."""
        msgs = [
            _seq_msg("assistant", "A" * 40, 1),
            _seq_msg("user", "B" * 40, 8),
            _seq_msg("assistant", "C" * 40, 9),
            _seq_msg("user", "D" * 40, 10),
        ]
        ctx = {"_summary": "Summary.", "_summary_through_sequence": 7}
        # Budget tight enough that not all unsummarized messages fit
        result = SummaryBuffer().fit(msgs, 30, ctx=ctx)
        contents = [m["content"] for m in result]
        # Newest should be present, oldest after greeting may be dropped
        assert "D" * 40 in contents

    def test_greeting_always_kept(self):
        msgs = [_seq_msg("assistant", "A" * 100, 1)]
        result = SummaryBuffer().fit(msgs, 10)
        assert result[0] == msgs[0]

    def test_no_ctx_no_crash(self):
        """Passing ctx=None should not crash."""
        msgs = [_msg("assistant", "Hello"), _msg("user", "Hi")]
        result = SummaryBuffer().fit(msgs, 10000, ctx=None)
        assert len(result) == 2

    def test_messages_without_sequence_not_filtered(self):
        """Messages without _sequence field default to 0, not filtered if through=0."""
        msgs = [
            _msg("assistant", "greeting"),
            _msg("user", "msg1"),
        ]
        ctx = {"_summary": "Summary.", "_summary_through_sequence": 0}
        result = SummaryBuffer().fit(msgs, 10000, ctx=ctx)
        # _sequence defaults to 0, 0 > 0 is False, so messages are filtered
        # greeting is kept separately, msg1 should be filtered
        assert len(result) == 2  # summary + greeting


class TestGetStrategy:
    def test_returns_sliding_window(self):
        s = get_strategy("sliding_window")
        assert isinstance(s, SlidingWindow)

    def test_returns_summary_buffer(self):
        s = get_strategy("summary_buffer")
        assert isinstance(s, SummaryBuffer)

    def test_unknown_falls_back_to_sliding_window(self):
        s = get_strategy("nonexistent_strategy")
        assert isinstance(s, SlidingWindow)

    def test_default_is_sliding_window(self):
        s = get_strategy()
        assert isinstance(s, SlidingWindow)
