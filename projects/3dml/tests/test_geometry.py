import numpy as np
from dtypes import Rect
from ops.geometry import crop, resize


def test_crop_basic(sample_rgb_array):
    # sample is 50x80
    rect = Rect(10, 5, 30, 20)
    result = crop(sample_rgb_array, rect)
    assert result.shape == (20, 30, 3)


def test_crop_clamps_to_bounds(sample_rgb_array):
    # rect extends beyond image (50x80)
    rect = Rect(60, 30, 100, 100)
    result = crop(sample_rgb_array, rect)
    assert result.shape[0] > 0
    assert result.shape[1] > 0
    assert result.shape[0] <= 50
    assert result.shape[1] <= 80


def test_crop_fully_outside_raises(sample_rgb_array):
    rect = Rect(200, 200, 10, 10)
    try:
        crop(sample_rgb_array, rect)
        assert False, "Should have raised"
    except ValueError as e:
        assert "no overlap" in str(e).lower()


def test_resize_basic(sample_rgb_array):
    result = resize(sample_rgb_array, 40, 25)
    assert result.shape == (25, 40, 3)
    assert result.dtype == np.float32


def test_resize_preserves_range(sample_rgb_array):
    result = resize(sample_rgb_array, 160, 100)
    assert result.min() >= 0.0
    assert result.max() <= 1.0
