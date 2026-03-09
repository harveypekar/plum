import base64
import io
import json
from PIL import Image
from PIL.PngImagePlugin import PngInfo


def parse_card_png(png_data: bytes) -> tuple[dict, bytes]:
    """Extract SillyTavern v2 card data and avatar from a PNG file.

    Returns (card_data dict, png_bytes for avatar).
    """
    img = Image.open(io.BytesIO(png_data))
    chara_b64 = img.text.get("chara", "")
    if not chara_b64:
        raise ValueError("PNG has no 'chara' tEXt chunk — not a SillyTavern card")
    card_json = base64.b64decode(chara_b64).decode("utf-8")
    card_data = json.loads(card_json)
    return card_data, png_data


def export_card_png(card_data: dict, avatar_png: bytes | None = None) -> bytes:
    """Create a SillyTavern PNG with card data embedded in tEXt chunk.

    If avatar_png is provided, uses it as the image. Otherwise creates a 400x600 placeholder.
    """
    if avatar_png:
        img = Image.open(io.BytesIO(avatar_png))
    else:
        img = Image.new("RGB", (400, 600), color=(40, 40, 50))

    meta = PngInfo()
    card_json = json.dumps(card_data, ensure_ascii=False)
    chara_b64 = base64.b64encode(card_json.encode("utf-8")).decode("ascii")
    meta.add_text("chara", chara_b64)

    buf = io.BytesIO()
    img.save(buf, format="PNG", pnginfo=meta)
    return buf.getvalue()


def extract_name(card_data: dict) -> str:
    """Get the character name from card data."""
    if "data" in card_data:
        return card_data["data"].get("name", card_data.get("name", "Unknown"))
    return card_data.get("name", "Unknown")
