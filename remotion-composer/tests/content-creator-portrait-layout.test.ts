import assert from "node:assert/strict";
import test from "node:test";

import { getResponsiveSceneLayout } from "../src/components/responsiveLayout.ts";

test("derives mobile-safe layout values for 1080x1920 scenes", () => {
  assert.deepEqual(getResponsiveSceneLayout(1080, 1920), {
    isPortrait: true,
    contentWidth: "84%",
    heroTitleFontSize: 81,
    heroSubtitleFontSize: 30,
    calloutFontSize: 36,
    calloutTitleFontSize: 43,
    scenePadding: 54,
    terminalFontSize: 30,
  });
});
