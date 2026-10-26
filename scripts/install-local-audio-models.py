"""Download pinned publisher files, verify SHA256, then hard-link into ComfyUI."""
import hashlib
import json
import os
from pathlib import Path

os.environ['HF_HUB_DISABLE_XET'] = '0'
os.environ['HF_XET_HIGH_PERFORMANCE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
from huggingface_hub import HfApi, hf_hub_download

ROOT = Path('/data/projects/open-source/comfyui')
OUT = ROOT / 'artifacts/audio-setup-2026-10-26'
SPECS = [
    ('Comfy-Org/ACE-Step-1.5', '6707deb277e9e0907fd9c14ce6b6f1d695c6a3fc', [
        ('split_files/diffusion_models/acestep_v1.5_turbo.safetensors', 'diffusion_models/acestep_v1.5_turbo.safetensors'),
        ('split_files/text_encoders/qwen_0.6b_ace15.safetensors', 'text_encoders/qwen_0.6b_ace15.safetensors'),
        ('split_files/text_encoders/qwen_1.7b_ace15.safetensors', 'text_encoders/qwen_1.7b_ace15.safetensors'),
        ('split_files/vae/ace_1.5_vae.safetensors', 'vae/ace_1.5_vae.safetensors'),
    ]),
    ('google-t5/t5-base', 'a9723ea7f1b39c1eae772870f3b547bf6ef7e6c1', [
        ('model.safetensors', 'text_encoders/t5_base.safetensors'),
    ]),
    ('stabilityai/stable-audio-open-1.0', 'f21265c1e2710b3bd2386596943f0007f55f802e', [
        ('model.safetensors', 'checkpoints/stable_audio_open_1.0.safetensors'),
    ]),
]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    api = HfApi()
    for repo, revision, files in SPECS:
        info = api.model_info(repo, revision=revision, files_metadata=True)
        metadata = {item.rfilename: item for item in info.siblings}
        for filename, dest_name in files:
            item = metadata[filename]
            expected = item.lfs.sha256
            dest = ROOT / 'models' / dest_name
            try:
                print(f'Downloading {repo}/{filename} ({item.size:,} bytes)', flush=True)
                cached = Path(hf_hub_download(repo, filename, revision=revision,
                    cache_dir=ROOT / 'cache/huggingface/hub'))
                actual = digest(cached)
                if cached.stat().st_size != item.size or actual != expected:
                    raise RuntimeError(f'Integrity verification failed: {filename}')
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    if digest(dest) != expected:
                        raise RuntimeError(f'Refusing to overwrite different existing file: {dest}')
                else:
                    os.link(cached.resolve(), dest)
                record = {'repo': repo, 'revision': revision, 'source_file': filename,
                          'path': str(dest), 'size_bytes': item.size, 'sha256': actual,
                          'status': 'verified'}
                print(f'Verified {dest.name}', flush=True)
            except Exception as exc:
                record = {'repo': repo, 'revision': revision, 'source_file': filename,
                          'path': str(dest), 'status': 'blocked', 'error_type': type(exc).__name__}
                print(f'Blocked {filename}: {type(exc).__name__}', flush=True)
            manifest.append(record)
            (OUT / 'models.json').write_text(json.dumps(manifest, indent=2) + '\n')
        # Retain model cards and licenses beside the install provenance.
        for name in ['README.md', 'LICENSE', 'LICENSE.md', 'LICENSE.txt']:
            if name in metadata:
                try:
                    p = Path(hf_hub_download(repo, name, revision=revision,
                        cache_dir=ROOT / 'cache/huggingface/hub'))
                    target = OUT / repo.replace('/', '--') / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(p.read_bytes())
                except Exception as exc:
                    print(f'Model documentation unavailable: {repo}/{name}: {type(exc).__name__}', flush=True)
    print(json.dumps({'verified': sum(x['status'] == 'verified' for x in manifest),
                      'blocked': sum(x['status'] == 'blocked' for x in manifest)}), flush=True)


if __name__ == '__main__':
    main()
