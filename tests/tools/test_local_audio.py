"""Local audio tools emit native graphs and real, correctly encoded files."""
import importlib
import json
from pathlib import Path
import subprocess

import pytest

from tools.audio.comfyui_music import ComfyUIMusic
from tools.base_tool import ToolStatus


def music_tool(monkeypatch):
    monkeypatch.delenv('COMFYUI_MUSIC_PROFILE', raising=False)
    monkeypatch.delenv('COMFYUI_MUSIC_TEXT_ENCODER_DEVICE', raising=False)
    tool = ComfyUIMusic()
    tool._client.is_available = lambda: True
    tool._client.check_models = lambda required: (required, [])
    tool._client.has_node = lambda name: True
    return tool


def test_ace15_emits_low_memory_native_graph_and_truthful_provenance(monkeypatch, tmp_path):
    tool = music_tool(monkeypatch)
    observed = {}
    def generate(workflow, output_node, dest, **kwargs):
        observed.update(workflow=workflow, output_node=output_node)
        return [Path(dest)]
    tool._client.generate = generate
    result = tool.execute({'prompt': 'instrumental ambient piano', 'model_profile': 'ace-step-1.5-turbo',
                          'duration_seconds': 30, 'seed': 0, 'output_path': str(tmp_path/'song.mp3')})
    assert result.success, result.error
    graph = observed['workflow']
    assert graph['1']['inputs']['unet_name'] == 'acestep_v1.5_turbo.safetensors'
    assert graph['11']['inputs']['clip_name2'] == 'qwen_1.7b_ace15.safetensors'
    assert graph['11']['inputs']['device'] == 'cpu'
    assert graph['2']['class_type'] == 'TextEncodeAceStepAudio1.5'
    assert graph['2']['inputs']['lyrics'] == '[Instrumental]'
    assert result.data['lyrics'] == '[Instrumental]'
    assert graph['2']['inputs']['duration'] == 30
    assert graph['2']['inputs']['seed'] == graph['8']['inputs']['seed'] == 0
    assert graph['4']['inputs']['batch_size'] == 1
    assert graph['8']['inputs']['steps'] == 8
    assert result.model == 'ace-step-1.5-turbo'
    assert result.data['workflow_provenance']['workflow'] == 'ace-step-1.5-t2a.json'
    assert result.cost_usd == 0


def test_profile_precedence_and_status_check_the_selected_stack(monkeypatch):
    tool = music_tool(monkeypatch)
    monkeypatch.setenv('COMFYUI_MUSIC_PROFILE', 'ace-step-1.5-turbo')
    stacks = []
    def check(required):
        stacks.append(required)
        return [], required
    tool._client.check_models = check
    assert tool.get_status() == ToolStatus.DEGRADED
    assert 'qwen_1.7b_ace15.safetensors' in stacks[-1]
    explicit = tool.execute({'prompt': 'piano', 'model_profile': 'ace-step-1'})
    assert not explicit.success
    assert stacks[-1] == ['ace_step_v1_3.5b.safetensors']


def test_ace15_missing_core_node_is_not_reported_available(monkeypatch):
    tool = music_tool(monkeypatch)
    monkeypatch.setenv('COMFYUI_MUSIC_PROFILE', 'ace-step-1.5-turbo')
    tool._client.has_node = lambda name: name != 'TextEncodeAceStepAudio1.5'
    assert tool.get_status() == ToolStatus.DEGRADED


def test_sfx_converts_native_flac_to_pcm_wav_and_keeps_seed(tmp_path):
    cls = importlib.import_module('tools.audio.comfyui_sfx').ComfyUISfx
    tool = cls()
    tool._client.is_available = lambda: True
    tool._client.check_models = lambda required: (required, [])
    tool._client.has_node = lambda name: True
    observed = {}
    def generate(workflow, output_node, dest, **kwargs):
        observed.update(graph=workflow, dest=Path(dest))
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'sine=frequency=750:duration=0.25', '-y', str(dest)], check=True)
        return [Path(dest)]
    tool._client.generate = generate
    output = tmp_path/'effect.wav'
    result = tool.execute({'prompt': 'a short click', 'duration_seconds': 0.25,
                          'seed': 0, 'output_path': str(output)})
    assert result.success, result.error
    assert observed['dest'].suffix == '.flac'
    assert output.read_bytes().startswith(b'RIFF')
    assert observed['graph']['8']['inputs']['seed'] == 0
    assert result.data['model'] == 'stable-audio-open-1.0'
    assert result.cost_usd == 0
    assert result.data['duration_seconds'] == pytest.approx(0.25, abs=0.02)


@pytest.mark.parametrize('duration', [-1, 0, float('nan'), float('inf'), 48])
def test_sfx_rejects_invalid_duration_without_contacting_server(duration, tmp_path):
    tool = importlib.import_module('tools.audio.comfyui_sfx').ComfyUISfx()
    tool._client.is_available = lambda: pytest.fail('Invalid input contacted server')
    result = tool.execute({'prompt': 'click', 'duration_seconds': duration,
                          'output_path': str(tmp_path/'effect.wav')})
    assert not result.success
    assert 'duration' in result.error.lower()
    assert not list(tmp_path.iterdir())


def test_cli_exposes_music_and_sfx_without_generation(capsys):
    cli = importlib.import_module('tools.audio.local_audio')
    with pytest.raises(SystemExit) as exc:
        cli.main(['--help'])
    assert exc.value.code == 0
    text = capsys.readouterr().out
    assert 'music' in text and 'sfx' in text


def test_invalid_profile_is_rejected_before_contacting_server(monkeypatch):
    tool = music_tool(monkeypatch)
    tool._client.is_available = lambda: pytest.fail('Invalid profile contacted server')
    result = tool.execute({'prompt': 'piano', 'model_profile': 'unknown'})
    assert not result.success
    assert 'model_profile' in result.error


def test_cli_failure_keeps_missing_model_report_and_never_calls_cloud(monkeypatch, tmp_path, capsys):
    cli = importlib.import_module('tools.audio.local_audio')
    from tools.tool_registry import registry
    from tools.base_tool import ToolResult
    class UnavailableLocalTool:
        def execute(self, inputs):
            return ToolResult(success=False, error='Missing local model',
                              data={'missing_models': [{'name': 'stable_audio_open_1.0.safetensors'}]})
    monkeypatch.setattr(registry, 'discover', lambda: None)
    def get(name):
        assert name == 'comfyui_sfx'
        return UnavailableLocalTool()
    monkeypatch.setattr(registry, 'get', get)
    with pytest.raises(SystemExit) as exc:
        cli.main(['sfx', '--prompt', 'click', '--duration-seconds', '2',
                  '--output-path', str(tmp_path/'effect.wav')])
    assert exc.value.code == 1
    report = json.loads(capsys.readouterr().out)
    assert report['data']['missing_models'][0]['name'] == 'stable_audio_open_1.0.safetensors'
    assert not list(tmp_path.iterdir())


def test_resumed_sfx_uses_original_graph_seed_prompt_and_duration(tmp_path):
    tool = importlib.import_module('tools.audio.comfyui_sfx').ComfyUISfx()
    tool._client.is_available = lambda: True
    tool._client.check_models = lambda required: (required, [])
    source = Path(__file__).parents[2]/'tools/_comfyui/workflows/stable-audio-open-sfx.json'
    graph = json.loads(source.read_text())
    graph['3']['inputs']['text'] = 'original bell'
    graph['5']['inputs']['seconds_total'] = 0.25
    graph['8']['inputs']['seed'] = 123
    tool._client.poll = lambda *a, **kw: {'prompt': [1, 'original-job', graph, {}, ['10']]}
    def generate(workflow, output_node, dest, **kwargs):
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'sine=frequency=750:duration=0.25', '-y', str(dest)], check=True)
        return [Path(dest)]
    tool._client.generate = generate
    result = tool.execute({'prompt': 'new wrong description', 'duration_seconds': 2, 'seed': 999,
                          'resume_prompt_id': 'original-job', 'output_path': str(tmp_path/'resumed.wav')})
    assert result.success, result.error
    assert result.seed == 123
    assert result.data['prompt'] == 'original bell'
    assert result.data['duration_seconds'] == pytest.approx(0.25, abs=0.02)
    from tools._comfyui.metadata import workflow_hash
    assert result.data['workflow_provenance']['workflow_hash_sha256'] == workflow_hash(graph)


def test_cli_music_passes_explicit_tempo_to_the_native_graph(monkeypatch, tmp_path):
    cli = importlib.import_module('tools.audio.local_audio')
    from tools.tool_registry import registry
    tool = music_tool(monkeypatch)
    observed = {}
    def generate(workflow, output_node, dest, **kwargs):
        observed['tempo'] = workflow['2']['inputs']['bpm']
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
                        'sine=frequency=750:duration=0.25','-y',str(dest)],check=True)
        return [Path(dest)]
    tool._client.generate = generate
    monkeypatch.setattr(registry, 'discover', lambda: None)
    monkeypatch.setattr(registry, 'get', lambda name: tool)
    cli.main(['music','--model-profile','ace-step-1.5-turbo','--bpm','90',
              '--prompt','instrumental piano, 90 BPM','--output-path',str(tmp_path/'song.mp3')])
    assert observed['tempo'] == 90
    saved = json.loads((tmp_path/'song.mp3.json').read_text())
    assert saved['cost_usd'] == 0
    assert saved['workflow_provenance']['parameters']['bpm'] == 90


def test_music_device_override_wins_over_workstation_configuration(monkeypatch, tmp_path):
    tool = music_tool(monkeypatch)
    monkeypatch.setenv('COMFYUI_MUSIC_TEXT_ENCODER_DEVICE', 'default')
    seen=[]
    def generate(graph, output_node, dest, **kwargs):
        seen.append(graph['11']['inputs']['device'])
        return [Path(dest)]
    tool._client.generate = generate
    base={'prompt':'instrumental piano','model_profile':'ace-step-1.5-turbo',
          'output_path':str(tmp_path/'song.mp3')}
    assert tool.execute(base).success
    assert seen[-1] == 'default'
    assert tool.execute({**base,'text_encoder_device':'cpu'}).success
    assert seen[-1] == 'cpu'


def test_invalid_music_device_fails_before_contacting_server(monkeypatch):
    tool=music_tool(monkeypatch)
    tool._client.is_available=lambda: pytest.fail('Invalid device contacted server')
    result=tool.execute({'prompt':'piano','model_profile':'ace-step-1.5-turbo',
                         'text_encoder_device':'unknown'})
    assert not result.success
    assert 'device' in result.error
