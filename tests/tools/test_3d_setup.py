"""Configuration preservation and real output validation for 3D setup."""

import importlib
import json
import subprocess

import pytest


def setup_module_api():
    try:
        return importlib.import_module("scripts.setup_3d_tools")
    except ModuleNotFoundError:
        pytest.fail("The repeatable 3D setup command has not been implemented")


def test_environment_update_preserves_other_settings_and_is_idempotent(tmp_path):
    setup = setup_module_api()
    path = tmp_path / ".env"
    path.write_text('# Keep this comment\nOTHER_TOKEN="keep me"\nHYPERFRAMES_CLI_PATH=old\n')
    setup.update_environment(path, {"HYPERFRAMES_CLI_PATH": "/runtime/cli.mjs"})
    first = path.read_bytes()
    setup.update_environment(path, {"HYPERFRAMES_CLI_PATH": "/runtime/cli.mjs"})
    assert path.read_bytes() == first
    assert '# Keep this comment\nOTHER_TOKEN="keep me"\n' in path.read_text()
    assert 'HYPERFRAMES_CLI_PATH="/runtime/cli.mjs"' in path.read_text()
    assert "old" not in path.read_text()


def test_environment_update_replaces_duplicate_target_keys_only(tmp_path):
    setup = setup_module_api()
    path = tmp_path / ".env"
    path.write_text("OTHER=1\nHYPERFRAMES_CLI_PATH=first\nHYPERFRAMES_CLI_PATH=second\n")
    setup.update_environment(path, {"HYPERFRAMES_CLI_PATH": "new"})
    assert path.read_text().count("HYPERFRAMES_CLI_PATH=") == 1
    assert path.read_text().startswith("OTHER=1\n")


def test_doctor_optional_audio_and_docker_do_not_block_visual_route():
    setup = setup_module_api()
    payload = {"ok": False, "checks": [
        {"name": "Chrome", "ok": True},
        {"name": "Node.js", "ok": True},
        {"name": "FFmpeg", "ok": True},
        {"name": "FFprobe", "ok": True},
        {"name": "Docker", "ok": False},
        {"name": "TTS (Kokoro)", "ok": False},
    ]}
    assert setup.required_doctor_errors(payload) == []
    payload["checks"][0]["ok"] = False
    assert "Chrome" in "; ".join(setup.required_doctor_errors(payload))


def test_video_verification_rejects_missing_output(tmp_path):
    setup = setup_module_api()
    with pytest.raises((ValueError, FileNotFoundError), match="missing|Missing"):
        setup.verify_video(tmp_path / "missing.mp4", 1, (64, 64), 10, tmp_path)


def test_video_verification_rejects_nonblank_static_output(tmp_path):
    setup = setup_module_api()
    video = tmp_path / "static.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        "smptebars=size=64x64:rate=10:duration=1", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", str(video),
    ], check=True, capture_output=True)
    with pytest.raises(ValueError, match="motion|static"):
        setup.verify_video(video, 1, (64, 64), 10, tmp_path / "frames")


def test_smoke_replaces_old_pass_report_when_readiness_raises(tmp_path, monkeypatch):
    setup = setup_module_api()
    report_path = tmp_path / "smoke-report.json"
    report_path.write_text('{"status":"passed"}')

    def broken_check():
        raise RuntimeError("health probe failed")

    monkeypatch.setattr(setup, "check", broken_check)
    try:
        result = setup.smoke(tmp_path)
    except RuntimeError as exc:
        pytest.fail(f"Smoke did not retain its failure report: {exc}")
    assert result["status"] == "failed"
    assert "health probe failed" in result["error"]
    assert '"status": "failed"' in report_path.read_text()


def test_unconfigured_check_never_invokes_npm_or_npx(monkeypatch):
    setup = setup_module_api()
    commands = []
    health = {"ok": True, "checks": [{"name": name, "ok": True} for name in
              ("Node.js", "FFmpeg", "FFprobe", "Chrome")]}

    def command_result(command, **kwargs):
        commands.append(command)
        output = json.dumps(health) if "doctor" in command else "0.8.206" if "view" in command else "v24.20.0"
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    monkeypatch.setenv("HYPERFRAMES_CLI_PATH", "")
    monkeypatch.setattr(setup.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", command_result)
    monkeypatch.setattr(setup.HyperFramesCompose, "_npm_resolve_cache", None)
    monkeypatch.setattr(setup.HyperFramesCompose, "_cli_probe_cache", None)
    result = setup.check()
    assert result["status"] == "blocked"
    assert not any(command[0].rsplit("/", 1)[-1] in {"npm", "npx"} for command in commands), commands


def test_check_blocks_manim_when_agents_cannot_use_math_animate(monkeypatch):
    setup = setup_module_api()

    class Unavailable:
        def get_status(self):
            return setup.ToolStatus.UNAVAILABLE

    class Tools:
        def get(self, name):
            return Unavailable() if name == "math_animate" else real.get(name)

    real = setup.discover()
    monkeypatch.setattr(setup, "discover", lambda: Tools())
    manim = setup.check()["routes"]["manim"]
    assert manim["status"] == "blocked"
    assert any("math_animate" in error for error in manim["errors"])


def test_browser_discovery_prefers_highest_version_number(tmp_path, monkeypatch):
    setup = setup_module_api()
    root = tmp_path / ".cache/puppeteer/chrome-headless-shell"
    for version in ("linux-99.0.1", "linux-154.0.8"):
        shell = root / version / "chrome-headless-shell-linux64/chrome-headless-shell"
        shell.parent.mkdir(parents=True)
        shell.write_text("")
        shell.chmod(0o755)
    monkeypatch.delenv("HYPERFRAMES_BROWSER_PATH", raising=False)
    monkeypatch.setattr(setup.Path, "home", lambda: tmp_path)
    assert "linux-154.0.8" in str(setup.existing_headless_browser())
