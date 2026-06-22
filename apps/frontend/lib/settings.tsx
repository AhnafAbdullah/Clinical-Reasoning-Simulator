"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

/**
 * User experience preferences, persisted in localStorage. Both default ON; the
 * user's explicit choice here overrides the OS "reduce motion" hint.
 *   motion — the patient's idle breathing + the walk-in cinematic
 *   sound  — the ambient clinic soundscape
 */
interface Settings {
  motion: boolean;
  sound: boolean;
  toggleMotion: () => void;
  toggleSound: () => void;
}

const SettingsContext = createContext<Settings | null>(null);
const KEY = { motion: "crs_motion", sound: "crs_sound" };

function readPref(key: string): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem(key) !== "off"; // default on
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [motion, setMotion] = useState(true);
  const [sound, setSound] = useState(true);

  // Hydrate from localStorage after mount (avoids SSR mismatch).
  useEffect(() => {
    setMotion(readPref(KEY.motion));
    setSound(readPref(KEY.sound));
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

  return (
    <SettingsContext.Provider value={{ motion, sound, toggleMotion, toggleSound }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings(): Settings {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings must be used within SettingsProvider");
  return ctx;
}
