from projects.rp.context import SlidingWindow, SummaryBuffer, get_strategy

def _char4(t):
    return len(t) // 4


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
        result = SlidingWindow().fit([greeting, old, recent], 40, token_counter=_char4)
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
        result = SlidingWindow().fit(msgs, 10, token_counter=_char4)
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
        result = SlidingWindow().fit(msgs, 1, token_counter=_char4)
        assert result == msgs

    def test_oversized_message_blocks_all_older(self):
        msgs = [
            _msg("assistant", "greet"),
            _msg("user", "old short"),
            _msg("user", "X" * 10000),
            _msg("assistant", "recent short"),
        ]
        result = SlidingWindow().fit(msgs, 20, token_counter=_char4)
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
        """Messages with sequence <= summary_through are excluded
        when enough post-summary messages exist for the style window."""
        msgs = [
            _seq_msg("assistant", "greeting", 1),
            _seq_msg("user", "old1", 2),
            _seq_msg("assistant", "old2", 3),
            _seq_msg("user", "new1", 4),
            _seq_msg("assistant", "new2", 5),
            _seq_msg("user", "new3", 6),
            _seq_msg("assistant", "new4", 7),
        ]
        ctx = {"_summary": "Previous events.", "_summary_through_sequence": 3}
        result = SummaryBuffer().fit(msgs, 10000, ctx=ctx)
        contents = [m["content"] for m in result]
        assert "old1" not in contents
        assert "old2" not in contents
        assert "new1" in contents
        assert "new2" in contents
        assert "greeting" in contents

    def test_summary_exceeding_budget_rejected(self):
        """Summary larger than remaining budget after greeting is not injected."""
        huge_summary = "X" * 2000
        msgs = [
            _seq_msg("assistant", "greeting", 1),
            _seq_msg("user", "recent", 10),
        ]
        ctx = {"_summary": huge_summary, "_summary_through_sequence": 5}
        # Budget of 100 tokens, greeting ~2 tokens, summary ~500 tokens → exceeds budget
        result = SummaryBuffer().fit(msgs, 100, token_counter=_char4, ctx=ctx)
        for m in result:
            assert "[Story so far]" not in m.get("content", "")

    def test_large_summary_within_budget_injected(self):
        """Large summary that fits within budget is injected (no fixed cap)."""
        large_summary = "X" * 4000  # ~1000 tokens with _char4
        msgs = [
            _seq_msg("assistant", "greeting", 1),
            _seq_msg("user", "recent", 10),
        ]
        ctx = {"_summary": large_summary, "_summary_through_sequence": 5}
        result = SummaryBuffer().fit(msgs, 2000, token_counter=_char4, ctx=ctx)
        assert any("[Story so far]" in m.get("content", "") for m in result)

    def test_summary_within_budget_injected(self):
        """Small summary is injected normally."""
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
        result = SummaryBuffer().fit(msgs, 30, token_counter=_char4, ctx=ctx)
        contents = [m["content"] for m in result]
        assert "D" * 40 in contents

    def test_greeting_always_kept(self):
        msgs = [_seq_msg("assistant", "A" * 100, 1)]
        result = SummaryBuffer().fit(msgs, 10, token_counter=_char4)
        assert result[0] == msgs[0]

    def test_no_ctx_no_crash(self):
        """Passing ctx=None should not crash."""
        msgs = [_msg("assistant", "Hello"), _msg("user", "Hi")]
        result = SummaryBuffer().fit(msgs, 10000, ctx=None)
        assert len(result) == 2

    def test_messages_without_sequence_not_filtered(self):
        """Messages without _sequence default to 0; the style window pulls them in."""
        msgs = [
            _msg("assistant", "greeting"),
            _msg("user", "msg1"),
        ]
        ctx = {"_summary": "Summary.", "_summary_through_sequence": 0}
        result = SummaryBuffer().fit(msgs, 10000, ctx=ctx)
        assert len(result) == 3  # summary + greeting + msg1 (style window)

    def test_style_window_pulls_pre_summary_messages(self):
        """When < STYLE_WINDOW post-summary messages exist, pre-summary messages
        are pulled in so the model has recent style examples."""
        msgs = [
            _seq_msg("assistant", "greeting", 1),
            _seq_msg("user", "old1", 2),
            _seq_msg("assistant", "old2", 3),
            _seq_msg("user", "old3", 4),
            _seq_msg("assistant", "old4", 5),
            _seq_msg("user", "new_only", 6),
        ]
        ctx = {"_summary": "Previous events.", "_summary_through_sequence": 5}
        result = SummaryBuffer().fit(msgs, 10000, ctx=ctx)
        contents = [m["content"] for m in result]
        # 1 post-summary message, STYLE_WINDOW=4 → pull 3 from pre-summary
        assert "new_only" in contents
        assert "old4" in contents  # most recent pre-summary
        assert "old3" in contents
        assert "old2" in contents
        assert "old1" not in contents  # too old, beyond style window

    def test_style_window_not_needed_when_enough_post_summary(self):
        """No pre-summary messages pulled in when post-summary count >= STYLE_WINDOW."""
        msgs = [
            _seq_msg("assistant", "greeting", 1),
            _seq_msg("user", "old1", 2),
            _seq_msg("assistant", "old2", 3),
            _seq_msg("user", "new1", 4),
            _seq_msg("assistant", "new2", 5),
            _seq_msg("user", "new3", 6),
            _seq_msg("assistant", "new4", 7),
        ]
        ctx = {"_summary": "Previous events.", "_summary_through_sequence": 3}
        result = SummaryBuffer().fit(msgs, 10000, ctx=ctx)
        contents = [m["content"] for m in result]
        assert "old1" not in contents
        assert "old2" not in contents
        assert "new1" in contents

    def test_style_window_respects_budget(self):
        """Style window messages are still subject to token budget."""
        msgs = [
            _seq_msg("assistant", "greeting", 1),
            _seq_msg("user", "A" * 400, 2),
            _seq_msg("assistant", "B" * 400, 3),
            _seq_msg("user", "C" * 400, 4),
            _seq_msg("assistant", "D" * 400, 5),
            _seq_msg("user", "recent", 6),
        ]
        ctx = {"_summary": "Short.", "_summary_through_sequence": 5}
        # Tight budget: greeting + summary + recent + maybe one style msg
        result = SummaryBuffer().fit(msgs, 30, token_counter=_char4, ctx=ctx)
        assert result[-1]["content"] == "recent"
        # Can't fit all 4 style window messages, budget limits it
        assert len(result) < 7

    def test_stale_summary_ignored(self):
        """Summary covering sequences beyond current messages is ignored."""
        msgs = [
            _seq_msg("assistant", "greeting", 1),
            _seq_msg("user", "recent msg", 2),
        ]
        ctx = {"_summary": "Old summary from before reset.", "_summary_through_sequence": 11}
        result = SummaryBuffer().fit(msgs, 10000, ctx=ctx)
        contents = [m["content"] for m in result]
        assert "recent msg" in contents
        assert not any("[Story so far]" in c for c in contents)


class TestGetStrategy:
    def test_returns_sliding_window(self):
        s = get_strategy("sliding_window")
        assert isinstance(s, SlidingWindow)

    def test_returns_summary_buffer(self):
        s = get_strategy("summary_buffer")
        assert isinstance(s, SummaryBuffer)

    def test_unknown_falls_back_to_summary_buffer(self):
        s = get_strategy("nonexistent_strategy")
        assert isinstance(s, SummaryBuffer)

    def test_default_is_summary_buffer(self):
        s = get_strategy()
        assert isinstance(s, SummaryBuffer)
