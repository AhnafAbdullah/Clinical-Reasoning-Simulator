"use client";

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type CSSProperties, type RefObject } from "react";

import { ClinicScene, PatientFigure } from "@/app/components/clinic";
import { SettingsMenu } from "@/app/components/ui";
import { CommitPanel, ExamPanel, TestsPanel } from "@/app/components/workspace";
import { useAmbience } from "@/lib/ambience";
import { api, ApiError, streamPatientTurn, type MessageItem } from "@/lib/api";
import { useCinematics } from "@/lib/cinematics";
import { useCaseNotes } from "@/lib/notes";
import { useSettings } from "@/lib/settings";
import { useSpeechToText, useTextToSpeech } from "@/lib/voice";

type Tab = "exam" | "tests" | "commit";

/** Turn a SpeechRecognition error code into a one-line hint (empty = stay quiet). */
function micHint(code: string): string {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone blocked — allow mic access for this site, and turn on Windows ‘Online speech recognition’.";
    case "audio-capture":
      return "No microphone available — is another app (e.g. Zoom) using it?";
    case "network":
      return "Speech service unreachable — check your connection.";
    case "no-speech":
      return "Didn’t catch that — try speaking again.";
    case "aborted":
      return ""; // normal on manual stop — no message
    default:
      return `Microphone error: ${code}.`;
  }
}

const TOUR_KEY = "crs_tour_seen";

interface TourStep {
  ref: RefObject<HTMLElement | null>;
  title: string;
  body: string;
  place: "top" | "bottom" | "left" | "right";
}

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
  const { motion: motionOn, sound, voice, voiceInput, toggleSound } = useSettings();
  const reduce = !motionOn; // settings drive animation; user choice overrides OS hint
  useAmbience(sound);
  const tts = useTextToSpeech();
  const router = useRouter();

  // The student's SOAP clipboard — drafted during the consult, carried into
  // the commit panel (Assessment → differential, Plan → management).
  const { notes, update: updateNotes, hasContent: hasNotes } = useCaseNotes(sessionId);
  const [showNotes, setShowNotes] = useState(false);

  const session = useQuery({ queryKey: ["session", sessionId], queryFn: () => api.getSession(sessionId) });
  const messages = useQuery({ queryKey: ["messages", sessionId], queryFn: () => api.listMessages(sessionId) });
  const patient = useQuery({ queryKey: ["patient", sessionId], queryFn: () => api.getPatient(sessionId) });

  const [entered, setEntered] = useState(false);
  const [draft, setDraft] = useState("");
  const [live, setLive] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [tab, setTab] = useState<Tab>("exam");

  // First-run guided tour. Targets these elements with arrow callouts.
  const [showTour, setShowTour] = useState(false);
  const tourTranscriptRef = useRef<HTMLDivElement>(null);
  const tourInputRef = useRef<HTMLDivElement>(null);
  const tourWorkspaceRef = useRef<HTMLButtonElement>(null);
  const tourControlsRef = useRef<HTMLDivElement>(null);
  const tourNotesRef = useRef<HTMLButtonElement>(null);

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
  // Abort the SSE read when a new turn starts or the room unmounts, so a stale
  // stream can't keep setting state (or hold the connection) after we've left.
  const streamAbortRef = useRef<AbortController | null>(null);
  useEffect(() => () => streamAbortRef.current?.abort(), []);
  const streamTurn = useCallback(
    async (messageId: string) => {
      streamAbortRef.current?.abort();
      const ctrl = new AbortController();
      streamAbortRef.current = ctrl;
      setLive("");
      liveTextRef.current = "";
      await streamPatientTurn(
        sessionId,
        messageId,
        {
          onToken: (t) => {
            liveTextRef.current += t;
            setLive((p) => (p ?? "") + t);
          },
          onDone: () => {
            setLive(null);
            messages.refetch();
            if (voice && tts.supported) tts.speak(liveTextRef.current, { gender: patient.data?.gender });
          },
          onError: (m) => {
            setLive(null);
            messages.refetch(); // whatever was said before the drop is persisted
            setSendError(m);
          },
        },
        { signal: ctrl.signal },
      );
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
    setSendError(null);
    setDraft("");
    try {
      const { message_id } = await api.sendMessage(sessionId, text);
      await messages.refetch();
      await streamTurn(message_id);
    } catch (err) {
      // The question never reached the patient — put it back, and say why.
      setDraft((d) => d || text);
      setSendError(
        err instanceof ApiError
          ? err.message
          : "Couldn't reach the clinic — check your connection and try again.",
      );
    } finally {
      setBusy(false);
      session.refetch();
    }
  }

  // Doctor dictation: stop the patient talking, then send the transcript as a turn.
  const dictation = useSpeechToText((t) => { tts.cancel(); send(t); });

  // Stop any in-flight speech when leaving the room. Depend on the STABLE cancel
  // (not the whole tts object, which is a new identity every render — that made
  // this cleanup fire on every re-render and cut the patient off mid-sentence).
  const { cancel: cancelSpeech } = tts;
  useEffect(() => () => cancelSpeech(), [cancelSpeech]);

  // Cinematic engine: one rAF loop drives camera, scene and patient procedurally.
  const sceneCamRef = useRef<HTMLDivElement>(null);
  const patientCamRef = useRef<HTMLDivElement>(null);
  const speakingRef = useRef(false);
  speakingRef.current = tts.speaking;
  useCinematics({
    enabled: !reduce,
    sceneRef: sceneCamRef,
    patientRef: patientCamRef,
    speakingRef,
    energyRef: tts.energyRef,
    revision: patient.data ? `${patient.data.gender}-${patient.data.age}-${patient.data.affect}` : "loading",
  });

  // Show the guided tour once, after the walk-in settles, for first-time users.
  useEffect(() => {
    if (entered && typeof window !== "undefined" && localStorage.getItem(TOUR_KEY) !== "1") {
      const t = setTimeout(() => setShowTour(true), 600);
      return () => clearTimeout(t);
    }
  }, [entered]);

  const finishTour = () => {
    if (typeof window !== "undefined") localStorage.setItem(TOUR_KEY, "1");
    setShowTour(false);
  };

  const tourSteps: TourStep[] = [
    {
      ref: tourTranscriptRef,
      title: "Meet your patient",
      body: "This is your consultation. Ask questions to take a focused history — the patient's replies appear here, and (with Voice on) are spoken aloud.",
      place: "right",
    },
    {
      ref: tourInputRef,
      title: "Ask — type or speak",
      body: "Type a question and press Ask. Or tap the 🎤 mic to speak it aloud. You can switch voice commands on/off in ⚙ Settings.",
      place: "top",
    },
    {
      ref: tourNotesRef,
      title: "Your clipboard",
      body: "Jot SOAP notes as you go — Subjective, Objective, Assessment, Plan. Your Assessment and Plan carry straight into the commit form, so draft your differential during the history.",
      place: "bottom",
    },
    {
      ref: tourWorkspaceRef,
      title: "Examine & submit here",
      body: "Open the Workspace to examine the patient, order tests, and commit your diagnosis & management — this is where you submit your solution.",
      place: "left",
    },
    {
      ref: tourControlsRef,
      title: "Settings & controls",
      body: "Open ⚙ Settings for voice, motion & sound. Mute the ambience with 🔊, track the case stage, or replay this tour with ?. Use ← Leave to exit.",
      place: "bottom",
    },
  ];

  return (
    <div className="fixed inset-0 overflow-hidden bg-navy">
      {/* Clinic backdrop — un-blurs/settles as you enter the room. The inner
          div is the camera the engine pans (kept separate from framer-motion's
          entrance transform so they don't fight). */}
      <motion.div
        className="absolute inset-0"
        initial={false}
        animate={{ scale: entered ? 1 : reduce ? 1 : 1.14, filter: entered ? "blur(2px)" : "blur(12px)" }}
        transition={{ duration: reduce ? 0 : 1.6, ease: [0.22, 1, 0.36, 1] }}
      >
        <div ref={sceneCamRef} className="absolute inset-0" style={{ willChange: "transform" }}>
          <ClinicScene className="h-full w-full" />
        </div>
      </motion.div>
      <div className="absolute inset-0 bg-navy/35" />

      {/* Patient avatar — walks in (framer-motion), then the engine takes over:
          breathing, head motion, blinks, saccades, speech-driven mouth. */}
      <motion.div
        initial={{ opacity: 0, y: reduce ? 0 : 60, x: reduce ? 0 : -28 }}
        animate={{ opacity: 1, y: 0, x: 0 }}
        transition={{ duration: reduce ? 0 : 0.9, delay: reduce ? 0 : 0.45, ease: "easeOut" }}
        className="pointer-events-none absolute bottom-0 left-2 z-10 w-[clamp(150px,20vw,290px)] sm:left-10"
      >
        <div ref={patientCamRef} style={{ willChange: "transform" }}>
          <PatientFigure
            gender={patient.data?.gender}
            age={patient.data?.age ?? null}
            affect={patient.data?.affect}
            alive={!reduce}
            className="h-auto w-full drop-shadow-2xl"
          />
        </div>
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
          <div ref={tourControlsRef} className="flex items-center gap-3">
            {patient.data?.name && (
              <span className="hidden rounded-full bg-navy/50 px-3 py-1 text-xs text-cream-card/80 backdrop-blur sm:inline">
                {patient.data.name}{patient.data.age ? `, ${patient.data.age}` : ""}
              </span>
            )}
            {typeof streak === "number" && streak > 0 && (
              <span className="rounded-full border border-gold/40 bg-navy/40 px-3 py-1 text-sm text-gold-soft backdrop-blur">🔥 {streak}</span>
            )}
            <button
              ref={tourNotesRef}
              onClick={() => setShowNotes((v) => !v)}
              aria-pressed={showNotes}
              title={showNotes ? "Close your clipboard" : "Open your clipboard (SOAP notes)"}
              className={`relative rounded-full border px-2.5 py-1 text-sm backdrop-blur transition-colors ${
                showNotes
                  ? "border-gold bg-gold/20 text-gold-soft"
                  : "border-cream-card/20 bg-navy/40 text-cream-card/80 hover:text-cream-card"
              }`}
            >
              📋
              {hasNotes && !showNotes && (
                <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-gold" aria-hidden />
              )}
            </button>
            <button
              onClick={() => setShowTour(true)}
              title="Replay the tour"
              aria-label="Replay the tour"
              className="rounded-full border border-cream-card/20 bg-navy/40 px-2.5 py-1 text-sm text-cream-card/80 backdrop-blur transition-colors hover:text-cream-card"
            >
              ?
            </button>
            <button
              onClick={toggleSound}
              aria-pressed={sound}
              title={sound ? "Mute clinic ambience" : "Play clinic ambience"}
              className="rounded-full border border-cream-card/20 bg-navy/40 px-2.5 py-1 text-sm text-cream-card/80 backdrop-blur transition-colors hover:text-cream-card"
            >
              {sound ? "🔊" : "🔈"}
            </button>
            <SettingsMenu triggerClassName="rounded-full border border-cream-card/20 bg-navy/40 px-2.5 py-1 text-sm text-cream-card/80 backdrop-blur transition-colors hover:text-cream-card" />
            <span className="hidden rounded-full bg-navy/50 px-3 py-1 text-xs text-cream-card/80 backdrop-blur sm:inline">{sstatus} · {stage}</span>
            <button ref={tourWorkspaceRef} onClick={() => setDrawer(true)} className="btn-gold px-4 py-1.5 text-sm">Workspace</button>
          </div>
        </div>

        {/* Transcript fills the height */}
        <div className="pointer-events-none flex min-h-0 flex-1">
          <div ref={tourTranscriptRef} className="pointer-events-auto flex min-h-0 w-full px-3 sm:ml-[clamp(160px,20vw,320px)] sm:w-[clamp(320px,44vw,560px)]">
            <Transcript messages={messages.data ?? []} live={live} />
          </div>
        </div>

        {/* Doctor input */}
        <div className="px-4 pb-5">
          <div ref={tourInputRef} className="mx-auto max-w-2xl">
            <div className="flex gap-2">
              <input
                className="flex-1 rounded-full border border-cream-card/20 bg-navy/50 px-5 py-3 text-cream-card placeholder:text-cream-card/40 backdrop-blur focus:border-gold focus:outline-none"
                placeholder={working ? "Ask the patient…" : "Consultation closed — open the Workspace to commit."}
                value={draft}
                disabled={!working || busy}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && send()}
              />
              {voiceInput && dictation.supported && (
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
            {sendError && (
              <p className="mt-1.5 px-3 text-center text-xs text-amber-300/90" role="alert">
                {sendError}
              </p>
            )}
            {voiceInput && dictation.supported && dictation.error && micHint(dictation.error) && (
              <p className="mt-1.5 px-3 text-center text-xs text-amber-300/90" role="status">
                {micHint(dictation.error)}
              </p>
            )}
          </div>
        </div>

        {/* Clipboard — SOAP notes, non-modal so you can write while talking */}
        <AnimatePresence>
          {showNotes && (
            <motion.aside
              initial={reduce ? false : { x: 40, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={reduce ? { opacity: 0 } : { x: 40, opacity: 0 }}
              transition={{ type: "spring", stiffness: 320, damping: 32 }}
              className="absolute bottom-24 right-3 top-14 z-20 flex w-72 flex-col rounded-xl2 border border-line bg-cream-card/95 shadow-lift backdrop-blur"
              aria-label="Clipboard — SOAP notes"
            >
              <div className="flex items-center justify-between border-b border-line px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="gold-strip w-6" />
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">Clipboard</h3>
                </div>
                <button onClick={() => setShowNotes(false)} className="text-ink-soft hover:text-navy" aria-label="Close clipboard">✕</button>
              </div>
              <div className="flex min-h-0 flex-1 flex-col gap-2 p-3">
                <NoteField label="S — Subjective" hint="What the patient tells you" value={notes.s} onChange={(v) => updateNotes("s", v)} />
                <NoteField label="O — Objective" hint="Findings, vitals, results" value={notes.o} onChange={(v) => updateNotes("o", v)} />
                <NoteField label="A — Assessment" hint="Differential — one per line" value={notes.a} onChange={(v) => updateNotes("a", v)} />
                <NoteField label="P — Plan" hint="Management thoughts" value={notes.p} onChange={(v) => updateNotes("p", v)} />
              </div>
              <p className="border-t border-line px-3 py-1.5 text-[10px] text-ink-soft">
                Assessment &amp; Plan carry into the commit form.
              </p>
            </motion.aside>
          )}
        </AnimatePresence>

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
                  {tab === "commit" && (
                    <CommitPanel
                      id={sessionId}
                      stage={stage}
                      status={sstatus}
                      onChange={() => session.refetch()}
                      initialDifferentials={notes.a}
                      initialPlan={notes.p}
                    />
                  )}
                </div>
              </motion.aside>
            </>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Consultation over → the story continues in the debrief */}
      {(sstatus === "EVALUATING" || sstatus === "COMPLETED") && (
        <div className="pointer-events-none absolute inset-0 z-40 grid place-items-center p-6">
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="pointer-events-auto max-w-sm rounded-xl2 border border-line bg-cream-card p-5 text-center shadow-lift"
          >
            <span className="gold-strip mx-auto mb-3 block w-10" />
            <h3 className="font-display text-lg font-semibold text-navy">Consultation complete</h3>
            <p className="mt-1 text-sm text-ink-soft">
              {sstatus === "EVALUATING"
                ? "Your consultant is reviewing the case."
                : "Your report is ready."}
            </p>
            <div className="mt-4 flex justify-center gap-2">
              <button onClick={() => router.push(`/sessions/${sessionId}/debrief`)} className="btn-gold px-5 py-2 text-sm">
                View debrief →
              </button>
              <button onClick={() => { tts.cancel(); onExit(); }} className="btn-ghost px-4 py-2 text-sm">
                Leave
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {/* First-run guided tour overlay */}
      <AnimatePresence>{showTour && <RoomTour steps={tourSteps} onClose={finishTour} />}</AnimatePresence>
    </div>
  );
}

function NoteField({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex min-h-0 flex-1 flex-col">
      <span className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-soft">{label}</span>
      <textarea
        className="min-h-0 flex-1 resize-none rounded-lg border border-line bg-cream px-2 py-1.5 text-xs text-ink placeholder:text-ink-soft/60 focus:border-gold focus:outline-none"
        placeholder={hint}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
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

/**
 * A first-run guided tour: dims the room, spotlights each target element and
 * floats an arrow-pointed callout beside it. Positions are measured from the
 * live element rects so the arrows track the real UI on any screen size.
 */
function RoomTour({ steps, onClose }: { steps: TourStep[]; onClose: () => void }) {
  const [i, setI] = useState(0);
  const [target, setTarget] = useState<DOMRect | null>(null);
  const [pos, setPos] = useState<{ left: number; top: number; ax: number; ay: number } | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const step = steps[i];
  const last = i === steps.length - 1;
  const gap = 14;

  // Measure the spotlighted element (and keep it in sync on resize).
  useEffect(() => {
    const measure = () => setTarget(step?.ref.current?.getBoundingClientRect() ?? null);
    measure();
    const id = window.setTimeout(measure, 60); // after any layout settle
    window.addEventListener("resize", measure);
    return () => { window.clearTimeout(id); window.removeEventListener("resize", measure); };
  }, [step]);

  // Place the callout next to the target, clamped on-screen; aim the arrow.
  useEffect(() => {
    if (!target || !cardRef.current) { setPos(null); return; }
    const c = cardRef.current.getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight, pad = 12;
    const cx = target.left + target.width / 2;
    const cy = target.top + target.height / 2;
    let left: number, top: number;
    switch (step.place) {
      case "top": top = target.top - gap - c.height; left = cx - c.width / 2; break;
      case "bottom": top = target.bottom + gap; left = cx - c.width / 2; break;
      case "left": left = target.left - gap - c.width; top = cy - c.height / 2; break;
      default: left = target.right + gap; top = cy - c.height / 2; break;
    }
    left = Math.min(Math.max(left, pad), vw - c.width - pad);
    top = Math.min(Math.max(top, pad), vh - c.height - pad);
    const ax = Math.min(Math.max(cx - left, 18), c.width - 18);
    const ay = Math.min(Math.max(cy - top, 18), c.height - 18);
    setPos({ left, top, ax, ay });
  }, [target, step.place]);

  const place = step.place;
  const arrowStyle: CSSProperties =
    place === "bottom" ? { left: (pos?.ax ?? 0) - 6, top: -6, borderRight: "none", borderBottom: "none" }
    : place === "top" ? { left: (pos?.ax ?? 0) - 6, bottom: -6, borderLeft: "none", borderTop: "none" }
    : place === "left" ? { top: (pos?.ay ?? 0) - 6, right: -6, borderLeft: "none", borderBottom: "none" }
    : { top: (pos?.ay ?? 0) - 6, left: -6, borderRight: "none", borderTop: "none" };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50">
      {/* click-blocking layer */}
      <div className="absolute inset-0" onClick={(e) => e.stopPropagation()} />
      {/* spotlight (dims everything except the target via a huge box-shadow) */}
      {target ? (
        <div
          className="pointer-events-none absolute"
          style={{
            left: target.left - 6, top: target.top - 6, width: target.width + 12, height: target.height + 12,
            borderRadius: 14, boxShadow: "0 0 0 9999px rgba(8,12,24,0.74)", outline: "2px solid #dec987", outlineOffset: 2,
          }}
        />
      ) : (
        <div className="absolute inset-0 bg-navy/75" />
      )}

      <div
        ref={cardRef}
        className="absolute w-72 rounded-xl2 border border-line bg-cream-card p-4 text-ink shadow-lift"
        style={{ left: pos?.left ?? -9999, top: pos?.top ?? -9999, visibility: pos ? "visible" : "hidden" }}
      >
        {pos && <span className="absolute h-3 w-3 rotate-45 border border-line bg-cream-card" style={arrowStyle} />}
        <div className="mb-1 flex items-center gap-2">
          <span className="gold-strip w-6" />
          <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-soft">{i + 1} / {steps.length}</span>
        </div>
        <h3 className="font-display text-base font-semibold text-navy">{step.title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-ink-soft">{step.body}</p>
        <div className="mt-3 flex items-center justify-between">
          <button onClick={onClose} className="text-xs text-ink-soft hover:text-navy">Skip</button>
          <div className="flex gap-2">
            {i > 0 && <button onClick={() => setI((n) => n - 1)} className="btn-ghost px-3 py-1.5 text-xs">Back</button>}
            <button onClick={() => (last ? onClose() : setI((n) => n + 1))} className="btn-gold px-4 py-1.5 text-xs">
              {last ? "Got it" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
