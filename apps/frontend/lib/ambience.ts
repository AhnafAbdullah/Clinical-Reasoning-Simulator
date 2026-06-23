"use client";

import { useEffect, useRef } from "react";

/**
 * Ambient clinic sound — generated with the Web Audio API (no audio files): a
 * soft low room tone plus an occasional gentle monitor beep. Driven by the
 * `enabled` flag (from settings). If the browser blocks autoplay, it resumes on
 * the first user interaction.
 */
export function useAmbience(enabled: boolean) {
  const ctxRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const Ctx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    ctxRef.current = ctx;

    // Brown-ish noise → low-pass → quiet gain = a calm room hum.
    const size = 2 * ctx.sampleRate;
    const buffer = ctx.createBuffer(1, size, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    let last = 0;
    for (let i = 0; i < size; i++) {
      const white = Math.random() * 2 - 1;
      last = (last + 0.02 * white) / 1.02;
      data[i] = last * 3.2;
    }
    // Low room tone — soft filtered brown noise.
    const noise = ctx.createBufferSource();
    noise.buffer = buffer;
    noise.loop = true;
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 540;
    const noiseGain = ctx.createGain();
    noiseGain.gain.value = 0.06;
    noise.connect(lp).connect(noiseGain).connect(ctx.destination);
    noise.start();

    // Warm ambient pad — two quiet, slightly detuned low sines (a fifth apart),
    // breathing via a slow tremolo so it never sits perfectly still.
    const padGain = ctx.createGain();
    padGain.gain.value = 0.03;
    const padLp = ctx.createBiquadFilter();
    padLp.type = "lowpass";
    padLp.frequency.value = 700;
    padGain.connect(padLp).connect(ctx.destination);
    const pad1 = ctx.createOscillator();
    pad1.type = "sine";
    pad1.frequency.value = 98; // ~G2
    const pad2 = ctx.createOscillator();
    pad2.type = "sine";
    pad2.frequency.value = 147; // a fifth above
    pad1.connect(padGain);
    pad2.connect(padGain);
    const lfo = ctx.createOscillator();
    lfo.frequency.value = 0.06;
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = 0.012;
    lfo.connect(lfoGain).connect(padGain.gain);
    pad1.start();
    pad2.start();
    lfo.start();

    const beep = () => {
      const o = ctx.createOscillator();
      o.type = "sine";
      o.frequency.value = 880;
      const g = ctx.createGain();
      g.gain.value = 0;
      o.connect(g).connect(ctx.destination);
      const t = ctx.currentTime;
      g.gain.linearRampToValueAtTime(0.025, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.5);
      o.start();
      o.stop(t + 0.55);
    };
    const interval = window.setInterval(beep, 11000);

    // Autoplay policy: a fresh AudioContext almost always starts "suspended"
    // until a user gesture. Try immediately (in case we already have activation),
    // and on every gesture until it's actually running — then stop listening.
    const resume = () => {
      ctx
        .resume()
        .then(() => {
          if (ctx.state === "running") {
            window.removeEventListener("pointerdown", resume);
            window.removeEventListener("keydown", resume);
          }
        })
        .catch(() => undefined);
    };
    resume();
    window.addEventListener("pointerdown", resume);
    window.addEventListener("keydown", resume);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener("pointerdown", resume);
      window.removeEventListener("keydown", resume);
      for (const s of [noise, pad1, pad2, lfo]) {
        try {
          s.stop();
        } catch {
          /* already stopped */
        }
      }
      ctx.close().catch(() => undefined);
      ctxRef.current = null;
    };
  }, [enabled]);
}
