import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont } from "@remotion/google-fonts/Poppins";

const { fontFamily } = loadFont();

// ---------------------------------------------------------------------------
// StoryScenes — the motion-graphics canvas for ExplainerStory's top band.
// Reference look ("Two Minute Papers" style, user-locked 2026-07-02):
// deep-navy premium-dark, glow/bloom on everything, thin line-art strokes with
// draw-on animation, white text + one accent word, soft bokeh behind content.
// Every scene is a layered composition: background (tone+particles+texture)
// -> content -> vignette. All deterministic (seeded), all pure CSS/SVG, $0.
// ---------------------------------------------------------------------------

export type SceneTone = "cold" | "steel" | "void" | "warm";

export interface SceneBackground {
  tone?: SceneTone;
  particles?: "bokeh" | "none";
  texture?: "grid" | "none";
}

export type SceneContent =
  | {
      type: "kinetic_text";
      lines: string[];
      accentWords?: string; // space-separated words to tint (matched case/punct-insensitive)
      accentColor?: string; // override the video accent for this scene (e.g. orange)
      subtitle?: string;    // small uppercase letter-spaced line under the title
      fontSize?: number;
    }
  | {
      type: "icon_scene";
      icon: "laptop" | "chip";
      overlay?: "lock";     // pops in over the icon after the draw-on
      burst?: boolean;      // glowing nodes explode out of the icon
      badge?: string;       // text inside the chip (e.g. "GLM 5.2")
      label?: string;       // caption under the icon
    }
  | {
      type: "network";
      nodeCount?: number;
      label?: string;
    }
  | {
      type: "chat_window";
      title?: string;    // mac-window title bar text (default "Ask AI")
      question: string;  // typed out character by character
      answer: string;    // streams in word by word after a "thinking" pause
    }
  | {
      type: "compare";
      title?: string;
      leftLabel: string;
      leftItems: string[];
      rightLabel: string;
      rightItems: string[];
    }
  | {
      type: "stat";
      value: string; // leading number counts up ("83°C", "6x", "1,000,000" → digits animate)
      label?: string;
    }
  | {
      type: "diagram";
      nodes: Array<{ label: string }>;  // revealed in order, arrows draw between
      column?: boolean;                 // stack vertically (default: row for ≤3 nodes)
    }
  | {
      type: "staged";
      elements: StagedElement[];        // the free-form visual stage (see below)
    };

// One prop on the stage: a drawable icon, a labeled entity badge, a keyword
// label, a fan of photo cards, or director-supplied raw SVG paths. Positioned
// in percent of the canvas, entering/exiting on its own schedule — the
// composable language that lets ANY sentence be staged visually.
export interface StagedElement {
  kind: "icon" | "entity" | "label" | "photos" | "path";
  icon?: string;           // kind=icon: a key of ICON_LIBRARY (e.g. "jail", "lock", "apple")
  name?: string;           // kind=entity/label: the text ("Fable 5", "BANNED")
  d?: string[];            // kind=path: raw SVG path data (100x100 viewBox), drawn on
  x: number;               // center, percent of canvas width (0-100)
  y: number;               // center, percent of canvas height (0-100)
  scale?: number;          // 1 = icon 260px tall / entity natural size
  color?: string;          // stroke/fill accent for this element
  at?: number;             // seconds: when it enters (default 0)
  enter?: "draw" | "pop" | "slide-left" | "slide-right" | "rise" | "fade";
  until?: number;          // seconds: when it exits (default: never)
  exit?: "fade" | "drop" | "fly-right";
  wiggle?: boolean;        // gentle idle rotation
}

export interface Scene {
  background?: SceneBackground;
  content: SceneContent;
}

// --- deterministic seeded random (same trick as OM's ParticleOverlay) --------
const seededRandom = (seed: number): number => {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
};

const NODE_PALETTE = ["#F59E0B", "#FBBF24", "#22D3EE", "#34D399", "#EC4899", "#A78BFA", "#60A5FA"];

// --- background layer --------------------------------------------------------
const TONES: Record<SceneTone, { base: string; glowA: string; glowB: string }> = {
  cold: { base: "#0A0F1E", glowA: "rgba(59,130,246,0.11)", glowB: "rgba(147,51,234,0.10)" },
  steel: { base: "#0D131F", glowA: "rgba(100,116,139,0.13)", glowB: "rgba(59,130,246,0.08)" },
  void: { base: "#05070D", glowA: "rgba(30,41,59,0.30)", glowB: "rgba(88,28,135,0.10)" },
  warm: { base: "#0B0E1A", glowA: "rgba(245,158,11,0.08)", glowB: "rgba(147,51,234,0.09)" },
};

const Bokeh: React.FC<{ seed?: number }> = ({ seed = 7 }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const dots = Array.from({ length: 13 }, (_, i) => {
    const r1 = seededRandom(seed + i * 3.1);
    const r2 = seededRandom(seed + i * 5.7 + 1);
    const r3 = seededRandom(seed + i * 7.3 + 2);
    const size = 36 + r1 * 84;
    const palette = ["#22D3EE", "#3B82F6", "#8B5CF6", "#A855F7"];
    return {
      x: r2 * width,
      y: r3 * height,
      size,
      color: palette[i % palette.length],
      drift: 14 + r1 * 18,
      speed: 0.15 + r2 * 0.2,
      phase: r3 * Math.PI * 2,
      opacity: 0.16 + r1 * 0.2,
    };
  });
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      {dots.map((d, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: d.x + Math.sin(t * d.speed + d.phase) * d.drift,
            top: d.y + Math.cos(t * d.speed * 0.8 + d.phase) * d.drift * 0.7,
            width: d.size,
            height: d.size,
            borderRadius: "50%",
            background: d.color,
            opacity: d.opacity,
            filter: "blur(22px)",
          }}
        />
      ))}
    </AbsoluteFill>
  );
};

const SceneBackdrop: React.FC<{ bg?: SceneBackground }> = ({ bg }) => {
  const tone = TONES[bg?.tone ?? "cold"];
  return (
    <>
      <AbsoluteFill
        style={{
          background: `radial-gradient(120% 90% at 28% 18%, ${tone.glowA}, transparent 60%), radial-gradient(95% 80% at 96% 72%, ${tone.glowB}, transparent 55%), ${tone.base}`,
        }}
      />
      {bg?.texture === "grid" && (
        <AbsoluteFill
          style={{
            background:
              "repeating-linear-gradient(90deg, rgba(148,163,184,0.05) 0px, rgba(148,163,184,0.05) 1.5px, transparent 1.5px, transparent 108px)",
          }}
        />
      )}
      {(bg?.particles ?? "bokeh") === "bokeh" && <Bokeh />}
    </>
  );
};

const Vignette: React.FC = () => (
  <AbsoluteFill
    style={{
      background: "radial-gradient(140% 120% at 50% 45%, transparent 55%, rgba(2,4,10,0.6) 100%)",
      pointerEvents: "none",
    }}
  />
);

// --- kinetic text: word-staggered blur reveal + one accent phrase ------------
const cleanWord = (w: string) => w.toLowerCase().replace(/[^a-z0-9]/g, "");

const KineticText: React.FC<{
  lines: string[];
  accentWords?: string;
  accent: string;
  subtitle?: string;
  fontSize?: number;
}> = ({ lines, accentWords, accent, subtitle, fontSize = 86 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // accent a CONTIGUOUS phrase (first occurrence) — set-matching tinted stray
  // duplicates of little words like "the" in other lines
  const flatClean = lines.flatMap((l) => l.split(/\s+/)).map(cleanWord);
  const phrase = (accentWords ?? "").split(/\s+/).map(cleanWord).filter(Boolean);
  let accentStart = -1;
  if (phrase.length) {
    for (let i = 0; i + phrase.length <= flatClean.length; i++) {
      if (phrase.every((p, k) => flatClean[i + k] === p)) {
        accentStart = i;
        break;
      }
    }
  }
  const inAccentPhrase = (idx: number) =>
    accentStart !== -1
      ? idx >= accentStart && idx < accentStart + phrase.length
      : phrase.includes(flatClean[idx]); // fallback when the exact phrase isn't found
  let wordIndex = 0;
  const totalWords = lines.reduce((n, l) => n + l.split(/\s+/).length, 0);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: "0 60px" }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
        {lines.map((line, li) => (
          <div key={li} style={{ display: "flex", gap: 22, justifyContent: "center", flexWrap: "wrap" }}>
            {line.split(/\s+/).map((word, wi) => {
              const idx = wordIndex++;
              const delay = Math.round((0.15 + idx * 0.09) * fps);
              const s = spring({ frame: frame - delay, fps, config: { damping: 13, stiffness: 130 } });
              const op = interpolate(frame - delay, [0, 0.3 * fps], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              const blur = interpolate(frame - delay, [0, 0.32 * fps], [9, 0], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              const isAccent = inAccentPhrase(idx);
              return (
                <span
                  key={wi}
                  style={{
                    fontFamily,
                    fontSize,
                    fontWeight: 700,
                    letterSpacing: -1,
                    lineHeight: 1.14,
                    color: isAccent ? accent : "#F8FAFC",
                    opacity: op,
                    filter: `blur(${blur}px)`,
                    transform: `translateY(${(1 - s) * 22}px)`,
                    textShadow: isAccent
                      ? `0 0 34px ${accent}66, 0 0 80px ${accent}33`
                      : "0 0 26px rgba(248,250,252,0.18)",
                  }}
                >
                  {word}
                </span>
              );
            })}
          </div>
        ))}
        {subtitle && (
          <div
            style={{
              marginTop: 30,
              fontFamily,
              fontSize: 27,
              fontWeight: 600,
              letterSpacing: 7,
              textTransform: "uppercase",
              color: "#38BDF8",
              opacity: interpolate(frame, [Math.round((0.3 + totalWords * 0.09) * fps), Math.round((0.65 + totalWords * 0.09) * fps)], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
              textShadow: "0 0 24px rgba(56,189,248,0.5)",
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

// --- glowing node (SVG): layered halos, deterministic ------------------------
const GlowNode: React.FC<{ cx: number; cy: number; r: number; color: string; reveal: number; pulse: number }> = ({
  cx,
  cy,
  r,
  color,
  reveal,
  pulse,
}) => {
  const rr = r * reveal * (1 + pulse * 0.1);
  return (
    <g opacity={reveal}>
      <circle cx={cx} cy={cy} r={rr * 2.6} fill={color} opacity={0.12} />
      <circle cx={cx} cy={cy} r={rr * 1.7} fill={color} opacity={0.24} />
      <circle cx={cx} cy={cy} r={rr} fill={color} />
      <circle cx={cx - rr * 0.22} cy={cy - rr * 0.22} r={rr * 0.28} fill="rgba(255,255,255,0.6)" />
    </g>
  );
};

// --- icon scene: line-art icons that draw themselves on, then glow -----------
const DRAW = { damping: 15, stiffness: 60, mass: 1 };

const IconScene: React.FC<{
  icon: "laptop" | "chip";
  overlay?: "lock";
  burst?: boolean;
  badge?: string;
  label?: string;
  accent: string;
}> = ({ icon, overlay, burst, badge, label, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const stroke = "#5EEAD4"; // teal line-art, per reference
  const drawMain = spring({ frame, fps, config: DRAW });
  const drawBase = spring({ frame: frame - Math.round(0.25 * fps), fps, config: DRAW });
  const fillIn = interpolate(frame, [0.45 * fps, 0.9 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const lockPop = spring({ frame: frame - Math.round(1.0 * fps), fps, config: { damping: 10, stiffness: 120 } });
  const glowPulse = 0.5 + Math.sin(t * 1.8) * 0.5;

  // burst nodes fan out of the screen center — wide fan, slight upward bias
  const burstNodes = Array.from({ length: 28 }, (_, i) => {
    const r1 = seededRandom(41 + i * 2.3);
    const r2 = seededRandom(97 + i * 4.9);
    const r3 = seededRandom(13 + i * 6.1);
    const ang = -Math.PI * (r1 * 1.15 - 0.075); // spills past horizontal on both sides
    const dist = 170 + r2 * 300;
    const pop = spring({ frame: frame - Math.round((0.9 + i * 0.045) * fps), fps, config: { damping: 12, stiffness: 90 } });
    return {
      x: 450 + Math.cos(ang) * dist * (0.4 + 0.6 * pop),
      y: 250 + Math.sin(ang) * dist * (0.4 + 0.6 * pop),
      r: 6 + r3 * 7,
      color: NODE_PALETTE[i % NODE_PALETTE.length],
      pop,
      pulse: Math.sin(t * 2 + i * 1.7),
    };
  });

  return (
    <AbsoluteFill style={{ flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 14 }}>
      <svg width={990} height={730} viewBox="0 0 900 660" style={{ overflow: "visible" }}>
        {burst &&
          burstNodes.map((n, i) => (
            <g key={`b${i}`}>
              <line
                x1={450}
                y1={250}
                x2={n.x}
                y2={n.y}
                stroke="rgba(226,232,240,0.13)"
                strokeWidth={1.2}
                opacity={n.pop}
              />
              <GlowNode cx={n.x} cy={n.y} r={n.r} color={n.color} reveal={n.pop} pulse={n.pulse} />
            </g>
          ))}

        {icon === "laptop" && (
          <g style={{ filter: `drop-shadow(0 0 ${6 + glowPulse * 5}px rgba(94,234,212,0.55))` }}>
            <rect
              x={270}
              y={125}
              width={360}
              height={250}
              rx={14}
              fill="#0E1B33"
              fillOpacity={fillIn}
              stroke={burst ? "#F0B429" : stroke}
              strokeWidth={4}
              pathLength={1}
              strokeDasharray={1}
              strokeDashoffset={1 - drawMain}
            />
            <path
              d="M 208 405 L 692 405 L 736 458 L 164 458 Z"
              fill="#14213D"
              fillOpacity={fillIn}
              stroke={stroke}
              strokeWidth={4}
              strokeLinejoin="round"
              pathLength={1}
              strokeDasharray={1}
              strokeDashoffset={1 - drawBase}
            />
          </g>
        )}

        {icon === "chip" && (
          <g style={{ filter: `drop-shadow(0 0 ${8 + glowPulse * 7}px rgba(245,158,11,0.5))` }}>
            {Array.from({ length: 8 }, (_, i) => {
              const p = 340 + i * 30;
              const pin = interpolate(frame, [(0.5 + i * 0.03) * fps, (0.7 + i * 0.03) * fps], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              return (
                <g key={i} opacity={pin}>
                  <rect x={p - 5} y={80} width={10} height={22} rx={3} fill="#F0B429" />
                  <rect x={p - 5} y={438} width={10} height={22} rx={3} fill="#F0B429" />
                  <rect x={258} y={p - 130 + 20} width={22} height={10} rx={3} fill="#F0B429" />
                  <rect x={620} y={p - 130 + 20} width={22} height={10} rx={3} fill="#F0B429" />
                </g>
              );
            })}
            <rect
              x={280}
              y={100}
              width={340}
              height={340}
              rx={26}
              fill="#131C33"
              fillOpacity={fillIn}
              stroke="#F0B429"
              strokeWidth={4}
              pathLength={1}
              strokeDasharray={1}
              strokeDashoffset={1 - drawMain}
            />
            <rect x={330} y={150} width={240} height={240} rx={16} fill="#1B2745" opacity={fillIn} />
            {badge && (
              <text
                x={450}
                y={286}
                textAnchor="middle"
                fontFamily={fontFamily}
                fontSize={54}
                fontWeight={800}
                fill="#FDE68A"
                opacity={fillIn}
                style={{ letterSpacing: 1 }}
              >
                {badge}
              </text>
            )}
          </g>
        )}

        {overlay === "lock" && (
          <g transform={`scale(${lockPop})`} style={{ transformOrigin: "450px 130px", transformBox: "fill-box" } as React.CSSProperties}>
            <g style={{ filter: "drop-shadow(0 0 14px rgba(240,180,41,0.45))" }}>
              <path
                d="M 416 100 V 62 A 34 34 0 0 1 484 62 V 100"
                stroke="#F0B429"
                strokeWidth={15}
                fill="none"
                strokeLinecap="round"
              />
              <rect x={398} y={96} width={104} height={88} rx={13} fill="#F5C044" stroke="#FDE68A" strokeWidth={2} />
              <circle cx={450} cy={130} r={10} fill="#1F2937" />
              <rect x={444} y={134} width={12} height={24} rx={5} fill="#1F2937" />
            </g>
          </g>
        )}
      </svg>
      {label && (
        <div
          style={{
            marginTop: -70,
            fontFamily,
            fontSize: 34,
            fontWeight: 600,
            color: "rgba(248,250,252,0.88)",
            letterSpacing: 0.3,
            opacity: interpolate(frame, [1.1 * fps, 1.5 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {label}
        </div>
      )}
    </AbsoluteFill>
  );
};

// --- network: the glowing node-graph (neural-net look) -----------------------
const NetworkScene: React.FC<{ nodeCount?: number; label?: string }> = ({ nodeCount = 52, label }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const t = frame / fps;
  const W = width;
  const H = 1000;

  const nodes = Array.from({ length: nodeCount }, (_, i) => {
    const r1 = seededRandom(3 + i * 2.7);
    const r2 = seededRandom(59 + i * 4.3);
    const r3 = seededRandom(23 + i * 8.9);
    const pop = spring({ frame: frame - Math.round((0.1 + i * 0.035) * fps), fps, config: { damping: 12, stiffness: 100 } });
    return {
      x: W * (0.08 + r1 * 0.84) + Math.sin(t * 0.5 + r3 * 10) * 9,
      y: H * (0.09 + r2 * 0.82) + Math.cos(t * 0.42 + r3 * 7) * 7,
      r: 5.5 + r3 * 8,
      color: NODE_PALETTE[i % NODE_PALETTE.length],
      pop,
      pulse: Math.sin(t * 2.1 + i * 1.3),
    };
  });

  // connect each node to its 2 nearest neighbours (deterministic)
  const edges: Array<[number, number]> = [];
  const seen = new Set<string>();
  nodes.forEach((n, i) => {
    const dists = nodes
      .map((m, j) => ({ j, d: (n.x - m.x) ** 2 + (n.y - m.y) ** 2 }))
      .filter((e) => e.j !== i)
      .sort((a, b) => a.d - b.d)
      .slice(0, 2);
    for (const e of dists) {
      const key = i < e.j ? `${i}-${e.j}` : `${e.j}-${i}`;
      if (!seen.has(key)) {
        seen.add(key);
        edges.push(i < e.j ? [i, e.j] : [e.j, i]);
      }
    }
  });

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ overflow: "visible" }}>
        {edges.map(([a, b], k) => (
          <line
            key={k}
            x1={nodes[a].x}
            y1={nodes[a].y}
            x2={nodes[b].x}
            y2={nodes[b].y}
            stroke="rgba(203,213,225,0.13)"
            strokeWidth={1.2}
            opacity={Math.min(nodes[a].pop, nodes[b].pop)}
          />
        ))}
        {nodes.map((n, i) => (
          <GlowNode key={i} cx={n.x} cy={n.y} r={n.r} color={n.color} reveal={n.pop} pulse={n.pulse} />
        ))}
      </svg>
      {label && (
        <div
          style={{
            position: "absolute",
            bottom: 80,
            fontFamily,
            fontSize: 34,
            fontWeight: 600,
            color: "rgba(248,250,252,0.88)",
            opacity: interpolate(frame, [1.2 * fps, 1.6 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {label}
        </div>
      )}
    </AbsoluteFill>
  );
};

// --- chat window: mac chrome, typed question, streaming answer ---------------
const MONO = "'SF Mono', 'Cascadia Code', Menlo, Consolas, monospace";

const ChatWindow: React.FC<{ title?: string; question: string; answer: string; accent: string }> = ({
  title = "Ask AI",
  question,
  answer,
  accent,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const appear = spring({ frame, fps, config: { damping: 14, stiffness: 110 } });

  const typeStart = Math.round(0.5 * fps);
  const charsPerFrame = 30 / fps; // ~30 chars/s typing feel
  const charsShown = Math.max(0, Math.min(question.length, Math.floor((frame - typeStart) * charsPerFrame)));
  const typingDone = charsShown >= question.length;
  const typeEndFrame = typeStart + Math.ceil(question.length / charsPerFrame);

  const thinkFrames = Math.round(0.7 * fps);
  const answerStart = typeEndFrame + thinkFrames;
  const answerWords = answer.split(/\s+/);
  const wordsShown = Math.max(0, Math.floor((frame - answerStart) / Math.max(1, Math.round(0.085 * fps))));
  const shownAnswer = answerWords.slice(0, wordsShown).join(" ");
  const thinking = typingDone && frame >= typeEndFrame && frame < answerStart;

  const cursorOn = Math.floor(frame / (0.4 * fps)) % 2 === 0;

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div
        style={{
          width: 880,
          minHeight: 340,
          borderRadius: 18,
          background: "#0D1526",
          border: "1.5px solid rgba(148,163,184,0.18)",
          boxShadow: `0 34px 90px rgba(0,0,0,0.55), 0 0 60px ${accent}14`,
          overflow: "hidden",
          transform: `scale(${0.92 + appear * 0.08}) translateY(${(1 - appear) * 30}px)`,
          opacity: appear,
        }}
      >
        <div
          style={{
            height: 58,
            background: "#131D33",
            borderBottom: "1px solid rgba(148,163,184,0.14)",
            display: "flex",
            alignItems: "center",
            padding: "0 24px",
            gap: 10,
          }}
        >
          <div style={{ width: 16, height: 16, borderRadius: "50%", background: "#FF5F57" }} />
          <div style={{ width: 16, height: 16, borderRadius: "50%", background: "#FEBC2E" }} />
          <div style={{ width: 16, height: 16, borderRadius: "50%", background: "#28C840" }} />
          <div
            style={{
              flex: 1,
              textAlign: "center",
              fontFamily: MONO,
              fontSize: 24,
              color: "rgba(203,213,225,0.75)",
              marginRight: 68,
            }}
          >
            {title}
          </div>
        </div>
        <div style={{ padding: "34px 38px", fontFamily: MONO, fontSize: 30, lineHeight: 1.65 }}>
          <div style={{ color: "#E2E8F0" }}>
            <span style={{ color: accent, fontWeight: 700 }}>❯ You: </span>
            {question.slice(0, charsShown)}
            {!typingDone && cursorOn && <span style={{ color: accent }}>▌</span>}
          </div>
          {thinking && (
            <div style={{ marginTop: 26, color: "rgba(203,213,225,0.6)" }}>
              {Array.from({ length: 3 }, (_, i) => (
                <span
                  key={i}
                  style={{
                    display: "inline-block",
                    width: 13,
                    height: 13,
                    borderRadius: "50%",
                    background: "rgba(203,213,225,0.6)",
                    marginRight: 10,
                    transform: `translateY(${Math.sin((frame / fps) * 6 + i * 0.9) * 5}px)`,
                  }}
                />
              ))}
            </div>
          )}
          {wordsShown > 0 && (
            <div style={{ marginTop: 26, color: "#CBD5E1" }}>
              <span style={{ color: "#F0B429", fontWeight: 700 }}>✦ AI: </span>
              {shownAnswer}
              {wordsShown < answerWords.length && cursorOn && <span style={{ color: "#F0B429" }}>▌</span>}
            </div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// --- compare: two panels slide in, items stagger ------------------------------
const ComparePanel: React.FC<{
  label: string;
  items: string[];
  color: string;
  fromX: number;
  delayS: number;
}> = ({ label, items, color, fromX, delayS }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - Math.round(delayS * fps), fps, config: { damping: 14, stiffness: 100 } });
  return (
    <div
      style={{
        width: 452,
        borderRadius: 20,
        background: "#0D1526",
        border: `2px solid ${color}55`,
        boxShadow: `0 24px 70px rgba(0,0,0,0.45), 0 0 44px ${color}1A`,
        padding: "30px 32px 34px",
        transform: `translateX(${(1 - s) * fromX}px)`,
        opacity: s,
      }}
    >
      <div
        style={{
          fontFamily,
          fontSize: 33,
          fontWeight: 700,
          color,
          marginBottom: 20,
          textShadow: `0 0 26px ${color}55`,
        }}
      >
        {label}
      </div>
      {items.map((it, i) => {
        const op = interpolate(frame, [(delayS + 0.45 + i * 0.22) * fps, (delayS + 0.75 + i * 0.22) * fps], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
          <div
            key={i}
            style={{
              display: "flex",
              gap: 14,
              alignItems: "flex-start",
              marginTop: i === 0 ? 0 : 16,
              opacity: op,
            }}
          >
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: color, marginTop: 15, flexShrink: 0 }} />
            <div style={{ fontFamily, fontSize: 29, fontWeight: 500, color: "#E2E8F0", lineHeight: 1.4 }}>{it}</div>
          </div>
        );
      })}
    </div>
  );
};

const CompareScene: React.FC<{
  title?: string;
  leftLabel: string;
  leftItems: string[];
  rightLabel: string;
  rightItems: string[];
  accent: string;
}> = ({ title, leftLabel, leftItems, rightLabel, rightItems, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 36 }}>
      {title && (
        <div
          style={{
            fontFamily,
            fontSize: 46,
            fontWeight: 700,
            color: "#F8FAFC",
            textShadow: "0 0 26px rgba(248,250,252,0.2)",
            opacity: interpolate(frame, [0, 0.35 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          }}
        >
          {title}
        </div>
      )}
      <div style={{ display: "flex", gap: 36 }}>
        <ComparePanel label={leftLabel} items={leftItems} color={accent} fromX={-70} delayS={0.15} />
        <ComparePanel label={rightLabel} items={rightItems} color="#F0B429" fromX={70} delayS={0.35} />
      </div>
    </AbsoluteFill>
  );
};

// --- stat: one big number counts up -------------------------------------------
const StatScene: React.FC<{ value: string; label?: string; accent: string }> = ({ value, label, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const m = value.match(/^([^0-9]*)([0-9][0-9,]*(?:\.[0-9]+)?)(.*)$/);
  const target = m ? parseFloat(m[2].replace(/,/g, "")) : 0;
  const decimals = m && m[2].includes(".") ? m[2].split(".")[1].length : 0;
  const hasThousands = m ? m[2].includes(",") : false;
  const progress = interpolate(frame, [0.2 * fps, 1.4 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: (t) => 1 - Math.pow(1 - t, 3),
  });
  const num = (target * progress).toFixed(decimals);
  const shown = m
    ? `${m[1]}${hasThousands ? num.replace(/\B(?=(\d{3})+(?!\d))/g, ",") : num}${m[3]}`
    : value;
  const pop = spring({ frame, fps, config: { damping: 13, stiffness: 90 } });
  return (
    <AbsoluteFill style={{ flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 18 }}>
      <div
        style={{
          fontFamily,
          fontSize: 190,
          fontWeight: 800,
          letterSpacing: -4,
          color: accent,
          transform: `scale(${0.8 + pop * 0.2})`,
          textShadow: `0 0 60px ${accent}66, 0 0 140px ${accent}33`,
        }}
      >
        {shown}
      </div>
      {label && (
        <div
          style={{
            fontFamily,
            fontSize: 36,
            fontWeight: 600,
            letterSpacing: 4,
            textTransform: "uppercase",
            color: "rgba(248,250,252,0.85)",
            opacity: interpolate(frame, [0.9 * fps, 1.3 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {label}
        </div>
      )}
    </AbsoluteFill>
  );
};

// --- diagram: labeled boxes revealed in order, arrows draw between ------------
const DiagramArrow: React.FC<{ vertical?: boolean; draw: number }> = ({ vertical, draw }) => {
  const w = vertical ? 24 : 74;
  const h = vertical ? 64 : 24;
  const lineEnd = vertical ? { x2: 12, y2: 44 } : { x2: 54, y2: 12 };
  return (
    <svg width={w} height={h} style={{ flexShrink: 0 }}>
      <line
        x1={12}
        y1={12}
        {...lineEnd}
        stroke="rgba(226,232,240,0.65)"
        strokeWidth={4}
        strokeLinecap="round"
        pathLength={1}
        strokeDasharray={1}
        strokeDashoffset={1 - draw}
      />
      {draw > 0.95 && (
        <path
          d={vertical ? "M 4 42 L 12 56 L 20 42" : "M 52 4 L 66 12 L 52 20"}
          fill="none"
          stroke="rgba(226,232,240,0.65)"
          strokeWidth={4}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
    </svg>
  );
};

const DiagramScene: React.FC<{ nodes: Array<{ label: string }>; column?: boolean; accent: string }> = ({
  nodes,
  column,
  accent,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const vertical = column ?? nodes.length > 3;
  const stepS = 0.55;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div
        style={{
          display: "flex",
          flexDirection: vertical ? "column" : "row",
          alignItems: "center",
          gap: 18,
          padding: "0 40px",
        }}
      >
        {nodes.map((n, i) => {
          const pop = spring({ frame: frame - Math.round((0.2 + i * stepS) * fps), fps, config: { damping: 12, stiffness: 110 } });
          const draw = interpolate(
            frame,
            [(0.2 + i * stepS + 0.28) * fps, (0.2 + i * stepS + 0.5) * fps],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          return (
            <React.Fragment key={i}>
              {i > 0 && <DiagramArrow vertical={vertical} draw={draw} />}
              <div
                style={{
                  borderRadius: 18,
                  background: "#0E1B33",
                  border: `2.5px solid ${i === nodes.length - 1 ? "#F0B429" : "#5EEAD4"}`,
                  boxShadow: `0 0 30px ${i === nodes.length - 1 ? "rgba(240,180,41,0.25)" : "rgba(94,234,212,0.22)"}`,
                  padding: "22px 34px",
                  transform: `scale(${pop})`,
                  opacity: pop,
                  maxWidth: vertical ? 700 : 320,
                }}
              >
                <div
                  style={{
                    fontFamily,
                    fontSize: 37,
                    fontWeight: 600,
                    color: "#F1F5F9",
                    textAlign: "center",
                    lineHeight: 1.3,
                  }}
                >
                  {n.label}
                </div>
              </div>
            </React.Fragment>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// --- the STAGE: composable line-art props, entities, labels, photo fans ------
// Every icon is stroke line-art in a 100x100 viewBox so it can DRAW ITSELF on.
export const ICON_LIBRARY: Record<string, string[]> = {
  jail: ["M 8 6 H 92", "M 8 94 H 92", "M 15 6 V 94", "M 32.5 6 V 94", "M 50 6 V 94", "M 67.5 6 V 94", "M 85 6 V 94"],
  lock: ["M 32 45 V 30 A 18 18 0 0 1 68 30 V 45",
         "M 26 45 H 74 A 6 6 0 0 1 80 51 V 82 A 6 6 0 0 1 74 88 H 26 A 6 6 0 0 1 20 82 V 51 A 6 6 0 0 1 26 45 Z",
         "M 50 58 a 5 5 0 1 0 0.01 0", "M 50 63 V 74"],
  apple: ["M 50 32 C 30 20 12 34 14 56 C 16 78 34 92 50 86 C 66 92 84 78 86 56 C 88 34 70 20 50 32",
          "M 50 30 Q 52 20 60 14", "M 60 22 Q 74 14 80 22 Q 72 30 60 22"],
  brain: ["M 35 30 A 14 14 0 0 1 62 26 A 13 13 0 0 1 80 40 A 13 13 0 0 1 80 62 A 14 14 0 0 1 60 76 A 14 14 0 0 1 34 70 A 15 15 0 0 1 26 46 A 13 13 0 0 1 35 30",
          "M 42 40 Q 50 44 46 52", "M 58 36 Q 64 44 58 50", "M 50 58 Q 58 60 62 66"],
  person: ["M 50 30 a 12 12 0 1 0 0.01 0", "M 26 84 Q 26 58 50 58 Q 74 58 74 84"],
  photo: ["M 16 20 H 84 V 80 H 16 Z", "M 22 72 L 42 48 L 56 62 L 66 52 L 78 72", "M 66 34 a 7 7 0 1 0 0.01 0"],
  magnifier: ["M 42 24 A 22 22 0 1 0 42.01 24", "M 58 62 L 82 86"],
  cloud: ["M 28 66 A 14 14 0 0 1 30 39 A 18 18 0 0 1 64 33 A 14 14 0 0 1 74 66 Z"],
  chip: ["M 30 30 H 70 V 70 H 30 Z", "M 42 42 H 58 V 58 H 42 Z",
         "M 38 30 V 18", "M 50 30 V 18", "M 62 30 V 18", "M 38 70 V 82", "M 50 70 V 82", "M 62 70 V 82",
         "M 30 38 H 18", "M 30 50 H 18", "M 30 62 H 18", "M 70 38 H 82", "M 70 50 H 82", "M 70 62 H 82"],
  laptop: ["M 24 24 H 76 V 62 H 24 Z", "M 16 70 H 84 L 90 80 H 10 Z"],
  book: ["M 50 26 Q 34 18 18 24 V 74 Q 34 68 50 76 Q 66 68 82 74 V 24 Q 66 18 50 26 V 74"],
  shield: ["M 50 14 L 82 26 V 50 Q 82 76 50 88 Q 18 76 18 50 V 26 Z", "M 36 50 L 46 60 L 66 38"],
  star: ["M 50 14 L 59 38 L 85 38 L 64 53 L 72 78 L 50 63 L 28 78 L 36 53 L 15 38 L 41 38 Z"],
  check: ["M 24 52 L 42 70 L 78 32"],
  cross: ["M 28 28 L 72 72", "M 72 28 L 28 72"],
  arrow: ["M 14 50 H 78", "M 62 34 L 82 50 L 62 66"],
  bulb: ["M 50 16 a 22 22 0 0 1 12 40 q -4 4 -4 10 H 42 q 0 -6 -4 -10 a 22 22 0 0 1 12 -40",
         "M 42 74 H 58", "M 44 82 H 56"],
  bubble: ["M 20 24 H 80 V 62 H 46 L 32 76 V 62 H 20 Z"],
  eye: ["M 14 50 Q 50 20 86 50 Q 50 80 14 50", "M 50 40 a 10 10 0 1 0 0.01 0"],
  globe: ["M 50 16 a 34 34 0 1 0 0.01 0", "M 16 50 H 84", "M 50 16 Q 30 50 50 84", "M 50 16 Q 70 50 50 84"],
  robot: ["M 30 34 H 70 V 68 H 30 Z", "M 42 48 a 3 3 0 1 0 0.01 0", "M 58 48 a 3 3 0 1 0 0.01 0",
          "M 50 34 V 22", "M 50 18 a 4 4 0 1 0 0.01 0", "M 42 60 H 58"],
  clock: ["M 50 14 a 36 36 0 1 0 0.01 0", "M 50 50 V 28", "M 50 50 L 66 58"],
  warning: ["M 50 16 L 88 82 H 12 Z", "M 50 38 V 58", "M 50 66 V 69"],
};

const StagedItem: React.FC<{ el: StagedElement; accent: string }> = ({ el, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const atF = Math.round((el.at ?? 0) * fps);
  const t = frame - atF;
  if (t < 0) return null;

  const enter = el.enter ?? (el.kind === "icon" || el.kind === "path" ? "draw" : "pop");
  const p = spring({ frame: t, fps, config: { damping: 13, stiffness: 110 } });
  const drawP = interpolate(t, [0, 0.7 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const fadeP = interpolate(t, [0, 0.3 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  let opacity = fadeP;
  let tx = 0, ty = 0, sc = 1;
  if (enter === "pop") sc = p;
  else if (enter === "slide-left") tx = -220 * (1 - p);
  else if (enter === "slide-right") tx = 220 * (1 - p);
  else if (enter === "rise") ty = 70 * (1 - p);
  else if (enter === "draw") opacity = 1;

  if (el.until !== undefined) {
    const outT = frame - Math.round(el.until * fps);
    if (outT >= 0) {
      const q = interpolate(outT, [0, 0.35 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
      if (q >= 1) return null;
      opacity *= 1 - q;
      if (el.exit === "drop") ty += 90 * q;
      if (el.exit === "fly-right") tx += 300 * q;
    }
  }

  const wig = el.wiggle ? Math.sin((frame / fps) * 2.4 + el.x) * 2.5 : 0;
  const scale = el.scale ?? 1;
  const color = el.color || "#5EEAD4";

  const style: React.CSSProperties = {
    position: "absolute",
    // CSS percent = relative to the SCENE CANVAS (the top band), not the full frame
    left: `${el.x}%`,
    top: `${el.y}%`,
    transform: `translate(-50%, -50%) translate(${tx}px, ${ty}px) scale(${sc}) rotate(${wig}deg)`,
    opacity,
  };

  if (el.kind === "icon" || el.kind === "path") {
    const paths = el.kind === "icon" ? ICON_LIBRARY[el.icon || ""] || ICON_LIBRARY.star : el.d || [];
    const size = 260 * scale;
    return (
      <div style={style}>
        <svg
          width={size}
          height={size}
          viewBox="0 0 100 100"
          style={{ overflow: "visible", filter: `drop-shadow(0 0 10px ${color}66)` }}
        >
          {paths.map((d, i) => (
            <path
              key={i}
              d={d}
              fill="none"
              stroke={color}
              strokeWidth={4.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              pathLength={1}
              strokeDasharray={1}
              strokeDashoffset={enter === "draw" ? 1 - Math.min(1, Math.max(0, drawP * paths.length - i * 0.6)) : 0}
            />
          ))}
        </svg>
      </div>
    );
  }

  if (el.kind === "entity") {
    return (
      <div
        style={{
          ...style,
          borderRadius: 22,
          background: "#0E1B33",
          border: `2.5px solid ${el.color || accent}`,
          boxShadow: `0 0 34px ${(el.color || accent)}44, 0 18px 50px rgba(0,0,0,0.45)`,
          padding: `${18 * scale}px ${34 * scale}px`,
        }}
      >
        <div style={{ fontFamily, fontSize: 46 * scale, fontWeight: 700, color: "#F8FAFC", whiteSpace: "nowrap" }}>
          {el.name}
        </div>
      </div>
    );
  }

  if (el.kind === "label") {
    return (
      <div
        style={{
          ...style,
          fontFamily,
          fontSize: 40 * scale,
          fontWeight: 800,
          letterSpacing: 5,
          textTransform: "uppercase",
          color,
          whiteSpace: "nowrap",
          textShadow: `0 0 28px ${color}66`,
        }}
      >
        {el.name}
      </div>
    );
  }

  // photos: a fan of framed photo cards popping in one after another
  const cards = Array.from({ length: 6 }, (_, i) => {
    const r1 = seededRandom(11 + i * 3.7 + el.x);
    const r2 = seededRandom(53 + i * 5.1 + el.y);
    const pop = spring({ frame: t - Math.round(i * 0.12 * fps), fps, config: { damping: 12, stiffness: 120 } });
    return { dx: (r1 - 0.5) * 300 * scale, dy: (r2 - 0.5) * 190 * scale, rot: (r1 - 0.5) * 26, pop };
  });
  return (
    <div style={style}>
      {cards.map((c2, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: c2.dx,
            top: c2.dy,
            transform: `translate(-50%, -50%) rotate(${c2.rot}deg) scale(${c2.pop})`,
            opacity: c2.pop,
            width: 170 * scale,
            height: 128 * scale,
            background: "#0E1B33",
            border: "3px solid rgba(248,250,252,0.85)",
            borderRadius: 8,
            boxShadow: "0 14px 34px rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <svg width={90 * scale} height={68 * scale} viewBox="0 0 100 76">
            <path d="M 8 66 L 34 34 L 52 52 L 64 40 L 92 66" fill="none" stroke="#5EEAD4" strokeWidth={5}
                  strokeLinecap="round" strokeLinejoin="round" />
            <circle cx={72} cy={20} r={8} fill="#F0B429" />
          </svg>
        </div>
      ))}
    </div>
  );
};

const StagedScene: React.FC<{ elements: StagedElement[]; accent: string }> = ({ elements, accent }) => (
  <AbsoluteFill>
    {elements.map((el, i) => (
      <StagedItem key={i} el={el} accent={accent} />
    ))}
  </AbsoluteFill>
);

// --- the canvas: backdrop -> content -> vignette ------------------------------
export const SceneCanvas: React.FC<{ scene: Scene; accent: string }> = ({ scene, accent }) => {
  const c = scene.content;
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <SceneBackdrop bg={scene.background} />
      {c.type === "kinetic_text" && (
        <KineticText
          lines={c.lines}
          accentWords={c.accentWords}
          accent={c.accentColor || accent}
          subtitle={c.subtitle}
          fontSize={c.fontSize}
        />
      )}
      {c.type === "icon_scene" && (
        <IconScene icon={c.icon} overlay={c.overlay} burst={c.burst} badge={c.badge} label={c.label} accent={accent} />
      )}
      {c.type === "network" && <NetworkScene nodeCount={c.nodeCount} label={c.label} />}
      {c.type === "chat_window" && (
        <ChatWindow title={c.title} question={c.question} answer={c.answer} accent={accent} />
      )}
      {c.type === "compare" && (
        <CompareScene
          title={c.title}
          leftLabel={c.leftLabel}
          leftItems={c.leftItems}
          rightLabel={c.rightLabel}
          rightItems={c.rightItems}
          accent={accent}
        />
      )}
      {c.type === "stat" && <StatScene value={c.value} label={c.label} accent={accent} />}
      {c.type === "diagram" && <DiagramScene nodes={c.nodes} column={c.column} accent={accent} />}
      {c.type === "staged" && <StagedScene elements={c.elements} accent={accent} />}
      <Vignette />
    </AbsoluteFill>
  );
};
