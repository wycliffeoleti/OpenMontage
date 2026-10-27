"""Pinned MediaPipe Tasks models shared by the face tools.

mediapipe >= 0.10.30 ships only the Tasks API, whose models are separate
downloads (Apache-2.0 per their model cards). Paths mirror the official
bucket so a shared model directory can hold several versions side by side.
"""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

BASE_URL = "https://storage.googleapis.com/mediapipe-models/"

MODELS = {
    # Full range (up to ~5 m), matching the legacy FaceDetection(model_selection=1).
    "face_detector": "face_detector/blaze_face_full_range/float16/1/blaze_face_full_range.tflite",
    # 478 landmarks, iris points 468-477 included (legacy refine_landmarks=True).
    "face_landmarker": "face_landmarker/face_landmarker/float16/1/face_landmarker.task",
}


def model_path(name: str) -> Path:
    """Return the local model file, downloading it on first use."""
    root = os.environ.get("MEDIAPIPE_MODELS_DIR") or Path.home() / ".cache" / "openmontage" / "mediapipe"
    path = Path(root) / MODELS[name]
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_name(path.name + ".part")
        urllib.request.urlretrieve(BASE_URL + MODELS[name], partial)
        partial.replace(path)
    return path
