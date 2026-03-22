from projects.rp.context import SlidingWindow, get_strategy


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


class TestGetStrategy:
    def test_returns_sliding_window(self):
        s = get_strategy("sliding_window")
        assert isinstance(s, SlidingWindow)

    def test_unknown_falls_back_to_sliding_window(self):
        s = get_strategy("nonexistent_strategy")
        assert isinstance(s, SlidingWindow)

    def test_default_is_sliding_window(self):
        s = get_strategy()
        assert isinstance(s, SlidingWindow)
