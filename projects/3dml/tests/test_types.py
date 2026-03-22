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
