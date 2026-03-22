import numpy as np
from pathlib import Path
from PIL import Image


def load(path: str) -> np.ndarray:
    """Load image as float32 HWC RGB [0,1]. Alpha is stripped."""
    p = Path(path)
    if not p.exists():
        raise ValueError(f"Image not found: {path}")
    img = Image.open(p)
    img = img.convert("RGB")
    arr = np.array(img, dtype=np.float32) / 255.0
    return arr


def save(img: np.ndarray, path: str) -> None:
    """Save float32 HWC RGB [0,1] image to disk."""
    if img.ndim != 3 or img.shape[2] != 3:
        raise ValueError(
            f"Expected HWC RGB image, got shape {img.shape}"
        )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    arr_uint8 = np.clip(img * 255, 0, 255).astype(np.uint8)
    Image.fromarray(arr_uint8).save(p)


def display(obj):
    """Wrapper for IPython display, importable for mocking in tests."""
    from IPython.display import display as ipython_display
    ipython_display(obj)


def show(img: np.ndarray):
    """Display image inline in Jupyter."""
    arr_uint8 = np.clip(img * 255, 0, 255).astype(np.uint8)
    pil_img = Image.fromarray(arr_uint8)
    display(pil_img)
