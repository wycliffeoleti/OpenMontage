"""Generate music or effects through the local registry, with no paid fallback."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description='Free local music and SFX via ComfyUI')
    parser.add_argument('kind', choices=['music', 'sfx'])
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--duration-seconds', type=float, default=30)
    parser.add_argument('--output-path', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--model-profile')
    parser.add_argument('--bpm', type=int, help='Explicit ACE-Step 1.5 music tempo; match the prompt.')
    parser.add_argument('--text-encoder-device', choices=['default','cpu'],
                        help='Native GPU placement or CPU encoding for more VRAM headroom.')
    parser.add_argument('--steps', type=int)
    parser.add_argument('--timeout-seconds', type=int, default=1800)
    parser.add_argument('--resume-prompt-id')
    args = parser.parse_args(argv)
    from tools.tool_registry import registry
    registry.discover()
    tool = registry.get('comfyui_music' if args.kind == 'music' else 'comfyui_sfx')
    path = args.output_path.expanduser().resolve()
    if path.exists() or path.with_suffix(path.suffix+'.json').exists():
        parser.error(f'Output or provenance already exists: {path}')
    if args.kind == 'music' and path.suffix.lower() != '.mp3':
        parser.error('Music output must have a .mp3 extension.')
    inputs = {'prompt': args.prompt, 'duration_seconds': args.duration_seconds,
              'output_path': str(path), 'seed': args.seed, 'timeout_seconds': args.timeout_seconds}
    for key in ['steps', 'model_profile', 'resume_prompt_id', 'bpm', 'text_encoder_device']:
        value = getattr(args, key)
        if value is not None:
            inputs[key] = value
    result = tool.execute(inputs)
    if not result.success:
        print(json.dumps({'success': False, 'error': result.error, 'data': result.data}, indent=2))
        raise SystemExit(1)
    metadata = {**result.data, 'seed': result.seed, 'cost_usd': result.cost_usd,
                'execution_seconds': result.duration_seconds,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    path.with_suffix(path.suffix+'.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
