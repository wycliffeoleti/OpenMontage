import assert from "node:assert/strict";
import test from "node:test";

import {
  carryBeatMedia,
  isVideoPresenterSource,
  resolveContentCreatorAsset,
} from "../src/integrations/content-creator/v1/media.ts";

test("resolves a POSIX absolute asset with exactly three URI slashes", () => {
  const resolved = resolveContentCreatorAsset("/tmp/content creator/frame 01.png", (path) => `static:${path}`);

  assert.equal(resolved, "file:///tmp/content%20creator/frame%2001.png");
});

test("detects presenter videos with query strings and fragments", () => {
  assert.equal(isVideoPresenterSource("https://example.test/presenter.mp4?token=abc#take-2"), true);
  assert.equal(isVideoPresenterSource("https://example.test/presenter.webp?token=abc#take-2"), false);
});

test("carries attribution only when a beat inherits prior media", () => {
  const beats = carryBeatMedia([
    {
      imageSrc: "beat-1.jpg",
      credit: "Photo: A very long attribution line from Openverse",
      inSeconds: 0,
      outSeconds: 2,
    },
    { imageSrc: null, videoSrc: null, credit: null, inSeconds: 2, outSeconds: 4 },
  ]);

  assert.equal(beats[1].imageSrc, "beat-1.jpg");
  assert.equal(beats[1].credit, "Photo: A very long attribution line from Openverse");
});

test("does not carry media or attribution into a motion-graphics scene", () => {
  const beats = carryBeatMedia([
    { imageSrc: "beat-1.jpg", credit: "Photo: Author", inSeconds: 0, outSeconds: 2 },
    {
      scene: { content: { type: "kinetic_text", lines: ["Next"] } },
      inSeconds: 2,
      outSeconds: 4,
    },
  ]);

  assert.equal(beats[1].imageSrc, undefined);
  assert.equal(beats[1].credit, undefined);
});
