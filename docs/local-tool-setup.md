# Local tool setup continuation — 2026-10-26

Continue on `feat/local-tool-compat`; no commit, merge or push is authorized yet.
Original handoff and retained smoke evidence:
`/data/projects/personal/content/OpenMontage/smoke-tests/2026-10-26/`.

## Verified now
- MediaPipe Tasks detector found faces in 16/16 sampled frames; landmarker enhanced 77/77 frames. Outputs are `face-tracks-mediapipe.json` and `eye-enhance-mediapipe.mp4`. Original evidence was preserved.
- Spandrel and MediaPipe compatibility tests pass, including an encoded control for video pixel drift and a direct spatial-isolation check.
- `ming_tts` is registry-discovered and served by the owner's existing local Ming server. Real sample: `ming-narration.wav`, 18 recognized words, 5.9 seconds, one take, no omissions; result/timings alongside it. GPU model unloaded afterward. Human listening is still the perceptual quality check.
- `local_diffusion` now uses SDXL Base 1.0 with an automatic SD/SDXL loader, fp16 model files and CUDA CPU offload. Real SDXL readiness depends on the queued download/smoke, not this code change.
- Wan honors explicit `model_variant`, then `VIDEO_GEN_LOCAL_MODEL`, then its historical default. Discovery, estimation and execution use the same configured default. With a configured model, only its local-video provider family is advertised; an unset model retains upstream flag-only behavior.

## Model download continuation
Claude's existing detached Wan downloader is preserved. Do not start a second
copy. Progress is in `wan-download.log`; completion requires `DOWNLOAD COMPLETE`.

Overnight internet outages: the continuation monitors preserve active transfers
and cached files. If a transfer exits with a transient network error, they wait
60 seconds and retry without an attempt limit. This includes resuming the
original Wan command after its own eight attempts run out, CUDA wheel downloads,
and subsequent SDXL/CLIP downloads and metadata requests. Authentication,
permission, storage and inference errors still stop and are logged. These are
detached one-shot jobs, not services: keep the PC awake and powered on; a reboot
requires starting the jobs again. Completed files are reused; an unfinished wheel
may need transferring again. No automatic startup or Git operations are added.

`scripts/setup_local_models.py --wan-pid <existing-hf-pid>` observes that download,
then prepares Wan, SDXL and CLIP serially. Its output is retained in
`continuation/setup-downloads.log`. It uses pinned revisions, verifies all files
listed by the selected repository manifest, rejects broken weight links, and
checksum-copies models into registered `/data/shared/models` paths. Original
caches remain intact. Conflicting destination files are retained and reported.

The runner tests each inference path in a separate process and refuses inference
while another Python/Blender engine holds GPU memory. Configuration is trialed
only in the child process and saved to `.env` after success. Inspect
`continuation/{wan,sdxl,clip}-result.json` and `setup-result.json`; absent reports
mean pending, not passed. Failures require investigation before retrying the
same model. Never substitute a provider or model silently.

Pinned revisions:
- Wan: `0fad780a534b6463e45facd96134c9f345acfa5b` (Apache-2.0).
- SDXL: `462165984030d82259a11f4367a4eed129e94a7b` ([Open RAIL++-M](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/462165984030d82259a11f4367a4eed129e94a7b/LICENSE.md), including use restrictions).
- CLIP: `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268` ([MIT](https://github.com/openai/CLIP/blob/main/LICENSE)).

## Whisper runtime
Pinned CUDA12 wheels use a separate installation target, `.venv/whisper-cuda12`:
`nvidia-cublas-cu12==12.4.5.8`, `nvidia-cudnn-cu12==9.1.0.70`.
Installation/real GPU acceptance status is recorded in the continuation evidence;
do not enable `WHISPER_CUDA12_ROOT` until its CUDA smoke succeeds. The existing
CUDA13 PyTorch environment stays intact. No global `LD_LIBRARY_PATH` is added.
The configured transcriber child receives only these private library paths;
native child failure retries with CPU and returns the GPU fallback reason.
The one-shot `--finish-whisper --runtime-pid <existing-uv-pid>` runner waits for
that installation and saves `WHISPER_CUDA12_ROOT` only after real CUDA
transcription succeeds. Its log is `continuation/whisper-setup.log` and its
acceptance report is `continuation/whisper-result.json`.

## Remaining owner prerequisites
- AnimatedDrawings source is pinned at `b859684857519c7424da51a0b0862fbd1fd258f4` under `~/Projects/open-source/animated-drawings`. Python 3.8 environment/data live under `/data/projects/open-source/animated-drawings`; code and weights are [MIT](https://github.com/facebookresearch/AnimatedDrawings#trained-model-weights). Docker/group access requires the owner. Auto-rig must use a fresh local drawing, not ship bundled example characters.
- Its renderer dependency/context verification passed: 37 compatible packages and a real OSMesa/llvmpipe OpenGL 4.5 context produced the expected pixels. Evidence: `artifacts/setup-2026-10-26/environment-result.json` in that data project. Ubuntu OSMesa was checksum-retained and extracted into `native-libs/` locally; no system package or global loader setting was changed. Headless rendering must set `view.USE_MESA: true` and pass `native-libs/usr/lib/x86_64-linux-gnu` through that child process's `LD_LIBRARY_PATH`; the upstream example defaults to a GLFW window.
- `UNSPLASH_ACCESS_KEY` has an empty entry in this checkout. Add an existing free key locally if desired; never put credentials in a handoff or test output. Videvo remains unverified.
- The final production acceptance short needs an owner brief and normal idea/script/scene/assets/publish approvals. Present both Remotion and HyperFrames; use Ming and local music/SFX; produce local platform bundles for manual upload. Setup approval is not full-run production pre-authorization.
