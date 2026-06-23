"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// ── Text-to-speech: the patient speaks ───────────────────────────────────────────

function pickVoice(voices: SpeechSynthesisVoice[], gender?: string): SpeechSynthesisVoice | undefined {
  const en = voices.filter((v) => v.lang?.toLowerCase().startsWith("en"));
  if (!en.length) return undefined;
  const female = /female|woman|zira|samantha|hazel|susan|fiona|tessa|aria|jenny|eva/i;
  const male = /male|man|david|mark|george|daniel|fred|alex|guy|ryan/i;
  const g = (gender || "").toLowerCase();
  const want = g.startsWith("f") ? female : g.startsWith("m") ? male : null;
  if (want) {
    const match = en.find((v) => want.test(v.name));
    if (match) return match;
  }
  return en.find((v) => v.default) ?? en[0];
}

export function useTextToSpeech() {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);
  const [speaking, setSpeaking] = useState(false);
  // Pseudo-amplitude the mouth animation reads: spikes on each spoken word and
  // is decayed by the animation loop. Drives lip movement without audio access.
  const energyRef = useRef(0);
  // Autoplay: browsers refuse speech until the user has interacted with the page,
  // so the patient's opening line (auto-triggered on entry) would be dropped. If
  // speak() is called before any gesture, defer it to the first interaction.
  const gesturedRef = useRef(false);
  const pendingRef = useRef<{ text: string; opts?: { gender?: string } } | null>(null);

  useEffect(() => {
    if (!supported) return;
    const load = () => {
      voicesRef.current = window.speechSynthesis.getVoices();
    };
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", load);
  }, [supported]);

  const speakNow = useCallback((text: string, opts?: { gender?: string }) => {
    const synth = window.speechSynthesis;
    // Only cancel when something is queued — calling cancel() on an idle engine
    // can swallow the very next speak() in Chromium/Edge.
    if (synth.speaking || synth.pending) synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    const v = pickVoice(voicesRef.current, opts?.gender);
    if (v) u.voice = v;
    u.rate = 1;
    u.pitch = (opts?.gender || "").toLowerCase().startsWith("f") ? 1.1 : 0.95;
    u.onstart = () => setSpeaking(true);
    u.onboundary = () => { energyRef.current = 0.6 + Math.random() * 0.4; };
    u.onend = () => { setSpeaking(false); energyRef.current = 0; };
    u.onerror = () => { setSpeaking(false); energyRef.current = 0; };
    synth.speak(u);
  }, []);

  // Record the first user gesture (sticky activation) and flush a deferred line.
  useEffect(() => {
    if (!supported) return;
    const nav = navigator as Navigator & { userActivation?: { hasBeenActive: boolean } };
    if (nav.userActivation?.hasBeenActive) gesturedRef.current = true;
    const onGesture = () => {
      gesturedRef.current = true;
      const p = pendingRef.current;
      pendingRef.current = null;
      if (p) speakNow(p.text, p.opts);
      window.removeEventListener("pointerdown", onGesture);
      window.removeEventListener("keydown", onGesture);
    };
    window.addEventListener("pointerdown", onGesture);
    window.addEventListener("keydown", onGesture);
    return () => {
      window.removeEventListener("pointerdown", onGesture);
      window.removeEventListener("keydown", onGesture);
    };
  }, [supported, speakNow]);

  const speak = useCallback(
    (text: string, opts?: { gender?: string }) => {
      if (!supported || !text.trim()) return;
      if (!gesturedRef.current) {
        pendingRef.current = { text, opts }; // autoplay-blocked → speak on first gesture
        return;
      }
      speakNow(text, opts);
    },
    [supported, speakNow],
  );

  const cancel = useCallback(() => {
    pendingRef.current = null;
    if (supported) window.speechSynthesis.cancel();
    setSpeaking(false);
    energyRef.current = 0;
  }, [supported]);

  return { supported, speaking, energyRef, speak, cancel };
}

// ── Speech-to-text: the doctor speaks ─────────────────────────────────────────────

interface SRAlt {
  transcript: string;
}
interface SRResultEvent {
  results: ArrayLike<ArrayLike<SRAlt>>;
}
interface SRErrorEvent {
  error?: string;
}
interface SpeechRec {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((e: SRResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: SRErrorEvent) => void) | null;
  start(): void;
  stop(): void;
}
type SRCtor = new () => SpeechRec;

function getSRCtor(): SRCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: SRCtor; webkitSpeechRecognition?: SRCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function useSpeechToText(onFinal: (text: string) => void) {
  const ctor = getSRCtor();
  const supported = !!ctor;
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<SpeechRec | null>(null);
  const onFinalRef = useRef(onFinal);
  onFinalRef.current = onFinal;

  const start = useCallback(() => {
    if (!ctor || listening) return;
    setError(null);
    const rec = new ctor();
    recRef.current = rec;
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    rec.onresult = (e) => {
      const t = e.results[0]?.[0]?.transcript ?? "";
      if (t) onFinalRef.current(t);
    };
    rec.onend = () => setListening(false);
    // Surface the real failure instead of swallowing it — the error code tells
    // us exactly why nothing registered (mic busy, blocked, offline, …).
    rec.onerror = (e) => {
      setError(e?.error ?? "error");
      setListening(false);
    };
    setListening(true);
    try {
      rec.start();
    } catch {
      setError("start-failed");
      setListening(false);
    }
  }, [ctor, listening]);

  const stop = useCallback(() => {
    recRef.current?.stop();
    setListening(false);
  }, []);

  return { supported, listening, error, start, stop };
}
