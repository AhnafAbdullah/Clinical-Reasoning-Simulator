"use client";

import { useEffect, useRef, type RefObject } from "react";

import { clamp, fbm, Spring, useRaf } from "@/lib/anim";

/**
 * The cinematic engine. A single rAF loop reads pointer + speech state and
 * procedurally drives the whole scene by mutating SVG attributes directly —
 * camera, parallax layers, lighting, dust, and the patient's breathing, blinks,
 * saccades, head motion and mouth. Elements opt in with `data-anim="…"` tags so
 * the presentational components stay dumb.
 *
 * Disney principles are baked into the maths: ease in/out (springs), overlapping
 * action (phase-lagged body parts), follow-through (under-damped head spring),
 * anticipation (a counter-kick before head moves) and settling (critically
 * damped pointer springs). Speech makes breathing recede and the head react.
 */

interface Els {
  far: Element | null;
  mid: Element | null;
  near: Element | null;
  light: Element | null;
  fog: Element | null;
  motes: Element[];
  moteBase: { x: number; y: number }[];
  chest: Element | null;
  head: Element | null;
  eyelids: { el: Element; px: number; py: number }[];
  pupils: Element | null;
  mouthRest: Element | null;
  mouthTalk: Element | null;
}

interface State {
  mx: number;
  my: number;
  camX: Spring;
  camY: Spring;
  breath: number;
  speakBlend: number;
  headRot: Spring;
  headX: Spring;
  headRotTgt: number;
  headXTgt: number;
  headT: number;
  blinkT: number;
  blinkState: number; // 0 idle, 1 first blink, 2 second (double)
  blinkPhase: number;
  sacX: Spring;
  sacY: Spring;
  sacXTgt: number;
  sacYTgt: number;
  sacT: number;
  mouth: Spring;
  els: Els | null;
}

function rand(lo: number, hi: number): number {
  return lo + Math.random() * (hi - lo);
}

export function useCinematics(opts: {
  enabled: boolean;
  sceneRef: RefObject<HTMLDivElement | null>;
  patientRef: RefObject<HTMLDivElement | null>;
  speakingRef: RefObject<boolean>;
  energyRef: RefObject<number>;
  /** Changes when the patient's rendered structure changes, so we re-query. */
  revision?: string;
}): void {
  const { enabled, sceneRef, patientRef, speakingRef, energyRef, revision } = opts;

  const stateRef = useRef<State | null>(null);
  if (!stateRef.current) {
    stateRef.current = {
      mx: 0,
      my: 0,
      camX: new Spring(0, 32, 1), // critically damped → settles after the pointer
      camY: new Spring(0, 32, 1),
      breath: 0,
      speakBlend: 0,
      headRot: new Spring(0, 46, 0.62), // under-damped → follow-through
      headX: new Spring(0, 46, 0.62),
      headRotTgt: 0,
      headXTgt: 0,
      headT: 1.5,
      blinkT: 2,
      blinkState: 0,
      blinkPhase: 0,
      sacX: new Spring(0, 220, 1), // stiff → ballistic eye flicks
      sacY: new Spring(0, 220, 1),
      sacXTgt: 0,
      sacYTgt: 0,
      sacT: 1,
      mouth: new Spring(0, 90, 1),
      els: null,
    };
  }

  // Pointer feeds the camera target; the springs do the settling.
  useEffect(() => {
    if (!enabled) return;
    const S = stateRef.current;
    if (!S) return;
    const onMove = (e: PointerEvent) => {
      S.mx = (e.clientX / window.innerWidth) * 2 - 1;
      S.my = (e.clientY / window.innerHeight) * 2 - 1;
    };
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
  }, [enabled]);

  // Re-query the DOM when we toggle on or the patient's structure changes
  // (e.g. data loads and a drowsy patient drops its eyelids/pupils nodes).
  useEffect(() => {
    if (stateRef.current) stateRef.current.els = null;
  }, [enabled, revision]);

  useRaf(enabled, (t, dt) => {
    const S = stateRef.current;
    if (!S) return;

    // ── Cache tagged elements on the first frame they're available ──────────
    if (!S.els) {
      const scene = sceneRef.current;
      const pat = patientRef.current;
      if (!scene || !pat) return;
      const motes = Array.from(scene.querySelectorAll('[data-anim="mote"]'));
      S.els = {
        far: scene.querySelector('[data-anim="layer-far"]'),
        mid: scene.querySelector('[data-anim="layer-mid"]'),
        near: scene.querySelector('[data-anim="layer-near"]'),
        light: scene.querySelector('[data-anim="light"]'),
        fog: scene.querySelector('[data-anim="fog"]'),
        motes,
        moteBase: motes.map((m) => ({
          x: parseFloat(m.getAttribute("cx") || "0"),
          y: parseFloat(m.getAttribute("cy") || "0"),
        })),
        chest: pat.querySelector('[data-anim="chest"]'),
        head: pat.querySelector('[data-anim="head"]'),
        eyelids: Array.from(pat.querySelectorAll('[data-anim="eyelid"]')).map((el) => ({
          el,
          px: parseFloat(el.getAttribute("data-px") || "0"),
          py: parseFloat(el.getAttribute("data-py") || "0"),
        })),
        pupils: pat.querySelector('[data-anim="pupils"]'),
        mouthRest: pat.querySelector('[data-anim="mouth-rest"]'),
        mouthTalk: pat.querySelector('[data-anim="mouth-talk"]'),
      };
    }
    const E = S.els;

    // Self-heal if a cached node detached (a re-render replaced the subtree).
    if (E.head && !E.head.isConnected) {
      S.els = null;
      return;
    }

    // ── Speech blend (smoothed) — gates breathing/mouth/head reactions ──────
    const speakTgt = speakingRef.current ? 1 : 0;
    S.speakBlend += (speakTgt - S.speakBlend) * Math.min(1, dt * 6);
    const sb = S.speakBlend;

    // ── Camera: handheld drift + breathing + pointer settle ─────────────────
    const driftX = 4.5 * fbm(t * 0.13, 1) + 2.2 * fbm(t * 0.41, 7);
    const driftY = 3.2 * fbm(t * 0.11, 3) + 1.6 * fbm(t * 0.37, 9);
    const camBreath = (1.8 + 0.7 * fbm(t * 0.05, 15)) * Math.sin(t * 0.55); // ~1–3px
    S.camX.step(S.mx * 10, dt);
    S.camY.step(S.my * 7, dt);
    const camX = driftX + S.camX.value;
    const camY = driftY + camBreath + S.camY.value;
    if (sceneRef.current) {
      sceneRef.current.style.transform = `translate3d(${camX.toFixed(2)}px, ${camY.toFixed(2)}px, 0) scale(1.06)`;
    }
    // Patient sits nearer → tracks the camera a touch more (parallax).
    if (patientRef.current) {
      patientRef.current.style.transform = `translate3d(${(camX * 1.25).toFixed(2)}px, ${(camY * 1.2).toFixed(2)}px, 0)`;
    }

    // ── Intra-scene parallax: layers drift opposite the pointer, by depth ───
    const px = S.camX.value;
    const py = S.camY.value;
    if (E.far) E.far.setAttribute("transform", `translate(${(-px * 0.3 + 2 * fbm(t * 0.08, 21)).toFixed(2)} ${(-py * 0.3 + 1.5 * fbm(t * 0.07, 22)).toFixed(2)})`);
    if (E.mid) E.mid.setAttribute("transform", `translate(${(-px * 0.8 + 3 * fbm(t * 0.1, 23)).toFixed(2)} ${(-py * 0.8 + 2.2 * fbm(t * 0.09, 24)).toFixed(2)})`);
    if (E.near) E.near.setAttribute("transform", `translate(${(-px * 1.6 + 4 * fbm(t * 0.12, 25)).toFixed(2)} ${(-py * 1.6 + 3 * fbm(t * 0.11, 26)).toFixed(2)})`);

    // ── Living light + atmospheric fog ──────────────────────────────────────
    if (E.light) E.light.setAttribute("opacity", (0.42 + 0.14 * fbm(t * 0.06, 51)).toFixed(3));
    if (E.fog) E.fog.setAttribute("opacity", (0.2 + 0.07 * fbm(t * 0.045, 53)).toFixed(3));

    // ── Dust motes: slow rise + lateral noise drift, wrapping around ────────
    for (let i = 0; i < E.motes.length; i++) {
      const base = E.moteBase[i];
      const span = 360;
      const y = base.y - ((t * (5 + (i % 4) * 2) + i * 47) % span);
      const wy = y < -20 ? y + span : y;
      const x = base.x + 18 * fbm(t * 0.2, 60 + i);
      const op = 0.06 + 0.26 * (0.5 + 0.5 * Math.sin(t * 0.6 + i * 1.7));
      const m = E.motes[i];
      m.setAttribute("cx", x.toFixed(1));
      m.setAttribute("cy", wy.toFixed(1));
      m.setAttribute("opacity", op.toFixed(2));
    }

    // ── Breathing: non-periodic rate, asymmetric inhale/exhale, recedes on speech
    const breathAmp = 1 - 0.55 * sb;
    S.breath += dt * (0.85 + 0.22 * fbm(t * 0.05, 31)); // wobbling rate ≈ 7s period
    const rawB = Math.sin(S.breath);
    const breath = rawB >= 0 ? Math.pow(rawB, 0.85) : -Math.pow(-rawB, 1.2); // inhale quicker
    if (E.chest) {
      const sc = (1 + (0.008 + 0.012 * ((breath + 1) / 2)) * breathAmp).toFixed(4);
      const rise = (-breath * 1.3 * breathAmp).toFixed(2);
      E.chest.setAttribute("transform", `translate(0 ${rise}) translate(140 360) scale(${sc}) translate(-140 -360)`);
    }

    // ── Head: breath follow (lagged = overlapping), idle micro-moves, sway,
    //         anticipation kick, plus a subtle nod while speaking ────────────
    const breathLag = Math.sin(S.breath - 0.7);
    S.headT -= dt;
    if (S.headT <= 0) {
      S.headRotTgt = rand(-1.3, 1.3);
      S.headXTgt = rand(-1.6, 1.6);
      S.headT = rand(2, 5.5);
      S.headRot.kick(-Math.sign(S.headRotTgt - S.headRot.value) * 6); // anticipation
    }
    S.headRot.step(S.headRotTgt, dt);
    S.headX.step(S.headXTgt, dt);
    const headRot = S.headRot.value + 0.6 * fbm(t * 0.12, 41) + sb * 0.8 * Math.sin(t * 2.6);
    const headX = S.headX.value + 0.6 * fbm(t * 0.1, 43);
    const headY = -breathLag * 1.1 * breathAmp + sb * 0.4 * Math.sin(t * 2.6 + 0.5);
    if (E.head) E.head.setAttribute("transform", `translate(${headX.toFixed(2)} ${headY.toFixed(2)}) rotate(${headRot.toFixed(2)} 140 196)`);

    // ── Blinks: irregular 3–8s, occasional double, fast close / slower open ─
    if (S.blinkState === 0) {
      S.blinkT -= dt;
      if (S.blinkT <= 0) {
        S.blinkState = 1;
        S.blinkPhase = 0;
      }
    }
    let lid = 0;
    if (S.blinkState > 0) {
      S.blinkPhase += dt / 0.13;
      lid = Math.sin(Math.min(S.blinkPhase, 1) * Math.PI); // 0→1→0
      if (S.blinkPhase >= 1) {
        if (S.blinkState === 1 && Math.random() < 0.22) {
          S.blinkState = 2; // double blink
          S.blinkPhase = -0.25; // brief gap before the second
        } else {
          S.blinkState = 0;
          S.blinkT = rand(3, 8);
        }
      }
    }
    for (const { el, px: ex, py: ey } of E.eyelids) {
      el.setAttribute("transform", `translate(${ex} ${ey}) scale(1 ${clamp(lid, 0, 1).toFixed(3)}) translate(${-ex} ${-ey})`);
    }

    // ── Eye saccades: small ballistic flicks while idle ─────────────────────
    S.sacT -= dt;
    if (S.sacT <= 0) {
      S.sacXTgt = rand(-1.6, 1.6);
      S.sacYTgt = rand(-0.8, 0.8);
      S.sacT = rand(0.5, 2.4);
    }
    S.sacX.step(S.sacXTgt, dt);
    S.sacY.step(S.sacYTgt, dt);
    if (E.pupils) E.pupils.setAttribute("transform", `translate(${S.sacX.value.toFixed(2)} ${S.sacY.value.toFixed(2)})`);

    // ── Mouth: driven by speech energy (boundary spikes + jitter), not a timer
    const spike = energyRef.current ?? 0;
    if (energyRef.current !== null && energyRef.current !== undefined) {
      (energyRef as { current: number }).current = spike * Math.exp(-dt * 7); // decay the spike
    }
    let amp = 0;
    if (sb > 0.01) {
      const jitter = Math.max(0, 0.26 + 0.22 * fbm(t * 7, 71) + 0.18 * fbm(t * 13, 73));
      amp = Math.max(spike, jitter) * sb;
    }
    S.mouth.step(amp, dt);
    const open = clamp(S.mouth.value, 0, 1);
    if (E.mouthTalk) {
      E.mouthTalk.setAttribute("ry", (1 + open * 7).toFixed(2));
      E.mouthTalk.setAttribute("rx", (7 + open * 2).toFixed(2));
      E.mouthTalk.setAttribute("opacity", sb.toFixed(2));
    }
    if (E.mouthRest) E.mouthRest.setAttribute("opacity", (1 - sb).toFixed(2));
  });
}
