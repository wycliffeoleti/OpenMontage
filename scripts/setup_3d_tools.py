#!/usr/bin/env python3
"""Prepare and verify OpenMontage's local world and mathematical 3D routes."""

from __future__ import annotations

import argparse
import functools
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.threejs_runtime import RUNTIME_ROOT, VERSIONS, world_runtime_errors
from tools.base_tool import ToolStatus
from tools.tool_registry import registry
from tools.video.hyperframes_compose import HyperFramesCompose


def run(command, *, timeout=60, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, **kwargs)


def update_environment(path: Path, values: dict[str, str]) -> None:
    """Atomically replace only selected keys, retaining other settings and comments."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    retained = [line for line in lines
                if not re.match(r"^\s*(?:export\s+)?(" + "|".join(map(re.escape, values)) + r")\s*=", line)]
    additions = [f"{key}={json.dumps(value)}" for key, value in values.items()]
    content = "\n".join([*retained, *additions]) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".env-3d-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def required_doctor_errors(payload: dict) -> list[str]:
    error = HyperFramesCompose._doctor_required_error(json.dumps(payload))
    return [error] if error else []


def discover():
    # Discover only relevant tools: a readiness check must not probe unrelated providers.
    for module in ("tools.graphics.math_animate", "tools.graphics.threejs_world",
                   "tools.video.hyperframes_compose"):
        registry.discover(module)
    return registry


def existing_headless_browser() -> Path:
    explicit = os.environ.get("HYPERFRAMES_BROWSER_PATH", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return path.resolve()
        raise ValueError(f"Configured HYPERFRAMES_BROWSER_PATH is not executable: {path}")
    patterns = [
        (Path.home() / ".cache/puppeteer/chrome-headless-shell", "linux-*/chrome-headless-shell-linux64/chrome-headless-shell"),
        (Path.home() / ".cache/ms-playwright", "chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"),
    ]
    def version(candidate: Path) -> tuple[int, ...]:
        # Version directories are e.g. linux-154.0.8037.57; compare numerically.
        return tuple(map(int, re.findall(r"\d+", candidate.parents[1].name)))
    for root, pattern in patterns:
        for candidate in sorted(root.glob(pattern), key=version, reverse=True):
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate.resolve()
    raise FileNotFoundError("No installed Chrome headless shell found; set HYPERFRAMES_BROWSER_PATH")


def setup() -> dict:
    cli = RUNTIME_ROOT / "node_modules/hyperframes/bin/hyperframes.mjs"
    package = cli.parent.parent / "package.json"
    cli_version = json.loads(package.read_text()).get("version") if package.is_file() else None
    if world_runtime_errors() or not cli.is_file() or cli_version != VERSIONS["hyperframes"]:
        proc = run(["npm", "ci", "--prefix", str(RUNTIME_ROOT), "--ignore-scripts",
                    "--no-audit", "--no-fund"], timeout=600)
        if proc.returncode:
            raise RuntimeError("Pinned npm install failed: " + proc.stderr[-2500:])
    try:
        manim_version = importlib.metadata.version("manim")
    except importlib.metadata.PackageNotFoundError:
        manim_version = None
    if manim_version is None:
        proc = run(["uv", "pip", "install", "--python", sys.executable, "manim==0.22.0"], timeout=600)
        if proc.returncode:
            raise RuntimeError("Manim installation failed: " + proc.stderr[-2500:])
    values = {"HYPERFRAMES_CLI_PATH": str(cli),
              "HYPERFRAMES_BROWSER_PATH": str(existing_headless_browser())}
    update_environment(ROOT / ".env", values)
    os.environ.update(values)
    HyperFramesCompose._cli_probe_cache = None
    return check()


def check() -> dict:
    tools = discover()
    hf = tools.get("hyperframes_compose")
    if hf._configured_cli() is None:
        # The general tool's legacy npx path may install on first use. Readiness
        # must reject that path before probing it; only --setup may install.
        runtime = {"runtime_available": False, "cli_path": None,
                   "npm_package_version": None,
                   "reasons": ["Pinned local CLI is not configured; run make 3d-setup"]}
    else:
        runtime = hf._runtime_check()
    world_errors = world_runtime_errors()
    world_errors.extend(runtime["reasons"])
    if runtime.get("npm_package_version") != VERSIONS["hyperframes"]:
        world_errors.append(f"Expected HyperFrames {VERSIONS['hyperframes']}; run make 3d-setup")
    browser = os.environ.get("HYPERFRAMES_BROWSER_PATH", "")
    if not browser or not Path(browser).is_file():
        world_errors.append("Configured optimized browser is missing; run make 3d-setup")

    manim_errors = []
    try:
        version = importlib.metadata.version("manim")
    except importlib.metadata.PackageNotFoundError:
        version = None
    if version != "0.22.0":
        manim_errors.append(f"Expected Manim 0.22.0, found {version}; run make 3d-setup")
    # The tool's own check, under the caller's PATH, is what pipeline agents see.
    if tools.get("math_animate").get_status() != ToolStatus.AVAILABLE:
        manim_errors.append("math_animate reports Manim unavailable in this environment")
    # `manim checkhealth` exits 0 even when it fails; check its executables directly.
    for command in ("latex", "dvisvgm", "ffmpeg", "ffprobe"):
        if not shutil.which(command):
            manim_errors.append(f"Missing executable: {command}")
    routes = {
        "hyperframes_threejs": {"status": "blocked" if world_errors else "ready",
                                 "errors": world_errors, "versions": VERSIONS,
                                 "runtime": runtime, "browser": browser},
        "manim": {"status": "blocked" if manim_errors else "ready", "version": version,
                  "errors": manim_errors},
    }
    return {"status": "ready" if not world_errors and not manim_errors else "blocked",
            "routes": routes, "note": "Readiness is distinct from a real render smoke result."}


def verify_video(path: Path, duration: float, size: tuple[int, int], fps: float,
                 frames_dir: Path) -> dict:
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Missing or empty video output: {path}")
    probe = run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames:format=duration",
                 "-of", "json", str(path)])
    if probe.returncode:
        raise ValueError("Video probe failed: " + probe.stderr)
    data = json.loads(probe.stdout)
    if not data.get("streams"):
        raise ValueError("Output has no video stream")
    stream = data["streams"][0]
    numerator, denominator = map(float, stream["r_frame_rate"].split("/"))
    actual_fps = numerator / denominator
    actual_duration = float(data["format"]["duration"])
    if (stream["width"], stream["height"]) != size:
        raise ValueError(f"Wrong frame size: {stream['width']}x{stream['height']}; expected {size}")
    if abs(actual_fps - fps) > 0.01 or abs(actual_duration - duration) > 1 / fps + 0.01:
        raise ValueError(f"Wrong timing: {actual_duration}s at {actual_fps}fps")
    expected_frames = round(duration * fps)
    if abs(int(stream["nb_read_frames"]) - expected_frames) > 1:
        raise ValueError(f"Wrong frame count: {stream['nb_read_frames']}; expected {expected_frames}")
    decoded = run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"], timeout=120)
    if decoded.returncode:
        raise ValueError("Full decode failed: " + decoded.stderr)
    frames_dir.mkdir(parents=True, exist_ok=True)
    from PIL import Image, ImageChops, ImageStat
    images, frames = [], []
    for number, second in enumerate((duration * 0.1, duration * 0.5, duration * 0.9)):
        output = frames_dir / f"{path.stem}-{number}.png"
        proc = run(["ffmpeg", "-v", "error", "-y", "-ss", str(second), "-i", str(path),
                    "-frames:v", "1", str(output)])
        if proc.returncode or not output.is_file():
            raise ValueError("Frame extraction failed: " + proc.stderr)
        with Image.open(output) as source:
            image = source.convert("RGB")
        if max(ImageStat.Stat(image).stddev) < 2:
            raise ValueError(f"Video contains a blank frame at {second}s")
        images.append(image)
        frames.append(str(output))
    delta = max(max(ImageStat.Stat(ImageChops.difference(images[0], image)).mean)
                for image in images[1:])
    if delta < 0.2:
        raise ValueError("Video is static: no visible motion detected")
    return {"status": "passed", "output": str(path), "duration": actual_duration,
            "fps": actual_fps, "size": list(size), "frames": stream["nb_read_frames"],
            "fully_decoded": True, "motion_difference": delta, "sample_frames": frames}


def world_spec() -> dict:
    return {
        "version": "1.0", "title": "3D readiness", "seed": 271026,
        "explicit_constraints": ["four-second setup blockout"],
        "inferred_details": ["two terrain regions and a ring landmark"],
        "world": {"size": 64, "resolution": 32, "elevation_scale": 5, "water_level": -1},
        "regions": [
            {"id": "hills", "center": [-0.3, 0], "radius": 0.8, "landform": "peak",
             "color": "#356456", "accent_color": "#b8e8c0", "scatter": {"tree": 8, "rock": 5}},
            {"id": "valley", "center": [0.35, 0], "radius": 0.8, "landform": "basin",
             "color": "#35586b", "accent_color": "#a5d4eb", "scatter": {"tree": 4, "rock": 5}},
        ],
        "landmarks": [{"id": "ring", "type": "ring", "region_id": "valley",
                       "position": [8, 0, 0], "scale": 3}],
        "camera_path": [
            {"time": 0, "position": [-26, 18, 25], "target": [0, 0, 0]},
            {"time": 2, "position": [0, 15, 28], "target": [6, 0, 0]},
            {"time": 4, "position": [26, 18, 18], "target": [8, 0, 0]},
        ],
    }


MANIM_SCENE = r'''
from manim import *

class Readiness3D(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=65*DEGREES, theta=-45*DEGREES, zoom=0.8)
        axes = ThreeDAxes(x_range=[-3,3,1], y_range=[-3,3,1], z_range=[-2,2,1])
        sphere = Sphere(radius=1, resolution=(12,24), fill_opacity=0.85, color=TEAL)
        label = MathTex(r"x^2+y^2+z^2=1").scale(0.8).to_corner(UL)
        self.add(axes, sphere)
        self.add_fixed_in_frame_mobjects(label)
        self.move_camera(theta=35*DEGREES, run_time=3, rate_func=linear)
'''


def browser_world_check(workspace: Path, output: Path) -> dict:
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    handler = functools.partial(QuietHandler, directory=str(workspace))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run(["node", str(RUNTIME_ROOT / "scripts/inspect-world.mjs"),
                      f"http://127.0.0.1:{server.server_port}/", str(output)], timeout=90)
        if result.returncode:
            raise RuntimeError("Offline browser check failed: " + result.stderr[-3000:])
        return json.loads(result.stdout)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def smoke(output: Path) -> dict:
    # Diagnostics leave the owner's 8 GB GPU free for other engines.
    os.environ.setdefault("PRODUCER_BROWSER_GPU_MODE", "software")
    report = {"status": "failed", "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "readiness": None, "routes": {}}
    output.mkdir(parents=True, exist_ok=True)
    latest_report = output / "smoke-report.json"
    # A zero-exit renderer that writes nothing must never reuse an old successful video.
    output = Path(tempfile.mkdtemp(prefix="run-", dir=output))
    report["run_directory"] = str(output)
    try:
        report["readiness"] = check()
        if report["readiness"]["status"] != "ready":
            raise RuntimeError("Readiness checks failed; run make 3d-check")
        tools = discover()
        for route in ("hyperframes_threejs", "manim"):
            started = time.monotonic()
            try:
                if route == "hyperframes_threejs":
                    workspace = output / "world"
                    built = tools.get("threejs_world").execute({
                        "operation": "build", "world_spec": world_spec(), "output_path": str(workspace),
                        "duration_seconds": 4, "width": 854, "height": 480,
                        "quality_tier": "blockout", "render_mode": "cinematic",
                    })
                    if not built.success:
                        raise RuntimeError(built.error)
                    browser = browser_world_check(workspace, output / "browser")
                    video = output / "hyperframes-threejs.mp4"
                    rendered = tools.get("hyperframes_compose").execute({
                        "operation": "render_existing", "workspace_path": str(workspace),
                        "output_path": str(video), "fps": 15, "quality": "draft",
                        "snapshots": True,
                    })
                    (output / "hyperframes-render.json").write_text(json.dumps(rendered.data, indent=2))
                    if not rendered.success:
                        raise RuntimeError(rendered.error)
                    checked = verify_video(video, 4, (854, 480), 15, output / "frames")
                    checked.update({"browser": browser, "quality_tier": "blockout"})
                else:
                    source = output / "manim-scene.py"
                    source.write_text(MANIM_SCENE)
                    video = output / "manim-3d.mp4"
                    rendered = tools.get("math_animate").execute({
                        "scene_code": MANIM_SCENE, "scene_name": "Readiness3D",
                        "quality": "low", "output_path": str(video),
                    })
                    if not rendered.success:
                        raise RuntimeError(rendered.error)
                    checked = verify_video(video, 3, (854, 480), 15, output / "frames")
                checked["elapsed_seconds"] = round(time.monotonic() - started, 2)
                report["routes"][route] = checked
            except Exception as exc:
                report["routes"][route] = {"status": "failed", "error": str(exc),
                                           "elapsed_seconds": round(time.monotonic() - started, 2)}
            print(f"{route}: {report['routes'][route]['status']}", file=sys.stderr, flush=True)
        report["status"] = "passed" if all(r["status"] == "passed" for r in report["routes"].values()) else "failed"
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        serialized = json.dumps(report, indent=2) + "\n"
        (output / "smoke-report.json").write_text(serialized)
        latest_report.write_text(serialized)
    return report


def main() -> int:
    os.environ.setdefault("DO_NOT_TRACK", "1")
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    for action in ("setup", "check", "smoke"):
        actions.add_argument(f"--{action}", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable report")
    parser.add_argument("--output", type=Path, default=ROOT / "projects/3d-readiness")
    args = parser.parse_args()
    if args.setup:
        # Installation needs repository tools such as uv. Check and smoke keep the
        # caller's PATH so they report what pipeline agents will actually find.
        os.environ["PATH"] = os.pathsep.join([str(ROOT / ".venv/bin"), str(Path.home() / ".local/bin"), os.environ.get("PATH", "")])
    try:
        registry._load_dotenv()
        report = setup() if args.setup else smoke(args.output.resolve()) if args.smoke else check()
    except Exception as exc:
        report = {"status": "blocked", "error": str(exc)}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"3D {('smoke' if args.smoke else 'readiness')}: {report['status']}")
        for name, route in report.get("routes", {}).items():
            print(f"  {name}: {route['status']}")
            for error in route.get("errors", [route["error"]] if route.get("error") else []):
                print(f"    {error}")
        if report.get("error"):
            print(report["error"])
    return 0 if report["status"] in {"ready", "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
