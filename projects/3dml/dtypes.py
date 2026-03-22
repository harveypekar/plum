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
