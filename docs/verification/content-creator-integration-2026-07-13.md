# Content Creator integration verification — 2026-07-13

## Verdict

The isolated branch `production/content-creator-integration-20260713` now contains a private-production Content Creator overlay reconstructed from the exact verified upstream baseline `f8d94632ea9bd0057da31904acca1cefecf005dd`.

The implementation is technically ready for Clicky/Wicky visual review. It is **not approved for production switching**: no production checkout, Content Creator file, service, timer, credential, remote, public fork, or GitHub resource was modified, and nothing was pushed or published.

Automated acceptance gates passed:

- Content Creator contract tests: 12 deterministic unit tests plus 2 live producer-contract tests.
- TypeScript: `tsc --noEmit` passes with zero errors (upstream had 15; the integrated historical tree had 18).
- Remotion: both stable IDs enumerate and all required still/motion renders complete.
- OpenMontage: lint passes; full suite is 850 passed, 9 skipped, 1 subtest passed.
- Content Creator read-only registry suite: 9 passed.
- Playwright: 1.61.x used matching Chromium/headless-shell revision 1228.

Motion, audio balance, attribution readability, and aesthetic quality remain human judgments assigned to Clicky/Wicky. No automated result is presented as aesthetic superiority.

## Scope and architecture

The integration is explicitly owned and versioned under:

`remotion-composer/src/integrations/content-creator/v1/`

Version: `1.0.0`.

Stable composition IDs:

- `ExplainerStory` — 1080x1920, 60fps, three-band story renderer.
- `ExplainerVertical` — 1080x1920, 30fps, restricted to an explicit portrait allowlist.

Validated portrait cut allowlist:

- `hero_title`
- `callout`
- `terminal_scene`

Unsupported portrait cut types fail metadata/runtime contract validation before rendering. The integration is registered through `ContentCreatorCompositions.tsx`; consumer-specific scene contracts are not presented as generic upstream OpenMontage core.

Upstream notices and the repository's AGPL-3.0 license remain intact.

## Preserved producer behavior

The overlay preserves:

- final static beat images with opacity-only crossfades and no Ken Burns zoom/drift;
- fixed four-word caption pages and active-word highlighting;
- the animated SVG host fallback and optional presenter media seam;
- narration/music layers, music swell fields, outro padding, and full-frame `outroText`;
- per-beat attribution and credit carry-forward when a beat inherits prior media;
- the Content Creator `StoryScenes` vocabulary: kinetic text, icon, network, chat, comparison, stat, diagram, staged, and bounded chart scenes.

## Audited defects closed

1. POSIX absolute paths now use `file://` plus the leading POSIX slash, producing exactly `file:///path`; spaces are URI-encoded.
2. Empty charts fail validation before Remotion rendering.
3. Chart inputs are bounded to 1–64 points; labels are non-empty and at most 80 characters; values must be finite.
4. All 18 historical TypeScript errors are gone, including the three custom `ExplainerStory`/Root generic errors.
5. Presenter media detection parses the URL pathname, so `.mp4?token=...#fragment` remains video.
6. Poppins requests are constrained to Latin and the five weights actually used instead of requesting the whole family.
7. Portrait cuts are allowlisted; unsupported types fail rather than silently rendering poorly.
8. `hero_title`, `callout`, and `terminal_scene` derive width, type scale, and padding from the active 1080x1920 video configuration.
9. The existing upstream `ProviderChip` pointer-events type defect and composition prop generic errors were corrected so the canonical typecheck is clean.

## Ordered commits

Starting point: `f8d94632ea9bd0057da31904acca1cefecf005dd`.

1. `57017c53e5e72a2c4e1bf445fef7820cf124c9b6` — `feat(content-creator): add versioned integration contracts`
2. `df06feb619920381475c4f030393d8d93346bf4b` — `feat(content-creator): add story renderer overlay`
3. `bb4ef0ec7918703f96afc069b70d1d2792ce7267` — `feat(content-creator): register compatible portrait compositions`
4. `079e6554b3f6594432d0f4afa0f86301c154ffd2` — `fix(content-creator): close audited rendering defects`
5. `b15430a8aac17d29a731ecb86739e29a733304ba` — `test(content-creator): verify live producer contracts`

Tests are co-located with their vertical TDD slices; each production behavior was introduced after a red-capable test or composition/typecheck loop.

## Exact verification

### Content Creator integration unit tests

```bash
cd remotion-composer
npm run test:content-creator
```

Result: pass — 12 passed, 0 failed.

Covered: valid story props, empty charts, chart bounds/finite values/labels, portrait allowlist acceptance/rejection, POSIX assets, presenter URL query/fragment handling, carried attribution, scene non-inheritance, and portrait layout values.

### Actual producer contracts, read-only

Vertical props were emitted by Content Creator's real `_assemble_props()` into the ignored verification directory. Story props were read from Content Creator's existing real popcorn output fixture.

```bash
CONTENT_CREATOR_STORY_PROPS=/home/wolnxpc/projects/Personal/automations/OpenMontage/remotion-composer/public/aitips/why-popcorn-pops/story_props.json \
CONTENT_CREATOR_VERTICAL_PROPS=/home/wolnxpc/projects/Personal/automations/OpenMontage/.worktrees/t_9f5efcba/projects/content-creator-integration-verification/metadata/actual-vertical-props.json \
NODE_NO_WARNINGS=1 node --experimental-strip-types --test tests/content-creator-live-contract.test.ts
```

Result: pass — 2 passed, 0 failed.

### TypeScript

```bash
cd remotion-composer
npm run typecheck
```

Result: pass — zero TypeScript errors.

### Remotion composition enumeration

```bash
cd remotion-composer
npx remotion compositions src/index.tsx
```

Result: pass. `ExplainerVertical` enumerates at 1080x1920/30fps and `ExplainerStory` at 1080x1920/60fps. Two `/public/` 404 console warnings are reproduced unchanged on a clean upstream `f8d9463` archive; targeted integration renders have no missing-asset failures.

### OpenMontage lint

```bash
make VENV_DIR=/home/wolnxpc/projects/Personal/automations/OpenMontage/.venv lint
```

Result: pass.

### Matching Playwright runtime

```bash
PLAYWRIGHT_BROWSERS_PATH=/home/wolnxpc/.cache/ms-playwright \
/home/wolnxpc/projects/Personal/automations/OpenMontage/.venv/bin/python -m playwright install --list
```

Result: Playwright 1.61.x with Chromium 1228, Chromium headless-shell 1228, and FFmpeg 1011 available.

### Full OpenMontage suite

```bash
PYTHONDONTWRITEBYTECODE=1 \
PLAYWRIGHT_BROWSERS_PATH=/home/wolnxpc/.cache/ms-playwright \
make VENV_DIR=/home/wolnxpc/projects/Personal/automations/OpenMontage/.venv test
```

Result: pass — 850 passed, 9 skipped, 50 existing deprecation warnings, 1 subtest passed in 43.38s. Both Backlot browser tests passed.

The suite rewrote tracked `diagram.png`; that known test side effect was restored immediately to the upstream content. Final Git status was clean before writing this report.

### Content Creator registry, read-only

```bash
PYTHONDONTWRITEBYTECODE=1 \
/home/wolnxpc/projects/Personal/automations/content_creator/.venv/bin/python \
-m pytest -p no:cacheprovider tests/test_registry.py -v
```

Result: pass — 9 passed in 0.02s.

### Real deterministic renders

Representative stills:

```bash
npx remotion still src/index.tsx ExplainerStory <output.png> --frame=<45|75|180|210|300|420> --props=tests/fixtures/content-creator-story.json --image-format=png
npx remotion still src/index.tsx ExplainerVertical <output.png> --frame=<30|45> --props=tests/fixtures/portrait-<cut>.json --image-format=png
```

Result: all required story stills and all three allowlisted portrait samples rendered at 1080x1920.

Short motion render:

```bash
npx remotion render src/index.tsx ExplainerStory \
  ../projects/content-creator-integration-verification/motion/story-motion.mp4 \
  --props=../projects/content-creator-integration-verification/metadata/render-props.json \
  --codec=h264 --crf=23 --concurrency=2
```

Result: pass — H.264/AAC, 1080x1920, 60fps, 474 video frames, approximately 7.9 seconds, 1,133,513 bytes.

Static-image verification cropped the top story band from frames 45 and 75 and hashed raw RGB pixels. Both hashes are identical:

`1080568abece27f601cab3ebd1e3723787c01cea2de5055d654578daca352c02`

This proves the beat image itself does not zoom or drift between those frames; the lower caption/host animation is intentionally excluded from the crop.

## Preserved verification artifacts

Root:

`/home/wolnxpc/projects/Personal/automations/OpenMontage/.worktrees/t_9f5efcba/projects/content-creator-integration-verification`

Key files:

- `contact-sheet.png`
- `motion/story-motion.mp4`
- `stills/story-static-a.png`
- `stills/story-static-b.png`
- `stills/long-carried-attribution.png`
- `stills/story-chart.png`
- `stills/presenter-fallback.png`
- `stills/story-outro.png`
- `portrait/hero-title.png`
- `portrait/callout.png`
- `portrait/terminal-scene.png`
- `metadata/ffprobe-story-motion.json`
- `metadata/checksums.sha256`
- `metadata/render-props.json`
- `metadata/actual-vertical-props.json`

Motion SHA-256:

`c83554f8a45abeada8be0fe42c0b03b13fcbd3fcae223df84b705fe009ca0e1f`

Contact-sheet SHA-256:

`e500f798fdb07f74f8e7539da6a71c75df62dd38a6648815fa75de4ef6659a62`

Bulky/generated media is intentionally ignored by Git but preserved in this task worktree.

## Human review gate

Clicky/Wicky must judge before any production switch:

- host mouth/caption timing, roaming, gesture rhythm, and whether motion distracts;
- caption page timing and beat-crossfade rhythm;
- music/narration balance, swell audibility, fade behavior, and outro duration;
- whether the ellipsized long attribution remains readable on a real phone;
- optional presenter crop/lip-sync/fallback transition using a real presenter file;
- final portrait framing for all three allowed cuts;
- whether routine output remains 60fps or should add a 30fps cost tier.

The contact sheet shows no obvious clipping or missing host/credit/outro at the sampled frames. That is frame-level technical evidence, not aesthetic approval.

## Security, reliability, licensing, and rollback

- Render props are trusted-local inputs. HTTP(S), data URLs, and absolute local paths remain supported for the existing producer contract. An untrusted render service would require scheme/root/domain allowlists, input-size limits, sandboxing, and minimal privileges.
- Arrays and chart values are now bounded at the integration seam; broader SVG/path complexity remains trusted-input territory.
- Poppins requests are reduced but remain Google-font backed rather than fully self-hosted; an entirely offline production policy should vendor approved font files in a later reviewed change.
- The private overlay remains AGPL-3.0 software. Private hosting does not remove source-offer obligations for network users; obtain legal advice before service launch.
- No secret, credential, production path, service setting, or external resource was changed.
- Immediate branch rollback is the pinned upstream baseline `f8d9463`; the untouched production rollback remains `fd297bd`.
- No production switch, commit push, merge, remote write, or public-fork modification occurred.
