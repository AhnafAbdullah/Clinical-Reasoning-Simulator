"use client";

// The student's SOAP clipboard for a session. Stored client-side per session
// (localStorage) — a deliberate v1: notes are a private scratchpad, and the
// upgrade path to server-side storage doesn't change this hook's surface.

import { useCallback, useState } from "react";

export interface CaseNotes {
  s: string; // Subjective — what the patient tells you
  o: string; // Objective — findings, vitals, results
  a: string; // Assessment — working differential (one per line)
  p: string; // Plan — management thoughts
}

const EMPTY: CaseNotes = { s: "", o: "", a: "", p: "" };
const key = (sessionId: string) => `crs_notes_${sessionId}`;

export function loadCaseNotes(sessionId: string): CaseNotes {
  if (typeof window === "undefined") return EMPTY;
  try {
    const raw = localStorage.getItem(key(sessionId));
    return raw ? { ...EMPTY, ...(JSON.parse(raw) as Partial<CaseNotes>) } : EMPTY;
  } catch {
    return EMPTY;
  }
}

export function useCaseNotes(sessionId: string) {
  const [notes, setNotes] = useState<CaseNotes>(() => loadCaseNotes(sessionId));
  const update = useCallback(
    (field: keyof CaseNotes, value: string) => {
      setNotes((prev) => {
        const next = { ...prev, [field]: value };
        try {
          localStorage.setItem(key(sessionId), JSON.stringify(next));
        } catch {
          // storage full/blocked — keep the in-memory copy working
        }
        return next;
      });
    },
    [sessionId],
  );
  const hasContent = Object.values(notes).some((v) => v.trim().length > 0);
  return { notes, update, hasContent };
}
