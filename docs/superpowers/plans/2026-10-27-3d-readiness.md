# HyperFrames/Three.js and Manim readiness

User approved this plan on 2026-10-27 with “Implement the plan”. Work in the
current checkout; preserve unrelated changes. No commits, merges or pushes.
The separate Remotion/Three.js explainer remains deferred.

## Global constraints

Free local tools, commercially usable dependencies, one GPU engine at a time.
Keep small smoke outputs in `projects/3d-readiness/` because `/data` is read-only
in this session. Diagnostic fixtures are setup checks, not a new production.
Do not install Docker or duplicate audio engines.

## Review focus

- Explicit CLI paths must fail clearly when broken, without fetching another CLI.
- Availability checks and renders must use the same configured executable.
- Generated worlds must load their complete module graph without CDN requests.
- Missing optional HyperFrames audio/Docker dependencies must remain optional.
- Readiness reports must not claim a failed, static or blank render passed.

### Task 1: Pinned local runtime and offline world dependencies

Add `hyperframes-runtime/` with locked HyperFrames 0.8.206, Three.js 0.181.2,
GSAP 3.14.2. Support `HYPERFRAMES_CLI_PATH` consistently in the HyperFrames
tool while preserving legacy behavior when unset. Stage local Three.js,
GLTFLoader, GSAP and license files into each world workspace. Check versions
and report missing dependencies before writing a workspace.

Write regressions first: configured CLI execution without npm/npx, broken paths,
complete local world resources, and missing-dependency errors. Preserve production
fidelity guards. Run the relevant HyperFrames, Three.js and Manim tool tests.
Expected: passing targeted tests; a generated world uses local imports only.

### Task 2: Repeatable setup, readiness and smoke commands

Add `make 3d-setup`, `make 3d-check`, `make 3d-smoke`. Setup installs only missing
pinned packages, preserves the working Manim 0.22.0 environment, configures the
CLI and existing optimized browser, and preserves unrelated `.env` settings.
Check does not install or render; it reports versions, readiness and actionable
blockers. Smoke builds a four-second world blockout through HyperFrames and a
three-second Manim ThreeDScene with camera movement and MathTex.

Verify the world in a browser with external requests blocked. Decode complete
videos; check dimensions, duration, frame rate and motion, retain sample frames
and machine-readable reports. Write meaningful tests for configuration updates,
required-vs-optional health checks and failed-output detection.
Expected: both routes pass real smoke checks; artifacts are retained locally.

### Task 3: Future routing, regression verification and review

Document commands and verified state. Update existing animation runtime guidance
to recommend HyperFrames for environments/fly-throughs and Manim for mathematical
diagrams, preserving per-video approvals and production fidelity requirements.
Run the focused tests and repository suite, inspect real smoke frames, then request
one independent review of this task's changes. Fix material findings with regression
tests. No Git integration action is authorized.
Expected: repeatable checks, verified artifacts, accurate handoff documentation.
