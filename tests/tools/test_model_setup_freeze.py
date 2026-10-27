import importlib.util
from pathlib import Path

import pytest


def _setup():
    path = Path(__file__).resolve().parents[2] / "scripts/setup_local_models.py"
    spec = importlib.util.spec_from_file_location("setup_local_models", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_freeze_copies_data_and_is_resumable(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "shared"
    source.mkdir()
    (source / "model.bin").write_bytes(b"weights")
    setup = _setup()
    setup.freeze_snapshot(source, destination, "test/model", "revision")
    setup.freeze_snapshot(source, destination, "test/model", "revision")
    assert (destination / "model.bin").read_bytes() == b"weights"
    assert not (destination / "model.bin").is_symlink()
    assert (source / "model.bin").read_bytes() == b"weights"
    assert (destination / "SHA256SUMS").exists()


def test_freeze_retains_conflicting_source_and_destination(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "shared"
    source.mkdir()
    destination.mkdir()
    (source / "model.bin").write_bytes(b"source")
    (destination / "model.bin").write_bytes(b"different")
    with pytest.raises(FileExistsError):
        _setup().freeze_snapshot(source, destination, "test/model", "revision")
    assert (destination / "model.bin").read_bytes() == b"different"
    assert (source / "model.bin").read_bytes() == b"source"


def test_dangling_weight_link_cannot_be_published(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "shared"
    source.mkdir()
    (source / "model_index.json").write_text("{}")
    (source / "weights.bin").symlink_to(source / "missing-blob")
    with pytest.raises(ValueError, match="missing|broken|incomplete"):
        _setup().freeze_snapshot(source, destination, "test/model", "revision")
    assert not (destination / "provenance.json").exists()


def test_expected_manifest_must_be_complete_before_copy(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "shared"
    source.mkdir()
    (source / "model_index.json").write_text("{}")
    with pytest.raises(ValueError, match="missing|incomplete"):
        _setup().freeze_snapshot(source, destination, "test/model", "revision",
                                 expected_files=["model_index.json", "weights-00001.safetensors"])
    assert not destination.exists()


def test_failed_smoke_does_not_change_persistent_configuration(tmp_path, monkeypatch):
    import subprocess
    setup = _setup()
    monkeypatch.setattr(setup, "REPO", tmp_path)
    (tmp_path / ".env").write_text("LOCAL_DIFFUSION_MODEL_PATH=old\n")
    received = []
    def failed(command, **kwargs):
        received.append(kwargs["env"]["LOCAL_DIFFUSION_MODEL_PATH"])
        return subprocess.CompletedProcess(command, 1)
    monkeypatch.setattr(setup.subprocess, "run", failed)
    with pytest.raises(RuntimeError):
        setup.run_smoke("sdxl", {"LOCAL_DIFFUSION_MODEL_PATH": "new"})
    assert received == ["new"]
    assert (tmp_path / ".env").read_text() == "LOCAL_DIFFUSION_MODEL_PATH=old\n"
