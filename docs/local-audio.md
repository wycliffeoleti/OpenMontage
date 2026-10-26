# Free local music and sound effects

This workstation uses the existing local ComfyUI installation for ACE-Step 1.5
Turbo music and Stable Audio Open 1.0 sound effects. The tools do not call paid
generation services. GPU use, electricity, disk space, and initial downloads are local.

## Installation state

The code, native workflows, local configuration, CLI, and Content Creator imports
are installed. All six model files completed publisher-checksum verification.
Host CUDA calculation, real 30-second music generation, and local Stable Audio
Open sound-effect generation passed on the RTX 4060 (8188 MiB).

The first SFX acceptance sample used the normal offline CLI with a three-second
airy-whoosh prompt, seed 202, and the bundled 50-step workflow. It completed in
5.09 seconds and produced 2.972 seconds of 44.1 kHz stereo PCM WAV. Full decoding,
finite/non-silent samples, no full-scale clipping, and provenance checksum checks
passed; reported API cost was $0. The sample is
`/data/projects/personal/content/OpenMontage/sound-effects/local-whoosh-smoke-2026-10-26.wav`.
Its technical acceptance report is `sfx-first-validation.json` in the setup
artifacts directory below. Human listening remains the quality check.

Observed samples: CPU text encoding took 210.19 seconds with 5300 MiB peak whole-device
VRAM. Native automatic GPU encoding took 20.05 seconds with 7438 MiB peak whole-device
VRAM. These are individual local samples, not a general performance guarantee; the
comparison used different prompts/seeds and a warm model cache. Outputs decoded as
30.024-second, non-silent audio. Human listening remains the quality check.

Weights live under `/data/projects/open-source/comfyui/models`, using the existing
ComfyUI environment. Exact pinned source revisions, hashes, license files, and
download status are recorded in
`/data/projects/open-source/comfyui/artifacts/audio-setup-2026-10-26/`.

Stable Audio Open requires a free Hugging Face account and model-access acceptance:
<https://huggingface.co/stabilityai/stable-audio-open-1.0>.
Its commercial use follows the applicable Stability license, including the
creator revenue threshold you accepted: <https://stability.ai/license>.
Keep authentication tokens out of chat, Git, and logs. The local login command is:

```bash
/data/projects/open-source/comfyui/environments/comfyui-py313/bin/hf auth login
```

The installer can be rerun after login. Verified downloads are reused, different
existing model files are never overwritten, and incomplete downloads are retained:

```bash
env -u LD_LIBRARY_PATH /data/projects/open-source/comfyui/environments/comfyui-py313/bin/python \
  /home/mooncactuspc/Projects/personal/content/OpenMontage/scripts/install-local-audio-models.py
```

## Start, generate, and stop

Start the foreground server in one terminal:

```bash
bash /home/mooncactuspc/Projects/open-source/comfyui/run-comfyui.sh
```

It binds only `127.0.0.1:8188`, disables paid partner and custom nodes, and does not
start at boot. Stop with Ctrl-C. Do not launch `source/main.py` directly: the
existing launcher isolates incompatible inherited CUDA library paths.

In a second terminal:

```bash
cd /home/mooncactuspc/Projects/personal/content/OpenMontage
.venv/bin/python -m tools.audio.local_audio music \
  --prompt "instrumental ambient electronic, 90 BPM, soft piano, calm background, no vocals" \
  --duration-seconds 30 --bpm 90 --seed 123 \
  --output-path /data/projects/personal/content/OpenMontage/music-library/calm-piano.mp3

.venv/bin/python -m tools.audio.local_audio sfx \
  --prompt "A short clean airy whoosh, a single fast movement, no music or speech" \
  --duration-seconds 2 --seed 123 \
  --output-path /data/projects/personal/content/OpenMontage/sound-effects/airy-whoosh.wav
```

The CLI refuses existing output/provenance files. Each successful output gets an
adjacent JSON file containing the prompt, seed, workflow hash, model stack, duration,
execution time, output checksum, and zero API cost. Music is MP3; SFX is real PCM WAV
converted from the native FLAC saver. SFX supports positive durations up to 47 seconds.
Use one GPU generation job at a time and batch size one on this 8 GB GPU.
The workstation sets `COMFYUI_MUSIC_TEXT_ENCODER_DEVICE=default` for the tested
native automatic GPU path. For more VRAM headroom, add `--text-encoder-device cpu`;
this uses the verified slower CPU-encoding path. An explicit device input wins over
the workstation setting; unset configuration keeps the portable CPU default.
The current upstream standalone GPU guide recommends a 0.6B LM at 8 GB:
<https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/GPU_COMPATIBILITY.md>.
That standalone configuration is not the same as ComfyUI’s split encoder stack.

The workstation music default is `COMFYUI_MUSIC_PROFILE=ace-step-1.5-turbo` in the
existing OpenMontage `.env`. An explicit tool `model_profile` wins over that setting. Empty lyrics in the 1.5
profile use the official `[Instrumental]` marker; use `--bpm` to match the structured
tempo to the prompt.
Without either, the historical v1 default remains. The server must be running and
the active stack must be installed for registry status to show available.

## Content Creator imports

Both the builder CLI and Studio build entry accept `--music-file PATH` and
`--sfx-cues PATH`, also with `--reuse-story`. Each file option conflicts with its
corresponding `--music` or `--sfx` preset. Other existing defaults remain.

A cue sheet is a JSON array; relative audio paths resolve beside the sheet:

```json
[
  {"path": "airy-whoosh.wav", "at_seconds": 1.25},
  {"path": "soft-click.wav", "at_seconds": 4.0}
]
```

For example, add these options to a normal story build or reuse command:

```text
--music-file /data/projects/personal/content/OpenMontage/music-library/calm-piano.mp3
--sfx-cues /path/to/audio-cues.json
```

Inputs are decoded and checked, then copied/transcoded into the new story staging
directory. Saved `story_props.json` and `audio-cue-sheet.json` retain the selected
sources, checksums, and cue timings. A custom music file restores the standard story
mix envelope if reused props do not have one. Cues must start inside the video;
effect tails are limited by the existing final-video mix duration.

OpenMontage's animation, animated-explainer, and cinematic asset stages expose both
local tools. Missing access, weights, nodes, or a stopped server are explicit errors;
they do not authorize a paid fallback.
