"""Local Stable Audio Open effects, using native ComfyUI nodes only."""
from __future__ import annotations

import math
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any

from tools.base_tool import (BaseTool, Determinism, ExecutionMode, ResourceProfile,
                            ToolResult, ToolRuntime, ToolStability, ToolStatus, ToolTier)
from tools._comfyui.client import ComfyUIClient, ComfyUIError
from tools._comfyui.metadata import missing_models_payload, model_stack, workflow_hash
from tools.audio.comfyui_music import ComfyUIMusic

_WORKFLOW = Path(__file__).resolve().parents[1] / '_comfyui/workflows/stable-audio-open-sfx.json'
_REQUIRED = ['stable_audio_open_1.0.safetensors', 't5_base.safetensors']


class ComfyUISfx(BaseTool):
    name = 'comfyui_sfx'
    version = '0.1.0'
    tier = ToolTier.GENERATE
    capability = 'sound_effect_generation'
    provider = 'comfyui'
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU
    dependencies = ['ffmpeg']
    agent_skills = ['comfyui']
    install_instructions = ('Start local ComfyUI; install Stable Audio Open 1.0 and t5_base.safetensors. '
                            'The model requires free Hugging Face access and applicable Stability license. '
                            'COMFYUI_SFX_SERVER_URL overrides COMFYUI_SERVER_URL.')
    capabilities = ['generate_sfx', 'generate_ambience']
    supports = {'offline': True, 'seed': True, 'free': True}
    fallback_tools = []
    input_schema = {'type': 'object', 'required': ['prompt', 'output_path'], 'properties': {
        'prompt': {'type': 'string'}, 'duration_seconds': {'type': 'number', 'default': 5},
        'seed': {'type': 'integer'}, 'output_path': {'type': 'string'},
        'steps': {'type': 'integer', 'default': 50},
        'timeout_seconds': {'type': 'integer', 'default': 1800},
        'resume_prompt_id': {'type': 'string'},
    }}
    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=8000, vram_mb=6000,
                                       disk_mb=100, network_required=False)
    side_effects = ['writes WAV audio and generation provenance']

    def __init__(self):
        self._client = ComfyUIClient(capability='sfx')

    def get_status(self):
        if not self._client.is_available():
            return ToolStatus.UNAVAILABLE
        _, missing = self._client.check_models(_REQUIRED)
        if missing or not self._client.has_node('ConditioningStableAudio'):
            return ToolStatus.DEGRADED
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs):
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.monotonic()
        try:
            duration = float(inputs.get('duration_seconds', 5))
            if not math.isfinite(duration) or not 0 < duration <= 47:
                raise ValueError('SFX duration_seconds must be greater than zero and at most 47.')
            if not str(inputs.get('prompt', '')).strip():
                raise ValueError('A sound-effect prompt is required.')
            dest = Path(inputs['output_path']).expanduser()
            if dest.suffix.lower() != '.wav':
                raise ValueError('SFX output_path must have a .wav extension.')
            if dest.exists():
                raise ValueError(f'Refusing to overwrite existing audio: {dest}')
            if not self._client.is_available():
                return ToolResult(success=False, error=self._client.unavailable_reason())
            _, missing = self._client.check_models(_REQUIRED)
            if missing:
                return ToolResult(success=False, error='Missing local SFX model files; no cloud fallback.',
                                  data=missing_models_payload(missing, workflow_key='stable-audio-open-sfx',
                                                              workflow_name=_WORKFLOW.name))
            seed = inputs.get('seed')
            if seed is None:
                seed = self._client.random_seed()
            graph = self._client.load_workflow(_WORKFLOW)
            graph = self._client.patch_workflow(graph, {
                '3': {'text': inputs['prompt']}, '5': {'seconds_total': duration},
                '6': {'seconds': max(1, duration)},
                '8': {'seed': seed, 'steps': inputs.get('steps', 50)},
                '10': {'filename_prefix': dest.stem},
            })
            prompt = inputs['prompt']
            if inputs.get('resume_prompt_id'):
                entry = self._client.poll(inputs['resume_prompt_id'],
                    timeout=inputs.get('timeout_seconds', 1800), interval=5)
                original = entry.get('prompt')
                if not isinstance(original, list) or len(original) < 3 or not isinstance(original[2], dict):
                    raise ValueError('Resumed SFX history lacks its original workflow; provenance cannot be verified.')
                graph = original[2]
                if graph.get('1', {}).get('inputs', {}).get('ckpt_name') != _REQUIRED[0]:
                    raise ValueError('Resumed prompt is not a Stable Audio Open SFX job.')
                seed = graph['8']['inputs']['seed']
                prompt = graph['3']['inputs']['text']
                duration = float(graph['5']['inputs']['seconds_total'])
                if not math.isfinite(duration) or not 0 < duration <= 47:
                    raise ValueError('Resumed SFX has an invalid duration.')
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='local-sfx-', dir=dest.parent) as tmp:
                paths = self._client.generate(graph, output_node='10', dest=Path(tmp)/'native.flac',
                    timeout=inputs.get('timeout_seconds', 1800), interval=5,
                    resume_prompt_id=inputs.get('resume_prompt_id'))
                subprocess.run(['ffmpeg', '-v', 'error', '-n', '-i', str(paths[0]), '-t', str(duration),
                                '-c:a', 'pcm_s16le', str(dest)], check=True, capture_output=True)
            provenance = {'source': 'bundled', 'workflow': _WORKFLOW.name,
                          'workflow_hash_sha256': workflow_hash(graph),
                          'parameters': {'steps': graph['8']['inputs']['steps'],
                                         'cfg': graph['8']['inputs']['cfg'],
                                         'duration_seconds': duration},
                          'model_stack': model_stack('stable-audio-open-sfx', inputs)}
            return ToolResult(success=True, data={'provider': 'comfyui', 'model': 'stable-audio-open-1.0',
                'prompt': prompt, 'output': str(dest), 'format': 'wav',
                'duration_seconds': ComfyUIMusic._probe_duration(dest), 'workflow_provenance': provenance},
                artifacts=[str(dest)], cost_usd=0, seed=seed, model='stable-audio-open-1.0',
                duration_seconds=round(time.monotonic()-start, 2))
        except ComfyUIError as exc:
            return ToolResult(success=False, error=str(exc),
                              data={'prompt_id': exc.prompt_id} if exc.prompt_id else {})
        except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
            return ToolResult(success=False, error=f'Local SFX generation failed: {exc}')
