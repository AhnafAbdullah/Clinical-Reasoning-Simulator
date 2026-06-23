"use client";

import { motion } from "framer-motion";

/**
 * A stylised doctor's room rendered entirely as SVG (no binary assets, so it's
 * crisp at any size and themeable). This component is purely presentational:
 * every element that should move carries a `data-anim` tag, and the cinematic
 * engine (lib/cinematics) drives it procedurally. With the engine off (SSR /
 * reduced motion) it renders as a calm static scene — motes stay invisible.
 */
export function ClinicScene({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 1600 900"
      preserveAspectRatio="xMidYMid slice"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <SceneDefs />

      {/* Static base — never moves, so camera/parallax can't reveal edge gaps. */}
      <rect x="-80" y="-80" width="1760" height="800" fill="url(#wall)" />
      <rect y="640" width="1600" height="320" fill="url(#floor)" />
      <rect y="632" width="1600" height="12" fill="#c2a14a" opacity="0.5" />

      {/* Far layer: things on the back wall */}
      <g data-anim="layer-far">
        <Window />
        <Clock />
        <EyeChart />
      </g>

      {/* Mid layer: furniture on the floor */}
      <g data-anim="layer-mid">
        <Couch />
        <Desk />
        <Plant />
      </g>

      {/* Near layer: living warm light + drifting dust */}
      <g data-anim="layer-near">
        <rect data-anim="light" x="-80" y="-80" width="1760" height="1060" fill="url(#glow)" opacity="0.45" />
        {MOTES.map((m, i) => (
          <circle key={i} data-anim="mote" cx={m.x} cy={m.y} r={m.r} fill="#f3e6c2" opacity="0" />
        ))}
      </g>

      {/* Atmospheric depth + foreground vignette (static overlays) */}
      <rect data-anim="fog" width="1600" height="900" fill="url(#fog)" opacity="0.22" />
      <rect width="1600" height="900" fill="url(#vignette)" />
    </svg>
  );
}

const MOTES = [
  { x: 180, y: 280, r: 3 }, { x: 300, y: 420, r: 2 }, { x: 420, y: 320, r: 3.5 },
  { x: 250, y: 560, r: 2.5 }, { x: 480, y: 240, r: 2 }, { x: 150, y: 640, r: 3 },
  { x: 700, y: 360, r: 2.5 }, { x: 900, y: 500, r: 2 }, { x: 1050, y: 300, r: 3 },
  { x: 1250, y: 460, r: 2.5 }, { x: 1400, y: 360, r: 2 }, { x: 820, y: 620, r: 3 },
  { x: 600, y: 520, r: 2 }, { x: 1150, y: 600, r: 2.5 }, { x: 360, y: 680, r: 2 },
  { x: 980, y: 680, r: 3 },
];

function SceneDefs() {
  return (
    <defs>
      <linearGradient id="wall" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#21304e" />
        <stop offset="1" stopColor="#172238" />
      </linearGradient>
      <linearGradient id="daylight" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#bcdcf4" />
        <stop offset="1" stopColor="#7fb4dd" />
      </linearGradient>
      <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#2a3a5c" />
        <stop offset="1" stopColor="#1d2840" />
      </linearGradient>
      <radialGradient id="glow" cx="0.5" cy="0.4" r="0.7">
        <stop offset="0" stopColor="#c2a14a" stopOpacity="0.30" />
        <stop offset="1" stopColor="#c2a14a" stopOpacity="0" />
      </radialGradient>
      {/* Atmospheric fog — cool haze pooling toward the floor for depth. */}
      <linearGradient id="fog" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#8fb6dd" stopOpacity="0" />
        <stop offset="0.7" stopColor="#7fa6cf" stopOpacity="0.05" />
        <stop offset="1" stopColor="#6f96c2" stopOpacity="0.16" />
      </linearGradient>
      {/* Foreground vignette — darkens the edges so the centre reads as nearer. */}
      <radialGradient id="vignette" cx="0.5" cy="0.5" r="0.75">
        <stop offset="0.55" stopColor="#0b1224" stopOpacity="0" />
        <stop offset="1" stopColor="#0b1224" stopOpacity="0.45" />
      </radialGradient>
    </defs>
  );
}

/* ── Scene props ──────────────────────────────────────────────────────────── */

function Window() {
  return (
    <g transform="translate(120 120)">
      <rect width="420" height="320" rx="10" fill="#0f1830" />
      <rect x="12" y="12" width="396" height="296" rx="6" fill="url(#daylight)" />
      {Array.from({ length: 7 }).map((_, i) => (
        <rect key={i} x="12" y={12 + i * 42} width="396" height="10" fill="#0f1830" opacity="0.18" />
      ))}
      <rect x="-8" y="312" width="436" height="14" rx="4" fill="#c2a14a" />
    </g>
  );
}

function Clock() {
  return (
    <g transform="translate(840 150)">
      <circle r="48" fill="#0f1830" stroke="#c2a14a" strokeWidth="3" />
      <circle r="4" fill="#dec987" />
      <line x1="0" y1="0" x2="0" y2="-30" stroke="#dec987" strokeWidth="3" />
      <line x1="0" y1="0" x2="22" y2="6" stroke="#dec987" strokeWidth="3" />
    </g>
  );
}

function EyeChart() {
  return (
    <g transform="translate(1040 150)">
      <rect width="150" height="200" rx="8" fill="#f7f2e7" />
      <rect x="10" y="10" width="130" height="180" rx="4" fill="#fffdf8" />
      <text x="75" y="60" textAnchor="middle" fontFamily="Georgia, serif" fontWeight="700" fontSize="42" fill="#1e2a44">E</text>
      <text x="75" y="100" textAnchor="middle" fontFamily="Georgia, serif" fontSize="26" fill="#1e2a44">F P</text>
      <text x="75" y="134" textAnchor="middle" fontFamily="Georgia, serif" fontSize="18" fill="#34466b">T O Z</text>
      <text x="75" y="162" textAnchor="middle" fontFamily="Georgia, serif" fontSize="12" fill="#56607a">L P E D</text>
    </g>
  );
}

function Couch() {
  return (
    <g transform="translate(1140 470)">
      <ellipse cx="180" cy="232" rx="200" ry="18" fill="#000" opacity="0.22" />
      <rect width="360" height="150" rx="16" fill="#243352" />
      <rect width="360" height="46" rx="16" fill="#2f456b" />
      <rect width="150" height="40" rx="12" fill="#34466b" />
      <rect y="150" width="22" height="80" fill="#1a2236" />
      <rect x="338" y="150" width="22" height="80" fill="#1a2236" />
    </g>
  );
}

function Desk() {
  return (
    <g transform="translate(150 560)">
      <ellipse cx="260" cy="210" rx="290" ry="16" fill="#000" opacity="0.22" />
      <rect width="520" height="40" rx="8" fill="#3a2c1e" />
      <rect width="520" height="6" rx="3" fill="#5a4632" opacity="0.7" />
      <rect y="36" width="40" height="170" fill="#2e2418" />
      <rect x="480" y="36" width="40" height="170" fill="#2e2418" />
      <rect x="60" y="-46" width="120" height="56" rx="6" fill="#f7f2e7" />
      <g transform="translate(360 -120)">
        <rect x="-6" y="80" width="60" height="10" rx="4" fill="#c2a14a" />
        <line x1="24" y1="80" x2="24" y2="36" stroke="#c2a14a" strokeWidth="6" />
        <path d="M24 36 L60 6 L78 22 L42 52 Z" fill="#dec987" />
        <circle cx="60" cy="14" r="40" fill="url(#glow)" />
      </g>
    </g>
  );
}

function Plant() {
  return (
    <g transform="translate(720 470)">
      <ellipse cx="0" cy="172" rx="44" ry="12" fill="#000" opacity="0.22" />
      <rect x="-26" y="120" width="52" height="50" rx="6" fill="#c2a14a" />
      <path d="M0 120 C-40 60 -30 10 0 0 C30 10 40 60 0 120 Z" fill="#2f6e55" />
      <path d="M0 120 C-10 70 -6 30 0 10 C6 30 10 70 0 120 Z" fill="#3c8a6c" />
    </g>
  );
}

/**
 * A seated patient that varies by gender, age bracket and affect. When `alive`,
 * the cinematic engine drives breathing, head motion, blinks, saccades and a
 * speech-energy mouth via the `data-anim` tags below. Static otherwise.
 */
export function PatientFigure({
  gender = "",
  age = null,
  affect = "calm",
  className = "",
  alive = false,
}: {
  gender?: string;
  age?: number | null;
  affect?: string;
  className?: string;
  alive?: boolean;
}) {
  const female = gender.toLowerCase().startsWith("f");
  const bracket = age == null ? "adult" : age < 16 ? "child" : age >= 65 ? "elderly" : "adult";
  const hair = bracket === "elderly" ? "#c9c6bd" : female ? "#3a2a1e" : "#2a2118";
  const worried = affect === "anxious" || affect === "in_pain";
  const sweaty = affect === "in_pain" || affect === "breathless";
  const drowsy = affect === "drowsy";
  const skin = sweaty ? "#e9c8a3" : "#edc39a";

  const mouth =
    affect === "in_pain"
      ? <ellipse cx="140" cy="176" rx="9" ry="7" fill="#7a3b32" />
      : affect === "breathless"
        ? <ellipse cx="140" cy="175" rx="6" ry="6" fill="#7a3b32" />
        : affect === "anxious"
          ? <path d="M127 177 Q140 169 153 177" stroke="#9c6b3f" strokeWidth="3" fill="none" strokeLinecap="round" />
          : affect === "drowsy" || affect === "stoic"
            ? <path d="M127 175 L153 175" stroke="#9c6b3f" strokeWidth="3" strokeLinecap="round" />
            : <path d="M128 172 Q140 180 152 172" stroke="#9c6b3f" strokeWidth="3" fill="none" strokeLinecap="round" />;

  return (
    <svg className={className} viewBox="0 0 280 360" xmlns="http://www.w3.org/2000/svg" aria-hidden>
      <defs>
        <linearGradient id="coat" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#eef2f7" />
          <stop offset="1" stopColor="#d7deea" />
        </linearGradient>
      </defs>
      <ellipse cx="140" cy="348" rx="92" ry="14" fill="#000" opacity="0.18" />

      <g transform={bracket === "child" ? "translate(140 360) scale(0.84) translate(-140 -360)" : undefined}>
        {/* torso — breathes from the chest (engine scales + lifts it) */}
        <g data-anim="chest">
          <path d="M52 360 C52 250 86 214 140 214 C194 214 228 250 228 360 Z" fill="url(#coat)" />
          <path d="M140 214 L140 360" stroke="#c2a14a" strokeWidth="3" opacity="0.6" />
        </g>

        {/* neck + head — engine translates/rotates this; inner g keeps elderly lean */}
        <g data-anim="head">
          <g transform={bracket === "elderly" ? "translate(6 4)" : undefined}>
            <rect x="124" y="176" width="32" height="40" rx="14" fill="#e3b58e" />
            {female && <path d="M92 150 C88 210 100 240 116 244 L116 150 Z" fill={hair} />}
            {female && <path d="M188 150 C192 210 180 240 164 244 L164 150 Z" fill={hair} />}
            <circle cx="140" cy="150" r="46" fill={skin} />
            <path d="M96 146 C96 96 184 96 184 146 C184 120 96 120 96 146 Z" fill={hair} />

            {/* brows */}
            {worried ? (
              <>
                <path d="M116 138 L132 134" stroke="#7a5a3a" strokeWidth="3" strokeLinecap="round" />
                <path d="M164 138 L148 134" stroke="#7a5a3a" strokeWidth="3" strokeLinecap="round" />
              </>
            ) : (
              <>
                <path d="M118 136 L132 136" stroke="#7a5a3a" strokeWidth="3" strokeLinecap="round" />
                <path d="M148 136 L162 136" stroke="#7a5a3a" strokeWidth="3" strokeLinecap="round" />
              </>
            )}

            {/* eyes */}
            {drowsy ? (
              <>
                <path d="M118 150 Q124 154 130 150" stroke="#1e2a44" strokeWidth="3" fill="none" strokeLinecap="round" />
                <path d="M150 150 Q156 154 162 150" stroke="#1e2a44" strokeWidth="3" fill="none" strokeLinecap="round" />
              </>
            ) : (
              <>
                {/* pupils flick with idle saccades */}
                <g data-anim="pupils">
                  <circle cx="124" cy="150" r="5" fill="#1e2a44" />
                  <circle cx="156" cy="150" r="5" fill="#1e2a44" />
                </g>
                {/* eyelids — engine blinks these (start open: scaleY 0) */}
                {alive && (
                  <>
                    <rect
                      data-anim="eyelid" data-px="124" data-py="140"
                      x="116" y="140" width="16" height="14" rx="5" fill={skin}
                      transform="translate(124 140) scale(1 0) translate(-124 -140)"
                    />
                    <rect
                      data-anim="eyelid" data-px="156" data-py="140"
                      x="148" y="140" width="16" height="14" rx="5" fill={skin}
                      transform="translate(156 140) scale(1 0) translate(-156 -140)"
                    />
                  </>
                )}
              </>
            )}

            {/* elderly glasses */}
            {bracket === "elderly" && (
              <g stroke="#56607a" strokeWidth="2.5" fill="none">
                <circle cx="124" cy="150" r="11" />
                <circle cx="156" cy="150" r="11" />
                <path d="M135 150 L145 150" />
              </g>
            )}

            {/* mouth — resting affect shape; engine cross-fades to the talking
                ellipse and drives its opening from speech energy */}
            <g data-anim="mouth-rest">{mouth}</g>
            {alive && <ellipse data-anim="mouth-talk" cx="140" cy="176" rx="7" ry="1" fill="#7a3b32" opacity="0" />}

            {sweaty && <path d="M182 132 q-5 9 0 13 q5 -4 0 -13" fill="#bfddf1" opacity="0.9" />}
          </g>
        </g>
      </g>
    </svg>
  );
}

/** The patient's words appear here, typing in token-by-token. */
export function Mindbox({ text, typing }: { text: string; typing?: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 260, damping: 24 }}
      className="relative max-w-md rounded-2xl border border-line bg-cream-card/95 p-4 text-navy shadow-lift backdrop-blur"
    >
      <span className="gold-strip mb-2 w-8" />
      <p className="text-[15px] leading-relaxed">
        {text}
        {typing && <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-navy align-middle" />}
      </p>
      <span className="absolute -bottom-2 left-10 h-4 w-4 rotate-45 border-b border-r border-line bg-cream-card/95" aria-hidden />
    </motion.div>
  );
}
