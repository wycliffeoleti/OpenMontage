import { useCurrentFrame, useVideoConfig } from "remotion";

// video_compose passes `fps` in props when OPENMONTAGE_OUTPUT_FPS is set;
// Remotion has no render flag for it, so compositions read it in calculateMetadata.
export const DEFAULT_FPS = 30;

// Scale a frame count authored for 30fps so it lasts the same time at any fps
// (identity at 30fps).
export const at30 = (frames: number, fps: number): number => (frames * fps) / DEFAULT_FPS;

// The current frame expressed in 30fps frames, for motion written as `frame * k`.
export const frames30 = (frame: number, fps: number): number => (frame * DEFAULT_FPS) / fps;

export const propsFps = (props: unknown): number => {
  const fps = (props as { fps?: unknown } | null)?.fps;
  return typeof fps === "number" && Number.isFinite(fps) && fps > 0 ? fps : DEFAULT_FPS;
};

// Self-contained animation components were authored in 30fps frames. These
// hooks present their timeline in 30fps units (fractional at higher rates), so
// every literal frame count keeps its duration while motion is sampled at the
// real rate. Never use them for <Sequence> offsets or media trims, which need
// real frames. Both are identities at 30fps.
export const useFrame30 = (): number => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return frames30(frame, fps);
};

export const useVideoConfig30 = () => {
  const config = useVideoConfig();
  return {
    ...config,
    fps: DEFAULT_FPS,
    durationInFrames: frames30(config.durationInFrames, config.fps),
  };
};
