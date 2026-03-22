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
