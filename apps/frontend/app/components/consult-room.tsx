"use client";

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";

import { ClinicScene, PatientFigure } from "@/app/components/clinic";
import { CommitPanel, ExamPanel, TestsPanel } from "@/app/components/workspace";
import { useAmbience } from "@/lib/ambience";
import { api, streamPatientTurn, type MessageItem } from "@/lib/api";
import { useSettings } from "@/lib/settings";
import { useSpeechToText, useTextToSpeech } from "@/lib/voice";

type Tab = "exam" | "tests" | "commit";

/**
 * The immersive, room-based consultation used by EVERY case (classic sessions
 * and the Daily Challenge). Renders the clinic, a per-case patient avatar, the
 * mindbox transcript, the doctor's input and a workspace drawer, with a short
 * "walk-in" cinematic on entry (skipped under reduced motion).
 */
export function ConsultRoom({
  sessionId,
  openingMessageId = null,
  streak,
  onExit,
}: {
  sessionId: string;
  openingMessageId?: string | null;
  streak?: number;
  onExit: () => void;
}) {
  const { motion: motionOn, sound, voice, toggleSound } = useSettings();
  const reduce = !motionOn; // settings drive animation; user choice overrides OS hint
  useAmbience(sound);
  const tts = useTextToSpeech();

  const session = useQuery({ queryKey: ["session", sessionId], queryFn: () => api.getSession(sessionId) });
  const messages = useQuery({ queryKey: ["messages", sessionId], queryFn: () => api.listMessages(sessionId) });
  const patient = useQuery({ queryKey: ["patient", sessionId], queryFn: () => api.getPatient(sessionId) });

  const [entered, setEntered] = useState(false);
  const [draft, setDraft] = useState("");
  const [live, setLive] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [tab, setTab] = useState<Tab>("exam");

  // Walk-in cinematic on mount.
  useEffect(() => {
    if (reduce) {
      setEntered(true);
      return;
    }
    const t = setTimeout(() => setEntered(true), 1500);
    return () => clearTimeout(t);
  }, [reduce]);

  const stage = session.data?.current_stage ?? "GREETING";
  const sstatus = session.data?.status ?? "ACTIVE";
  const working = sstatus === "ACTIVE" && stage !== "MANAGEMENT";

  // Accumulates the patient's streamed reply so we can speak the whole line on done.
  const liveTextRef = useRef("");
  const streamTurn = useCallback(
    async (messageId: string) => {
      setLive("");
      liveTextRef.current = "";
      await streamPatientTurn(sessionId, messageId, {
        onToken: (t) => {
          liveTextRef.current += t;
          setLive((p) => (p ?? "") + t);
        },
        onDone: () => {
          setLive(null);
          messages.refetch();
          if (voice && tts.supported) tts.speak(liveTextRef.current, { gender: patient.data?.gender });
        },
        onError: () => setLive(null),
      });
    },
    [sessionId, messages, voice, tts, patient.data?.gender],
  );

  const streamedOpening = useRef(false);
  useEffect(() => {
    if (streamedOpening.current || !openingMessageId) return;
    streamedOpening.current = true;
    streamTurn(openingMessageId);
  }, [openingMessageId, streamTurn]);

  async function send(spoken?: string) {
    const text = (spoken ?? draft).trim();
    if (!text || busy) return;
    setBusy(true);
    setDraft("");
    try {
      const { message_id } = await api.sendMessage(sessionId, text);
      await messages.refetch();
      await streamTurn(message_id);
    } finally {
      setBusy(false);
      session.refetch();
    }
  }

  // Doctor dictation: stop the patient talking, then send the transcript as a turn.
  const dictation = useSpeechToText((t) => { tts.cancel(); send(t); });

  // Stop any in-flight speech when leaving the room.
  useEffect(() => () => tts.cancel(), [tts]);

  return (
    <div className="fixed inset-0 overflow-hidden bg-navy">
      {/* Clinic backdrop — un-blurs/settles as you enter the room */}
      <motion.div
        className="absolute inset-0"
        initial={false}
        animate={{ scale: entered ? 1 : reduce ? 1 : 1.14, filter: entered ? "blur(2px)" : "blur(12px)" }}
        transition={{ duration: reduce ? 0 : 1.6, ease: [0.22, 1, 0.36, 1] }}
      >
        <ClinicScene className="h-full w-full" parallax={!reduce} />
      </motion.div>
      <div className="absolute inset-0 bg-navy/35" />

      {/* Patient avatar (walks in, then idle-breathes) */}
      <motion.div
        initial={{ opacity: 0, y: reduce ? 0 : 60, x: reduce ? 0 : -28 }}
        animate={{ opacity: 1, y: 0, x: 0 }}
        transition={{ duration: reduce ? 0 : 0.9, delay: reduce ? 0 : 0.45, ease: "easeOut" }}
        className="pointer-events-none absolute bottom-0 left-2 z-10 w-[clamp(150px,20vw,290px)] sm:left-10"
      >
        <motion.div
          animate={reduce ? undefined : { y: [0, -3, 0], scale: [1, 1.012, 1] }}
          transition={reduce ? undefined : { duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
          style={{ transformOrigin: "bottom center" }}
        >
          <PatientFigure
            gender={patient.data?.gender}
            age={patient.data?.age ?? null}
            affect={patient.data?.affect}
            alive={!reduce}
            speaking={tts.speaking}
            className="h-auto w-full drop-shadow-2xl"
          />
        </motion.div>
      </motion.div>

      {/* Foreground UI */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: entered ? 1 : 0 }}
        transition={{ duration: reduce ? 0 : 0.5, delay: reduce ? 0 : 0.2 }}
        className="absolute inset-0 z-20 flex flex-col"
      >
        <div className="flex items-center justify-between px-5 py-4">
          <button onClick={() => { tts.cancel(); onExit(); }} className="text-sm text-cream-card/80 hover:text-cream-card">← Leave</button>
          <div className="flex items-center gap-3">
            {patient.data?.name && (
              <span className="hidden rounded-full bg-navy/50 px-3 py-1 text-xs text-cream-card/80 backdrop-blur sm:inline">
                {patient.data.name}{patient.data.age ? `, ${patient.data.age}` : ""}
              </span>
            )}
            {typeof streak === "number" && streak > 0 && (
              <span className="rounded-full border border-gold/40 bg-navy/40 px-3 py-1 text-sm text-gold-soft backdrop-blur">🔥 {streak}</span>
            )}
            <button
              onClick={toggleSound}
              aria-pressed={sound}
              title={sound ? "Mute clinic ambience" : "Play clinic ambience"}
              className="rounded-full border border-cream-card/20 bg-navy/40 px-2.5 py-1 text-sm text-cream-card/80 backdrop-blur transition-colors hover:text-cream-card"
            >
              {sound ? "🔊" : "🔈"}
            </button>
            <span className="rounded-full bg-navy/50 px-3 py-1 text-xs text-cream-card/80 backdrop-blur">{sstatus} · {stage}</span>
            <button onClick={() => setDrawer(true)} className="btn-gold px-4 py-1.5 text-sm">Workspace</button>
          </div>
        </div>

        {/* Transcript fills the height */}
        <div className="pointer-events-none flex min-h-0 flex-1">
          <div className="pointer-events-auto flex min-h-0 w-full px-3 sm:ml-[clamp(160px,20vw,320px)] sm:w-[clamp(320px,44vw,560px)]">
            <Transcript messages={messages.data ?? []} live={live} />
          </div>
        </div>

        {/* Doctor input */}
        <div className="px-4 pb-5">
          <div className="mx-auto flex max-w-2xl gap-2">
            <input
              className="flex-1 rounded-full border border-cream-card/20 bg-navy/50 px-5 py-3 text-cream-card placeholder:text-cream-card/40 backdrop-blur focus:border-gold focus:outline-none"
              placeholder={working ? "Ask the patient…" : "Consultation closed — open the Workspace to commit."}
              value={draft}
              disabled={!working || busy}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
            />
            {voice && dictation.supported && (
              <button
                onClick={() => (dictation.listening ? dictation.stop() : dictation.start())}
                disabled={!working || busy}
                aria-pressed={dictation.listening}
                title={dictation.listening ? "Listening… click to stop" : "Speak to the patient"}
                className={`grid w-12 place-items-center rounded-full border backdrop-blur transition-colors disabled:opacity-40 ${
                  dictation.listening
                    ? "animate-pulse border-gold bg-gold/20 text-gold-soft"
                    : "border-cream-card/20 bg-navy/50 text-cream-card/80 hover:text-cream-card"
                }`}
              >
                🎤
              </button>
            )}
            <button onClick={() => send()} disabled={!working || busy} className="btn-gold px-6">{busy ? "…" : "Ask"}</button>
          </div>
        </div>

        {/* Workspace drawer */}
        <AnimatePresence>
          {drawer && (
            <>
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                onClick={() => setDrawer(false)} className="absolute inset-0 z-30 bg-navy/40 backdrop-blur-sm" />
              <motion.aside
                initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
                transition={{ type: "spring", stiffness: 320, damping: 34 }}
                className="absolute right-0 top-0 z-40 flex h-full w-full max-w-md flex-col bg-cream shadow-lift"
              >
                <div className="flex items-center justify-between border-b border-line px-4 py-3">
                  <div className="flex">
                    {(["exam", "tests", "commit"] as Tab[]).map((t) => (
                      <button key={t} onClick={() => setTab(t)}
                        className={`relative px-3 py-1.5 text-sm capitalize ${tab === t ? "font-semibold text-navy" : "text-ink-soft"}`}>
                        {t}
                        {tab === t && <span className="absolute inset-x-3 bottom-0 h-[2px] rounded-full bg-gold" />}
                      </button>
                    ))}
                  </div>
                  <button onClick={() => setDrawer(false)} className="text-ink-soft hover:text-navy" aria-label="Close">✕</button>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto p-4">
                  {tab === "exam" && <ExamPanel id={sessionId} working={working} />}
                  {tab === "tests" && <TestsPanel id={sessionId} working={working} />}
                  {tab === "commit" && <CommitPanel id={sessionId} stage={stage} status={sstatus} onChange={() => session.refetch()} />}
                </div>
              </motion.aside>
            </>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

function Transcript({ messages, live }: { messages: MessageItem[]; live: string | null }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [messages, live]);

  const empty = messages.length === 0 && live === null;
  const fade = "linear-gradient(to bottom, transparent 0, #000 16%, #000 100%)";

  return (
    <div ref={ref} className="h-full w-full overflow-y-auto pr-1" style={{ maskImage: fade, WebkitMaskImage: fade }}>
      <div className="flex min-h-full flex-col justify-end space-y-3 py-3">
        {empty ? (
          <div className="rounded-2xl border border-line bg-cream-card/90 px-4 py-3 text-sm text-ink-soft backdrop-blur">
            The patient settles in…
          </div>
        ) : (
          <>
            {messages.map((m) => <ChatTurn key={m.id} role={m.role} text={m.message} />)}
            {live !== null && <ChatTurn role="patient" text={live || "…"} typing={!live} latest />}
          </>
        )}
      </div>
    </div>
  );
}

function ChatTurn({ role, text, typing, latest }: { role: string; text: string; typing?: boolean; latest?: boolean }) {
  const isDoctor = role === "student";
  return (
    <motion.div
      initial={latest ? { opacity: 0, y: 10 } : false}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isDoctor ? "justify-end" : "justify-start"}`}
    >
      <div className="max-w-[88%]">
        <div className={`mb-0.5 text-[10px] uppercase tracking-wide ${isDoctor ? "text-right text-sky-200" : "text-gold-soft"}`}>
          {isDoctor ? "You" : "Patient"}
        </div>
        <div
          className={`rounded-2xl px-3.5 py-2 text-sm leading-relaxed shadow-lift ${
            isDoctor ? "rounded-tr-sm bg-sky text-navy" : "rounded-tl-sm border border-line bg-cream-card/95 text-navy backdrop-blur"
          }`}
        >
          {!isDoctor && <span className="gold-strip mb-1.5 block w-7" />}
          {text}
          {typing && <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-navy align-middle" />}
        </div>
      </div>
    </motion.div>
  );
}
