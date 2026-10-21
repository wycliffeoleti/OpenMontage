export type StaticFileResolver = (path: string) => string;

const VIDEO_EXTENSIONS = [".mp4", ".webm", ".mov", ".m4v"];

export interface BeatMedia extends Record<string, unknown> {
  scene?: unknown;
  imageSrc?: string | null;
  videoSrc?: string | null;
  credit?: string | null;
}

export function carryBeatMedia<T extends BeatMedia>(beats: T[]): T[] {
  let imageSrc: string | null = null;
  let videoSrc: string | null = null;
  let credit: string | null = null;

  return beats.map((beat) => {
    if (beat.scene) {
      return { ...beat };
    }
    const hasOwnMedia = Boolean(beat.imageSrc || beat.videoSrc);
    if (hasOwnMedia) {
      imageSrc = beat.imageSrc ?? null;
      videoSrc = beat.videoSrc ?? null;
      credit = beat.credit ?? null;
      return { ...beat };
    }
    return { ...beat, imageSrc, videoSrc, credit };
  });
}

export function isVideoPresenterSource(source: string): boolean {
  let pathname: string;
  try {
    pathname = new URL(source, "file:///").pathname;
  } catch {
    pathname = source.split(/[?#]/, 1)[0];
  }
  const normalized = pathname.toLowerCase();
  return VIDEO_EXTENSIONS.some((extension) => normalized.endsWith(extension));
}

export function resolveContentCreatorAsset(
  source: string,
  staticFileResolver: StaticFileResolver,
): string {
  if (/^(https?:|data:)/i.test(source)) {
    return source;
  }

  const clean = source.replace(/^file:\/\/\/?/i, "");
  const posix = clean.replace(/\\/g, "/");
  if (posix.startsWith("/")) {
    return `file://${encodeURI(posix)}`;
  }
  if (/^[A-Za-z]:\//.test(posix)) {
    return `file:///${encodeURI(posix)}`;
  }
  return staticFileResolver(clean);
}
