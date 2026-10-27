#!/usr/bin/env python3
"""Finish the owner's approved, serial local model setup after Wan downloads.

Run from OpenMontage's .venv. No services, paid APIs, deletion or Git operations.
The existing downloads are preserved while running. Transient network failures
wait and retry using the same caches, including after a long overnight outage.
"""
from __future__ import annotations

import argparse
import fcntl
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
DATA = Path("/data/projects/personal/content/OpenMontage")
EVIDENCE = DATA / "smoke-tests/2026-10-26/continuation"
WAN_REV = "0fad780a534b6463e45facd96134c9f345acfa5b"
SDXL_REV = "462165984030d82259a11f4367a4eed129e94a7b"
CLIP_REV = "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"


def is_network_error(error):
    import httpx
    current, seen, messages = error, set(), []
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, OSError) and current.errno in {13, 28, 30}:
            return False
        response = getattr(current, "response", None)
        status = getattr(response, "status_code", None) or getattr(current, "code", None)
        if isinstance(status, int):
            return status == 429 or 500 <= status <= 599
        if isinstance(current, (httpx.TransportError, ConnectionError, TimeoutError)):
            return True
        messages.append(str(current).lower())
        current = current.__cause__ or current.__context__
    message = " ".join(messages)
    if any(text in message for text in ("permission denied", "read-only file system", "no space left", "401 client error", "403 client error", "404 client error", "401 unauthorized", "403 forbidden", "404 not found")):
        return False
    return any(text in message for text in (
        "temporary failure in name resolution", "name or service not known", "connectionerror",
        "connecterror", "connecttimeout", "readtimeout", "timed out", "timeout expired",
        "connection reset", "connection refused", "connection aborted", "network is unreachable",
        "failed to establish a new connection", "temporary dns", "error sending request",
        "http 429", "http 502", "http 503", "http 504", "502 bad gateway", "503 service unavailable",
        "request failed after", "failed to lookup address", "dns error",
    ))


def retry_network(action):
    while True:
        try:
            return action()
        except Exception as exc:
            if not is_network_error(exc):
                raise
            print("Network transfer interrupted; keeping cached files and retrying in 60 seconds.", flush=True)
            time.sleep(60)


def run_download_command(command, log, env=None):
    log = Path(log)
    with log.open("ab") as handle:
        offset = handle.tell()
        process = subprocess.run(command, cwd=REPO, env=env, stdout=handle, stderr=subprocess.STDOUT)
    if process.returncode:
        if process.returncode < 0:
            raise RuntimeError(f"Download process stopped by signal {-process.returncode}")
        with log.open("rb") as handle:
            handle.seek(offset)
            detail = handle.read()[-16000:].decode(errors="replace")
        raise RuntimeError(f"Download exited {process.returncode}: {detail}")
    return process


def download_script_processes(script):
    """Find the wrapper, which stays alive while its HF children retry."""
    script = Path(script).resolve()
    found = []
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            args = (process / "cmdline").read_bytes().decode(errors="replace").split("\0")
            if Path(args[0]).name not in {"bash", "sh", "dash"}:
                continue
            for arg in args[1:]:
                if Path(arg).name != script.name:
                    continue
                path = Path(arg) if Path(arg).is_absolute() else (process / "cwd").resolve() / arg
                if path.resolve() == script:
                    found.append(int(process.name))
                    break
        except (OSError, ValueError):
            continue
    return found


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def freeze_snapshot(source, destination, repo_id, revision, expected_files=None):
    """Copy first, checksum-verify, retain all conflicting originals."""
    source, destination = Path(source), Path(destination)
    paths = sorted(source.rglob("*"))
    for path in paths:
        if path.is_symlink() and not path.exists():
            raise ValueError(f"Snapshot contains broken link: {path}")
    for relative in expected_files or []:
        if not (source / relative).is_file():
            raise ValueError(f"Snapshot is incomplete; missing {relative}")
    checksums = []
    for path in paths:
        if not path.is_file() or ".cache" in path.relative_to(source).parts:
            continue
        relative = path.relative_to(source)
        digest = sha256(path)
        blob = path.resolve().name
        if path.is_symlink() and re.fullmatch(r"[0-9a-f]{64}", blob) and digest != blob:
            raise ValueError(f"Source weight checksum mismatch: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if sha256(target) != digest:
                raise FileExistsError(f"Retaining conflicting destination: {target}")
        else:
            partial = target.with_name(target.name + ".part")
            shutil.copyfile(path, partial)
            if sha256(partial) != digest:
                raise ValueError(f"Copy checksum mismatch: {relative}")
            partial.replace(target)
        checksums.append(f"{digest}  {relative}")
    (destination / "SHA256SUMS").write_text("\n".join(checksums) + "\n")
    (destination / "provenance.json").write_text(json.dumps({
        "repo_id": repo_id, "revision": revision, "source": str(source), "files": len(checksums),
    }, indent=2))
    return destination


def configure(values):
    path = REPO / ".env"
    text = path.read_text()
    for key, value in values.items():
        line = f"{key}={value}"
        pattern = rf"^{re.escape(key)}=.*$"
        text = re.sub(pattern, lambda match: line, text, flags=re.MULTILINE) if re.search(pattern, text, re.MULTILINE) else text.rstrip() + "\n" + line + "\n"
        os.environ[key] = str(value)
    path.write_text(text)


def register(identifier, path):
    catalog = Path("/data/CATALOG.yaml")
    text = catalog.read_text()
    if f"- id: {identifier}\n" not in text:
        with catalog.open("a") as handle:
            handle.write(f"\n  - id: {identifier}\n    type: shared-model\n    path: {path}\n    classification: reproducible-commercial-ok\n    backup_tier: excluded\n    tags: [shared, models, openmontage]\n")


def run_smoke(kind, values):
    # Trial configuration exists only in the inference child. Persist it after
    # success, so failed setup never displaces a working .env configuration.
    env = {**os.environ, "HF_HUB_OFFLINE": "1", **{key: str(value) for key, value in values.items()}}
    process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--smoke", kind],
                             cwd=REPO, env=env, timeout=1800)
    if process.returncode:
        raise RuntimeError(f"{kind} smoke process exited {process.returncode}")
    configure(values)


def verify_storage():
    uuid = "b2ef3ba7-789b-4ac7-915b-c638e8a201be"
    observed = subprocess.check_output(["findmnt", "-n", "-o", "UUID", "--target", "/data"], text=True).strip()
    serials = subprocess.check_output(["lsblk", "-s", "-n", "-o", "SERIAL", f"/dev/disk/by-uuid/{uuid}"], text=True)
    if observed != uuid or "S6BCNX0T403221R" not in serials:
        raise RuntimeError("Primary data storage identity mismatch")


def smoke(kind):
    sys.path.insert(0, str(REPO))
    processes = subprocess.check_output([
        "nvidia-smi", "--query-compute-apps=process_name,used_memory", "--format=csv,noheader,nounits",
    ], text=True)
    for line in processes.splitlines():
        name, memory = line.rsplit(",", 1)
        if any(engine in name.lower() for engine in ("python", "blender")) and float(memory.strip()) > 256:
            raise RuntimeError("Another GPU engine is active; unload it before retrying this smoke test")
    if kind == "wan":
        from tools.video.wan_video import WanVideo
        result = WanVideo().execute({"prompt": "A small red sailboat moving gently across a calm lake in daylight, steady camera.",
            "model_variant": "wan2.1-1.3b", "width": 832, "height": 480, "num_frames": 17,
            "num_inference_steps": 4, "seed": 42, "offload_mode": "sequential",
            "output_path": str(EVIDENCE / "wan-video.mp4")})
    elif kind == "sdxl":
        from tools.graphics.local_diffusion import LocalDiffusion
        result = LocalDiffusion().execute({"prompt": "A red sailboat on a calm blue lake in daylight, natural landscape photograph.",
            "width": 1024, "height": 1024, "num_inference_steps": 20, "seed": 42,
            "output_path": str(EVIDENCE / "sdxl-image.png")})
    elif kind == "clip":
        from tools.analysis.video_understand import VideoUnderstand
        result = VideoUnderstand().execute({"input_path": str(EVIDENCE / "sdxl-image.png"), "mode": "describe", "model": "clip"})
    else:
        from tools.analysis.transcriber import Transcriber
        result = Transcriber().execute({"input_path": str(EVIDENCE.parent / "ming-narration.wav"),
                                        "output_dir": str(EVIDENCE), "language": "en"})
        if result.success and result.data.get("device") != "cuda":
            result.success = False
            result.error = "CUDA acceptance fell back to CPU: " + str(result.data.get("gpu_fallback_reason"))
    report = {"success": result.success, "data": result.data, "error": result.error, "wall_seconds": result.duration_seconds}
    try:
        import torch
        report["peak_vram_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
    except ImportError:
        pass
    (EVIDENCE / f"{kind}-result.json").write_text(json.dumps(report, indent=2))
    if not result.success:
        raise RuntimeError(result.error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wan-pid", type=int)
    parser.add_argument("--smoke", choices=["wan", "sdxl", "clip", "whisper"])
    parser.add_argument("--finish-whisper", action="store_true")
    parser.add_argument("--runtime-pid", type=int)
    args = parser.parse_args()
    if args.smoke:
        smoke(args.smoke)
        return
    verify_storage()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if args.finish_whisper:
        if not args.runtime_pid:
            parser.error("--finish-whisper requires --runtime-pid")
        lock = (EVIDENCE / "whisper-setup.lock").open("w")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print("Waiting for existing isolated CUDA12 wheel installation.", flush=True)
        while True:
            try:
                os.kill(args.runtime_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(15)
        root = REPO / ".venv/whisper-cuda12"
        libraries = [root / "nvidia" / library for library in
                     ("cublas/lib/libcublas.so.12", "cudnn/lib/libcudnn.so.9")]
        if not all(path.is_file() for path in libraries):
            env = {**os.environ, "UV_CACHE_DIR": str(DATA / "cache/uv")}
            command = [shutil.which("uv"), "pip", "install", "--python", str(REPO / ".venv/bin/python"),
                       "--target", str(root), "--no-deps", "nvidia-cublas-cu12==12.4.5.8", "nvidia-cudnn-cu12==9.1.0.70"]
            retry_network(lambda: run_download_command(command, EVIDENCE / "whisper-install.log", env))
        if not all(path.is_file() for path in libraries):
            raise RuntimeError("CUDA12 installation incomplete; inspect its install log")
        run_smoke("whisper", {"WHISPER_CUDA12_ROOT": str(root)})
        print("Whisper CUDA acceptance passed; private runtime configured.", flush=True)
        return
    lock = (EVIDENCE / "setup.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.environ.setdefault("HF_HUB_CACHE", "/data/cache/huggingface/hub")
    from huggingface_hub import HfApi, snapshot_download
    log = EVIDENCE.parent / "wan-download.log"
    print("Waiting for existing Wan downloader; no concurrent duplicate download will start.", flush=True)
    while "DOWNLOAD COMPLETE" not in log.read_text():
        # Track the shell's lifetime, not just one HF child: the original shell
        # sleeps between attempts and starts each attempt with a new HF PID.
        owners = download_script_processes(log.with_name("wan-download.sh"))
        if owners:
            args.wan_pid = owners[0]
        if args.wan_pid:
            try:
                os.kill(args.wan_pid, 0)
            except ProcessLookupError:
                # The bounded original downloader may exhaust its retries while
                # offline. Resume that same pinned command only after it exits.
                print("Existing Wan downloader ended; resuming with cached files.", flush=True)
                retry_network(lambda: run_download_command(["bash", str(log.with_name("wan-download.sh"))], log))
                args.wan_pid = None
        else:
            retry_network(lambda: run_download_command(["bash", str(log.with_name("wan-download.sh"))], log))
        time.sleep(30)
    stages = [
        ("wan", "Wan-AI/Wan2.1-T2V-1.3B-Diffusers", WAN_REV, "wan-ai/wan2.1-t2v-1.3b", None),
        ("sdxl", "stabilityai/stable-diffusion-xl-base-1.0", SDXL_REV, "stabilityai/stable-diffusion-xl-base-1.0",
         ["model_index.json", "LICENSE.md", "README.md", "scheduler/*", "tokenizer/*", "tokenizer_2/*", "text_encoder/config.json", "text_encoder/*.fp16.safetensors", "text_encoder_2/config.json", "text_encoder_2/*.fp16.safetensors", "unet/config.json", "unet/*.fp16.safetensors", "vae/config.json", "vae/*.fp16.safetensors"]),
        ("clip", "openai/clip-vit-base-patch32", CLIP_REV, "openai/clip-vit-base-patch32",
         ["*.json", "merges.txt", "vocab.json", "pytorch_model.bin", "README.md"]),
    ]
    failures = []
    for kind, repo_id, revision, relative, patterns in stages:
        try:
            verify_storage()
            print(f"Preparing {kind}: {repo_id}@{revision}", flush=True)
            cached = retry_network(lambda: snapshot_download(repo_id, revision=revision, allow_patterns=patterns,
                                                             local_files_only=(kind == "wan")))
            manifest = retry_network(lambda: HfApi().model_info(repo_id, revision=revision))
            expected = [entry.rfilename for entry in manifest.siblings
                        if patterns is None or any(fnmatch.fnmatchcase(entry.rfilename, pattern) for pattern in patterns)]
            target = freeze_snapshot(cached, Path("/data/shared/models") / relative / revision,
                                     repo_id, revision, expected_files=expected)
            register(f"openmontage-{kind}-models", target)
            values = {}
            if kind == "wan":
                values = {"VIDEO_GEN_LOCAL_ENABLED": "true", "VIDEO_GEN_LOCAL_MODEL": "wan2.1-1.3b", "VIDEO_GEN_LOCAL_MODEL_PATH": str(target)}
            elif kind == "sdxl":
                values = {"LOCAL_DIFFUSION_MODEL_PATH": str(target)}
            run_smoke(kind, values)
            print(f"{kind}: verified", flush=True)
        except Exception as exc:
            failures.append({"stage": kind, "error": str(exc)})
            print(f"{kind}: FAILED: {exc}", flush=True)
    (EVIDENCE / "setup-result.json").write_text(json.dumps({"success": not failures, "failures": failures}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
