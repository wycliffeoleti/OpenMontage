import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  CalculateMetadataFunction,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Poppins";
import { SceneCanvas, type Scene } from "./StoryScenes";

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
  videoSrc?: string; // real b-roll clip for this beat (muted, cover-fit)
  scene?: Scene;     // motion-graphics scene (preferred over image/video when set)
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

// --- one beat visual (scene, image w/ Ken Burns, or muted b-roll) + crossfade ---
// Beats OVERLAP by ~0.4s in the props; fading fully out over that window makes a
// true crossfade between consecutive beats (no library needed).
const CROSSFADE_S = 0.4;

const useBeatFade = (durationInFrames: number): number => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fade = Math.max(1, Math.round(CROSSFADE_S * fps));
  const fadeIn = interpolate(frame, [0, fade], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(frame, [durationInFrames - fade, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return fadeIn * fadeOut;
};

const BeatScene: React.FC<{ scene: Scene; durationInFrames: number; accent: string }> = ({
  scene,
  durationInFrames,
  accent,
}) => {
  const opacity = useBeatFade(durationInFrames);
  return (
    <AbsoluteFill style={{ opacity }}>
      <SceneCanvas scene={scene} accent={accent} />
    </AbsoluteFill>
  );
};

const BeatBottomBlend: React.FC = () => (
  <AbsoluteFill
    style={{ background: "linear-gradient(to bottom, rgba(15,23,42,0) 70%, rgba(15,23,42,0.85) 100%)" }}
  />
);

const BeatImage: React.FC<{ src: string; durationInFrames: number }> = ({ src, durationInFrames }) => {
  const frame = useCurrentFrame();
  const progress = durationInFrames > 1 ? Math.min(1, frame / durationInFrames) : 0;
  const scale = 1 + progress * 0.14;
  const drift = interpolate(progress, [0, 1], [0, -18]);
  const opacity = useBeatFade(durationInFrames);
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <Img
        src={resolveAsset(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity,
          transform: `scale(${scale}) translateY(${drift}px)`,
          willChange: "transform, opacity",
        }}
      />
      <BeatBottomBlend />
    </AbsoluteFill>
  );
};

const BeatVideo: React.FC<{ src: string; durationInFrames: number }> = ({ src, durationInFrames }) => {
  const opacity = useBeatFade(durationInFrames);
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <OffthreadVideo
        src={resolveAsset(src)}
        muted
        style={{ width: "100%", height: "100%", objectFit: "cover", opacity }}
      />
      <BeatBottomBlend />
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

// --- ANIMATED HOST: a friendly bespectacled character that actually "speaks" ---
// Mouth/gestures are driven by the same word timings the captions use (active
// word = mouth open), blinks every ~2.7s, pops "!"/"?" marks when the narration
// exclaims/asks. Pure Remotion SVG (OM's animation-pipeline rules: springs, no
// linear motion, overshoot pop-ins). Replaced by the AI-clone video via
// `presenterSrc` later — this is the free stand-in.
type MouthShape = "closed" | "small_o" | "wide" | "smile";

const HOST_SPRING = { damping: 12, stiffness: 80, mass: 1 }; // flat-motion-graphics feel
const MARK_MS = 900; // how long a !/? reaction mark stays up

const Mouth: React.FC<{ shape: MouthShape }> = ({ shape }) => {
  const ink = "#0F172A";
  switch (shape) {
    case "small_o":
      return <circle cx={200} cy={206} r={9} fill={ink} />;
    case "wide":
      return <ellipse cx={200} cy={206} rx={17} ry={12} fill={ink} />;
    case "smile":
      return <path d="M 180 200 Q 200 220 220 200" stroke={ink} strokeWidth={6} fill="none" strokeLinecap="round" />;
    default:
      return <rect x={186} y={203} width={28} height={6} rx={3} fill={ink} />;
  }
};

const AnimatedHost: React.FC<{ words: WordCaption[]; name: string; accent: string }> = ({
  words,
  name,
  accent,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ms = (frame / fps) * 1000;
  const ink = "#0F172A";
  const skin = "#F8FAFC";

  // --- speaking state from word timings (same source as the caption band) ---
  let active = -1;
  for (let i = 0; i < words.length; i++) {
    if (ms >= words[i].startMs && ms < words[i].endMs) {
      active = i;
      break;
    }
  }
  const speaking = active !== -1;
  let mouth: MouthShape = "closed";
  if (speaking) {
    const w = words[active].word.trim();
    if (w.endsWith(".") || w.endsWith(",")) mouth = "smile";
    else mouth = active % 2 === 0 ? "wide" : "small_o";
  }

  // --- idle life: bob, gaze drift, deterministic blink every ~2.7s ---
  const bob = Math.sin((frame / fps) * 2.0) * 5;
  const sway = Math.sin((frame / fps) * 0.9) * 1.5; // degrees, whole-body
  const gazeX = Math.sin((frame / fps) * 0.7) * 4;
  const blink = frame % Math.round(2.7 * fps) < Math.max(2, Math.round(0.13 * fps)) ? 0.08 : 1;

  // --- arm gesture on each caption-page start (anticipate -> raise -> settle) ---
  const pages = buildCaptionPages(words);
  let pageStartFrame = 0;
  for (const p of pages) {
    const f = Math.round((p.startMs / 1000) * fps);
    if (f <= frame) pageStartFrame = f;
    else break;
  }
  const tSince = frame - pageStartFrame;
  const lift = spring({ frame: tSince, fps, config: HOST_SPRING });
  const hold = interpolate(tSince, [0, Math.round(0.87 * fps), Math.round(1.47 * fps)], [1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const armAngle = -14 - 38 * lift * hold; // rest -> raised -> back to rest

  // --- "!"/"?" reaction mark when the narration exclaims or asks ---
  let mark: { char: string; startMs: number } | null = null;
  for (const w of words) {
    const last = w.word.trim().slice(-1);
    if ((last === "!" || last === "?") && ms >= w.startMs && ms < w.startMs + MARK_MS) {
      mark = { char: last, startMs: w.startMs };
      break;
    }
  }
  const markFrame = mark ? frame - Math.round((mark.startMs / 1000) * fps) : 0;
  const markPop = spring({ frame: markFrame, fps, config: { damping: 9, stiffness: 190, mass: 0.8 } });
  const markOpacity = mark
    ? interpolate(ms - mark.startMs, [0, 100, MARK_MS - 250, MARK_MS], [0, 1, 1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
      <svg
        width={430}
        height={400}
        viewBox="0 0 400 380"
        style={{ transform: `translateY(${bob}px) rotate(${sway}deg)`, transformOrigin: "50% 90%" }}
      >
        {/* floor shadow */}
        <ellipse cx={200} cy={366} rx={95} ry={12} fill="rgba(0,0,0,0.35)" />
        {/* left arm (rests) */}
        <line x1={152} y1={282} x2={116} y2={330} stroke={skin} strokeWidth={11} strokeLinecap="round" />
        <circle cx={114} cy={332} r={11} fill={skin} />
        {/* body */}
        <rect x={146} y={244} width={108} height={118} rx={42} fill="#1E293B" stroke={`${accent}55`} strokeWidth={3} />
        <circle cx={200} cy={292} r={13} fill={accent} opacity={0.9} />
        {/* gesturing right arm (pivots at the shoulder) */}
        <g transform={`rotate(${armAngle} 250 280)`}>
          <line x1={250} y1={280} x2={306} y2={318} stroke={skin} strokeWidth={11} strokeLinecap="round" />
          <circle cx={308} cy={320} r={11} fill={skin} />
        </g>
        {/* antenna */}
        <line x1={200} y1={62} x2={200} y2={38} stroke={skin} strokeWidth={5} strokeLinecap="round" />
        <circle cx={200} cy={32} r={8} fill={accent} />
        {/* head */}
        <circle cx={200} cy={148} r={86} fill={skin} />
        {/* glasses: round specs + bridge + temples */}
        <circle cx={166} cy={142} r={27} fill={`${accent}1F`} stroke={ink} strokeWidth={7} />
        <circle cx={234} cy={142} r={27} fill={`${accent}1F`} stroke={ink} strokeWidth={7} />
        <line x1={193} y1={142} x2={207} y2={142} stroke={ink} strokeWidth={7} strokeLinecap="round" />
        <line x1={139} y1={140} x2={118} y2={132} stroke={ink} strokeWidth={6} strokeLinecap="round" />
        <line x1={261} y1={140} x2={282} y2={132} stroke={ink} strokeWidth={6} strokeLinecap="round" />
        {/* pupils (gaze drift + blink) */}
        <g transform={`translate(${gazeX} 0)`}>
          <ellipse cx={166} cy={144} rx={9} ry={9 * blink} fill={ink} />
          <ellipse cx={234} cy={144} rx={9} ry={9 * blink} fill={ink} />
        </g>
        <Mouth shape={mouth} />
        {/* reaction mark */}
        {mark && (
          <text
            x={310}
            y={84}
            fontFamily={fontFamily}
            fontSize={82}
            fontWeight={800}
            fill={accent}
            opacity={markOpacity}
            transform={`scale(${markPop})`}
            style={{ transformOrigin: "310px 84px", transformBox: "fill-box" } as React.CSSProperties}
          >
            {mark.char}
          </text>
        )}
      </svg>
      <div style={{ fontFamily, fontSize: 28, fontWeight: 600, color: "#F8FAFC", letterSpacing: 0.5, opacity: 0.85 }}>
        {name}
      </div>
    </div>
  );
};

const STORY_FPS = 60; // cinematic-smooth motion graphics; platforms cap at 60

const calculateStoryMetadata: CalculateMetadataFunction<ExplainerStoryProps> = async ({ props }) => {
  const beats = props.beats || [];
  const lastEnd = beats.length ? Math.max(...beats.map((b) => b.outSeconds || 0)) : 20;
  return { durationInFrames: Math.ceil((lastEnd + 0.8) * STORY_FPS), fps: STORY_FPS };
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

  // carry the last available image forward if a beat has no visual of its own
  let lastImg: string | undefined;
  const filled = beats.map((b) => {
    if (b.scene) return b; // motion-graphics beats never carry images
    if (b.imageSrc) lastImg = b.imageSrc;
    return { ...b, imageSrc: b.imageSrc || (b.videoSrc ? undefined : lastImg) };
  });

  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      {/* TOP — story images */}
      <div style={{ position: "absolute", top: 0, left: 0, width, height: IMG_H, overflow: "hidden" }}>
        {filled.map((b, i) => {
          const from = Math.round(b.inSeconds * fps);
          const dur = Math.max(1, Math.round((b.outSeconds - b.inSeconds) * fps));
          if (!b.scene && !b.videoSrc && !b.imageSrc) return null;
          return (
            <Sequence key={i} from={from} durationInFrames={dur} layout="none">
              {b.scene ? (
                <BeatScene scene={b.scene} durationInFrames={dur} accent={accent} />
              ) : b.videoSrc ? (
                <BeatVideo src={b.videoSrc} durationInFrames={dur} />
              ) : (
                <BeatImage src={b.imageSrc!} durationInFrames={dur} />
              )}
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
          <AnimatedHost words={captions} name={presenterName} accent={accent} />
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
