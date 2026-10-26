"""ComfyUI music generation via a local or remote ComfyUI server.

Native bundled profiles cover ACE-Step v1 and ACE-Step 1.5 Turbo. An explicit
model_profile overrides COMFYUI_MUSIC_PROFILE; unset configuration retains v1.
Custom API-format workflows remain supported with an explicit output node.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools._comfyui.client import ComfyUIClient, ComfyUIError
from tools._comfyui.metadata import (
    BUNDLED_MODEL_STACKS,
    COMFYUI_SETUP_OFFER,
    missing_models_payload,
    model_stack,
    workflow_hash,
)

_WORKFLOWS = Path(__file__).resolve().parent.parent / "_comfyui" / "workflows"

# Model required by the bundled ACE-Step v1 workflow
_REQUIRED_MODELS = ["ace_step_v1_3.5b.safetensors"]
_PROFILES = {
    "ace-step-1": ("ace-step-1-t2a", "ace-step-v1-3.5b", _REQUIRED_MODELS),
    "ace-step-1.5-turbo": ("ace-step-1.5-t2a", "ace-step-1.5-turbo", [
        "acestep_v1.5_turbo.safetensors", "qwen_0.6b_ace15.safetensors",
        "qwen_1.7b_ace15.safetensors", "ace_1.5_vae.safetensors",
    ]),
}


class ComfyUIMusic(BaseTool):
    name = "comfyui_music"
    version = "0.3.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "comfyui"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []  # checked at runtime via server health
    setup_offer = COMFYUI_SETUP_OFFER
    install_instructions = (
        "Start a ComfyUI server and set COMFYUI_SERVER_URL "
        "(default http://localhost:8188).\n"
        "Set COMFYUI_MUSIC_PROFILE=ace-step-1.5-turbo for the split ACE-Step 1.5 "
        "model stack reported by get_info(). Unset configuration uses v1 and "
        "requires ace_step_v1_3.5b.safetensors in checkpoints.\n"
        "Running a separate ComfyUI instance for music? Set "
        "COMFYUI_MUSIC_SERVER_URL instead -- it takes priority over "
        "COMFYUI_SERVER_URL for this tool only."
    )
    agent_skills = ["comfyui"]

    capabilities = ["generate_background_music", "generate_song", "generate_instrumental"]
    supports = {
        "seed": True,
        "lyrics": True,
        "custom_workflow": True,
        "custom_output_node": True,
        "offline": True,
    }
    best_for = [
        "local GPU music generation without API costs",
        "instrumentals and songs via native ACE-Step v1 or 1.5 Turbo",
        "full control over sampling or other ACE-Step versions/node packs via custom ComfyUI workflows",
    ]
    not_good_for = [
        "setups without a running ComfyUI server",
        "CPU-only machines",
    ]
    fallback_tools = ["music_library"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "model_profile": {"type": "string", "enum": list(_PROFILES)},
            "text_encoder_device": {"type": "string", "enum": ["default", "cpu"],
                "description": "ACE-Step 1.5: native automatic GPU placement or CPU encoding."},
            "prompt": {
                "type": "string",
                "description": (
                    "Style/mood/genre description (ACE-Step 'tags'), e.g. "
                    "'upbeat electronic pop, female vocals, driving bassline'. "
                    "Comma-separated tags work best. Not injected for custom workflows."
                ),
            },
            "lyrics": {
                "type": "string",
                "default": "",
                "description": (
                    "Optional lyrics. Leave empty for instrumental. Supports structure "
                    "tags like [verse]/[chorus]/[bridge] and language-code prefixes "
                    "(e.g. [zh], [ja]) for non-English lines."
                ),
            },
            "duration_seconds": {"type": "number", "default": 120.0},
            "bpm": {"type": "integer", "minimum": 10, "maximum": 300,
                    "description": "Explicit ACE-Step 1.5 tempo; defaults to 100."},
            "steps": {"type": "integer", "description": "Defaults to 8 for 1.5 Turbo, 50 for v1."},
            "cfg": {"type": "number", "description": "Defaults to 1 for 1.5 Turbo, 5 for v1."},
            "lyrics_strength": {"type": "number", "default": 0.99},
            "seed": {"type": "integer", "description": "Random if omitted"},
            "output_path": {"type": "string", "description": "Where to save the audio"},
            "workflow_json": {
                "type": "string",
                "description": "Optional full ComfyUI workflow JSON. Requires output_node.",
            },
            "workflow_path": {
                "type": "string",
                "description": "Optional path to a ComfyUI workflow JSON file. Requires output_node.",
            },
            "output_node": {
                "type": "string",
                "description": "ComfyUI output node ID for custom workflow_json/workflow_path.",
            },
            "workflow_name": {
                "type": "string",
                "description": "Optional human-readable provenance label for a custom workflow.",
            },
            "workflow_model": {
                "type": "string",
                "description": "Optional model/provenance label for a custom workflow.",
            },
            "workflow_model_stack": {
                "type": "array",
                "description": (
                    "Optional provenance metadata for custom workflow dependencies. "
                    "Items should include name, role, and node-pack origin when known."
                ),
                "items": {"type": "object"},
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "How long to wait for the ComfyUI job before giving up. Default 1800s (30min).",
            },
            "resume_prompt_id": {
                "type": "string",
                "description": "A prompt_id from a previous timed-out call. Skips resubmission and resumes waiting/downloading.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=8000, vram_mb=8000, disk_mb=500, network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["prompt", "lyrics", "duration_seconds", "seed"]
    side_effects = ["writes audio file to output_path"]
    user_visible_verification = ["Listen to generated audio for mood, genre accuracy, and quality"]

    def __init__(self) -> None:
        self._client = ComfyUIClient(capability="music")
        self._last_progress_log = 0.0

    def get_status(self) -> ToolStatus:
        if not self._client.is_available():
            return ToolStatus.UNAVAILABLE
        try:
            profile = self._profile({})
            if profile == "ace-step-1.5-turbo":
                self._text_encoder_device({})
        except ValueError:
            return ToolStatus.UNAVAILABLE
        _, missing = self._client.check_models(_PROFILES[profile][2])
        if missing:
            return ToolStatus.DEGRADED
        if profile == "ace-step-1.5-turbo":
            graph = ComfyUIClient.load_workflow(_WORKFLOWS / "ace-step-1.5-t2a.json")
            if any(not self._client.has_node(node['class_type']) for node in graph.values()):
                return ToolStatus.DEGRADED
        return ToolStatus.AVAILABLE

    @staticmethod
    def _profile(inputs: dict[str, Any]) -> str:
        profile = inputs.get("model_profile") or os.environ.get("COMFYUI_MUSIC_PROFILE", "ace-step-1")
        if profile not in _PROFILES:
            raise ValueError(f"Unknown local music model_profile: {profile}")
        return profile

    @staticmethod
    def _text_encoder_device(inputs: dict[str, Any]) -> str:
        device = inputs.get("text_encoder_device") or os.environ.get("COMFYUI_MUSIC_TEXT_ENCODER_DEVICE", "cpu")
        if device not in ("default", "cpu"):
            raise ValueError(f"Unknown music text_encoder_device: {device}")
        return device

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return float(inputs.get("steps", 50)) * 2.0

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["setup_offer"] = self.setup_offer
        key = _PROFILES[self._profile({})][0]
        info["bundled_model_stack"] = BUNDLED_MODEL_STACKS[key]
        info["model_profile"] = self._profile({})
        if info["model_profile"] == "ace-step-1.5-turbo":
            info["text_encoder_device"] = os.environ.get("COMFYUI_MUSIC_TEXT_ENCODER_DEVICE", "cpu")
        return info

    def _log_progress(self, data: dict) -> None:
        """Throttled progress line (see comfyui_video for rationale)."""
        now = time.monotonic()
        if now - self._last_progress_log < 10:
            return
        self._last_progress_log = now
        value, max_value = data.get("value"), data.get("max")
        if value is not None and max_value:
            print(f"[comfyui_music] step {value}/{max_value}")

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        custom_workflow = bool(inputs.get("workflow_json") or inputs.get("workflow_path"))
        try:
            profile = self._profile(inputs) if not custom_workflow else "ace-step-1"
            if profile == "ace-step-1.5-turbo":
                self._text_encoder_device(inputs)
                duration = float(inputs.get('duration_seconds', 120))
                if not math.isfinite(duration) or not 1 <= duration <= 600:
                    raise ValueError('Music duration_seconds must be between 1 and 600 seconds.')
                if not str(inputs.get('prompt', '')).strip():
                    raise ValueError('A music prompt is required.')
                if inputs.get('output_path') and Path(inputs['output_path']).suffix.lower() != '.mp3':
                    raise ValueError('Bundled music output_path must have a .mp3 extension.')
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))
        if profile == "ace-step-1.5-turbo" and not inputs.get("lyrics"):
            inputs = {**inputs, "lyrics": "[Instrumental]"}
        workflow_key = _PROFILES[profile][0]
        if custom_workflow and not inputs.get("output_node"):
            return ToolResult(
                success=False,
                error=(
                    "Custom ComfyUI workflows require output_node so OpenMontage "
                    "knows which ComfyUI node to download artifacts from."
                ),
            )

        if not self._client.is_available():
            return ToolResult(success=False, error=self._client.unavailable_reason())

        if not custom_workflow:
            _, missing = self._client.check_models(_PROFILES[profile][2])
            if missing:
                return ToolResult(
                    success=False,
                    data=missing_models_payload(
                        missing,
                        workflow_key=workflow_key,
                        workflow_name=f"{workflow_key}.json",
                    ),
                    error=(
                        f"ComfyUI server is running but missing required models: "
                        f"{', '.join(missing)}.\n"
                        f"See data.missing_models for destination hints and download URLs."
                    ),
                )

        start = time.time()
        seed = inputs.get("seed")
        if seed is None:
            seed = ComfyUIClient.random_seed()
        output_path = Path(inputs.get("output_path", f"comfyui_music_{seed}.mp3"))

        try:
            if custom_workflow:
                workflow = self._load_custom_workflow(inputs)
                output_node = str(inputs["output_node"])
            else:
                workflow = ComfyUIClient.load_workflow(_WORKFLOWS / f"{workflow_key}.json")
                workflow = ComfyUIClient.patch_workflow(workflow, {
                    "2": {
                        "tags": inputs["prompt"],
                        "lyrics": inputs.get("lyrics", ""),
                    },
                    "4": {"seconds": inputs.get("duration_seconds", 120.0)},
                    "8": {
                        "seed": seed,
                        "steps": inputs.get("steps", 8 if profile == "ace-step-1.5-turbo" else 50),
                        "cfg": inputs.get("cfg", 1.0 if profile == "ace-step-1.5-turbo" else 5.0),
                    },
                    "10": {"filename_prefix": output_path.stem},
                })
                if profile == "ace-step-1.5-turbo":
                    workflow["11"]["inputs"]["device"] = self._text_encoder_device(inputs)
                    workflow["2"]["inputs"].update(
                        duration=inputs.get("duration_seconds", 120.0), seed=seed,
                        bpm=inputs.get("bpm", 100),
                    )
                else:
                    workflow["2"]["inputs"]["lyrics_strength"] = inputs.get("lyrics_strength", 0.99)
                output_node = "10"

            provenance = self._workflow_provenance(inputs, custom_workflow, output_node, workflow)
            paths = self._client.generate(
                workflow,
                output_node=output_node,
                dest=output_path,
                timeout=inputs.get("timeout_seconds", 1800),
                interval=10,
                resume_prompt_id=inputs.get("resume_prompt_id"),
                on_progress=self._log_progress,
            )

        except ComfyUIError as exc:
            data = {"prompt_id": exc.prompt_id} if exc.prompt_id else {}
            if exc.prompt_id:
                error_msg = (
                    f"{exc}\n\nThis job was NOT cancelled and is very likely still "
                    f"running server-side. To recover it without resubmitting, call "
                    f"execute() again with resume_prompt_id={exc.prompt_id!r} "
                    f"(and a longer timeout_seconds if it needs more time), or poll "
                    f"GET {{COMFYUI_SERVER_URL}}/history/{exc.prompt_id} directly."
                )
            else:
                error_msg = str(exc)
            return ToolResult(success=False, error=error_msg, data=data)
        except Exception as exc:
            return ToolResult(success=False, error=f"ComfyUI music generation failed: {exc}")

        duration = self._probe_duration(paths[0])
        model_name = self._model_name(inputs, custom_workflow)
        return ToolResult(
            success=True,
            data={
                "provider": "comfyui",
                "model": model_name,
                "prompt": inputs["prompt"],
                "lyrics": inputs.get("lyrics", ""),
                "duration_seconds": duration,
                "output": str(paths[0]),
                "format": paths[0].suffix.lstrip("."),
                "workflow_provenance": provenance,
            },
            artifacts=[str(p) for p in paths],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=seed,
            model=model_name,
        )

    @staticmethod
    def _load_custom_workflow(inputs: dict[str, Any]) -> dict:
        if inputs.get("workflow_json"):
            return json.loads(inputs["workflow_json"])
        return ComfyUIClient.load_workflow(Path(inputs["workflow_path"]))

    @staticmethod
    def _model_name(inputs: dict[str, Any], custom_workflow: bool) -> str:
        if not custom_workflow:
            return _PROFILES[ComfyUIMusic._profile(inputs)][1]
        return (
            inputs.get("workflow_model")
            or inputs.get("model")
            or inputs.get("workflow_name")
            or "custom-comfyui-workflow"
        )

    @staticmethod
    def _workflow_provenance(
        inputs: dict[str, Any],
        custom_workflow: bool,
        output_node: str,
        workflow: dict[str, Any],
    ) -> dict[str, Any]:
        if not custom_workflow:
            key = _PROFILES[ComfyUIMusic._profile(inputs)][0]
            return {
                "source": "bundled",
                "workflow": f"{key}.json",
                "workflow_hash_sha256": workflow_hash(workflow),
                "model_stack": model_stack(key, inputs),
                "output_node": output_node,
                "parameters": {
                    "steps": workflow["8"]["inputs"]["steps"],
                    "cfg": workflow["8"]["inputs"]["cfg"],
                    "duration_seconds": workflow["4"]["inputs"]["seconds"],
                    **({"bpm": workflow["2"]["inputs"]["bpm"],
                        "text_encoder_device": workflow["11"]["inputs"]["device"]}
                       if key == "ace-step-1.5-t2a" else {}),
                },
            }
        stack = inputs.get("workflow_model_stack")
        return {
            "source": "user_supplied",
            "workflow_name": inputs.get("workflow_name"),
            "workflow_path": inputs.get("workflow_path"),
            "model": inputs.get("workflow_model") or inputs.get("model"),
            "workflow_hash_sha256": workflow_hash(workflow),
            "model_stack": stack if isinstance(stack, list) else [],
            "model_stack_source": "caller_supplied" if stack else "unknown_custom_workflow",
            "output_node": output_node,
        }

    @staticmethod
    def _probe_duration(path: Path) -> float | None:
        """Best-effort track duration via ffprobe; None if unavailable."""
        if shutil.which("ffprobe") is None:
            return None
        try:
            out = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                capture_output=True, text=True, timeout=15, check=True,
            )
            value = out.stdout.strip()
            return round(float(value), 2) if value else None
        except (subprocess.SubprocessError, ValueError):
            return None
