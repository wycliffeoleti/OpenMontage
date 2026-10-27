"""math_animate must work from the venv interpreter without .venv/bin on PATH."""

import subprocess
import sys

from tools.base_tool import ToolStatus
from tools.graphics import math_animate
from tools.graphics.math_animate import MathAnimate

SCENE = (
    "from manim import *\n"
    "class Demo(Scene):\n"
    "    def construct(self):\n"
    "        self.add(Circle())\n"
)


def test_installed_module_is_available_without_manim_on_path(monkeypatch):
    monkeypatch.setattr(math_animate.shutil, "which", lambda name: None)
    monkeypatch.setattr(math_animate.importlib.util, "find_spec", lambda name: object())
    assert MathAnimate().get_status() == ToolStatus.AVAILABLE


def test_missing_module_and_executable_is_unavailable(monkeypatch):
    monkeypatch.setattr(math_animate.shutil, "which", lambda name: None)
    monkeypatch.setattr(math_animate.importlib.util, "find_spec", lambda name: None)
    assert MathAnimate().get_status() == ToolStatus.UNAVAILABLE
    result = MathAnimate().execute({"scene_code": SCENE, "scene_name": "Demo"})
    assert not result.success
    assert "Manim not found" in (result.error or "")


def test_render_uses_interpreter_module_without_manim_on_path(monkeypatch):
    commands = []

    def failed_render(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="stop")

    monkeypatch.setattr(math_animate.shutil, "which", lambda name: None)
    monkeypatch.setattr(math_animate.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(math_animate.subprocess, "run", failed_render)
    MathAnimate().execute({"scene_code": SCENE, "scene_name": "Demo", "quality": "low"})
    assert commands and commands[0][:3] == [sys.executable, "-m", "manim"]
