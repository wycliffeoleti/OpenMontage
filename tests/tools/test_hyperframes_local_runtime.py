"""Configured local CLI must work without npm and must never silently fall back."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.video.hyperframes_compose import HyperFramesCompose


@pytest.fixture
def local_cli(tmp_path, monkeypatch):
    package = tmp_path / "node_modules" / "hyperframes"
    (package / "bin").mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({
        "name": "hyperframes", "version": "0.8.206",
    }))
    cli = package / "bin" / "hyperframes.mjs"
    payload = {"ok": True, "checks": [{"name": name, "ok": True} for name in
               ("Node.js", "FFmpeg", "FFprobe", "Chrome")]}
    cli.write_text('console.log(process.argv.includes("doctor") ? '
                   f'JSON.stringify({json.dumps(payload)}) : "LOCAL-CLI-0.8.206");\n')
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the local executable boundary test")
    monkeypatch.setenv("HYPERFRAMES_CLI_PATH", str(cli))
    original_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name, *a, **kw:
                        None if name in {"npm", "npx"} else original_which(name, *a, **kw))
    monkeypatch.setattr(HyperFramesCompose, "_npm_resolve_cache", None)
    monkeypatch.setattr(HyperFramesCompose, "_cli_probe_cache", None)
    return cli


def test_configured_cli_is_available_without_npm(local_cli):
    result = HyperFramesCompose()._runtime_check()
    assert result["runtime_available"], result["reasons"]
    assert result["npm_package_version"] == "0.8.206"


def test_render_invocation_uses_configured_cli(local_cli, tmp_path):
    try:
        result = HyperFramesCompose()._run_hf(
            ["--version"], cwd=tmp_path, timeout=2, check=False,
        )
    except OSError as exc:
        pytest.fail(f"Configured local CLI was not used: {exc}")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "LOCAL-CLI-0.8.206"


def test_broken_configured_path_is_not_replaced_with_npx(tmp_path, monkeypatch):
    missing = tmp_path / "missing-cli.mjs"
    monkeypatch.setenv("HYPERFRAMES_CLI_PATH", str(missing))
    result = HyperFramesCompose()._runtime_check()
    assert not result["runtime_available"]
    assert str(missing) in "; ".join(result["reasons"])


def test_doctor_required_failure_is_not_hidden_by_zero_exit(local_cli):
    local_cli.write_text('console.log(JSON.stringify({ok:false,checks:['
                        '{name:"Chrome",ok:false,detail:"missing"}]}));\n')
    result = HyperFramesCompose()._runtime_check()
    assert not result["runtime_available"]
    assert "Chrome" in "; ".join(result["reasons"])


def test_optional_doctor_warnings_allow_visual_rendering(local_cli):
    local_cli.write_text('console.log(JSON.stringify({ok:false,checks:['
                        '{name:"Chrome",ok:true,detail:"installed"},'
                        '{name:"Node.js",ok:true},{name:"FFmpeg",ok:true},{name:"FFprobe",ok:true},'
                        '{name:"Docker",ok:false,detail:"optional"},'
                        '{name:"TTS (Kokoro)",ok:false,detail:"optional"}]}));\n')
    result = HyperFramesCompose()._runtime_check()
    assert result["runtime_available"], result["reasons"]


def test_incomplete_doctor_report_cannot_claim_readiness(local_cli):
    local_cli.write_text('console.log(JSON.stringify({ok:true,checks:[]}));\n')
    result = HyperFramesCompose()._runtime_check()
    assert not result["runtime_available"]
    assert "Chrome" in "; ".join(result["reasons"])
