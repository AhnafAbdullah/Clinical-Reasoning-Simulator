"use client";

import { motion } from "framer-motion";

/**
 * A stylised doctor's room rendered entirely as SVG (no binary assets, so it's
 * crisp at any size and themeable). The cinematic un-blurs and scales this.
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
      </defs>

      {/* Walls + floor */}
      <rect width="1600" height="640" fill="url(#wall)" />
      <rect y="640" width="1600" height="260" fill="url(#floor)" />
      <rect y="632" width="1600" height="12" fill="#c2a14a" opacity="0.5" />

      {/* Window with daylight + blinds + gold sill */}
      <g transform="translate(120 120)">
        <rect width="420" height="320" rx="10" fill="#0f1830" />
        <rect x="12" y="12" width="396" height="296" rx="6" fill="url(#daylight)" />
        {Array.from({ length: 7 }).map((_, i) => (
          <rect key={i} x="12" y={12 + i * 42} width="396" height="10" fill="#0f1830" opacity="0.18" />
        ))}
        <rect x="-8" y="312" width="436" height="14" rx="4" fill="#c2a14a" />
      </g>

      {/* Wall clock */}
      <g transform="translate(840 150)">
        <circle r="48" fill="#0f1830" stroke="#c2a14a" strokeWidth="3" />
        <circle r="4" fill="#dec987" />
        <line x1="0" y1="0" x2="0" y2="-30" stroke="#dec987" strokeWidth="3" />
        <line x1="0" y1="0" x2="22" y2="6" stroke="#dec987" strokeWidth="3" />
      </g>

      {/* Framed eye chart */}
      <g transform="translate(1040 150)">
        <rect width="150" height="200" rx="8" fill="#f7f2e7" />
        <rect x="10" y="10" width="130" height="180" rx="4" fill="#fffdf8" />
        <text x="75" y="60" textAnchor="middle" fontFamily="Georgia, serif" fontWeight="700" fontSize="42" fill="#1e2a44">E</text>
        <text x="75" y="100" textAnchor="middle" fontFamily="Georgia, serif" fontSize="26" fill="#1e2a44">F P</text>
        <text x="75" y="134" textAnchor="middle" fontFamily="Georgia, serif" fontSize="18" fill="#34466b">T O Z</text>
        <text x="75" y="162" textAnchor="middle" fontFamily="Georgia, serif" fontSize="12" fill="#56607a">L P E D</text>
      </g>

      {/* Examination couch */}
      <g transform="translate(1140 470)">
        <rect width="360" height="150" rx="16" fill="#243352" />
        <rect width="360" height="46" rx="16" fill="#2f456b" />
        <rect width="150" height="40" rx="12" fill="#34466b" />
        <rect y="150" width="22" height="80" fill="#1a2236" />
        <rect x="338" y="150" width="22" height="80" fill="#1a2236" />
      </g>

      {/* Desk with lamp + paper */}
      <g transform="translate(150 560)">
        <rect width="520" height="40" rx="8" fill="#3a2c1e" />
        <rect y="36" width="40" height="170" fill="#2e2418" />
        <rect x="480" y="36" width="40" height="170" fill="#2e2418" />
        <rect x="60" y="-46" width="120" height="56" rx="6" fill="#f7f2e7" />
        {/* desk lamp */}
        <g transform="translate(360 -120)">
          <rect x="-6" y="80" width="60" height="10" rx="4" fill="#c2a14a" />
          <line x1="24" y1="80" x2="24" y2="36" stroke="#c2a14a" strokeWidth="6" />
          <path d="M24 36 L60 6 L78 22 L42 52 Z" fill="#dec987" />
          <circle cx="60" cy="14" r="40" fill="url(#glow)" />
        </g>
      </g>

      {/* Potted plant */}
      <g transform="translate(720 470)">
        <rect x="-26" y="120" width="52" height="50" rx="6" fill="#c2a14a" />
        <path d="M0 120 C-40 60 -30 10 0 0 C30 10 40 60 0 120 Z" fill="#2f6e55" />
        <path d="M0 120 C-10 70 -6 30 0 10 C6 30 10 70 0 120 Z" fill="#3c8a6c" />
      </g>

      {/* warm ambient glow */}
      <rect width="1600" height="900" fill="url(#glow)" opacity="0.5" />
    </svg>
  );
}

/**
 * A seated patient that varies by gender, age bracket and affect (Phase B).
 * Still a single parameterised SVG — no binary assets.
 */
export function PatientFigure({
  gender = "",
  age = null,
  affect = "calm",
  className = "",
}: {
  gender?: string;
  age?: number | null;
  affect?: string;
  className?: string;
}) {
  const female = gender.toLowerCase().startsWith("f");
  const bracket = age == null ? "adult" : age < 16 ? "child" : age >= 65 ? "elderly" : "adult";
  const hair = bracket === "elderly" ? "#c9c6bd" : female ? "#3a2a1e" : "#2a2118";
  const worried = affect === "anxious" || affect === "in_pain";
  const sweaty = affect === "in_pain" || affect === "breathless";
  const drowsy = affect === "drowsy";

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
        {/* body */}
        <path d="M52 360 C52 250 86 214 140 214 C194 214 228 250 228 360 Z" fill="url(#coat)" />
        <path d="M140 214 L140 360" stroke="#c2a14a" strokeWidth="3" opacity="0.6" />

        {/* neck + head (elderly leans slightly forward) */}
        <g transform={bracket === "elderly" ? "translate(6 4)" : undefined}>
          <rect x="124" y="176" width="32" height="40" rx="14" fill="#e3b58e" />
          {/* female: longer hair framing the face */}
          {female && <path d="M92 150 C88 210 100 240 116 244 L116 150 Z" fill={hair} />}
          {female && <path d="M188 150 C192 210 180 240 164 244 L164 150 Z" fill={hair} />}
          <circle cx="140" cy="150" r="46" fill={sweaty ? "#e9c8a3" : "#edc39a"} />
          {/* hair cap */}
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

          {/* eyes (drowsy = half-closed) */}
          {drowsy ? (
            <>
              <path d="M118 150 Q124 154 130 150" stroke="#1e2a44" strokeWidth="3" fill="none" strokeLinecap="round" />
              <path d="M150 150 Q156 154 162 150" stroke="#1e2a44" strokeWidth="3" fill="none" strokeLinecap="round" />
            </>
          ) : (
            <>
              <circle cx="124" cy="150" r="5" fill="#1e2a44" />
              <circle cx="156" cy="150" r="5" fill="#1e2a44" />
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

          {mouth}

          {/* sweat for pain/breathlessness */}
          {sweaty && <path d="M182 132 q-5 9 0 13 q5 -4 0 -13" fill="#bfddf1" opacity="0.9" />}
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
      {/* little tail pointing toward the patient */}
      <span className="absolute -bottom-2 left-10 h-4 w-4 rotate-45 border-b border-r border-line bg-cream-card/95" aria-hidden />
    </motion.div>
  );
}
