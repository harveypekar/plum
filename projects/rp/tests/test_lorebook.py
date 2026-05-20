from projects.rp.lorebook import (
    _keywords_match, match_entries, build_injection_text, extract_character_book,
)


def _entry(name="e", keys=None, content="info", enabled=True, constant=False,
           selective=False, secondary_keys=None, position="after_char",
           insertion_order=100):
    return {
        "name": name, "keys": keys or [], "content": content,
        "enabled": enabled, "constant": constant, "selective": selective,
        "secondary_keys": secondary_keys or [], "position": position,
        "insertion_order": insertion_order,
    }


def _msgs(*texts):
    return [{"role": "user", "content": t} for t in texts]


class TestKeywordsMatch:
    def test_basic_match(self):
        assert _keywords_match("the tavern is dark", ["tavern"])

    def test_case_insensitive(self):
        assert _keywords_match("The TAVERN is dark", ["tavern"])

    def test_no_match(self):
        assert not _keywords_match("the inn is dark", ["tavern"])

    def test_empty_keys(self):
        assert not _keywords_match("anything", [])

    def test_empty_key_string(self):
        assert not _keywords_match("anything", [""])

    def test_multiple_keys_any_match(self):
        assert _keywords_match("the inn is dark", ["tavern", "inn"])


class TestMatchEntries:
    def test_keyword_match(self):
        entries = [_entry("tavern", keys=["tavern"], content="A smoky tavern")]
        result = match_entries(entries, _msgs("I enter the tavern"))
        assert len(result) == 1
        assert result[0]["name"] == "tavern"

    def test_no_match(self):
        entries = [_entry("tavern", keys=["tavern"])]
        result = match_entries(entries, _msgs("I walk outside"))
        assert result == []

    def test_disabled_entry_skipped(self):
        entries = [_entry("tavern", keys=["tavern"], enabled=False)]
        result = match_entries(entries, _msgs("I enter the tavern"))
        assert result == []

    def test_empty_content_skipped(self):
        entries = [_entry("tavern", keys=["tavern"], content="")]
        result = match_entries(entries, _msgs("I enter the tavern"))
        assert result == []

    def test_constant_always_matches(self):
        entries = [_entry("lore", keys=[], content="world facts", constant=True)]
        result = match_entries(entries, _msgs("hello"))
        assert len(result) == 1

    def test_selective_needs_both_keys(self):
        entries = [_entry("secret", keys=["tavern"], secondary_keys=["basement"],
                          content="hidden room", selective=True)]
        assert match_entries(entries, _msgs("I enter the tavern")) == []
        assert len(match_entries(entries, _msgs("tavern basement"))) == 1

    def test_selective_without_secondary_matches_primary_only(self):
        entries = [_entry("x", keys=["tavern"], secondary_keys=[],
                          content="info", selective=True)]
        assert len(match_entries(entries, _msgs("tavern"))) == 1

    def test_scan_depth_limits_window(self):
        entries = [_entry("old", keys=["dragon"], content="dragon lore")]
        msgs = _msgs("a dragon appears") + _msgs(*["filler"] * 15)
        assert match_entries(entries, msgs, scan_depth=5) == []
        assert len(match_entries(entries, msgs, scan_depth=20)) == 1

    def test_sorted_by_insertion_order(self):
        entries = [
            _entry("b", keys=["x"], content="b", insertion_order=200),
            _entry("a", keys=["x"], content="a", insertion_order=50),
        ]
        result = match_entries(entries, _msgs("x"))
        assert [e["name"] for e in result] == ["a", "b"]


class TestBuildInjectionText:
    def test_after_char(self):
        entries = [_entry(content="fact one"), _entry(content="fact two")]
        before, after = build_injection_text(entries)
        assert before == ""
        assert "fact one" in after and "fact two" in after

    def test_before_char(self):
        entries = [_entry(content="preamble", position="before_char")]
        before, after = build_injection_text(entries)
        assert "preamble" in before
        assert after == ""

    def test_mixed_positions(self):
        entries = [
            _entry(content="before stuff", position="before_char"),
            _entry(content="after stuff", position="after_char"),
        ]
        before, after = build_injection_text(entries)
        assert "before stuff" in before
        assert "after stuff" in after

    def test_empty_content_skipped(self):
        entries = [_entry(content=""), _entry(content="real")]
        _, after = build_injection_text(entries)
        assert after == "real"


class TestExtractCharacterBook:
    def test_extracts_from_v2(self):
        card = {"data": {"name": "Test", "character_book": {"entries": [{"keys": ["x"]}]}}}
        result = extract_character_book(card)
        assert result is not None
        assert len(result["entries"]) == 1

    def test_returns_none_when_missing(self):
        assert extract_character_book({"data": {"name": "Test"}}) is None

    def test_returns_none_for_empty_book(self):
        assert extract_character_book({"data": {"character_book": {}}}) is None

    def test_handles_flat_data(self):
        card = {"name": "Test", "character_book": {"entries": [{"keys": ["y"]}]}}
        result = extract_character_book(card)
        assert result is not None
