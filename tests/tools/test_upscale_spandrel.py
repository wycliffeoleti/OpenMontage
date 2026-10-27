"""Upscale falls back to spandrel when realesrgan cannot be imported.

realesrgan depends on basicsr 1.4.2, which imports the removed
``torchvision.transforms.functional_tensor`` and fails on torchvision >= 0.17.
spandrel (MIT) loads the same Real-ESRGAN checkpoints. These tests run the real
spandrel loader on a tiny ESRGAN checkpoint placed where the tool caches
weights, so no network download happens.
"""

import shutil
import subprocess
import sys

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
torch = pytest.importorskip("torch")
pytest.importorskip("spandrel")

from spandrel.architectures.ESRGAN import ESRGAN

from tools.base_tool import ToolStatus
from tools.enhancement.upscale import Upscale, _tiled_forward


@pytest.fixture
def without_realesrgan(monkeypatch):
    # A None entry makes ``import realesrgan`` raise ImportError.
    monkeypatch.setitem(sys.modules, "realesrgan", None)


@pytest.fixture
def tiny_weights(tmp_path, monkeypatch):
    hub = tmp_path / "torch-hub"
    (hub / "checkpoints").mkdir(parents=True)
    torch.manual_seed(0)
    model = ESRGAN(num_filters=8, num_blocks=1, scale=4)
    torch.save({"params_ema": model.state_dict()}, hub / "checkpoints" / "RealESRGAN_x4plus.pth")
    previous = torch.hub.get_dir()
    torch.hub.set_dir(str(hub))
    yield hub
    torch.hub.set_dir(previous)


def _image(path, channels):
    rng = np.random.default_rng(1)
    pixels = rng.integers(0, 256, size=(12, 16, channels), dtype=np.uint8)
    if channels == 4:
        pixels[:, :8, 3] = 0
        pixels[:, 8:, 3] = 255
    cv2.imwrite(str(path), pixels)
    return path


def test_status_is_available_through_spandrel(without_realesrgan):
    assert Upscale().get_status() == ToolStatus.AVAILABLE


def test_status_is_unavailable_without_any_backend(without_realesrgan, monkeypatch):
    monkeypatch.setitem(sys.modules, "spandrel", None)
    assert Upscale().get_status() == ToolStatus.UNAVAILABLE


def test_image_is_upscaled_four_times(without_realesrgan, tiny_weights, tmp_path):
    output = tmp_path / "out.png"
    result = Upscale().execute({
        "input_path": str(_image(tmp_path / "in.png", 3)),
        "output_path": str(output),
    })
    assert result.success, result.error
    assert result.data["backend"] == "spandrel"
    assert cv2.imread(str(output)).shape == (48, 64, 3)


def test_scale_two_resizes_the_four_times_model_output(without_realesrgan, tiny_weights, tmp_path):
    output = tmp_path / "out.png"
    result = Upscale().execute({
        "input_path": str(_image(tmp_path / "in.png", 3)),
        "output_path": str(output),
        "scale": 2,
    })
    assert result.success, result.error
    assert cv2.imread(str(output)).shape == (24, 32, 3)


def test_alpha_channel_survives_upscaling(without_realesrgan, tiny_weights, tmp_path):
    output = tmp_path / "out.png"
    result = Upscale().execute({
        "input_path": str(_image(tmp_path / "in.png", 4)),
        "output_path": str(output),
    })
    assert result.success, result.error
    upscaled = cv2.imread(str(output), cv2.IMREAD_UNCHANGED)
    assert upscaled.shape == (48, 64, 4)
    assert upscaled[:, :28, 3].max() == 0
    assert upscaled[:, 36:, 3].min() == 255


def test_face_enhance_is_refused_without_gfpgan(without_realesrgan, tiny_weights, tmp_path):
    result = Upscale().execute({
        "input_path": str(_image(tmp_path / "in.png", 3)),
        "output_path": str(tmp_path / "out.png"),
        "face_enhance": True,
    })
    assert result.success is False
    assert "face_enhance" in result.error


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_video_frames_are_upscaled(without_realesrgan, tiny_weights, tmp_path):
    source, output = tmp_path / "in.mp4", tmp_path / "out.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=16x12:rate=5:duration=0.6",
         "-pix_fmt", "yuv420p", str(source)],
        capture_output=True, check=True, timeout=30,
    )
    result = Upscale().execute({"input_path": str(source), "output_path": str(output)})
    assert result.success, result.error
    capture = cv2.VideoCapture(str(output))
    assert (capture.get(cv2.CAP_PROP_FRAME_WIDTH), capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) == (64, 48)
    capture.release()


@pytest.mark.parametrize("tile", [5, 7, 64])
def test_tiles_reassemble_into_the_whole_image_result(tile):
    image = torch.arange(12 * 16 * 3, dtype=torch.float32).reshape(1, 3, 12, 16)

    def nearest_x4(tensor):
        return torch.nn.functional.interpolate(tensor, scale_factor=4, mode="nearest")

    tiled = _tiled_forward(nearest_x4, image, scale=4, tile=tile, tile_pad=2)
    assert torch.equal(tiled, nearest_x4(image))
