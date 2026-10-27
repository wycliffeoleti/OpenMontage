"""Exercise model dispatch and memory policy without downloading model weights."""
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

from tools.graphics.local_diffusion import LocalDiffusion


@pytest.mark.parametrize("cuda,model,want", [
    (True, None, "stabilityai/stable-diffusion-xl-base-1.0"),
    (False, None, "stabilityai/stable-diffusion-xl-base-1.0"),
    (True, "custom-sd15", "custom-sd15"),
])
def test_model_dispatch_offload_and_image_output(monkeypatch, tmp_path, cuda, model, want):
    events = []
    class Pipeline:
        @classmethod
        def from_pretrained(cls, model_id, **kwargs):
            events.append(("load", model_id, kwargs))
            return cls()
        def enable_model_cpu_offload(self):
            events.append(("offload",))
        def enable_vae_tiling(self):
            pass
        def to(self, device):
            events.append(("to", device))
            return self
        def __call__(self, prompt, **kwargs):
            return SimpleNamespace(images=[Image.new("RGB", (kwargs["width"], kwargs["height"]), "red")])
    monkeypatch.setitem(sys.modules, "diffusers", SimpleNamespace(AutoPipelineForText2Image=Pipeline, StableDiffusionPipeline=Pipeline))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: cuda, empty_cache=lambda: None),
        float16="fp16", float32="fp32",
    ))
    monkeypatch.delenv("LOCAL_DIFFUSION_MODEL_PATH", raising=False)
    inputs = {"prompt": "test", "width": 64, "height": 48, "output_path": str(tmp_path / "out.png")}
    if model:
        inputs["model"] = model
    result = LocalDiffusion().execute(inputs)
    assert result.success, result.error
    assert result.data["model"] == want
    expected = {"torch_dtype": "fp16" if cuda else "fp32"}
    if model is None:
        expected["variant"] = "fp16"
    assert events[0] == ("load", want, expected)
    assert (("offload",) in events) == cuda
    assert ("to", "cuda") not in events
    if not cuda:
        assert ("to", "cpu") in events
    assert Image.open(tmp_path / "out.png").size == (64, 48)


def test_verified_local_snapshot_is_used_for_default_only(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_DIFFUSION_MODEL_PATH", str(tmp_path))
    tool = LocalDiffusion()
    assert tool._model_source({}) == str(tmp_path)
    assert tool._model_source({"model": "custom"}) == "custom"
