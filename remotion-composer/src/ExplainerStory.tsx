import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  CalculateMetadataFunction,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Poppins";

const { fontFamily } = loadFont();

// ---------------------------------------------------------------------------
// ExplainerStory — a 3-band vertical (1080x1920) "illustrated story" layout:
//   TOP    : one image per story beat (Ken Burns), swaps as the narration moves
//   MIDDLE : word captions (the centered divider)
//   BOTTOM : a presenter — placeholder avatar now, the user's AI clone later
// ---------------------------------------------------------------------------

function resolveAsset(src: string): string {
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) {
    return src;
  }
  const clean = src.replace(/^file:\/\/\/?/, "");
  if (clean.startsWith("/") || /^[A-Za-z]:[\\/]/.test(clean)) {
    return `file:///${clean.replace(/\\/g, "/")}`;
  }
  return staticFile(clean);
}

interface Beat {
  imageSrc?: string;
  inSeconds: number;
  outSeconds: number;
}

interface WordCaption {
  word: string;
  startMs: number;
  endMs: number;
}

interface AudioLayer {
  src: string;
  volume?: number;
  loop?: boolean;
  fadeInSeconds?: number;
  fadeOutSeconds?: number;
}

export interface ExplainerStoryProps {
  beats: Beat[];
  captions: WordCaption[];
  presenterSrc?: string;
  presenterName?: string;
  audio?: { narration?: AudioLayer; music?: AudioLayer };
  accentColor?: string;
}

const BG = "#0F172A";
const ACCENT = "#22D3EE";

// --- one beat image with a slow Ken Burns zoom + fade (sequence-relative) ---
const BeatImage: React.FC<{ src: string; durationInFrames: number }> = ({ src, durationInFrames }) => {
  const frame = useCurrentFrame();
  const progress = durationInFrames > 1 ? Math.min(1, frame / durationInFrames) : 0;
  const scale = 1 + progress * 0.14;
  const drift = interpolate(progress, [0, 1], [0, -18]);
  const fadeIn = interpolate(frame, [0, 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const fadeOut = interpolate(frame, [durationInFrames - 10, durationInFrames], [1, 0.55], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{ overflow: "hidden", background: BG }}>
      <Img
        src={resolveAsset(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: fadeIn * fadeOut,
          transform: `scale(${scale}) translateY(${drift}px)`,
          willChange: "transform, opacity",
        }}
      />
      {/* subtle bottom gradient so the caption band blends in */}
      <AbsoluteFill
        style={{ background: "linear-gradient(to bottom, rgba(15,23,42,0) 70%, rgba(15,23,42,0.85) 100%)" }}
      />
    </AbsoluteFill>
  );
};

// --- caption band: fixed PAGES of words — a page holds still while the highlight
//     walks through it (active=accent, past=full, future=dimmed), then swaps ---
const WORDS_PER_PAGE = 4;

interface CaptionPage {
  words: WordCaption[];
  startMs: number;
}

function buildCaptionPages(words: WordCaption[]): CaptionPage[] {
  const pages: CaptionPage[] = [];
  for (let i = 0; i < words.length; i += WORDS_PER_PAGE) {
    const pageWords = words.slice(i, i + WORDS_PER_PAGE);
    pages.push({ words: pageWords, startMs: pageWords[0].startMs });
  }
  return pages;
}

const CaptionPageView: React.FC<{ page: CaptionPage; seqStartMs: number; accent: string }> = ({
  page,
  seqStartMs,
  accent,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ms = seqStartMs + (frame / fps) * 1000;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "0 18px", justifyContent: "center", alignItems: "center", padding: "0 70px" }}>
      {page.words.map((w, k) => {
        const active = ms >= w.startMs && ms < w.endMs;
        const past = ms >= w.endMs;
        return (
          <span
            key={k}
            style={{
              fontFamily,
              fontSize: 58,
              fontWeight: 700,
              color: active ? accent : "#F8FAFC",
              opacity: active ? 1 : past ? 0.95 : 0.55,
              lineHeight: 1.15,
            }}
          >
            {w.word}
          </span>
        );
      })}
    </div>
  );
};

const CaptionBand: React.FC<{ words: WordCaption[]; accent: string }> = ({ words, accent }) => {
  const { fps, durationInFrames } = useVideoConfig();
  if (words.length === 0) return null;
  const pages = buildCaptionPages(words);
  return (
    <>
      {pages.map((page, i) => {
        // first page shows from frame 0; each page stays until the next one starts;
        // the last page stays up through the outro padding
        const from = i === 0 ? 0 : Math.round((page.startMs / 1000) * fps);
        const next = pages[i + 1];
        const until = next ? Math.round((next.startMs / 1000) * fps) : durationInFrames;
        return (
          <Sequence key={i} from={from} durationInFrames={Math.max(1, until - from)} layout="none">
            <CaptionPageView page={page} seqStartMs={(from / fps) * 1000} accent={accent} />
          </Sequence>
        );
      })}
    </>
  );
};

// --- presenter placeholder (a simple stylized "host"); clone plugs in later ---
const PresenterPlaceholder: React.FC<{ name: string; accent: string }> = ({ name, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const bob = Math.sin((frame / fps) * 2.2) * 6; // gentle idle motion
  return (
    <div
      style={{
        width: 460,
        height: 300,
        borderRadius: 32,
        background: "linear-gradient(160deg, #1E293B, #0B1220)",
        border: `2px solid ${accent}33`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 14,
        boxShadow: "0 20px 60px rgba(0,0,0,0.45)",
      }}
    >
      <div
        style={{
          transform: `translateY(${bob}px)`,
          width: 150,
          height: 150,
          borderRadius: "50%",
          background: `radial-gradient(circle at 50% 38%, ${accent}, #0EA5B7)`,
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* simple bust silhouette */}
        <div style={{ position: "absolute", top: 34, left: "50%", width: 54, height: 54, borderRadius: "50%", background: "#0F172A", transform: "translateX(-50%)" }} />
        <div style={{ position: "absolute", bottom: -8, left: "50%", width: 110, height: 70, borderRadius: "55px 55px 0 0", background: "#0F172A", transform: "translateX(-50%)" }} />
      </div>
      <div style={{ fontFamily, fontSize: 30, fontWeight: 600, color: "#F8FAFC", letterSpacing: 0.5 }}>{name}</div>
    </div>
  );
};

const calculateStoryMetadata: CalculateMetadataFunction<ExplainerStoryProps> = async ({ props }) => {
  const beats = props.beats || [];
  const lastEnd = beats.length ? Math.max(...beats.map((b) => b.outSeconds || 0)) : 20;
  return { durationInFrames: Math.ceil((lastEnd + 0.8) * 30) };
};

export const ExplainerStory: React.FC<ExplainerStoryProps> = ({
  beats,
  captions,
  presenterSrc,
  presenterName = "Your AI host",
  audio,
  accentColor,
}) => {
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const accent = accentColor || ACCENT;

  const IMG_H = Math.round(height * 0.54);       // top: images
  const CAP_TOP = IMG_H;
  const CAP_H = Math.round(height * 0.13);        // middle: caption divider
  const PRES_TOP = CAP_TOP + CAP_H;               // bottom: presenter

  // carry the last available image forward if a beat has none
  let lastImg: string | undefined;
  const filled = beats.map((b) => {
    if (b.imageSrc) lastImg = b.imageSrc;
    return { ...b, imageSrc: b.imageSrc || lastImg };
  });

  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      {/* TOP — story images */}
      <div style={{ position: "absolute", top: 0, left: 0, width, height: IMG_H, overflow: "hidden" }}>
        {filled.map((b, i) => {
          const from = Math.round(b.inSeconds * fps);
          const dur = Math.max(1, Math.round((b.outSeconds - b.inSeconds) * fps));
          if (!b.imageSrc) return null;
          return (
            <Sequence key={i} from={from} durationInFrames={dur} layout="none">
              <BeatImage src={b.imageSrc} durationInFrames={dur} />
            </Sequence>
          );
        })}
      </div>

      {/* MIDDLE — caption divider band */}
      <div
        style={{
          position: "absolute",
          top: CAP_TOP,
          left: 0,
          width,
          height: CAP_H,
          background: "#0B1220",
          borderTop: `3px solid ${accent}`,
          borderBottom: `3px solid ${accent}55`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <CaptionBand words={captions} accent={accent} />
      </div>

      {/* BOTTOM — presenter (placeholder now → clone later) */}
      <div
        style={{
          position: "absolute",
          top: PRES_TOP,
          left: 0,
          width,
          height: height - PRES_TOP,
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "center",
          paddingTop: 60,
        }}
      >
        {presenterSrc ? (
          <Img src={resolveAsset(presenterSrc)} style={{ width: 460, height: 300, objectFit: "cover", borderRadius: 32 }} />
        ) : (
          <PresenterPlaceholder name={presenterName} accent={accent} />
        )}
      </div>

      {/* Audio — narration + music */}
      {audio?.narration?.src && (
        <Audio src={resolveAsset(audio.narration.src)} volume={audio.narration.volume ?? 1} />
      )}
      {audio?.music?.src && (
        <Audio
          src={resolveAsset(audio.music.src)}
          loop={audio.music.loop ?? true}
          loopVolumeCurveBehavior="repeat"
          volume={(f) => {
            const base = audio.music!.volume ?? 0.07;
            const fadeIn = interpolate(f, [0, (audio.music!.fadeInSeconds ?? 1) * fps], [0, base], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const fadeOut = interpolate(
              f,
              [durationInFrames - (audio.music!.fadeOutSeconds ?? 2) * fps, durationInFrames],
              [base, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            return Math.min(fadeIn, fadeOut);
          }}
        />
      )}
    </AbsoluteFill>
  );
};

export { calculateStoryMetadata };
