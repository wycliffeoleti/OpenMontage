# Local tool setup implementation plan

Goal: finish the approved local, commercially usable OpenMontage setup and validate a post-ready short through the normal approval gates.

Spec: `/data/projects/personal/content/OpenMontage/smoke-tests/2026-10-26/HANDOFF.md`, plus the approved continuation plan in this conversation.

Global constraints: free/local only; 8 GB RTX 4060; uv-managed .venv; one OpenCV package <5; one GPU engine at a time; manual loopback servers; immutable original evidence and voice references; registered /data paths. No commit, merge or push without owner approval. Continue on the existing dirty feat/local-tool-compat branch as approved.

Review focus: narration omissions and chunk timestamp offsets; HTTP failures and GPU cleanup; cross-provider video defaults; CUDA12/CUDA13 isolation; model/download provenance and incomplete snapshots.

### Task 1: Complete interrupted compatibility work
- Correct the encoded-pixel assertion using a no-enhancement encoding control and add an in-memory isolation assertion.
- Verify MediaPipe/spandrel/MPS focused tests and run real face models on the retained face clip, producing new evidence paths.

### Task 2: Ming TTS
- Create tools/audio/ming_tts.py and focused HTTP-fixture tests. Reuse a self-contained helper for script alignment/skipped-word checks.
- Inputs: text, voice/voice_id, output_path, output_format, timestamps. Defaults: loopback MING_TTS_URL, MING_TTS_VOICE=me-narration; max 25 words/chunk, three total takes/chunk, CPU large-v3-turbo verification.
- Outputs: normal ToolResult audio artifact, provider/model metadata, retake/omission diagnostics, optional word timestamps in seconds and timing artifact. Unload in finally; no provider fallback.
- Health determines status; registry auto-discovers. Real two-sentence smoke test.

### Task 3: Local-video routing
- Test explicit variant > VIDEO_GEN_LOCAL_MODEL > existing default for Wan; share resolution across schema metadata, estimates and execute.
- When a model is configured, local-generation status only enables its provider family; preserve legacy flag-only behavior with no configured model.
- Add optional configured local snapshot loading; validate completed Wan snapshot before enabling. Smoke 832x480, 17 frames, small step count.

### Task 4: SDXL and remaining local runtime setup
- Test and replace local_diffusion default with SDXL base 1.0; use AutoPipelineForText2Image, CUDA fp16 CPU offload, CPU float32; preserve explicit older models. Smoke 1024x1024 after Wan download.
- Isolate CUDA12 Whisper dependencies in a dedicated target and subprocess environment, retaining CPU fallback/output contract. Tests and real CUDA smoke.
- Validate CLIP cache and retrieve missing files; check existing Unsplash key without printing it.
- Prepare AnimatedDrawings isolated source/environment/data and licenses; owner installs Docker and grants access. Auto-rig a fresh local drawing after that prerequisite.

### Task 5: Evidence and acceptance
- Full pytest, uv pip check, diff checks and capability comparison; retain logs and update owner profile/handoff with actual results.
- Follow animated-explainer for an owner-specified short, presenting both runtimes, using Ming/local music and respecting every approval gate. Export local files only.
- Independent final code review; fix important findings with regression tests; show diff and request commit/merge/push approval only after reviewable work is ready.
