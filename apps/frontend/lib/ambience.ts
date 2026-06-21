"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Optional ambient clinic sound — generated with the Web Audio API (no audio
 * files): a soft low room tone plus an occasional gentle monitor beep. Off by
 * default; only starts on a user gesture (the toggle), per autoplay policy.
 */
export function useAmbience() {
  const [on, setOn] = useState(false);
  const ctxRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (!on) return;
    const Ctx =
      window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
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
    const noise = ctx.createBufferSource();
    noise.buffer = buffer;
    noise.loop = true;
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 460;
    const gain = ctx.createGain();
    gain.gain.value = 0.04;
    noise.connect(lp).connect(gain).connect(ctx.destination);
    noise.start();

    const beep = () => {
      const o = ctx.createOscillator();
      o.type = "sine";
      o.frequency.value = 880;
      const g = ctx.createGain();
      g.gain.value = 0;
      o.connect(g).connect(ctx.destination);
      const t = ctx.currentTime;
      g.gain.linearRampToValueAtTime(0.018, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.5);
      o.start();
      o.stop(t + 0.55);
    };
    const interval = window.setInterval(beep, 9000);

    return () => {
      window.clearInterval(interval);
      try {
        noise.stop();
      } catch {
        /* already stopped */
      }
      ctx.close().catch(() => undefined);
      ctxRef.current = null;
    };
  }, [on]);

  return { on, toggle: () => setOn((v) => !v) };
}
