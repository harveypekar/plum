import numpy as np
from PIL import Image

from dtypes import Rect


def crop(img: np.ndarray, rect: Rect) -> np.ndarray:
    """Crop image to rect. Clamps to image bounds. Raises if no overlap."""
    h, w = img.shape[:2]
    x1 = max(0, rect.x)
    y1 = max(0, rect.y)
    x2 = min(w, rect.x + rect.w)
    y2 = min(h, rect.y + rect.h)
    if x2 <= x1 or y2 <= y1:
        raise ValueError(
            f"Crop rect has no overlap with image: "
            f"rect=({rect.x},{rect.y},{rect.w},{rect.h}), "
            f"image size=({w},{h})"
        )
    return img[y1:y2, x1:x2].copy()


def resize(img: np.ndarray, w: int, h: int, method: str = "lanczos") -> np.ndarray:
    """Resize image to (w, h). Returns float32 HWC."""
    methods = {
        "lanczos": Image.LANCZOS,
        "bilinear": Image.BILINEAR,
        "nearest": Image.NEAREST,
    }
    if method not in methods:
        raise ValueError(f"Unknown resize method: {method}. Use: {list(methods)}")
    arr_uint8 = np.clip(img * 255, 0, 255).astype(np.uint8)
    pil_img = Image.fromarray(arr_uint8)
    pil_img = pil_img.resize((w, h), methods[method])
    return np.array(pil_img, dtype=np.float32) / 255.0
