export const CONTENT_CREATOR_INTEGRATION_VERSION = "1.0.0" as const;
export const ALLOWED_PORTRAIT_CUT_TYPES = [
  "hero_title",
  "callout",
  "terminal_scene",
] as const;

const portraitCutTypes = new Set<string>(ALLOWED_PORTRAIT_CUT_TYPES);

export interface StoryBeat extends Record<string, unknown> {
  scene?: Record<string, unknown> | null;
  imageSrc?: string | null;
  videoSrc?: string | null;
  credit?: string | null;
  inSeconds: number;
  outSeconds: number;
}

export interface StoryCaption extends Record<string, unknown> {
  word: string;
  startMs: number;
  endMs: number;
}

export interface ExplainerStoryProps extends Record<string, unknown> {
  beats: StoryBeat[];
  captions?: StoryCaption[];
  audio?: Record<string, unknown>;
  accentColor?: string;
  presenterName?: string;
  presenterSrc?: string;
  outroSeconds?: number;
  outroText?: string;
}

export interface ContentCreatorVerticalProps extends Record<string, unknown> {
  cuts: Array<Record<string, unknown>>;
  overlays?: Array<Record<string, unknown>>;
  captions?: Array<Record<string, unknown>>;
  audio?: Record<string, unknown>;
}

function expectRecord(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError(`${path} must be an object`);
  }
  return value as Record<string, unknown>;
}

function expectFiniteNumber(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(`${path} must be a finite number`);
  }
  return value;
}

export function validateStoryProps(input: unknown): ExplainerStoryProps {
  const props = expectRecord(input, "props");
  if (!Array.isArray(props.beats) || props.beats.length === 0) {
    throw new TypeError("props.beats must be a non-empty array");
  }

  props.beats.forEach((candidate, index) => {
    const beat = expectRecord(candidate, `props.beats[${index}]`);
    const start = expectFiniteNumber(beat.inSeconds, `props.beats[${index}].inSeconds`);
    const end = expectFiniteNumber(beat.outSeconds, `props.beats[${index}].outSeconds`);
    if (start < 0 || end <= start) {
      throw new RangeError(`props.beats[${index}] must have 0 <= inSeconds < outSeconds`);
    }

    if (beat.scene !== undefined && beat.scene !== null) {
      const scene = expectRecord(beat.scene, `props.beats[${index}].scene`);
      const content = expectRecord(scene.content, `props.beats[${index}].scene.content`);
      if (content.type === "chart") {
        if (!Array.isArray(content.points) || content.points.length < 1 || content.points.length > 64) {
          throw new RangeError("chart points must contain between 1 and 64 entries");
        }
        content.points.forEach((candidate, pointIndex) => {
          const point = expectRecord(candidate, `chart points[${pointIndex}]`);
          if (
            typeof point.label !== "string" ||
            point.label.trim().length === 0 ||
            point.label.length > 80
          ) {
            throw new RangeError(
              `chart points[${pointIndex}].label must be a non-empty string up to 80 characters`,
            );
          }
          expectFiniteNumber(point.value, `chart points[${pointIndex}].value`);
        });
      }
    }
  });

  if (props.captions !== undefined && !Array.isArray(props.captions)) {
    throw new TypeError("props.captions must be an array");
  }

  return input as ExplainerStoryProps;
}

export function validateVerticalProps(input: unknown): ContentCreatorVerticalProps {
  const props = expectRecord(input, "props");
  if (!Array.isArray(props.cuts) || props.cuts.length === 0 || props.cuts.length > 32) {
    throw new RangeError("props.cuts must contain between 1 and 32 entries");
  }

  props.cuts.forEach((candidate, index) => {
    const cut = expectRecord(candidate, `props.cuts[${index}]`);
    if (typeof cut.type !== "string") {
      throw new TypeError(`props.cuts[${index}].type must be a string`);
    }
    if (!portraitCutTypes.has(cut.type)) {
      throw new RangeError(`props.cuts[${index}].type is not supported by ExplainerVertical`);
    }
    const start = expectFiniteNumber(cut.in_seconds, `props.cuts[${index}].in_seconds`);
    const end = expectFiniteNumber(cut.out_seconds, `props.cuts[${index}].out_seconds`);
    if (start < 0 || end <= start) {
      throw new RangeError(`props.cuts[${index}] must have 0 <= in_seconds < out_seconds`);
    }
  });

  return input as ContentCreatorVerticalProps;
}
