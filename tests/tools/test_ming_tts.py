"""Real loopback transport/audio; only expensive speech recognition is replaced."""
import importlib
import io
import json
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tools.base_tool import ToolStatus


def _wav(seconds=1):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        handle.writeframes(b"\x00\x01" * (24000 * seconds))
    return buffer.getvalue()


@pytest.fixture
def server(monkeypatch):
    state = {"requests": [], "takes": [], "healthy": True, "error": False, "unload_error": False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200 if state["healthy"] else 503)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "model": "test-ming"}).encode())

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            state["requests"].append((self.path, json.loads(body) if body else {}))
            if self.path == "/unload":
                if state["unload_error"]:
                    self.send_response(503)
                    self.end_headers()
                    return
                payload = b'{"model_loaded": false}'
            elif state["error"]:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"synthesis failed")
                return
            else:
                payload = state["takes"].pop(0) if state["takes"] else _wav()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(payload)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("MING_TTS_URL", f"http://127.0.0.1:{httpd.server_port}")
    monkeypatch.setenv("MING_TTS_VOICE", "me-narration")
    yield state
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def _module():
    return importlib.import_module("tools.audio.ming_tts")


def test_status_tracks_real_http_health(server):
    tool = _module().MingTTS()
    assert tool.get_status() == ToolStatus.AVAILABLE
    server["healthy"] = False
    assert tool.get_status() == ToolStatus.UNAVAILABLE


def test_chunks_preserve_text_and_prefer_sentence_boundaries():
    split = _module().split_text
    text = "First short sentence. " + " ".join(f"word{i}" for i in range(26))
    chunks = split(text)
    assert chunks[0] == "First short sentence."
    assert " ".join(chunks) == text
    assert [len(c.split()) for c in chunks] == [3, 25, 1]
    assert split("  \n ") == []


def test_wav_retake_keeps_complete_take_and_writes_timings(server, monkeypatch, tmp_path):
    module = _module()
    server["takes"] = [_wav(), _wav(2)]
    heard = iter([
        [{"word": "Hello", "start": 0.1, "end": 0.5}],
        [{"word": "Hello", "start": 0.1, "end": 0.5}, {"word": "world", "start": 0.7, "end": 1.8}],
    ])
    monkeypatch.setattr(module, "transcribe_words", lambda path: next(heard))
    output = tmp_path / "voice.wav"
    result = module.MingTTS().execute({
        "text": "Hello world.", "voice_id": "custom", "output_path": str(output), "timestamps": True,
    })
    assert result.success, result.error
    with wave.open(str(output)) as audio:
        assert audio.getnframes() / audio.getframerate() == 2
    assert result.data["attempts"] == [2]
    assert result.data["skipped_words"] == []
    assert result.data["word_timestamps"] == [
        {"word": "Hello", "start": 0.1, "end": 0.5},
        {"word": "world", "start": 0.7, "end": 1.8},
    ]
    assert json.loads(output.with_suffix(".timings.json").read_text()) == result.data["word_timestamps"]
    speech = [body for path, body in server["requests"] if path == "/v1/audio/speech"]
    assert [body["voice"] for body in speech] == ["custom", "custom"]
    assert server["requests"][-1][0] == "/unload"


def test_multiple_chunks_have_global_timestamps_and_mp3_output(server, monkeypatch, tmp_path):
    module = _module()
    text = " ".join(["hello"] * 25) + ". World."
    def recognize(path):
        if len([r for r in server["requests"] if r[0] == "/v1/audio/speech"]) == 1:
            return [{"word": "hello", "start": i / 25, "end": (i + 1) / 25} for i in range(25)]
        return [{"word": "World", "start": 0.1, "end": 0.9}]
    monkeypatch.setattr(module, "transcribe_words", recognize)
    result = module.MingTTS().execute({"text": text, "output_path": str(tmp_path / "voice.mp3"), "timestamps": True})
    assert result.success, result.error
    assert result.data["format"] == "mp3"
    assert result.data["word_timestamps"][-1] == {"word": "World", "start": 1.1, "end": 1.9}
    assert (tmp_path / "voice.mp3").stat().st_size > 100
    assert result.data["attempts"] == [1, 1]


def test_three_incomplete_takes_keep_best_and_report_omissions(server, monkeypatch, tmp_path):
    module = _module()
    server["takes"] = [_wav(), _wav(2), _wav(3)]
    heard = iter([[], [{"word": "Hello", "start": 0.1, "end": 0.5}], []])
    monkeypatch.setattr(module, "transcribe_words", lambda path: next(heard))
    output = tmp_path / "best.wav"
    result = module.MingTTS().execute({"text": "Hello world.", "output_path": str(output)})
    assert result.success, result.error
    assert result.data["attempts"] == [3]
    assert result.data["skipped_words"] == ["world"]
    assert result.data["warnings"]
    with wave.open(str(output)) as audio:
        assert audio.getnframes() / audio.getframerate() == 2


@pytest.mark.parametrize("failure", ["http", "bad_audio", "recognition"])
def test_failures_return_error_and_unload(server, monkeypatch, tmp_path, failure):
    module = _module()
    server["error"] = failure == "http"
    if failure == "bad_audio":
        server["takes"] = [b"not a wav"]
    def recognize(path):
        raise RuntimeError("recognition unavailable")
    monkeypatch.setattr(module, "transcribe_words", recognize)
    output = tmp_path / "fail.wav"
    result = module.MingTTS().execute({"text": "Hello world.", "output_path": str(output)})
    assert not result.success
    assert result.error
    assert not output.exists()
    assert server["requests"][-1][0] == "/unload"


def test_rejects_empty_text_and_remote_backend_without_contact(server, monkeypatch, tmp_path):
    module = _module()
    tool = module.MingTTS()
    assert not tool.execute({"text": "   ", "output_path": str(tmp_path / "x.wav")}).success
    monkeypatch.setenv("MING_TTS_URL", "https://example.com")
    assert tool.get_status() == ToolStatus.UNAVAILABLE
    assert not tool.execute({"text": "Hello", "output_path": str(tmp_path / "x.wav")}).success
    assert server["requests"] == []


@pytest.mark.parametrize("script,heard,missing", [
    ("The package contains three screws", "The package contains screw", ["three"]),
    ("Please bring the red and blue boxes", "Please bring a box", ["the", "red", "and", "blue"]),
    ("Bring twenty five screws", "Bring 25 screws", []),
    ("Spend $50 today", "Spend fifty dollars today", []),
])
def test_alignment_reports_omissions_without_rejecting_numeric_normalization(script, heard, missing):
    from tools.audio._ming_alignment import align
    words = [{"word": word, "start": i, "end": i + 1} for i, word in enumerate(heard.split())]
    _, omitted = align(script, words, len(words))
    assert omitted == missing


def test_synthesis_and_unload_failures_are_both_reported(server, monkeypatch, tmp_path):
    module = _module()
    server["unload_error"] = True
    def recognize(path):
        raise RuntimeError("recognition unavailable")
    monkeypatch.setattr(module, "transcribe_words", recognize)
    result = module.MingTTS().execute({"text": "Hello world", "output_path": str(tmp_path / "x.wav")})
    assert not result.success
    assert "recognition unavailable" in result.error
    assert "unload" in result.error.lower()


def test_spelling_matches_cannot_reverse_caption_timestamps():
    from tools.audio._ming_alignment import align
    words, missing = align("red boxes", [
        {"word": "box", "start": 0.2, "end": 0.8},
        {"word": "reddish", "start": 1.0, "end": 1.8},
    ], 2.0)
    assert missing == ["red"]
    assert words[0]["end"] <= words[1]["start"]


def test_output_format_selects_default_filename(server, monkeypatch, tmp_path):
    module = _module()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "transcribe_words", lambda path: [{"word": "Hello", "start": 0.1, "end": 0.9}])
    result = module.MingTTS().execute({"text": "Hello", "output_format": "mp3"})
    assert result.success, result.error
    assert (tmp_path / "ming_narration.mp3").is_file()
