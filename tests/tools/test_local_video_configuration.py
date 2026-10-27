"""Configuration must select the same model in discovery, estimates and execution."""
import sys
from types import SimpleNamespace

import pytest

from tools.base_tool import ToolResult, ToolStatus
from tools.video.wan_video import DEFAULT_VARIANT, WanVideo
from tools.video.hunyuan_video import HunyuanVideo
from tools.video.ltx_video_local import LTXVideoLocal
from tools.video.cogvideo_video import CogVideoVideo


@pytest.fixture
def local_stack(monkeypatch):
    monkeypatch.setenv("VIDEO_GEN_LOCAL_ENABLED", "true")
    monkeypatch.setenv("VIDEO_GEN_LOCAL_MODEL", "wan2.1-1.3b")
    monkeypatch.delenv("VIDEO_GEN_LOCAL_MODEL_PATH", raising=False)
    monkeypatch.setitem(sys.modules, "diffusers", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)))


def test_only_configured_family_is_advertised(local_stack):
    assert WanVideo().get_status() == ToolStatus.AVAILABLE
    for tool in (HunyuanVideo(), LTXVideoLocal(), CogVideoVideo()):
        assert tool.get_status() == ToolStatus.UNAVAILABLE


def test_wan_configured_default_controls_plan_schema_and_execution(local_stack, monkeypatch):
    tool = WanVideo()
    assert tool._plan({})["width"] == 832
    assert tool.get_info()["input_schema"]["properties"]["model_variant"]["default"] == "wan2.1-1.3b"
    def generate(**kwargs):
        chosen = kwargs["inputs"].get("model_variant") or kwargs["default_variant"]
        return ToolResult(success=True, data={"chosen": chosen})
    monkeypatch.setattr("tools.video.wan_video.generate_wan", generate)
    assert tool.execute({"prompt": "test"}).data["chosen"] == "wan2.1-1.3b"
    assert tool.execute({"prompt": "test", "model_variant": "wan2.1-14b"}).data["chosen"] == "wan2.1-14b"
    assert tool._plan({"model_variant": "wan2.1-14b"})["width"] == 1280


def test_unset_model_keeps_legacy_flag_behavior(local_stack, monkeypatch):
    monkeypatch.delenv("VIDEO_GEN_LOCAL_MODEL")
    for tool in (WanVideo(), HunyuanVideo(), LTXVideoLocal(), CogVideoVideo()):
        assert tool.get_status() == ToolStatus.AVAILABLE
    assert WanVideo().get_info()["input_schema"]["properties"]["model_variant"]["default"] == DEFAULT_VARIANT


def test_invalid_config_does_not_advertise_or_silently_choose_model(local_stack, monkeypatch):
    monkeypatch.setenv("VIDEO_GEN_LOCAL_MODEL", "not-a-model")
    assert WanVideo().get_status() == ToolStatus.UNAVAILABLE
    result = WanVideo().execute({"prompt": "test"})
    assert not result.success


def test_configured_snapshot_only_applies_to_matching_variant(local_stack, monkeypatch, tmp_path):
    from tools.video._wan_engine import generate_wan
    from tools.video._shared import WAN_VARIANTS
    monkeypatch.setenv("VIDEO_GEN_LOCAL_MODEL_PATH", str(tmp_path))
    seen = []
    def load(**kwargs):
        seen.append(kwargs["model_id"])
        raise RuntimeError("stop before inference")
    monkeypatch.setattr("tools.video._wan_engine.load_wan_pipeline", load)
    for variant in ("wan2.1-1.3b", "wan2.1-14b"):
        generate_wan(tool_name="wan_video", variants=WAN_VARIANTS, default_variant=variant,
                     inputs={"prompt": "test", "model_variant": variant})
    assert seen == [str(tmp_path), "Wan-AI/Wan2.1-T2V-14B-Diffusers"]
