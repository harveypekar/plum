import pytest
from projects.rp.cards import parse_card_png, export_card_png, extract_name


def _make_card_data(name="TestChar", description="A test character"):
    return {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": name,
            "description": description,
            "personality": "brave",
            "mes_example": "",
            "first_mes": "Hello!",
            "system_prompt": "",
        },
    }


class TestParseExportRoundTrip:
    def test_round_trip_preserves_card_data(self):
        original = _make_card_data()
        png = export_card_png(original)
        parsed, avatar_bytes = parse_card_png(png)
        assert parsed["data"]["name"] == "TestChar"
        assert parsed["data"]["description"] == "A test character"
        assert parsed["spec"] == "chara_card_v2"

    def test_round_trip_with_unicode(self):
        original = _make_card_data(name="Ëlaria", description="She wields a flaming sörd")
        png = export_card_png(original)
        parsed, _ = parse_card_png(png)
        assert parsed["data"]["name"] == "Ëlaria"
        assert "sörd" in parsed["data"]["description"]

    def test_round_trip_with_avatar(self):
        original = _make_card_data()
        placeholder_png = export_card_png({"data": {"name": "x"}})
        png = export_card_png(original, avatar_png=placeholder_png)
        parsed, returned_png = parse_card_png(png)
        assert parsed["data"]["name"] == "TestChar"
        assert len(returned_png) > 0

    def test_parse_raises_on_plain_png(self):
        from PIL import Image
        import io
        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        with pytest.raises(ValueError, match="no 'chara' tEXt chunk"):
            parse_card_png(buf.getvalue())

    def test_export_no_avatar_creates_placeholder(self):
        original = _make_card_data()
        png = export_card_png(original)
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(png))
        assert img.size == (400, 600)


class TestExtractName:
    def test_v2_format(self):
        assert extract_name({"data": {"name": "Jessica"}}) == "Jessica"

    def test_flat_format(self):
        assert extract_name({"name": "Sol"}) == "Sol"

    def test_v2_missing_name_falls_to_top_level(self):
        assert extract_name({"data": {}, "name": "Fallback"}) == "Fallback"

    def test_completely_empty(self):
        assert extract_name({}) == "Unknown"

    def test_v2_no_name_no_fallback(self):
        assert extract_name({"data": {}}) == "Unknown"
