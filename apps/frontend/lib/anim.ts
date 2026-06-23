"use client";

import { useEffect, useRef } from "react";

/**
 * Procedural-animation primitives for the cinematic scene. No CSS keyframes,
 * no fixed timers — every value is sampled from smooth noise or integrated by a
 * spring, so nothing moves at a constant speed and nothing is perfectly periodic.
 */

export function clamp(x: number, lo: number, hi: number): number {
  return x < lo ? lo : x > hi ? hi : x;
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/**
 * Smooth value noise in roughly [-1, 1], built from three non-harmonic sines so
 * it never visibly repeats on human timescales. `seed` decorrelates channels.
 */
export function fbm(t: number, seed = 0): number {
  return (
    0.55 * Math.sin(t * 0.73 + seed * 1.7) +
    0.3 * Math.sin(t * 1.63 + seed * 0.9 + 1.3) +
    0.15 * Math.sin(t * 2.91 + seed * 2.3 + 2.7)
  );
}

/**
 * A damped harmonic oscillator integrated with sub-stepped semi-implicit Euler.
 * `ratio` 1 = critically damped (settles, no overshoot); < 1 = a little
 * follow-through/overshoot for secondary motion.
 */
export class Spring {
  value: number;
  vel = 0;
  private k: number;
  private c: number;

  constructor(value = 0, stiffness = 60, ratio = 1) {
    this.value = value;
    this.k = stiffness;
    this.c = 2 * Math.sqrt(stiffness) * ratio;
  }

  /** Advance toward `target` by `dt` seconds; returns the new value. */
  step(target: number, dt: number): number {
    const steps = dt > 0.02 ? Math.ceil(dt / 0.016) : 1;
    const h = dt / steps;
    for (let i = 0; i < steps; i++) {
      const a = -this.k * (this.value - target) - this.c * this.vel;
      this.vel += a * h;
      this.value += this.vel * h;
    }
    return this.value;
  }

  /** A brief velocity impulse — used for tiny anticipation before a move. */
  kick(v: number): void {
    this.vel += v;
  }
}

/**
 * Runs a single requestAnimationFrame loop while `active`. The callback gets
 * `t` (seconds since start, a continuous clock) and `dt` (seconds since last
 * frame, clamped so springs stay stable across tab-switch gaps). Browsers pause
 * rAF on hidden tabs, so this idles automatically when backgrounded.
 */
export function useRaf(active: boolean, cb: (t: number, dt: number) => void): void {
  const cbRef = useRef(cb);
  cbRef.current = cb;

  useEffect(() => {
    if (!active) return;
    let raf = 0;
    let start = 0;
    let last = 0;
    const loop = (now: number) => {
      if (!start) {
        start = now;
        last = now;
      }
      const t = (now - start) / 1000;
      let dt = (now - last) / 1000;
      last = now;
      if (dt > 0.05) dt = 0.05; // clamp long gaps (tab return) for stability
      cbRef.current(t, dt);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [active]);
}
