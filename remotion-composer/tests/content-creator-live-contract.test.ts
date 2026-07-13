import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { validateStoryProps } from "../src/integrations/content-creator/v1/contracts.ts";

const fixturePath = process.env.CONTENT_CREATOR_STORY_PROPS;

test("accepts Content Creator's actual emitted story props", () => {
  assert.ok(
    fixturePath,
    "set CONTENT_CREATOR_STORY_PROPS to an actual story_props.json emitted by Content Creator",
  );
  const props: unknown = JSON.parse(readFileSync(fixturePath, "utf8"));
  assert.deepEqual(validateStoryProps(props), props);
});
