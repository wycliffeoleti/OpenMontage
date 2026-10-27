# Local 3D workflows

The main OpenMontage checkout is prepared for these two routes:

| Content | Route | Notes |
|---|---|---|
| Terrain, environments, camera fly-throughs | `threejs_world` → `hyperframes_compose` | Editable world specification; local browser libraries; explicit blockout/production quality tiers |
| Mathematical and scientific diagrams | `math_animate` → Manim `ThreeDScene` | Geometry, formulas and camera animation; the OpenMontage wrapper remains experimental |

Choose the route from the video's explanation and visual needs at proposal time.
Present available composition runtimes and retain normal approval gates. A Manim
clip is an asset for the selected composition runtime; it does not replace the
runtime choice. Neither route guarantees the explanation is scientifically correct.

The custom Remotion/Three.js explainer remains in its separate worktree. This
setup does not integrate it or change existing Remotion dependencies.

## Commands

Run from the OpenMontage repository root:

```bash
make 3d-setup
make 3d-check
make 3d-smoke
```

`3d-setup` installs missing locked JavaScript packages, installs Manim 0.22.0 only
if absent, and configures the local HyperFrames CLI and an existing optimized
headless browser. It preserves unrelated `.env` settings. System dependencies
such as LaTeX, Cairo/Pango and FFmpeg must already be installed; missing ones are
reported, never installed through sudo. Existing packages are not broadly upgraded.

`3d-check` installs nothing and renders nothing. It checks the local libraries,
the actual HyperFrames CLI's required visual dependencies, the pinned Manim
version, `math_animate`'s own availability, and the LaTeX, dvisvgm and FFmpeg
executables. It runs under your current `PATH`, so a ready result matches what
pipeline agents see; `math_animate` uses the venv's Manim module when `manim`
is not on `PATH`. LaTeX compilation itself is proven by `3d-smoke`'s MathTex
render. It exits nonzero when a route is blocked. Docker and HyperFrames' optional speech,
transcription and music backends are not required for either visual workflow.

`3d-smoke` uses software browser rendering by default, leaves the GPU free, and
retains its small outputs under `projects/3d-readiness/`. It exercises a four-second
world blockout and a three-second Manim sphere/axes/formula scene. It blocks
external requests during the browser world check, checks real camera movement and
pixel-identical repeated seeks, fully decodes both MP4s, checks their timing and
frame counts, detects blank/static output, and writes representative PNG frames.
The report is `projects/3d-readiness/smoke-report.json`.

For machine-readable output or a separate diagnostic directory:

```bash
.venv/bin/python scripts/setup_3d_tools.py --check --json
.venv/bin/python scripts/setup_3d_tools.py --smoke --json --output projects/my-3d-check
```

The script uses the repository `.venv` and executable paths. It performs targeted
tool discovery so unrelated provider health probes cannot delay a 3D check.

## Runtime and assets

The lockfile in `hyperframes-runtime/` pins HyperFrames 0.8.206, Three.js 0.181.2
and GSAP 3.14.2. `HYPERFRAMES_CLI_PATH` selects that CLI for both availability
checks and execution; a broken explicit path blocks the workflow instead of
fetching a substitute. Unconfigured installations retain their existing npx path.
`HYPERFRAMES_BROWSER_PATH` selects the installed Chrome headless shell.

World builds copy their JavaScript module graph and original license notices into
`vendor/`, with dependency versions and file hashes in `vendor/manifest.json`.
GLTFLoader and its helper use the same local Three.js version. Custom fonts and
production models/textures must also be supplied locally for a self-contained
production; HyperFrames may otherwise auto-localize named fonts into its cache.

The smoke world is intentionally a **blockout**, not a production environment.
Detailed worlds still need licensed catalogs, materials and the existing production
fidelity review. No asset-generation API, Docker installation or duplicate audio
engine is added by these commands.

## Verified on 2026-10-27

Node.js 24.20.0, Manim 0.22.0, LaTeX/dvisvgm, FFmpeg/FFprobe and the existing
Puppeteer Chrome headless shell passed the required checks. Real smoke outputs:

- HyperFrames/Three.js: 4 seconds, 854×480, 15 fps, 60 frames; full decode and offline browser checks passed.
- Manim: 3 seconds, 854×480, 15 fps, 45 frames; full decode, MathTex and visible motion passed.

Both are silent diagnostic clips. Normal videos retain the owner's music, sound
design and narration requirements. Setup approval does not pre-authorize video
production or publication. No commit, merge or push was performed.

Final regression verification: 2,318 tests passed, 11 skipped and 3 expected
failures. Independent reviews found a readiness-check installation issue and a
check that passed only with `.venv/bin` on `PATH`. Both have regression tests.
`3d-check` and `3d-smoke` now pass from a shell without `.venv/bin` on `PATH`.
