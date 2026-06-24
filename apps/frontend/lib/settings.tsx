"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

/**
 * User experience preferences, persisted in localStorage. Both default ON; the
 * user's explicit choice here overrides the OS "reduce motion" hint.
 *   motion     — the patient's idle breathing + the walk-in cinematic
 *   sound      — the ambient clinic soundscape
 *   voice      — the patient speaks their replies aloud (TTS)
 *   voiceInput — voice commands: dictate to the patient with the mic (STT)
 */
interface Settings {
  motion: boolean;
  sound: boolean;
  voice: boolean;
  voiceInput: boolean;
  toggleMotion: () => void;
  toggleSound: () => void;
  toggleVoice: () => void;
  toggleVoiceInput: () => void;
}

const SettingsContext = createContext<Settings | null>(null);
const KEY = { motion: "crs_motion", sound: "crs_sound", voice: "crs_voice", voiceInput: "crs_voice_input" };

function readPref(key: string): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem(key) !== "off"; // default on
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [motion, setMotion] = useState(true);
  const [sound, setSound] = useState(true);
  const [voice, setVoice] = useState(true);
  const [voiceInput, setVoiceInput] = useState(true);

  // Hydrate from localStorage after mount (avoids SSR mismatch).
  useEffect(() => {
    setMotion(readPref(KEY.motion));
    setSound(readPref(KEY.sound));
    setVoice(readPref(KEY.voice));
    setVoiceInput(readPref(KEY.voiceInput));
  }, []);

  function toggleMotion() {
    setMotion((v) => {
      const next = !v;
      localStorage.setItem(KEY.motion, next ? "on" : "off");
      return next;
    });
  }
  function toggleSound() {
    setSound((v) => {
      const next = !v;
      localStorage.setItem(KEY.sound, next ? "on" : "off");
      return next;
    });
  }
  function toggleVoice() {
    setVoice((v) => {
      const next = !v;
      localStorage.setItem(KEY.voice, next ? "on" : "off");
      return next;
    });
  }
  function toggleVoiceInput() {
    setVoiceInput((v) => {
      const next = !v;
      localStorage.setItem(KEY.voiceInput, next ? "on" : "off");
      return next;
    });
  }

  return (
    <SettingsContext.Provider
      value={{ motion, sound, voice, voiceInput, toggleMotion, toggleSound, toggleVoice, toggleVoiceInput }}
    >
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings(): Settings {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings must be used within SettingsProvider");
  return ctx;
}
