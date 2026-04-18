"""Tests for the hard-gate heuristic filter."""

from projects.rp.lora_curate import filter_message


class TestStockPhrases:
    def test_zero_stock_phrases_passes(self):
        result = filter_message(
            "She kicked the door open and stomped inside.",
            user_message="Come in",
            previous_assistant_messages=[],
        )
        assert result.passed

    def test_one_stock_phrase_passes(self):
        result = filter_message(
            "Her breath hitched as she entered the room.",
            user_message="She pushed the door open and stepped inside the apartment",
            previous_assistant_messages=[],
        )
        assert result.passed

    def test_two_stock_phrases_rejects(self):
        result = filter_message(
            "Her breath hitched as electricity coursed through her body.",
            user_message="Touch me",
            previous_assistant_messages=[],
        )
        assert not result.passed
        assert "stock_phrases" in result.reason


class TestRepetition:
    def test_no_history_passes(self):
        result = filter_message(
            "She walked to the kitchen and grabbed a beer.",
            user_message="Get a drink",
            previous_assistant_messages=[],
        )
        assert result.passed

    def test_unique_message_passes(self):
        result = filter_message(
            "She walked to the kitchen and grabbed a beer.",
            user_message="Get a drink",
            previous_assistant_messages=[
                "He sat on the couch watching television quietly."
            ],
        )
        assert result.passed

    def test_highly_repetitive_rejects(self):
        repeated = "She nuzzled into the crook of his neck, breathing in his scent, feeling the warmth of his body."
        result = filter_message(
            repeated,
            user_message="Hold me",
            previous_assistant_messages=[repeated],
        )
        assert not result.passed
        assert "repetition" in result.reason


class TestLengthRatio:
    def test_reasonable_length_passes(self):
        result = filter_message(
            "She smiled and nodded. 'Sure thing.'",
            user_message="Can you help me?",
            previous_assistant_messages=[],
        )
        assert result.passed

    def test_extreme_length_alone_passes(self):
        """Length ratio alone is not a hard reject."""
        long_msg = "word " * 200
        result = filter_message(
            long_msg,
            user_message="hi",
            previous_assistant_messages=[],
        )
        assert result.passed

    def test_extreme_length_plus_stock_phrase_rejects(self):
        """Length ratio + one stock phrase = reject."""
        long_msg = ("word " * 200) + " her breath hitched"
        result = filter_message(
            long_msg,
            user_message="hi",
            previous_assistant_messages=[],
        )
        assert not result.passed


class TestFilterResult:
    def test_passed_result(self):
        result = filter_message(
            "Normal message here.",
            user_message="Hello",
            previous_assistant_messages=[],
        )
        assert result.passed
        assert result.reason == ""
        assert result.stock_phrase_count == 0

    def test_failed_result_has_details(self):
        result = filter_message(
            "Her breath hitched as electricity coursed through her veins.",
            user_message="x",
            previous_assistant_messages=[],
        )
        assert not result.passed
        assert result.stock_phrase_count == 2
