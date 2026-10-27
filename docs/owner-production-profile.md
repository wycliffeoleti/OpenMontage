# Owner production profile (this workstation)

Binding defaults for any agent producing videos on this machine. The owner set them on 2026-10-26.
The pipeline rules in `AGENT_GUIDE.md` still apply. This file adds the owner's choices and the local
setup. When the owner asks for something different in a brief, the brief wins.

## Channels and deliverables
The owner posts to monetized channels and **uploads the files manually**. Never post, upload, or schedule anything.

| Platform | Aspect / size | Default length |
|---|---|---|
| YouTube Shorts | 9:16, 1080×1920 | ≤ 60 s |
| TikTok | 9:16, 1080×1920 | ≤ 60 s |
| Instagram Reels | 9:16, 1080×1920 | ≤ 60 s |
| YouTube (long) | 16:9, 1920×1080 | per brief |

- At proposal, ask which platform set the video is for (vertical trio, long-form, or both) unless the brief says.
- Vertical cuts: burned-in captions; keep text and key visuals out of the platform UI zones (roughly the bottom 20% and the right edge).
- Always run the pipeline's `publish` stage (director: `skills/pipelines/<pipeline>/publish-director.md`, tool `export_bundle`).
- The finished package goes in `projects/<id>/renders/`:
  - one MP4 per requested platform;
  - `publish/metadata.md` with a title, description and hashtags per platform;
  - a 1280×720 thumbnail for long YouTube videos.
- Delivery target: H.264 + AAC, integrated loudness about −14 LUFS, true peak ≤ −1 dBTP. Verify on the real output.

## Approvals
Use the manifest gates as written (`human_approval_default`). The owner approves idea/proposal, script, scene plan, assets, and publish. Never pre-authorize a full run on the owner's behalf.

## Narration voice
- **Default: the owner's cloned voice (Ming-3.0-tts, profile `me-narration`)**, served locally at `http://127.0.0.1:17500` (OpenAI-style `POST /v1/audio/speech`, WAV out).
  - Start it: `cd ~/Projects/personal/content/voice-backends && ming-3.0-tts/.venv/bin/python ming_server.py`.
  - Check it: `GET /health`. Free the GPU: `POST /unload`.
  - Refs are biometric. They stay in `/data/projects/personal/content/voice-backends/refs`; never upload them.
- Ming needs short pieces (≤ about 25 words per request, refs ≤ about 15 s). Re-take when words are skipped. Content Creator's `tools/tts_clone.py` shows the proven retake and word-timing logic.
- OpenMontage integration: use `tts_selector` with `preferred_tool: "ming_tts"` and `voice: "me-narration"`. The tool chunks text, verifies words with CPU Whisper, retries at most three takes per chunk, and unloads the GPU model. Set `timestamps: true` for caption timings. Review any `skipped_words` or cleanup warnings; a successful audio export can still need a narration retake.
- Fallback, only with the owner's OK: Piper `en_US-ljspeech-high` / `en_US-norman-medium` (paths in the local tool table). Never `en_US-lessac` (research-only).

## Free, commercial-OK only
The channels are monetized.
- Use only free, local tools whose model weights allow commercial use. Read the license before adding any model.
- Never call a paid API without the owner's explicit OK for that video.
- Non-commercial weights are excluded from production. These include Wav2Lip, SadTalker, CodeFormer/GFPGAN (`face_restore`), OPT-based BLIP-2 (`video_understand` mode `blip2`), FLUX.1/2 [dev], and HunyuanVideo (its license excludes the EU).

## GPU: one engine at a time (RTX 4060, 8 GB)
Only one of Ming, ComfyUI, Wan/diffusers, Blender Cycles, or GPU Whisper should hold the GPU at once. Unload or stop one before starting the next. Ming's built-in word verification uses CPU Whisper. Start servers by hand (no services or autostart) and stop them when done:
- ComfyUI: `bash ~/Projects/open-source/comfyui/run-comfyui.sh` (loopback :8188). Enables `comfyui_music` (ACE-Step 1.5), `comfyui_sfx` (Stable Audio Open) and `comfyui_image` (SD 1.5 custom workflows).
- Ming: see above.

## Local tools set up on this machine
Run Python with `PATH=$PWD/.venv/bin:$HOME/.local/bin:$PATH`; otherwise piper and manim show as unavailable.

| Need | Tool | Notes |
|---|---|---|
| Narration | `ming_tts`, `piper_tts` | Ming registered and real narration verified; Piper requires approval as a substitute |
| Music / SFX | `comfyui_music`, `comfyui_sfx`, `pixabay_music`, `music_library` | ComfyUI must be running for the first two |
| Stock media | `pexels_*`, `pixabay_*`, `corpus_builder` | free keys in `.env` |
| Images | `comfyui_image` (SD 1.5), `local_diffusion` | Default repaired to SDXL base 1.0, fp16 with CPU offload. SDXL preload/real inference acceptance is pending; see continuation evidence |
| Local video gen | `wan_video` (Wan 2.1 T2V 1.3B, Apache-2.0) | Download/real inference acceptance pending. Set configured model/path only after smoke success; provider statuses then exclude other families |
| Composition | Remotion, HyperFrames, FFmpeg | present both runtimes at proposal (AGENT_GUIDE hard rule) |
| Math / diagrams | `math_animate` (Manim + LaTeX), `diagram_gen` | |
| 3D | `blender_world` (Blender 4.5 LTS), `threejs_world` | |
| Cleanup | `bg_remove`, `upscale` (spandrel), `face_tracker`, `eye_enhance`, `color_grade`, `audio_enhance` | |
| Transcripts | `transcriber` (faster-whisper) | Optional `WHISPER_CUDA12_ROOT` isolates CUDA12 in a child process; retains CPU fallback. See continuation evidence for real CUDA acceptance |

The setup status, remaining items and evidence are in
`/data/projects/personal/content/OpenMontage/smoke-tests/2026-10-26/HANDOFF.md`.
Free/local audio details: `docs/local-audio.md`.

## Setup continuation
`docs/local-tool-setup.md` records the current implementation, queued downloads,
and remaining owner prerequisites. Do not infer model readiness from installed
Python packages: check the real inference reports under the dated smoke folder.
