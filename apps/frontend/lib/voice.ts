"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// ── Text-to-speech: the patient speaks ───────────────────────────────────────────

export function useTextToSpeech() {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    if (!supported) return;
    const load = () => {
      voicesRef.current = window.speechSynthesis.getVoices();
    };
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", load);
  }, [supported]);

  const pickVoice = (gender?: string): SpeechSynthesisVoice | undefined => {
    const en = voicesRef.current.filter((v) => v.lang?.toLowerCase().startsWith("en"));
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
  };

  const speak = useCallback(
    (text: string, opts?: { gender?: string }) => {
      if (!supported || !text.trim()) return;
      const synth = window.speechSynthesis;
      synth.cancel();
      const u = new SpeechSynthesisUtterance(text);
      const v = pickVoice(opts?.gender);
      if (v) u.voice = v;
      u.rate = 1;
      u.pitch = (opts?.gender || "").toLowerCase().startsWith("f") ? 1.1 : 0.95;
      synth.speak(u);
    },
    [supported],
  );

  const cancel = useCallback(() => {
    if (supported) window.speechSynthesis.cancel();
  }, [supported]);

  return { supported, speak, cancel };
}

// ── Speech-to-text: the doctor speaks ─────────────────────────────────────────────

interface SRAlt {
  transcript: string;
}
interface SRResultEvent {
  results: ArrayLike<ArrayLike<SRAlt>>;
}
interface SpeechRec {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((e: SRResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
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
  const recRef = useRef<SpeechRec | null>(null);
  const onFinalRef = useRef(onFinal);
  onFinalRef.current = onFinal;

  const start = useCallback(() => {
    if (!ctor || listening) return;
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
    rec.onerror = () => setListening(false);
    setListening(true);
    rec.start();
  }, [ctor, listening]);

  const stop = useCallback(() => {
    recRef.current?.stop();
    setListening(false);
  }, []);

  return { supported, listening, start, stop };
}
