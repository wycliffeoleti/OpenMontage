"""Versioned, local browser dependencies for generated Three.js workspaces."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parent.parent / "hyperframes-runtime"
VERSIONS = {"three": "0.181.2", "gsap": "3.14.2", "hyperframes": "0.8.206"}
WORLD_FILES = {
    "three/build/three.module.js": "three/three.module.js",
    "three/build/three.core.js": "three/three.core.js",
    "three/examples/jsm/loaders/GLTFLoader.js": "three/addons/loaders/GLTFLoader.js",
    "three/examples/jsm/utils/BufferGeometryUtils.js": "three/addons/utils/BufferGeometryUtils.js",
    "three/LICENSE": "three/LICENSE",
    "gsap/dist/gsap.min.js": "gsap/gsap.min.js",
    # GSAP publishes its license notice in the README/package metadata and JS header.
    "gsap/README.md": "gsap/README.md",
    "gsap/package.json": "gsap/package.json",
}


def world_runtime_errors(runtime_root: Path = RUNTIME_ROOT) -> list[str]:
    errors = []
    for name in ("three", "gsap"):
        try:
            package = json.loads((runtime_root / "node_modules" / name / "package.json").read_text())
            if package.get("version") != VERSIONS[name]:
                errors.append(f"{name}: expected {VERSIONS[name]}, found {package.get('version')}")
        except (OSError, ValueError) as exc:
            errors.append(f"{name}: {exc}")
    for source in WORLD_FILES:
        if not (runtime_root / "node_modules" / source).is_file():
            errors.append(f"missing {source}")
    return errors


def stage_world_runtime(workspace: Path, runtime_root: Path = RUNTIME_ROOT) -> list[str]:
    errors = world_runtime_errors(runtime_root)
    if errors:
        raise FileNotFoundError("Run make 3d-setup: " + "; ".join(errors))
    artifacts = []
    manifest = {"versions": {k: VERSIONS[k] for k in ("three", "gsap")}, "files": {}}
    for source, relative in WORLD_FILES.items():
        origin = runtime_root / "node_modules" / source
        target = workspace / "vendor" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
        manifest["files"][f"vendor/{relative}"] = hashlib.sha256(target.read_bytes()).hexdigest()
        artifacts.append(str(target))
    manifest_path = workspace / "vendor" / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return [*artifacts, str(manifest_path)]
