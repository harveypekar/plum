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
