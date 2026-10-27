"""Face tracking tool using the MediaPipe Tasks face detector.

Tracks face bounding boxes across video frames.
Outputs per-frame face data as JSON — used by auto_reframe, face_enhance,
and other tools that need to know where the speaker's face is.

Falls back to OpenCV Haar cascade if the MediaPipe Tasks API is not installed.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class FaceTracker(BaseTool):
    name = "face_tracker"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "mediapipe"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg"]
    install_instructions = (
        "For best results install MediaPipe (Tasks API):\n"
        "pip install mediapipe opencv-contrib-python\n"
        "The face detector model downloads on first use (MEDIAPIPE_MODELS_DIR).\n\n"
        "Falls back to OpenCV Haar cascade (ships with opencv-python)."
    )
    agent_skills = ["ffmpeg"]

    capabilities = [
        "face_detection",
        "face_tracking",
        "face_bounding_box",
        "head_pose_estimation",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string"},
            "output_path": {
                "type": "string",
                "description": "Path for face tracking JSON output",
            },
            "sample_fps": {
                "type": "number",
                "default": 5,
                "description": "Frames per second to sample (lower = faster, less precise)",
            },
            "min_detection_confidence": {
                "type": "number",
                "default": 0.5,
                "minimum": 0.0,
                "maximum": 1.0,
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "frame_count": {"type": "integer"},
            "face_detected_count": {"type": "integer"},
            "video_width": {"type": "integer"},
            "video_height": {"type": "integer"},
            "fps": {"type": "number"},
            "duration_seconds": {"type": "number"},
            "faces": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "frame_index": {"type": "integer"},
                        "timestamp_seconds": {"type": "number"},
                        "bbox": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "number"},
                                "y": {"type": "number"},
                                "width": {"type": "number"},
                                "height": {"type": "number"},
                            },
                        },
                    },
                },
            },
        },
    }

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=100)
    idempotency_key_fields = ["input_path", "sample_fps", "min_detection_confidence"]
    side_effects = ["writes face tracking JSON to output_path"]
    user_visible_verification = [
        "Spot-check bounding boxes against video frames",
    ]

    fallback_tools = []

    def _has_mediapipe(self) -> bool:
        # mediapipe >= 0.10.30 dropped mp.solutions; require the Tasks API.
        import importlib

        try:
            importlib.import_module("mediapipe.tasks.python.vision")
            return True
        except ImportError:
            return False

    def _create_face_detector(self, confidence: float):
        from mediapipe.tasks.python import BaseOptions, vision

        from tools._mediapipe import model_path

        options = vision.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=str(model_path("face_detector"))),
            running_mode=vision.RunningMode.VIDEO,
            min_detection_confidence=confidence,
        )
        return vision.FaceDetector.create_from_options(options)

    def _has_opencv(self) -> bool:
        try:
            import cv2  # noqa: F401
            return True
        except ImportError:
            return False

    def get_status(self) -> ToolStatus:
        if self._has_mediapipe() and self._has_opencv():
            return ToolStatus.AVAILABLE
        if self._has_opencv():
            return ToolStatus.DEGRADED
        return ToolStatus.UNAVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        if not self._has_opencv():
            return ToolResult(
                success=False,
                error="opencv-python is required. Install: pip install opencv-python",
            )

        output_path = Path(
            inputs.get("output_path", str(input_path.with_suffix(".faces.json")))
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        sample_fps = inputs.get("sample_fps", 5)
        confidence = inputs.get("min_detection_confidence", 0.5)

        start = time.time()

        if self._has_mediapipe():
            result_data = self._track_mediapipe(input_path, sample_fps, confidence)
        else:
            result_data = self._track_opencv(input_path, sample_fps)

        elapsed = time.time() - start

        output_path.write_text(json.dumps(result_data, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "output": str(output_path),
                "video_width": result_data["video_width"],
                "video_height": result_data["video_height"],
                "fps": result_data["fps"],
                "duration_seconds": result_data["duration_seconds"],
                "frames_sampled": result_data["frame_count"],
                "faces_detected": result_data["face_detected_count"],
                "method": "mediapipe" if self._has_mediapipe() else "opencv_haar",
            },
            artifacts=[str(output_path)],
            duration_seconds=round(elapsed, 2),
        )

    def _track_mediapipe(
        self, input_path: Path, sample_fps: float, confidence: float
    ) -> dict:
        import cv2
        import mediapipe as mp

        cap = cv2.VideoCapture(str(input_path))

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        video_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        video_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps if video_fps > 0 else 0

        # Calculate frame sampling interval
        sample_interval = max(1, int(video_fps / sample_fps))

        faces_data: list[dict] = []
        frame_idx = 0
        sampled = 0

        with self._create_face_detector(confidence) as detector:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % sample_interval == 0:
                    sampled += 1
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    # VIDEO mode needs strictly increasing timestamps (ms).
                    results = detector.detect_for_video(image, int(frame_idx * 1000 / video_fps))

                    if results.detections:
                        # Use the highest-confidence detection
                        det = max(
                            results.detections,
                            key=lambda d: d.categories[0].score,
                        )
                        # Tasks boxes are in pixels; keep the relative output schema.
                        bbox = det.bounding_box
                        faces_data.append({
                            "frame_index": frame_idx,
                            "timestamp_seconds": round(frame_idx / video_fps, 3),
                            "confidence": round(det.categories[0].score, 3),
                            "bbox": {
                                "x": round(bbox.origin_x / video_w, 4),
                                "y": round(bbox.origin_y / video_h, 4),
                                "width": round(bbox.width / video_w, 4),
                                "height": round(bbox.height / video_h, 4),
                            },
                        })

                frame_idx += 1

        cap.release()

        return {
            "video_width": video_w,
            "video_height": video_h,
            "fps": round(video_fps, 2),
            "duration_seconds": round(duration, 3),
            "frame_count": sampled,
            "face_detected_count": len(faces_data),
            "faces": faces_data,
        }

    def _track_opencv(self, input_path: Path, sample_fps: float) -> dict:
        """Fallback: OpenCV Haar cascade face detection."""
        import cv2

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)

        cap = cv2.VideoCapture(str(input_path))
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        video_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        video_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps if video_fps > 0 else 0

        sample_interval = max(1, int(video_fps / sample_fps))

        faces_data: list[dict] = []
        frame_idx = 0
        sampled = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_interval == 0:
                sampled += 1
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                detected = cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
                )

                if len(detected) > 0:
                    # Pick largest face
                    areas = [w * h for (_, _, w, h) in detected]
                    best_idx = areas.index(max(areas))
                    x, y, w, h = detected[best_idx]
                    faces_data.append({
                        "frame_index": frame_idx,
                        "timestamp_seconds": round(frame_idx / video_fps, 3),
                        "confidence": 0.0,  # Haar doesn't provide confidence
                        "bbox": {
                            "x": round(x / video_w, 4),
                            "y": round(y / video_h, 4),
                            "width": round(w / video_w, 4),
                            "height": round(h / video_h, 4),
                        },
                    })

            frame_idx += 1

        cap.release()

        return {
            "video_width": video_w,
            "video_height": video_h,
            "fps": round(video_fps, 2),
            "duration_seconds": round(duration, 3),
            "frame_count": sampled,
            "face_detected_count": len(faces_data),
            "faces": faces_data,
        }
