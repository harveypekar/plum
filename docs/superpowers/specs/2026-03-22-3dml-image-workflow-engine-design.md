# 3DML — Image & Avatar Workflow Engine

## Overview

A Python workflow engine for digital avatar creation and image manipulation. Workflows are dataclasses that compose pure operations, with typed inputs that auto-generate Jupyter widget UIs for artist control.

Independent from ComfyUI. Deployment-agnostic. Jupyter notebooks for prototyping.

## Vision

Three planned workflow categories (only the first is in scope for v1):

1. **Image processing** — crop, color correction, curves (super-resolution deferred until ML deps are set up)
2. **3D avatar** — photo → 3D model → piercings/accessories → skeleton + blend shapes → export
3. **Scene composition** — text description + character references → consistent multi-image output

Character appearance consistency across images is a core long-term requirement.

## Architecture

### Three Layers

**`Op`** — atomic, stateless functions. Take arrays in, return arrays out. Grouped by domain in `ops/` modules.

**`Workflow`** — a Python dataclass that orchestrates ops. Declares typed, annotated input fields. Has a `run()` method that calls ops in sequence. Branching and convergence are plain Python in `run()`.

**`WorkflowUI`** — inspects a workflow's type annotations and auto-generates Jupyter widgets (sliders, file pickers, color pickers, curve editors). Thin layer, no custom DSL.

### Type System

Images are `float32 HWC [0,1]` (`np.ndarray`), always RGB (3 channels). Alpha is stripped on load. Normalization happens at load/save boundaries.

All types live in `dtypes.py` (named to avoid shadowing Python's built-in `types` module). Input types use `typing.Annotated` with widget metadata:

```python
from typing import Annotated
from dataclasses import dataclass, field

@dataclass
class Rect:
    x: int; y: int; w: int; h: int

IDENTITY_CURVE = [(0.0, 0.0), (1.0, 1.0)]

@dataclass
class Curve:
    points: list[tuple[float, float]] = field(default_factory=lambda: list(IDENTITY_CURVE))
    # control points in 0-1 range, interpolated via cubic spline
    # identity curve [(0,0),(1,1)] = no change
    # empty points list is invalid — always at least 2 points

# Widget hints via Annotated
# "default" in metadata is extracted by the UI layer and used as the dataclass field default
Slider = lambda **kw: Annotated[float, {"widget": "slider", **kw}]
ColorPick = Annotated[tuple[float,float,float], {"widget": "color"}]
FilePath = lambda **kw: Annotated[str, {"widget": "file", **kw}]
```

### Widget Resolution

The UI layer resolves widgets in order:
1. `Annotated` metadata with explicit `"widget"` key → use that widget
2. Type-based fallback: `Curve` → curve editor, `Rect` → numeric inputs, `str` → text input
3. Unknown type → skip (no widget, must be set programmatically)

### Defaults

The `"default"` key in `Annotated` metadata serves as both the dataclass field default and the widget's initial value. The UI layer extracts it during instantiation. For types without `Annotated` wrappers (e.g. `Curve`), use `dataclasses.field(default_factory=...)`.

### Example Workflow

```python
from .dtypes import FilePath, Slider, Rect, Curve
from .ops import io as ops_io, color, geometry

@dataclass
class ImageProcessWorkflow:
    input_image: FilePath(accept=".png,.jpg")
    crop_rect: Rect = field(default_factory=lambda: Rect(0, 0, 512, 512))
    saturation: Slider(min=0, max=2, default=1.0) = 1.0
    curve_r: Curve = field(default_factory=Curve)
    curve_g: Curve = field(default_factory=Curve)
    curve_b: Curve = field(default_factory=Curve)
    output_path: FilePath(accept=".png", mode="save") = "output.png"

    def run(self) -> np.ndarray:
        img = ops_io.load(self.input_image)
        img = geometry.crop(img, self.crop_rect)
        img = color.to_hsv(img)
        img = color.adjust_saturation(img, self.saturation)
        img = color.to_rgb(img)
        img = color.apply_curves(img, self.curve_r, self.curve_g, self.curve_b)
        ops_io.save(img, self.output_path)
        return img
```

### Notebook Usage

```python
from workflows.image_process import ImageProcessWorkflow
from ui import run_workflow

run_workflow(ImageProcessWorkflow)
```

One import, one call. The UI is generated from the workflow class.

## Operations Library (v1)

### `ops/io.py`

- `load(path) → ndarray` — reads any image format, normalizes to float32 HWC [0,1]
- `save(img, path)` — converts to uint8, writes to disk
- `show(img)` — inline IPython display for debugging

### `ops/geometry.py`

- `crop(img, rect) → img`
- `resize(img, w, h, method="lanczos") → img`

### `ops/color.py`

- `to_hsv(img) → img` / `to_rgb(img) → img`
- `adjust_saturation(img, factor) → img` — convenience wrapper, operates on HSV channel 1
- `apply_curves(img, curve_r, curve_g, curve_b) → img` — cubic spline interpolation from Curve control points, applied per channel. Identity curve `[(0,0),(1,1)]` = no change.

### Op Conventions

- Input/output: `ndarray` float32 HWC RGB (except I/O ops)
- No side effects (except save/show)
- No internal state
- Validate inputs with `ValueError` (not `assert`) — messages should be actionable (e.g. "crop rect exceeds image bounds: rect.w=800 but image width=512")
- Ops clamp invalid geometry to image bounds rather than crashing (e.g. crop rect partially outside → crop to intersection)

## Widget UI Layer (`ui.py`)

`run_workflow(workflow_class)` does:

1. Read each field's `Annotated` metadata
2. Create matching widget (slider → `FloatSlider`, file → `FileUpload`, color → `ColorPicker`)
3. Layout vertically with labels
4. Add "Run" button → instantiate workflow with current values → call `run()`
5. Display output image inline

Special widgets for prototyping:
- **Curve editor** — `ipycanvas` canvas, click to add/move control points, cubic spline preview (v1 uses text input for curve control points; interactive ipycanvas editor is deferred)
- **Crop tool** — numeric inputs (x, y, w, h) with image preview overlay
- **Image preview** — auto-shown after `run()`, also via `ops.show()` mid-pipeline
- **File save** (`mode="save"`) — `Text` input for the output path (no native file-save picker in ipywidgets)

After `run()` completes, widgets stay live — the user can tweak parameters and re-run. No reset button; re-running overwrites the previous output display.

## Project Structure

```
projects/3dml/
├── ops/
│   ├── __init__.py
│   ├── io.py
│   ├── geometry.py
│   └── color.py
├── workflows/
│   ├── __init__.py
│   └── image_process.py
├── dtypes.py
├── ui.py
├── notebooks/
│   └── image_process.ipynb
├── requirements.txt
└── .venv/
```

## Dependencies

**v1 (install now):**
- `numpy` — image arrays
- `Pillow` — image I/O
- `scipy` — cubic spline interpolation for curves
- `ipywidgets` — Jupyter controls
- `ipycanvas` — curve editor canvas

**Later (as needed):**
- `realesrgan` / `torch` — superres
- `trimesh` / `open3d` — 3D workflows
- ML model packages per workflow

## Out of Scope (v1)

- 3D operations (workflow #2)
- Scene composition (workflow #3)
- Character consistency system
- Non-Jupyter UI
- ComfyUI integration
- Deployment / API
- Caching / incremental re-execution

## First Milestone

Run the image processing workflow end-to-end in a notebook: load image → crop → HSV adjust → curves → save. With auto-generated widget controls. Super-resolution is deferred until ML dependencies (torch, realesrgan) are set up — the workflow framework and basic ops come first.
