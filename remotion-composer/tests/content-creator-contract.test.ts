import assert from "node:assert/strict";
import test from "node:test";

import {
  ALLOWED_PORTRAIT_CUT_TYPES,
  CONTENT_CREATOR_INTEGRATION_VERSION,
  validateStoryProps,
  validateVerticalProps,
} from "../src/integrations/content-creator/v1/contracts.ts";

test("accepts the Content Creator ExplainerStory producer contract", () => {
  const props = {
    beats: [
      {
        scene: null,
        imageSrc: "aitips/example/beat0.jpg",
        videoSrc: null,
        credit: "Photo: Example Author / Openverse",
        inSeconds: 0,
        outSeconds: 3.4,
      },
    ],
    captions: [{ word: "Hello", startMs: 0, endMs: 400 }],
    audio: {
      narration: { src: "aitips/example/narration.mp3", volume: 1 },
      music: {
        src: "aitips/example/music.mp3",
        volume: 0.11,
        fadeInSeconds: 1,
        fadeOutSeconds: 1.2,
        loop: true,
        swellAtSeconds: 3,
        swellToVolume: 0.3,
      },
    },
    accentColor: "#22D3EE",
    presenterName: "AI in Simple",
    outroSeconds: 3,
    outroText: "Follow for more",
  };

  assert.equal(CONTENT_CREATOR_INTEGRATION_VERSION, "1.0.0");
  assert.deepEqual(validateStoryProps(props), props);
});

test("rejects an empty Content Creator chart before rendering", () => {
  const props = {
    beats: [
      {
        scene: {
          content: {
            type: "chart",
            title: "No observations",
            source: "Fixture",
            kind: "line",
            points: [],
          },
        },
        inSeconds: 0,
        outSeconds: 3,
      },
    ],
    captions: [],
  };

  assert.throws(
    () => validateStoryProps(props),
    /chart points must contain between 1 and 64 entries/,
  );
});

test("accepts every validated Content Creator portrait cut", () => {
  const cuts = [
    { id: "hook", type: "hero_title", text: "Hook", in_seconds: 0, out_seconds: 1 },
    { id: "tip", type: "callout", text: "Tip", in_seconds: 1, out_seconds: 2 },
    {
      id: "demo",
      type: "terminal_scene",
      steps: [{ kind: "out", text: "Done" }],
      in_seconds: 2,
      out_seconds: 3,
    },
  ];
  const props = { cuts, overlays: [], captions: [], audio: {} };

  assert.deepEqual(ALLOWED_PORTRAIT_CUT_TYPES, ["hero_title", "callout", "terminal_scene"]);
  assert.deepEqual(validateVerticalProps(props), props);
});

test("rejects unsupported portrait cuts before rendering", () => {
  const props = {
    cuts: [
      {
        id: "unsafe-chart",
        type: "line_chart",
        in_seconds: 0,
        out_seconds: 3,
        chartData: [{ x: 2026, y: 1, label: "2026" }],
      },
    ],
  };

  assert.throws(
    () => validateVerticalProps(props),
    /type is not supported by ExplainerVertical/,
  );
});

test("rejects non-finite Content Creator chart values", () => {
  const props = {
    beats: [
      {
        scene: {
          content: {
            type: "chart",
            points: [{ label: "2026", value: Number.NaN }],
          },
        },
        inSeconds: 0,
        outSeconds: 3,
      },
    ],
  };

  assert.throws(
    () => validateStoryProps(props),
    /chart points\[0\]\.value must be a finite number/,
  );
});

test("bounds Content Creator chart inputs", () => {
  const props = {
    beats: [
      {
        scene: {
          content: {
            type: "chart",
            points: Array.from({ length: 65 }, (_, index) => ({
              label: String(index),
              value: index,
            })),
          },
        },
        inSeconds: 0,
        outSeconds: 3,
      },
    ],
  };

  assert.throws(
    () => validateStoryProps(props),
    /chart points must contain between 1 and 64 entries/,
  );
});

test("requires a bounded label for every Content Creator chart point", () => {
  const props = {
    beats: [
      {
        scene: { content: { type: "chart", points: [{ value: 1 }] } },
        inSeconds: 0,
        outSeconds: 3,
      },
    ],
  };

  assert.throws(
    () => validateStoryProps(props),
    /chart points\[0\]\.label must be a non-empty string up to 80 characters/,
  );
});
