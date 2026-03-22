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

    getter_fn() returns a dict of field_name -> current value.
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
