import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tools.analysis.transcriber import Transcriber


@pytest.fixture(autouse=True)
def no_parent_inference(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("configured isolated inference must not construct a parent model")
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=forbidden))


def test_cuda_worker_gets_private_libraries_without_changing_parent(monkeypatch, tmp_path):
    root = tmp_path / "cuda12"
    for package in ("cublas", "cudnn"):
        (root / "nvidia" / package / "lib").mkdir(parents=True)
    monkeypatch.setenv("WHISPER_CUDA12_ROOT", str(root))
    monkeypatch.setenv("LD_LIBRARY_PATH", "/other/cuda13")
    input_path = tmp_path / "in.wav"
    input_path.write_bytes(b"fixture")
    received = []
    def run(command, **kwargs):
        received.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, json.dumps({
            "success": True, "data": {"device": "cuda", "word_timestamps": []}, "artifacts": [],
        }), "")
    monkeypatch.setattr("subprocess.run", run)
    result = Transcriber().execute({"input_path": str(input_path), "output_dir": str(tmp_path)})
    assert result.success
    assert result.data["device"] == "cuda"
    command, kwargs = received[0]
    assert command[-1] == "tools.analysis._whisper_worker"
    assert kwargs["env"]["LD_LIBRARY_PATH"].split(os.pathsep) == [
        str(root / "nvidia/cublas/lib"), str(root / "nvidia/cudnn/lib"),
    ]
    assert kwargs["env"]["OPENMONTAGE_WHISPER_WORKER"] == "1"
    assert os.environ["LD_LIBRARY_PATH"] == "/other/cuda13"


def test_worker_native_failure_is_retried_on_cpu(monkeypatch, tmp_path):
    monkeypatch.setenv("WHISPER_CUDA12_ROOT", str(tmp_path))
    source = tmp_path / "in.wav"
    source.write_bytes(b"fixture")
    devices = []
    def run(command, **kwargs):
        cpu = kwargs["env"].get("OPENMONTAGE_WHISPER_FORCE_CPU") == "1"
        devices.append(cpu)
        if not cpu:
            return subprocess.CompletedProcess(command, -6, "", "missing CUDA library")
        return subprocess.CompletedProcess(command, 0, json.dumps({
            "success": True, "data": {"device": "cpu"}, "artifacts": [],
        }), "")
    monkeypatch.setattr("subprocess.run", run)
    result = Transcriber().execute({"input_path": str(source)})
    assert result.success
    assert result.data["device"] == "cpu"
    assert "missing CUDA library" in result.data["gpu_fallback_reason"]
    assert devices == [False, True]
