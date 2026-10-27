"""OPENMONTAGE_OUTPUT_FPS sets the finished-video frame rate everywhere."""

import subprocess

import pytest

from lib.media_profiles import delivery_fps, ffmpeg_output_args, get_profile
from tools.graphics import math_animate
from tools.graphics.math_animate import MathAnimate
from tools.video.hyperframes_compose import HyperFramesCompose

SCENE = "from manim import *\nclass Demo(Scene):\n    def construct(self):\n        self.add(Circle())\n"


def manim_command(monkeypatch, quality):
    commands = []

    def stop_render(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="stop")

    monkeypatch.setattr(math_animate.subprocess, "run", stop_render)
    monkeypatch.setattr(math_animate, "_manim_command", lambda: ["manim"])
    MathAnimate().execute({"scene_code": SCENE, "scene_name": "Demo", "quality": quality})
    return commands[0]


def test_unset_keeps_profile_defaults(monkeypatch):
    monkeypatch.delenv("OPENMONTAGE_OUTPUT_FPS", raising=False)
    assert delivery_fps(30) == 30
    assert get_profile("youtube_shorts").fps == 30
    assert get_profile("cinematic").fps == 24


def test_setting_overrides_every_profile_and_encode(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_OUTPUT_FPS", "60")
    assert delivery_fps(30) == 60
    for name in ("youtube_landscape", "youtube_shorts", "tiktok", "instagram_reels", "cinematic"):
        assert get_profile(name).fps == 60
    args = ffmpeg_output_args(get_profile("tiktok"))
    assert args[args.index("-r") + 1] == "60"


@pytest.mark.parametrize("value", ["sixty", "45", "0"])
def test_invalid_setting_fails_clearly(monkeypatch, value):
    monkeypatch.setenv("OPENMONTAGE_OUTPUT_FPS", value)
    with pytest.raises(ValueError, match="OPENMONTAGE_OUTPUT_FPS"):
        delivery_fps(30)


def test_hyperframes_final_renders_use_delivery_rate_but_drafts_do_not(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_OUTPUT_FPS", "60")
    assert HyperFramesCompose._requested_fps({"quality": "standard"}) == 60
    assert HyperFramesCompose._requested_fps({}) == 60
    assert HyperFramesCompose._requested_fps({"quality": "draft"}) == 30
    assert HyperFramesCompose._requested_fps({"quality": "high", "fps": 24}) == 24


def test_hyperframes_unset_keeps_thirty(monkeypatch):
    monkeypatch.delenv("OPENMONTAGE_OUTPUT_FPS", raising=False)
    assert HyperFramesCompose._requested_fps({"quality": "high"}) == 30


def test_manim_delivery_presets_follow_setting_and_drafts_stay_fast(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_OUTPUT_FPS", "60")
    medium = manim_command(monkeypatch, "medium")
    assert medium[medium.index("--frame_rate") + 1] == "60"
    assert "--frame_rate" not in manim_command(monkeypatch, "high")  # already 60
    assert "--frame_rate" not in manim_command(monkeypatch, "low")


def test_manim_unset_adds_no_frame_rate(monkeypatch):
    monkeypatch.delenv("OPENMONTAGE_OUTPUT_FPS", raising=False)
    assert "--frame_rate" not in manim_command(monkeypatch, "medium")


def remotion_props(tmp_path, monkeypatch):
    """Run the Remotion path with the CLI stubbed; return the props it would render."""
    import json
    import shutil as shutil_module

    from tools.video.video_compose import VideoCompose

    monkeypatch.setattr(shutil_module, "which", lambda name: f"/usr/bin/{name}")
    tool, seen = VideoCompose(), []

    def fake_run(cmd, **kwargs):
        props = next(a.split("=", 1)[1] for a in cmd if a.startswith("--props="))
        seen.append(json.loads(open(props, encoding="utf-8").read()))

    monkeypatch.setattr(tool, "run_command", fake_run)
    tool._remotion_render({
        "output_path": str(tmp_path / "final.mp4"),
        "composition_data": {"renderer_family": "explainer-data", "cuts": [
            {"id": "c1", "type": "text_card", "text": "Hi", "in_seconds": 0, "out_seconds": 2}]},
    })
    return seen[0]


def test_remotion_receives_delivery_fps(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_OUTPUT_FPS", "60")
    assert remotion_props(tmp_path, monkeypatch)["fps"] == 60


def test_remotion_props_unchanged_when_unset(tmp_path, monkeypatch):
    assert "fps" not in remotion_props(tmp_path, monkeypatch)


@pytest.fixture
def thirty_fps_video(tmp_path):
    path = tmp_path / "out.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path),
    ], check=True, capture_output=True)
    return path


def test_final_review_blocks_wrong_delivery_rate(monkeypatch, thirty_fps_video):
    from tools.video.video_compose import VideoCompose

    monkeypatch.setenv("OPENMONTAGE_OUTPUT_FPS", "60")
    review = VideoCompose()._run_final_review(thirty_fps_video)
    assert any("Delivery frame rate mismatch" in i for i in review["issues_found"])
    assert review["status"] == "revise"


def test_final_review_allows_drafts_and_unset(monkeypatch, thirty_fps_video):
    from tools.video.video_compose import VideoCompose

    monkeypatch.setenv("OPENMONTAGE_OUTPUT_FPS", "60")
    draft = VideoCompose()._run_final_review(thirty_fps_video, draft=True)
    monkeypatch.delenv("OPENMONTAGE_OUTPUT_FPS")
    unset = VideoCompose()._run_final_review(thirty_fps_video)
    for review in (draft, unset):
        assert not any("frame rate mismatch" in i for i in review["issues_found"])


def test_blender_animation_defaults_to_delivery_rate(tmp_path, monkeypatch):
    from tools.graphics import blender_world

    commands = []
    monkeypatch.setenv("OPENMONTAGE_OUTPUT_FPS", "60")
    monkeypatch.setattr(blender_world, "find_blender", lambda: "/usr/bin/blender")
    monkeypatch.setattr(blender_world.subprocess, "run", lambda cmd, **kw: commands.append(cmd)
                        or subprocess.CompletedProcess(cmd, 1, stdout="", stderr="stop"))
    blender_world.BlenderWorld().execute({
        "operation": "render_animation", "world_spec": {}, "duration_seconds": 1,
        "blend_path": str(tmp_path / "w.blend"), "output_path": str(tmp_path / "out"),
    })
    assert commands and commands[0][commands[0].index("--fps") + 1] == "60"
