"""Tests for per-message score truncation in lora_export."""

from projects.rp.lora_export import truncate_by_score


class TestTruncateByScore:
    def test_all_above_threshold_keeps_all(self):
        messages = [
            {"id": 1, "role": "user", "content": "hi", "sequence": 1},
            {"id": 2, "role": "assistant", "content": "hey", "sequence": 2},
            {"id": 3, "role": "user", "content": "sup", "sequence": 3},
            {"id": 4, "role": "assistant", "content": "nm", "sequence": 4},
        ]
        scores = {2: 4.0, 4: 3.5}
        result = truncate_by_score(messages, scores, min_score=3.0)
        assert len(result) == 4

    def test_second_assistant_below_truncates(self):
        messages = [
            {"id": 1, "role": "user", "content": "hi", "sequence": 1},
            {"id": 2, "role": "assistant", "content": "hey", "sequence": 2},
            {"id": 3, "role": "user", "content": "sup", "sequence": 3},
            {"id": 4, "role": "assistant", "content": "bad reply", "sequence": 4},
            {"id": 5, "role": "user", "content": "ok", "sequence": 5},
            {"id": 6, "role": "assistant", "content": "good again", "sequence": 6},
        ]
        scores = {2: 4.0, 4: 2.0, 6: 4.5}
        result = truncate_by_score(messages, scores, min_score=3.0)
        assert len(result) == 2
        assert result[-1]["id"] == 2

    def test_first_assistant_below_returns_empty(self):
        messages = [
            {"id": 1, "role": "user", "content": "hi", "sequence": 1},
            {"id": 2, "role": "assistant", "content": "bad", "sequence": 2},
        ]
        scores = {2: 1.0}
        result = truncate_by_score(messages, scores, min_score=3.0)
        assert len(result) == 0

    def test_unscored_excluded_by_default(self):
        messages = [
            {"id": 1, "role": "user", "content": "hi", "sequence": 1},
            {"id": 2, "role": "assistant", "content": "hey", "sequence": 2},
        ]
        scores = {}
        result = truncate_by_score(messages, scores, min_score=3.0)
        assert len(result) == 0

    def test_unscored_included_with_flag(self):
        messages = [
            {"id": 1, "role": "user", "content": "hi", "sequence": 1},
            {"id": 2, "role": "assistant", "content": "hey", "sequence": 2},
        ]
        scores = {}
        result = truncate_by_score(messages, scores, min_score=3.0,
                                    include_unscored=True)
        assert len(result) == 2
