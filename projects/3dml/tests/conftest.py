import sys
from pathlib import Path

# Make projects/3dml/ importable for tests
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from PIL import Image
import pytest


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_rgb_array():
    """50x80 RGB float32 image with a gradient."""
    h, w = 50, 80
    img = np.zeros((h, w, 3), dtype=np.float32)
    img[:, :, 0] = np.linspace(0, 1, w)[np.newaxis, :]  # red gradient L→R
    img[:, :, 1] = np.linspace(0, 1, h)[:, np.newaxis]  # green gradient T→B
    img[:, :, 2] = 0.5
    return img


@pytest.fixture
def sample_image_path(sample_rgb_array, tmp_path):
    """Write sample image to a temporary PNG and return its path."""
    path = tmp_path / "sample.png"
    arr_uint8 = (sample_rgb_array * 255).astype(np.uint8)
    Image.fromarray(arr_uint8).save(path)
    return str(path)


@pytest.fixture
def sample_rgba_path(tmp_path):
    """Write a 4-channel RGBA PNG and return its path."""
    h, w = 20, 30
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[:, :, 0] = 200
    arr[:, :, 3] = 128
    path = tmp_path / "rgba.png"
    Image.fromarray(arr, mode="RGBA").save(path)
    return str(path)
