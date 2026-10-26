"""Regression tests for audio_mixer full_mix ducking filtergraph.

The ducking branch built an `acopy[speech_dup]` filter whose output pad was
never consumed, leaving the FFmpeg filtergraph with a dangling output. FFmpeg
rejects that, so `full_mix` with the most common shape — a single narration
track plus one music bed, with ducking enabled (the default) — always failed.
"""

import shutil
import math
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.audio.audio_mixer import AudioMixer  # noqa: E402

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg required for full_mix"
)


def _sine(path: Path, freq: int, dur: int) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}", str(path)],
        capture_output=True,
        check=True,
        timeout=30,
    )


def _has_audio(path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    return "audio" in out.stdout


def test_full_mix_single_narration_plus_music_with_ducking(tmp_path):
    speech = tmp_path / "speech.wav"
    music = tmp_path / "music.wav"
    _sine(speech, 440, 2)
    _sine(music, 220, 3)
    out = tmp_path / "mixed.wav"

    result = AudioMixer().execute(
        {
            "operation": "full_mix",
            "tracks": [
                {"path": str(speech), "role": "speech"},
                {"path": str(music), "role": "music"},
            ],
            "ducking": {"enabled": True},
            "output_path": str(out),
        }
    )

    assert result.success is True, result.error
    assert out.exists() and _has_audio(out)


def test_full_mix_multi_narration_plus_music_with_ducking(tmp_path):
    s1, s2 = tmp_path / "s1.wav", tmp_path / "s2.wav"
    music = tmp_path / "music.wav"
    _sine(s1, 440, 2)
    _sine(s2, 330, 2)
    _sine(music, 220, 3)
    out = tmp_path / "mixed_multi.wav"

    result = AudioMixer().execute(
        {
            "operation": "full_mix",
            "tracks": [
                {"path": str(s1), "role": "speech"},
                {"path": str(s2), "role": "speech"},
                {"path": str(music), "role": "music"},
            ],
            "ducking": {"enabled": True},
            "output_path": str(out),
        }
    )

    assert result.success is True, result.error
    assert out.exists() and _has_audio(out)


@pytest.mark.parametrize('operation', ['duck', 'full_mix'])
def test_ducking_times_keep_the_public_millisecond_units(tmp_path, monkeypatch, operation):
    speech, music = tmp_path/'speech.wav', tmp_path/'music.wav'
    speech.touch(); music.touch()
    commands = []
    tool = AudioMixer()
    def run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout='', stderr='')
    monkeypatch.setattr(tool, 'run_command', run)
    result = tool.execute({'operation':operation, 'tracks':[
        {'path':str(speech),'role':'speech'}, {'path':str(music),'role':'music'}],
        'ducking':{'attack_ms':40,'release_ms':700},
        'output_path':str(tmp_path/'mix.wav')})
    assert result.success, result.error
    graph=commands[-1][commands[-1].index('-filter_complex')+1]
    assert 'attack=40:release=700:' in graph


def test_full_mix_music_returns_gradually_after_speech(tmp_path):
    speech, music, output = tmp_path/'speech.wav', tmp_path/'music.wav', tmp_path/'mix.wav'
    _sine(speech, 600, 1)
    _sine(music, 220, 3)
    result = AudioMixer().execute({'operation':'full_mix','tracks':[
        {'path':str(speech),'role':'speech'},{'path':str(music),'role':'music'}],
        'ducking':{'attack_ms':40,'release_ms':700}, 'normalize':False,
        'target_duration':3,'output_path':str(output)})
    assert result.success, result.error
    def rms(start, end):
        with wave.open(str(output),'rb') as handle:
            handle.setpos(round(start*handle.getframerate()))
            raw=handle.readframes(round((end-start)*handle.getframerate()))
        samples=struct.unpack(f'<{len(raw)//2}h', raw)
        return math.sqrt(sum(x*x for x in samples)/len(samples))
    assert rms(2.5,2.6)>1.4*rms(1.05,1.1)
