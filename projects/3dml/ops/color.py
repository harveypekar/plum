import numpy as np
from PIL import Image
from scipy.interpolate import CubicSpline


def to_hsv(img: np.ndarray) -> np.ndarray:
    """Convert RGB float32 [0,1] to HSV float32. H in [0,1], S in [0,1], V in [0,1]."""
    if img.ndim != 3 or img.shape[2] != 3:
        raise ValueError(f"Expected HWC RGB, got shape {img.shape}")
    arr_uint8 = np.clip(img * 255, 0, 255).astype(np.uint8)
    pil_img = Image.fromarray(arr_uint8, mode="RGB")
    hsv_img = pil_img.convert("HSV")
    return np.array(hsv_img, dtype=np.float32) / 255.0


def to_rgb(img: np.ndarray) -> np.ndarray:
    """Convert HSV float32 [0,1] back to RGB float32 [0,1]."""
    if img.ndim != 3 or img.shape[2] != 3:
        raise ValueError(f"Expected HWC HSV, got shape {img.shape}")
    arr_uint8 = np.clip(img * 255, 0, 255).astype(np.uint8)
    pil_img = Image.fromarray(arr_uint8, mode="HSV")
    rgb_img = pil_img.convert("RGB")
    return np.array(rgb_img, dtype=np.float32) / 255.0


def adjust_saturation(img: np.ndarray, factor: float) -> np.ndarray:
    """Adjust saturation by factor. Input/output are RGB float32 [0,1]."""
    hsv = to_hsv(img)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * factor, 0, 1)
    return to_rgb(hsv)


def _build_curve_lut(curve) -> np.ndarray:
    """Build a 256-entry LUT from a Curve's control points via cubic spline."""
    points = sorted(curve.points, key=lambda p: p[0])
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    if len(points) == 2 and points[0] == (0.0, 0.0) and points[1] == (1.0, 1.0):
        return np.linspace(0, 1, 256, dtype=np.float32)
    cs = CubicSpline(xs, ys, bc_type="clamped")
    lut_x = np.linspace(0, 1, 256)
    lut_y = cs(lut_x)
    return np.clip(lut_y, 0, 1).astype(np.float32)


def apply_curves(img: np.ndarray, curve_r, curve_g, curve_b) -> np.ndarray:
    """Apply per-channel curves to RGB float32 [0,1] image."""
    if img.ndim != 3 or img.shape[2] != 3:
        raise ValueError(f"Expected HWC RGB, got shape {img.shape}")
    result = img.copy()
    for ch, curve in enumerate([curve_r, curve_g, curve_b]):
        lut = _build_curve_lut(curve)
        indices = np.clip(result[:, :, ch] * 255, 0, 255).astype(np.int32)
        result[:, :, ch] = lut[indices]
    return result
