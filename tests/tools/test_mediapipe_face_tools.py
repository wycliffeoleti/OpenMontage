"""Face tools run on the MediaPipe Tasks API.

mediapipe >= 0.10.30 no longer ships the legacy ``mp.solutions`` API that
face_tracker and eye_enhance used, so a current install made both tools report
AVAILABLE and then crash. These tests use MediaPipe's real result containers and
replace only model inference, which needs downloaded weights and a real face.
"""

import json
import shutil
import subprocess
import sys

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
mp = pytest.importorskip("mediapipe")
pytest.importorskip("mediapipe.tasks.python.vision")

from mediapipe.tasks.python.components.containers.bounding_box import BoundingBox
from mediapipe.tasks.python.components.containers.category import Category
from mediapipe.tasks.python.components.containers.detections import Detection, DetectionResult
from mediapipe.tasks.python.components.containers.landmark import NormalizedLandmark
from mediapipe.tasks.python.vision.face_landmarker import FaceLandmarkerResult

from tools import _mediapipe
from tools.analysis.face_tracker import FaceTracker
from tools.base_tool import ToolStatus
from tools.enhancement.eye_enhance import LEFT_EYE, EyeEnhance

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")


def _video(path, source):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", source, "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, check=True, timeout=30,
    )
    return path


class _VideoModeModel:
    """Enforces the VIDEO running-mode contract of the real Tasks models."""

    def __init__(self, result, width, height):
        self.result, self.width, self.height = result, width, height
        self.timestamps = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def detect_for_video(self, image, timestamp_ms):
        assert isinstance(image, mp.Image)
        assert (image.width, image.height) == (self.width, self.height)
        if self.timestamps and timestamp_ms <= self.timestamps[-1]:
            raise ValueError("timestamps must be monotonically increasing")
        self.timestamps.append(timestamp_ms)
        return self.result


def test_model_path_uses_the_configured_directory(tmp_path, monkeypatch):
    model = tmp_path / _mediapipe.MODELS["face_detector"]
    model.parent.mkdir(parents=True)
    model.write_bytes(b"tflite")
    monkeypatch.setenv("MEDIAPIPE_MODELS_DIR", str(tmp_path))
    monkeypatch.setattr(_mediapipe.urllib.request, "urlretrieve", pytest.fail)
    assert _mediapipe.model_path("face_detector") == model


def test_missing_model_is_downloaded_once(tmp_path, monkeypatch):
    fetched = []

    def urlretrieve(url, filename):
        fetched.append(url)
        with open(filename, "wb") as handle:
            handle.write(b"task")

    monkeypatch.setenv("MEDIAPIPE_MODELS_DIR", str(tmp_path))
    monkeypatch.setattr(_mediapipe.urllib.request, "urlretrieve", urlretrieve)
    path = _mediapipe.model_path("face_landmarker")
    _mediapipe.model_path("face_landmarker")
    assert fetched == [
        "https://storage.googleapis.com/mediapipe-models/"
        "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
    ]
    assert path.read_bytes() == b"task"
    assert not list(path.parent.glob("*.part"))


@pytest.mark.parametrize("tool_class", [FaceTracker, EyeEnhance])
def test_status_is_degraded_without_the_tasks_api(tool_class, monkeypatch):
    monkeypatch.setitem(sys.modules, "mediapipe.tasks.python.vision", None)
    assert tool_class().get_status() == ToolStatus.DEGRADED


def test_face_tracker_keeps_the_most_confident_face(tmp_path, monkeypatch):
    source = _video(tmp_path / "in.mp4", "testsrc=size=128x96:rate=10:duration=1")
    detections = DetectionResult(detections=[
        Detection(bounding_box=BoundingBox(origin_x=0, origin_y=0, width=16, height=16),
                  categories=[Category(index=0, score=0.6)], keypoints=[]),
        Detection(bounding_box=BoundingBox(origin_x=64, origin_y=24, width=32, height=48),
                  categories=[Category(index=0, score=0.9)], keypoints=[]),
    ])
    detector = _VideoModeModel(detections, 128, 96)
    monkeypatch.setattr(FaceTracker, "_create_face_detector", lambda self, confidence: detector)

    output = tmp_path / "faces.json"
    result = FaceTracker().execute({"input_path": str(source), "output_path": str(output), "sample_fps": 5})

    assert result.success, result.error
    assert result.data["method"] == "mediapipe"
    tracks = json.loads(output.read_text())
    assert (tracks["frame_count"], tracks["face_detected_count"]) == (5, 5)
    assert detector.timestamps == [0, 200, 400, 600, 800]
    assert tracks["faces"][1]["frame_index"] == 2
    assert tracks["faces"][1]["confidence"] == 0.9
    assert tracks["faces"][1]["bbox"] == {"x": 0.5, "y": 0.25, "width": 0.25, "height": 0.5}


def test_eye_enhance_brightens_only_the_eye_region(tmp_path, monkeypatch):
    source = _video(tmp_path / "in.mp4", "color=c=0x646464:size=160x120:rate=5:duration=1")
    landmarks = [NormalizedLandmark(x=0.05, y=0.05, z=0.0) for _ in range(478)]
    for step, index in enumerate(LEFT_EYE):
        angle = 2 * np.pi * step / len(LEFT_EYE)
        landmarks[index] = NormalizedLandmark(
            x=0.3 + 0.1 * np.cos(angle), y=0.5 + 0.1 * np.sin(angle), z=0.0,
        )
    face = FaceLandmarkerResult(
        face_landmarks=[landmarks], face_blendshapes=[], facial_transformation_matrixes=[],
    )
    landmarker = _VideoModeModel(face, 160, 120)
    monkeypatch.setattr(EyeEnhance, "_create_face_landmarker", lambda self: landmarker)

    # Check spatial isolation before lossy video encoding changes pixel values.
    original = np.full((120, 160, 3), 100, dtype=np.uint8)
    enhanced = EyeEnhance()._apply_eye_enhancements(
        original, landmarks, 160, 120, ["brighten_eyes"], 0.4, 1.0, 0.3,
    )
    assert np.array_equal(enhanced[10, 150], original[10, 150])
    assert enhanced[60, 48].mean() > original[60, 48].mean()

    output = tmp_path / "out.mp4"
    result = EyeEnhance().execute({
        "input_path": str(source), "output_path": str(output),
        "operations": ["brighten_eyes"], "eye_brighten_intensity": 1.0,
    })

    assert result.success, result.error
    assert result.data["method"] == "mediapipe_face_landmarker"
    assert result.data["frames_enhanced"] == result.data["frames_processed"] == 5
    capture = cv2.VideoCapture(str(output))
    ok, frame = capture.read()
    capture.release()
    assert ok
    eye, corner = int(frame[60, 48].mean()), frame[10, 150].astype(int)
    assert eye >= 110

    # An unchanged frame takes the same mp4v -> H.264 path. Compare against
    # that control instead of assuming that lossy RGB/YUV encoding preserves 100.
    empty = FaceLandmarkerResult(
        face_landmarks=[], face_blendshapes=[], facial_transformation_matrixes=[],
    )
    control_model = _VideoModeModel(empty, 160, 120)
    monkeypatch.setattr(EyeEnhance, "_create_face_landmarker", lambda self: control_model)
    control_path = tmp_path / "control.mp4"
    control_result = EyeEnhance().execute({
        "input_path": str(source), "output_path": str(control_path),
    })
    assert control_result.success, control_result.error
    capture = cv2.VideoCapture(str(control_path))
    ok, control = capture.read()
    capture.release()
    assert ok
    assert np.max(np.abs(corner - control[10, 150].astype(int))) <= 3
