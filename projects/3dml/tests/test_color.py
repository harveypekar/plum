import numpy as np
from dtypes import Curve, IDENTITY_CURVE
from ops.color import to_hsv, to_rgb, adjust_saturation, apply_curves


def test_hsv_roundtrip(sample_rgb_array):
    hsv = to_hsv(sample_rgb_array)
    rgb = to_rgb(hsv)
    # uint8 quantization in PIL HSV conversion causes precision loss
    np.testing.assert_allclose(rgb, sample_rgb_array, atol=6.0 / 255)


def test_hsv_shape(sample_rgb_array):
    hsv = to_hsv(sample_rgb_array)
    assert hsv.shape == sample_rgb_array.shape
    assert hsv.dtype == np.float32


def test_adjust_saturation_identity(sample_rgb_array):
    """Factor 1.0 should not change the image."""
    result = adjust_saturation(sample_rgb_array, 1.0)
    # Two uint8 roundtrips (rgb→hsv→rgb) accumulate error
    np.testing.assert_allclose(result, sample_rgb_array, atol=6.0 / 255)


def test_adjust_saturation_zero():
    """Factor 0.0 should produce a grayscale image."""
    img = np.array([[[1.0, 0.0, 0.0]]], dtype=np.float32)  # pure red
    result = adjust_saturation(img, 0.0)
    # all channels should be equal (grayscale)
    assert abs(result[0, 0, 0] - result[0, 0, 1]) < 1e-5
    assert abs(result[0, 0, 1] - result[0, 0, 2]) < 1e-5


def test_apply_curves_identity(sample_rgb_array):
    """Identity curves should not change the image."""
    identity = Curve()
    result = apply_curves(sample_rgb_array, identity, identity, identity)
    # LUT quantization: float→uint8 index→LUT value introduces ~1/255 error
    np.testing.assert_allclose(result, sample_rgb_array, atol=2.0 / 255)


def test_apply_curves_invert():
    """Curve from (0,1) to (1,0) should invert."""
    img = np.array([[[0.0, 0.5, 1.0]]], dtype=np.float32)
    invert = Curve(points=[(0.0, 1.0), (1.0, 0.0)])
    identity = Curve()
    # Invert only R channel
    result = apply_curves(img, invert, identity, identity)
    assert abs(result[0, 0, 0] - 1.0) < 0.05  # 0.0 → ~1.0
    assert abs(result[0, 0, 1] - 0.5) < 0.05  # G unchanged
    assert abs(result[0, 0, 2] - 1.0) < 0.05  # B unchanged


def test_apply_curves_clamps_output():
    """Output should stay in [0,1] even with extreme curves."""
    img = np.array([[[0.5, 0.5, 0.5]]], dtype=np.float32)
    extreme = Curve(points=[(0.0, 0.0), (0.5, 1.5), (1.0, 1.0)])
    identity = Curve()
    result = apply_curves(img, extreme, identity, identity)
    assert result.min() >= 0.0
    assert result.max() <= 1.0
