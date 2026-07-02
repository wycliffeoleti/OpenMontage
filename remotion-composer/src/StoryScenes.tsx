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
    };

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
      <Vignette />
    </AbsoluteFill>
  );
};
