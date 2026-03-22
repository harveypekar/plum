# 3DML Image Workflow Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python workflow engine where dataclass workflows compose pure image operations, with typed inputs that auto-generate Jupyter widget UIs for artist control.

**Architecture:** Three layers — pure ops (stateless functions), workflows (dataclasses with `run()`), and a UI layer that auto-generates Jupyter widgets from type annotations. Images are always float32 HWC RGB [0,1].

**Tech Stack:** Python 3.12, numpy, Pillow, scipy, ipywidgets, ipycanvas, Jupyter

**Spec:** `docs/superpowers/specs/2026-03-22-3dml-image-workflow-engine-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `projects/3dml/__init__.py` | Create | Package init |
| `projects/3dml/dtypes.py` | Create | Rect, Curve, IDENTITY_CURVE, Slider/FilePath/ColorPick annotated type factories |
| `projects/3dml/ops/__init__.py` | Create | Ops package init |
| `projects/3dml/ops/io.py` | Create | load, save, show |
| `projects/3dml/ops/geometry.py` | Create | crop, resize |
| `projects/3dml/ops/color.py` | Create | to_hsv, to_rgb, adjust_saturation, apply_curves |
| `projects/3dml/workflows/__init__.py` | Create | Workflows package init |
| `projects/3dml/workflows/image_process.py` | Create | ImageProcessWorkflow dataclass |
| `projects/3dml/ui.py` | Create | run_workflow, widget generation from annotations |
| `projects/3dml/notebooks/image_process.ipynb` | Create | Demo notebook |
| `projects/3dml/requirements.txt` | Create | Dependencies |
| `projects/3dml/tests/__init__.py` | Create | Test package init |
| `projects/3dml/tests/test_types.py` | Create | Tests for types |
| `projects/3dml/tests/test_io.py` | Create | Tests for ops/io |
| `projects/3dml/tests/test_geometry.py` | Create | Tests for ops/geometry |
| `projects/3dml/tests/test_color.py` | Create | Tests for ops/color |
| `projects/3dml/tests/test_workflow.py` | Create | Tests for ImageProcessWorkflow |
| `projects/3dml/tests/test_ui.py` | Create | Tests for widget generation |
| `projects/3dml/tests/fixtures/` | Create | Test images |
| `projects/3dml/imageToModel.ipynb` | Delete | Old empty notebook |

---

## Task 1: Project Setup & Dependencies

**Files:**
- Create: `projects/3dml/__init__.py`
- Create: `projects/3dml/ops/__init__.py`
- Create: `projects/3dml/workflows/__init__.py`
- Create: `projects/3dml/tests/__init__.py`
- Create: `projects/3dml/requirements.txt`
- Delete: `projects/3dml/imageToModel.ipynb`

- [ ] **Step 1: Create requirements.txt**

```
numpy
Pillow
scipy
ipywidgets>=8.0
ipycanvas
jupyterlab
pytest
```

- [ ] **Step 2: Create package init files**

`projects/3dml/__init__.py` — empty file.
`projects/3dml/ops/__init__.py` — empty file.
`projects/3dml/workflows/__init__.py` — empty file.
`projects/3dml/tests/__init__.py` — empty file.

- [ ] **Step 3: Install dependencies**

```bash
cd /mnt/d/prg/plum/projects/3dml
source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 4: Delete old notebook**

```bash
rm projects/3dml/imageToModel.ipynb
```

- [ ] **Step 5: Create test fixtures directory with a test image**

```bash
mkdir -p projects/3dml/tests/fixtures
```

Generate a small test image programmatically (in `conftest.py`):

Create `projects/3dml/tests/conftest.py`:

```python
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
```

- [ ] **Step 6: Verify pytest runs**

```bash
cd /mnt/d/prg/plum/projects/3dml
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: 0 tests collected, no errors.

- [ ] **Step 7: Commit**

```bash
git add projects/3dml/__init__.py projects/3dml/ops/__init__.py projects/3dml/workflows/__init__.py projects/3dml/tests/ projects/3dml/requirements.txt
git commit -m "feat(3dml): scaffold project structure and dependencies"
```

---

## Task 2: Type System (`dtypes.py`)

**Files:**
- Create: `projects/3dml/dtypes.py`
- Create: `projects/3dml/tests/test_types.py`

- [ ] **Step 1: Write failing tests for types**

Create `projects/3dml/tests/test_types.py`:

```python
from typing import get_args
from dtypes import Rect, Curve, IDENTITY_CURVE, Slider, FilePath, ColorPick


def test_rect_fields():
    r = Rect(10, 20, 100, 200)
    assert r.x == 10
    assert r.y == 20
    assert r.w == 100
    assert r.h == 200


def test_curve_default_is_identity():
    c = Curve()
    assert c.points == [(0.0, 0.0), (1.0, 1.0)]


def test_curve_default_not_shared():
    """Each Curve instance should get its own points list."""
    c1 = Curve()
    c2 = Curve()
    c1.points.append((0.5, 0.5))
    assert len(c2.points) == 2


def test_slider_returns_annotated():
    ann = Slider(min=0, max=2, default=1.0)
    args = get_args(ann)
    assert args[0] is float
    meta = args[1]
    assert meta["widget"] == "slider"
    assert meta["min"] == 0
    assert meta["max"] == 2
    assert meta["default"] == 1.0


def test_filepath_returns_annotated():
    ann = FilePath(accept=".png,.jpg")
    args = get_args(ann)
    assert args[0] is str
    meta = args[1]
    assert meta["widget"] == "file"
    assert meta["accept"] == ".png,.jpg"


def test_colorpick_is_annotated():
    args = get_args(ColorPick)
    assert args[0] == tuple[float, float, float]
    meta = args[1]
    assert meta["widget"] == "color"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/d/prg/plum/projects/3dml
source .venv/bin/activate
python -m pytest tests/test_types.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'dtypes'`

- [ ] **Step 3: Implement dtypes.py**

Create `projects/3dml/dtypes.py` (named `dtypes` to avoid shadowing Python's built-in `types` module):

```python
from typing import Annotated
from dataclasses import dataclass, field


IDENTITY_CURVE = [(0.0, 0.0), (1.0, 1.0)]


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass
class Curve:
    points: list[tuple[float, float]] = field(
        default_factory=lambda: list(IDENTITY_CURVE)
    )


def Slider(**kw):
    return Annotated[float, {"widget": "slider", **kw}]


def FilePath(**kw):
    return Annotated[str, {"widget": "file", **kw}]


ColorPick = Annotated[tuple[float, float, float], {"widget": "color"}]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/d/prg/plum/projects/3dml
source .venv/bin/activate
python -m pytest tests/test_types.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add projects/3dml/dtypes.py projects/3dml/tests/test_types.py
git commit -m "feat(3dml): add type system — Rect, Curve, Slider, FilePath, ColorPick"
```

---

## Task 3: I/O Operations (`ops/io.py`)

**Files:**
- Create: `projects/3dml/ops/io.py`
- Create: `projects/3dml/tests/test_io.py`

- [ ] **Step 1: Write failing tests**

Create `projects/3dml/tests/test_io.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_io.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'ops'`

- [ ] **Step 3: Implement ops/io.py**

Create `projects/3dml/ops/io.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_io.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add projects/3dml/ops/io.py projects/3dml/tests/test_io.py
git commit -m "feat(3dml): add I/O ops — load, save, show"
```

---

## Task 4: Geometry Operations (`ops/geometry.py`)

**Files:**
- Create: `projects/3dml/ops/geometry.py`
- Create: `projects/3dml/tests/test_geometry.py`

- [ ] **Step 1: Write failing tests**

Create `projects/3dml/tests/test_geometry.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_geometry.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement ops/geometry.py**

Create `projects/3dml/ops/geometry.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_geometry.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add projects/3dml/ops/geometry.py projects/3dml/tests/test_geometry.py
git commit -m "feat(3dml): add geometry ops — crop, resize"
```

---

## Task 5: Color Operations (`ops/color.py`)

**Files:**
- Create: `projects/3dml/ops/color.py`
- Create: `projects/3dml/tests/test_color.py`

- [ ] **Step 1: Write failing tests**

Create `projects/3dml/tests/test_color.py`:

```python
import numpy as np
from dtypes import Curve, IDENTITY_CURVE
from ops.color import to_hsv, to_rgb, adjust_saturation, apply_curves


def test_hsv_roundtrip(sample_rgb_array):
    hsv = to_hsv(sample_rgb_array)
    rgb = to_rgb(hsv)
    # uint8 quantization in PIL HSV conversion causes precision loss
    np.testing.assert_allclose(rgb, sample_rgb_array, atol=3.0 / 255)


def test_hsv_shape(sample_rgb_array):
    hsv = to_hsv(sample_rgb_array)
    assert hsv.shape == sample_rgb_array.shape
    assert hsv.dtype == np.float32


def test_adjust_saturation_identity(sample_rgb_array):
    """Factor 1.0 should not change the image."""
    result = adjust_saturation(sample_rgb_array, 1.0)
    # Two uint8 roundtrips (rgb→hsv→rgb) accumulate error
    np.testing.assert_allclose(result, sample_rgb_array, atol=3.0 / 255)


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
    np.testing.assert_allclose(result, sample_rgb_array, atol=1e-5)


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_color.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement ops/color.py**

Create `projects/3dml/ops/color.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_color.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add projects/3dml/ops/color.py projects/3dml/tests/test_color.py
git commit -m "feat(3dml): add color ops — hsv, saturation, curves"
```

---

## Task 6: ImageProcessWorkflow

**Files:**
- Create: `projects/3dml/workflows/image_process.py`
- Create: `projects/3dml/tests/test_workflow.py`

- [ ] **Step 1: Write failing tests**

Create `projects/3dml/tests/test_workflow.py`:

```python
import numpy as np
from dtypes import Rect, Curve
from workflows.image_process import ImageProcessWorkflow


def test_workflow_defaults():
    """Workflow can be instantiated with just input/output paths."""
    wf = ImageProcessWorkflow(input_image="in.png", output_path="out.png")
    assert wf.saturation == 1.0
    assert wf.crop_rect.w == 512


def test_workflow_run_end_to_end(sample_image_path, tmp_path):
    out = str(tmp_path / "result.png")
    wf = ImageProcessWorkflow(
        input_image=sample_image_path,
        crop_rect=Rect(0, 0, 40, 30),
        saturation=1.2,
        output_path=out,
    )
    result = wf.run()
    assert result.dtype == np.float32
    assert result.shape == (30, 40, 3)
    assert (tmp_path / "result.png").exists()


def test_workflow_identity(sample_image_path, tmp_path):
    """With default params (full crop, sat=1.0, identity curves), output ≈ input."""
    from ops.io import load
    original = load(sample_image_path)
    h, w = original.shape[:2]
    out = str(tmp_path / "identity.png")
    wf = ImageProcessWorkflow(
        input_image=sample_image_path,
        crop_rect=Rect(0, 0, w, h),
        output_path=out,
    )
    result = wf.run()
    # HSV roundtrip (adjust_saturation with factor=1.0) + uint8 save causes precision loss
    np.testing.assert_allclose(result, original, atol=4.0 / 255)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_workflow.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement workflow**

Create `projects/3dml/workflows/image_process.py`:

```python
from dataclasses import dataclass, field

import numpy as np

from dtypes import Rect, Curve, Slider, FilePath
from ops import io as ops_io
from ops import geometry
from ops import color


@dataclass
class ImageProcessWorkflow:
    input_image: FilePath(accept=".png,.jpg") = ""
    crop_rect: Rect = field(default_factory=lambda: Rect(0, 0, 512, 512))
    saturation: Slider(min=0, max=2, default=1.0) = 1.0
    curve_r: Curve = field(default_factory=Curve)
    curve_g: Curve = field(default_factory=Curve)
    curve_b: Curve = field(default_factory=Curve)
    output_path: FilePath(accept=".png", mode="save") = "output.png"

    def run(self) -> np.ndarray:
        img = ops_io.load(self.input_image)
        img = geometry.crop(img, self.crop_rect)
        img = color.adjust_saturation(img, self.saturation)
        img = color.apply_curves(img, self.curve_r, self.curve_g, self.curve_b)
        ops_io.save(img, self.output_path)
        return img
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_workflow.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS (types + io + geometry + color + workflow).

- [ ] **Step 6: Commit**

```bash
git add projects/3dml/workflows/image_process.py projects/3dml/tests/test_workflow.py
git commit -m "feat(3dml): add ImageProcessWorkflow"
```

---

## Task 7: Widget UI Layer (`ui.py`)

**Files:**
- Create: `projects/3dml/ui.py`
- Create: `projects/3dml/tests/test_ui.py`

- [ ] **Step 1: Write failing tests**

The UI layer generates ipywidgets, which we can test by inspecting the returned widget tree without rendering. Create `projects/3dml/tests/test_ui.py`:

```python
from dataclasses import dataclass, field
from dtypes import Slider, FilePath, Rect, Curve
from ui import build_widgets, get_widget_for_field
import ipywidgets as widgets


@dataclass
class SimpleWorkflow:
    name: FilePath(accept=".png") = "test.png"
    brightness: Slider(min=0, max=2, default=1.0) = 1.0
    rect: Rect = field(default_factory=lambda: Rect(0, 0, 100, 100))
    curve: Curve = field(default_factory=Curve)

    def run(self):
        return None


def test_slider_widget():
    w = get_widget_for_field("brightness", Slider(min=0, max=2, default=1.0), 1.0)
    assert isinstance(w, widgets.FloatSlider)
    assert w.min == 0
    assert w.max == 2
    assert w.value == 1.0


def test_filepath_widget():
    w = get_widget_for_field("name", FilePath(accept=".png"), "test.png")
    assert isinstance(w, widgets.Text)
    assert w.value == "test.png"


def test_filepath_save_widget():
    w = get_widget_for_field("out", FilePath(accept=".png", mode="save"), "out.png")
    assert isinstance(w, widgets.Text)


def test_rect_widget():
    w = get_widget_for_field("rect", Rect, Rect(0, 0, 100, 100))
    # Rect produces a group of 4 IntText widgets
    assert isinstance(w, widgets.HBox)
    assert len(w.children) == 4


def test_build_widgets_returns_vbox():
    widget_box, getter = build_widgets(SimpleWorkflow)
    assert isinstance(widget_box, widgets.VBox)
    # Should have widgets for each field + a Run button
    vals = getter()
    assert "brightness" in vals
    assert "name" in vals
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_ui.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement ui.py**

Create `projects/3dml/ui.py`:

```python
import dataclasses
from typing import get_args, get_origin, Annotated, get_type_hints
import ipywidgets as widgets
from IPython.display import display, clear_output

from dtypes import Rect, Curve


def _get_annotated_meta(annotation):
    """Extract widget metadata dict from an Annotated type, or None."""
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        for arg in args[1:]:
            if isinstance(arg, dict) and "widget" in arg:
                return arg
    return None


def get_widget_for_field(name: str, annotation, default):
    """Create an ipywidget for a single field based on its type annotation."""
    meta = _get_annotated_meta(annotation)

    if meta is not None:
        wtype = meta["widget"]
        if wtype == "slider":
            return widgets.FloatSlider(
                value=default if default is not dataclasses.MISSING else meta.get("default", 0),
                min=meta.get("min", 0),
                max=meta.get("max", 1),
                step=meta.get("step", 0.01),
                description=name,
            )
        elif wtype == "file":
            return widgets.Text(
                value=default if isinstance(default, str) else "",
                description=name,
                placeholder="path...",
            )
        elif wtype == "color":
            return widgets.ColorPicker(
                value="#808080",
                description=name,
            )

    # Type-based fallback
    if annotation is Rect or (isinstance(annotation, type) and issubclass(annotation, Rect)):
        r = default if isinstance(default, Rect) else Rect(0, 0, 100, 100)
        return widgets.HBox([
            widgets.IntText(value=r.x, description="x", layout=widgets.Layout(width="120px")),
            widgets.IntText(value=r.y, description="y", layout=widgets.Layout(width="120px")),
            widgets.IntText(value=r.w, description="w", layout=widgets.Layout(width="120px")),
            widgets.IntText(value=r.h, description="h", layout=widgets.Layout(width="120px")),
        ])

    if annotation is Curve or (isinstance(annotation, type) and issubclass(annotation, Curve)):
        # Prototyping simplification: text input instead of ipycanvas curve editor.
        # Spec calls for ipycanvas interactive editor — deferred to a later task.
        c = default if isinstance(default, Curve) else Curve()
        pts_str = "; ".join(f"{x},{y}" for x, y in c.points)
        return widgets.Text(
            value=pts_str,
            description=name,
            placeholder="x1,y1; x2,y2; ...",
        )

    if isinstance(default, str):
        return widgets.Text(value=default, description=name)

    return None


def _parse_curve_text(text: str) -> Curve:
    """Parse 'x1,y1; x2,y2; ...' into a Curve."""
    points = []
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        x, y = part.split(",")
        points.append((float(x.strip()), float(y.strip())))
    if len(points) < 2:
        points = [(0.0, 0.0), (1.0, 1.0)]
    return Curve(points=points)


def build_widgets(workflow_class):
    """Build widgets for a workflow class. Returns (vbox, getter_fn).

    getter_fn() returns a dict of field_name → current value.
    """
    hints = get_type_hints(workflow_class, include_extras=True)
    fields = dataclasses.fields(workflow_class)

    field_widgets = {}
    widget_list = []

    for f in fields:
        annotation = hints.get(f.name, f.type)
        default = f.default if f.default is not dataclasses.MISSING else (
            f.default_factory() if f.default_factory is not dataclasses.MISSING else dataclasses.MISSING
        )
        w = get_widget_for_field(f.name, annotation, default)
        if w is not None:
            field_widgets[f.name] = (w, annotation)
            widget_list.append(w)

    vbox = widgets.VBox(widget_list)

    def getter():
        result = {}
        for name, (w, ann) in field_widgets.items():
            if isinstance(w, widgets.HBox) and (ann is Rect or (isinstance(ann, type) and issubclass(ann, Rect))):
                children = w.children
                result[name] = Rect(
                    x=children[0].value,
                    y=children[1].value,
                    w=children[2].value,
                    h=children[3].value,
                )
            elif ann is Curve or (isinstance(ann, type) and issubclass(ann, Curve)):
                result[name] = _parse_curve_text(w.value)
            elif isinstance(w, widgets.FloatSlider):
                result[name] = w.value
            elif isinstance(w, widgets.Text):
                result[name] = w.value
            elif isinstance(w, widgets.ColorPicker):
                # Convert hex "#rrggbb" to tuple[float, float, float]
                hex_val = w.value.lstrip("#")
                result[name] = (
                    int(hex_val[0:2], 16) / 255.0,
                    int(hex_val[2:4], 16) / 255.0,
                    int(hex_val[4:6], 16) / 255.0,
                )
        return result

    return vbox, getter


def run_workflow(workflow_class):
    """Auto-generate UI for a workflow class and display it in Jupyter."""
    widget_box, getter = build_widgets(workflow_class)
    output = widgets.Output()
    run_btn = widgets.Button(description="Run", button_style="primary")

    def on_run(btn):
        vals = getter()
        wf = workflow_class(**vals)
        with output:
            clear_output(wait=True)
            from ops.io import show
            result = wf.run()
            show(result)

    run_btn.on_click(on_run)
    display(widgets.VBox([widget_box, run_btn, output]))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_ui.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add projects/3dml/ui.py projects/3dml/tests/test_ui.py
git commit -m "feat(3dml): add widget UI layer — auto-generates Jupyter controls from workflow annotations"
```

---

## Task 8: Demo Notebook & Integration Test

**Files:**
- Create: `projects/3dml/notebooks/image_process.ipynb`

- [ ] **Step 1: Create notebooks directory and demo notebook**

```bash
mkdir -p projects/3dml/notebooks
```

Create `projects/3dml/notebooks/image_process.ipynb` with these cells:

**Cell 1 (markdown):**
```markdown
# Image Processing Workflow

Load an image, crop, adjust saturation, apply per-channel curves, save.
```

**Cell 2 (code):**
```python
import sys
sys.path.insert(0, "..")

from workflows.image_process import ImageProcessWorkflow
from ui import run_workflow

run_workflow(ImageProcessWorkflow)
```

- [ ] **Step 2: Run all tests one final time**

```bash
cd /mnt/d/prg/plum/projects/3dml
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add projects/3dml/notebooks/image_process.ipynb
git commit -m "feat(3dml): add image processing demo notebook"
```

---

## Task 9: Update spec with rename

**Files:**
- Modify: `docs/superpowers/specs/2026-03-22-3dml-image-workflow-engine-design.md`

- [ ] **Step 1: Update spec to reflect `types.py` → `dtypes.py` rename**

In `docs/superpowers/specs/2026-03-22-3dml-image-workflow-engine-design.md`, make these replacements:
- `All types live in \`types.py\`` → `All types live in \`dtypes.py\``
- `from .types import` → `from .dtypes import`
- `├── types.py` → `├── dtypes.py`
- Also add a note under the curve editor line: `(v1 uses text input for curve control points; interactive ipycanvas editor is deferred)`

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-03-22-3dml-image-workflow-engine-design.md
git commit -m "docs(3dml): update spec — rename types.py to dtypes.py to avoid stdlib collision"
```
