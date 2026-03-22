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
    """With default params (full crop, sat=1.0, identity curves), output ~ input."""
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
    # HSV roundtrip (adjust_saturation with factor=1.0) + uint8 save + LUT quantization
    np.testing.assert_allclose(result, original, atol=8.0 / 255)
