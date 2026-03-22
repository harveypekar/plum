import numpy as np
from unittest.mock import patch, MagicMock
from ops.io import load, save, show


def test_load_returns_float32_hwc_rgb(sample_image_path):
    img = load(sample_image_path)
    assert img.dtype == np.float32
    assert img.ndim == 3
    assert img.shape[2] == 3
    assert img.min() >= 0.0
    assert img.max() <= 1.0


def test_load_strips_alpha(sample_rgba_path):
    img = load(sample_rgba_path)
    assert img.shape[2] == 3


def test_load_nonexistent_raises():
    try:
        load("/nonexistent/path.png")
        assert False, "Should have raised"
    except ValueError as e:
        assert "not found" in str(e).lower()


def test_save_roundtrip(sample_rgb_array, tmp_path):
    path = str(tmp_path / "out.png")
    save(sample_rgb_array, path)
    reloaded = load(path)
    # PNG is uint8 so we lose precision — check within 1/255
    np.testing.assert_allclose(reloaded, sample_rgb_array, atol=1.0 / 255 + 0.01)


def test_save_creates_parent_dirs(sample_rgb_array, tmp_path):
    path = str(tmp_path / "sub" / "dir" / "out.png")
    save(sample_rgb_array, path)
    reloaded = load(path)
    assert reloaded.shape == sample_rgb_array.shape


@patch("ops.io.display")
def test_show_does_not_crash(mock_display, sample_rgb_array):
    show(sample_rgb_array)
    mock_display.assert_called_once()
