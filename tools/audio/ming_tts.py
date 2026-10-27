"""Local Ming narration with bounded chunks, omission checks and caption timing.

Start the owner's existing loopback Ming server manually. References stay in
that server; this client sends only text and the selected local voice name.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import wave
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from tools.audio._ming_alignment import align
from tools.base_tool import (
    BaseTool, Determinism, ResourceProfile, ToolResult, ToolRuntime,
    ToolStability, ToolStatus, ToolTier,
)


def split_text(text: str) -> list[str]:
    """Preserve normalized whitespace, preferring punctuation before word 25."""
    words = text.split()
    chunks = []
    while words:
        limit = min(25, len(words))
        if len(words) > 25:
            boundaries = [i + 1 for i, word in enumerate(words[:25]) if re.search(r"[.!?;,:][\"'”’)]*$", word)]
            if boundaries:
                limit = boundaries[-1]
        chunks.append(" ".join(words[:limit]))
        words = words[limit:]
    return chunks


@lru_cache(maxsize=1)
def _verifier():
    from faster_whisper import WhisperModel
    # CPU verification leaves the 8 GB GPU exclusively to Ming. Never download
    # weights silently during narration; setup preloads the pinned checkpoint.
    return WhisperModel("large-v3-turbo", device="cpu", compute_type="int8", local_files_only=True)


def transcribe_words(path: Path) -> list[dict]:
    import numpy as np
    decoded = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, check=True, timeout=60,
    )
    segments, _ = _verifier().transcribe(
        np.frombuffer(decoded.stdout, dtype=np.float32), language="en", word_timestamps=True,
    )
    return [{"word": word.word.strip(), "start": word.start, "end": word.end}
            for segment in segments for word in (segment.words or [])]


def _url() -> str:
    url = os.environ.get("MING_TTS_URL", "http://127.0.0.1:17500").rstrip("/")
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("MING_TTS_URL must be a local loopback HTTP server")
    return url


class MingTTS(BaseTool):
    name = "ming_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "ming"
    runtime = ToolRuntime.LOCAL_GPU
    stability = ToolStability.EXPERIMENTAL
    determinism = Determinism.STOCHASTIC
    dependencies = ["cmd:ffmpeg", "python:faster_whisper", "python:httpx"]
    agent_skills = ["ffmpeg"]
    install_instructions = (
        "Start Ming manually: cd ~/Projects/personal/content/voice-backends && "
        "ming-3.0-tts/.venv/bin/python ming_server.py\n"
        "Set MING_TTS_URL (default http://127.0.0.1:17500) and MING_TTS_VOICE "
        "(default me-narration). Preload faster-whisper large-v3-turbo for CPU verification."
    )
    capabilities = ["text_to_speech", "voice_cloning", "word_timestamps", "offline_generation"]
    supports = {"voice_cloning": True, "offline": True, "native_audio": True, "word_timestamps": True}
    best_for = ["owner's cloned narration voice", "private local narration with omission checks"]
    not_good_for = ["servers that are not running", "simultaneous GPU generation"]
    resource_profile = ResourceProfile(cpu_cores=4, ram_mb=8000, vram_mb=4000, disk_mb=2000, network_required=False)
    side_effects = ["writes narration and optional timings", "unloads Ming GPU model after generation"]
    input_schema = {
        "type": "object", "required": ["text"], "properties": {
            "text": {"type": "string"}, "voice": {"type": "string"}, "voice_id": {"type": "string"},
            "output_path": {"type": "string"},
            "output_format": {"type": "string", "enum": ["wav", "mp3"]},
            "timestamps": {"type": "boolean", "default": False},
        },
    }

    def get_status(self) -> ToolStatus:
        try:
            with httpx.Client(trust_env=False, timeout=2) as client:
                response = client.get(_url() + "/health")
                if response.status_code == 200 and response.json().get("status") == "ok":
                    return ToolStatus.AVAILABLE
        except (httpx.HTTPError, ValueError, AttributeError):
            pass
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict) -> float:
        return 0.0

    def execute(self, inputs: dict) -> ToolResult:
        start = time.monotonic()
        try:
            text = inputs["text"]
            if not isinstance(text, str) or not text.strip() or not re.search(r"\w", text):
                raise ValueError("text must contain words")
            if inputs.get("voice") and inputs.get("voice_id") and inputs["voice"] != inputs["voice_id"]:
                raise ValueError("voice and voice_id disagree")
            voice = inputs.get("voice") or inputs.get("voice_id") or os.environ.get("MING_TTS_VOICE") or "me-narration"
            default_format = inputs.get("output_format") or "wav"
            output = Path(inputs.get("output_path") or f"ming_narration.{default_format}")
            fmt = inputs.get("output_format") or output.suffix.lstrip(".").lower()
            if fmt not in {"wav", "mp3"} or output.suffix.lower() != f".{fmt}":
                raise ValueError("output_path and output_format must agree (wav or mp3)")
            url = _url()
            if self.get_status() != ToolStatus.AVAILABLE:
                raise RuntimeError("Ming is unavailable. " + self.install_instructions)
            output.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".ming-", dir=output.parent) as folder:
                with httpx.Client(trust_env=False, timeout=httpx.Timeout(900, connect=2)) as client:
                    generation_error = None
                    unload_error = None
                    try:
                        result = self._generate(client, url, text, voice, output, fmt, Path(folder), bool(inputs.get("timestamps")))
                    except Exception as exc:
                        generation_error = exc
                    finally:
                        try:
                            unloaded = client.post(url + "/unload", timeout=60)
                            unloaded.raise_for_status()
                        except httpx.HTTPError as exc:
                            unload_error = f"Ming unload failed: {type(exc).__name__}; GPU state is uncertain"
                    if generation_error:
                        detail = f"{generation_error}; {unload_error}" if unload_error else str(generation_error)
                        raise RuntimeError(detail) from generation_error
                    if unload_error:
                        result.data.setdefault("warnings", []).append(unload_error)
                result.duration_seconds = round(time.monotonic() - start, 2)
                return result
        except Exception as exc:
            return ToolResult(success=False, error=f"Ming narration failed: {exc}", duration_seconds=round(time.monotonic() - start, 2))

    def _generate(self, client, url, text, voice, output, fmt, folder, timestamps):
        chunks = split_text(text)
        selected, attempts, all_words, skipped = [], [], [], []
        offset = 0.0
        for index, chunk in enumerate(chunks):
            best = None
            for take in range(1, 4):
                response = client.post(url + "/v1/audio/speech", json={"input": chunk, "voice": voice, "response_format": "wav"})
                response.raise_for_status()
                raw, normalized = folder / f"raw-{index}-{take}.wav", folder / f"take-{index}-{take}.wav"
                raw.write_bytes(response.content)
                # Normalize rate/channels/sample width so concatenation is exact.
                proc = subprocess.run(
                    ["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(normalized)],
                    capture_output=True, timeout=60,
                )
                if proc.returncode:
                    raise ValueError("Ming returned invalid audio")
                with wave.open(str(normalized)) as audio:
                    duration = audio.getnframes() / audio.getframerate()
                if duration <= 0:
                    raise ValueError("Ming returned empty audio")
                words, missing = align(chunk, transcribe_words(normalized), duration)
                if best is None or len(missing) < len(best[0]):
                    best = (missing, normalized, words, duration)
                if not missing:
                    break
            missing, chosen, words, duration = best
            selected.append(chosen)
            attempts.append(take)
            skipped.extend(missing)
            all_words.extend({**word, "start": round(word["start"] + offset, 6), "end": round(word["end"] + offset, 6)} for word in words)
            offset += duration
        assembled = folder / "assembled.wav"
        with wave.open(str(assembled), "wb") as destination:
            destination.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            for path in selected:
                with wave.open(str(path)) as source:
                    destination.writeframes(source.readframes(source.getnframes()))
        staged = folder / ("final." + fmt)
        if fmt == "mp3":
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(assembled), "-c:a", "libmp3lame", "-q:a", "2", str(staged)], check=True, capture_output=True, timeout=60)
        else:
            shutil.copyfile(assembled, staged)
        staged.replace(output)
        artifacts = [str(output)]
        data = {"provider": self.provider, "model": "Ming-3.0-tts-0.5b", "voice": voice,
                "output": str(output), "format": fmt, "audio_duration_seconds": round(offset, 6),
                "attempts": attempts, "skipped_words": skipped}
        if skipped:
            data["warnings"] = ["No complete take after three attempts; review skipped_words before publishing."]
        if timestamps:
            timing_path = output.with_suffix(".timings.json")
            timing_path.write_text(json.dumps(all_words, ensure_ascii=False, indent=2), encoding="utf-8")
            artifacts.append(str(timing_path))
            data.update(word_timestamps=all_words, timings_path=str(timing_path))
        return ToolResult(success=True, data=data, artifacts=artifacts, model=data["model"], cost_usd=0.0)
