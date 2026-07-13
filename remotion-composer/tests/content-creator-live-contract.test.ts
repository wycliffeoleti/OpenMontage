import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  validateStoryProps,
  validateVerticalProps,
} from "../src/integrations/content-creator/v1/contracts.ts";

const fixturePath = process.env.CONTENT_CREATOR_STORY_PROPS;
const verticalFixturePath = process.env.CONTENT_CREATOR_VERTICAL_PROPS;

test("accepts Content Creator's actual emitted story props", () => {
  assert.ok(
    fixturePath,
    "set CONTENT_CREATOR_STORY_PROPS to an actual story_props.json emitted by Content Creator",
  );
  const props: unknown = JSON.parse(readFileSync(fixturePath, "utf8"));
  assert.deepEqual(validateStoryProps(props), props);
});

test("accepts Content Creator's actual emitted vertical props", () => {
  assert.ok(
    verticalFixturePath,
    "set CONTENT_CREATOR_VERTICAL_PROPS to props emitted by Content Creator._assemble_props",
  );
  const props: unknown = JSON.parse(readFileSync(verticalFixturePath, "utf8"));
  assert.deepEqual(validateVerticalProps(props), props);
});
