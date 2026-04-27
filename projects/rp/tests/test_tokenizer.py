"""Tests for projects/rp/tokenizer.py — tiktoken-based token counting."""

from projects.rp.tokenizer import count_tokens


class TestCountTokens:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_single_word(self):
        result = count_tokens("hello")
        assert result == 1

    def test_short_sentence(self):
        result = count_tokens("The quick brown fox jumps over the lazy dog.")
        assert 8 <= result <= 12

    def test_longer_text_more_accurate_than_char_div(self):
        text = "She walked into the dimly lit room, her heels clicking against the hardwood floor."
        tiktoken_count = count_tokens(text)
        crude_count = len(text) // 4
        assert tiktoken_count != crude_count

    def test_repeated_chars_not_one_per_char(self):
        text = "A" * 100
        result = count_tokens(text)
        assert result < 100

    def test_unicode(self):
        result = count_tokens("Héllo wörld café")
        assert result > 0

    def test_special_characters(self):
        result = count_tokens("{{user}} said: 'Hello, ${char}!'")
        assert result > 0

    def test_multiline(self):
        text = "Line one.\nLine two.\nLine three."
        result = count_tokens(text)
        assert result > 0

    def test_consistent_results(self):
        text = "Consistency check."
        assert count_tokens(text) == count_tokens(text)
