"use client";

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { ClinicScene, PatientFigure } from "@/app/components/clinic";
import { CommitPanel, ExamPanel, TestsPanel } from "@/app/components/workspace";
import { api, ApiError, streamPatientTurn, type MessageItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Phase = "intro" | "entering" | "consult";
type Tab = "exam" | "tests" | "commit";

export default function DailyPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  const status = useQuery({ queryKey: ["daily"], queryFn: () => api.dailyStatus(), enabled: !!user });

  const [phase, setPhase] = useState<Phase>("intro");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [streak, setStreak] = useState(0);
  const [starting, setStarting] = useState(false);
  const openingRef = useRef<string | null>(null);

  async function begin() {
    if (starting) return;
    setStarting(true);
    try {
      const res = await api.startDaily();
      setSessionId(res.session_id);
      setStreak(res.streak);
      openingRef.current = res.opening_message_id;
      if (reduce) {
        setPhase("consult");
      } else {
        setPhase("entering");
        setTimeout(() => setPhase("consult"), 1900);
      }
    } catch (err) {
      setStarting(false);
      alert(err instanceof ApiError ? err.message : "Could not start today's challenge.");
    }
  }

  if (loading || !user) return <div className="min-h-screen bg-navy" />;

  const focused = phase === "consult";

  return (
    <div className="fixed inset-0 overflow-hidden bg-navy">
      {/* Cinematic backdrop */}
      <motion.div
        className="absolute inset-0"
        initial={false}
        animate={
          reduce
            ? { scale: 1, filter: focused ? "blur(3px)" : "blur(10px)" }
            : {
                scale: phase === "intro" ? 1.18 : 1,
                filter: focused ? "blur(2px)" : "blur(14px)",
              }
        }
        transition={{ duration: reduce ? 0 : 1.8, ease: [0.22, 1, 0.36, 1] }}
      >
        <ClinicScene className="h-full w-full" />
      </motion.div>
      {/* Dimming overlay (lighter once we settle into the room) */}
      <motion.div
        className="absolute inset-0 bg-navy"
        initial={false}
        animate={{ opacity: focused ? 0.32 : 0.62 }}
        transition={{ duration: reduce ? 0 : 1.6 }}
      />

      {/* Patient figure (enters during the cinematic, stays for the consult) */}
      <AnimatePresence>
        {phase !== "intro" && (
          <motion.div
            key="patient"
            initial={{ opacity: 0, y: reduce ? 0 : 60, x: reduce ? 0 : -30 }}
            animate={{ opacity: 1, y: 0, x: 0 }}
            transition={{ duration: reduce ? 0 : 0.9, delay: reduce ? 0 : 0.5, ease: "easeOut" }}
            className="pointer-events-none absolute bottom-0 left-2 z-10 w-[clamp(160px,22vw,300px)] sm:left-10"
          >
            <PatientFigure className="h-auto w-full drop-shadow-2xl" />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {phase === "intro" ? (
          <Intro
            key="intro"
            streak={status.data?.streak ?? 0}
            difficulty={status.data?.difficulty}
            attempted={status.data?.attempted ?? false}
            starting={starting}
            onStart={begin}
            onExit={() => router.push("/")}
          />
        ) : phase === "consult" && sessionId ? (
          <Consult key="consult" sessionId={sessionId} streak={streak} openingRef={openingRef} onExit={() => router.push("/")} />
        ) : (
          <motion.div key="enter" className="absolute inset-0 grid place-items-center">
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: [0, 1, 1, 0] }}
              transition={{ duration: 1.9, times: [0, 0.3, 0.7, 1] }}
              className="font-display text-2xl text-cream-card"
            >
              A patient is walking in…
            </motion.p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Intro({
  streak,
  difficulty,
  attempted,
  starting,
  onStart,
  onExit,
}: {
  streak: number;
  difficulty?: string;
  attempted: boolean;
  starting: boolean;
  onStart: () => void;
  onExit: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="absolute inset-0 z-20 grid place-items-center px-6 text-center"
    >
      <div className="max-w-lg">
        <button onClick={onExit} className="absolute left-5 top-5 text-sm text-cream-card/70 hover:text-cream-card">
          ← Dashboard
        </button>
        {streak > 0 && (
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-gold/40 bg-navy/40 px-3 py-1 text-sm text-gold-soft backdrop-blur">
            🔥 {streak}-day streak — keep it alive
          </div>
        )}
        <h1 className="font-display text-5xl font-semibold text-cream-card drop-shadow">The Daily Challenge</h1>
        <p className="mx-auto mt-3 max-w-sm text-cream-card/75">
          One patient. One shot. Walk into the room, take the history, and reason your way to the
          diagnosis. {difficulty ? <>Today&apos;s case is <b className="text-gold-soft">{difficulty}</b>.</> : null}
        </p>

        <motion.button
          onClick={onStart}
          disabled={starting}
          whileHover={{ scale: 1.04 }}
          whileTap={{ scale: 0.97 }}
          className="group relative mt-9 inline-flex items-center gap-3 rounded-full px-9 py-4 text-lg font-semibold text-navy disabled:opacity-70"
          style={{ background: "linear-gradient(180deg,#dec987,#c2a14a)" }}
        >
          <span className="absolute inset-0 -z-10 animate-pulse rounded-full" style={{ boxShadow: "0 0 50px 8px rgba(194,161,74,0.55)" }} />
          {starting ? "Opening the door…" : attempted ? "Resume today's patient →" : "Enter the room →"}
        </motion.button>
        <p className="mt-4 text-xs text-cream-card/50">Plays once per day · builds your streak</p>
      </div>
    </motion.div>
  );
}

function Consult({
  sessionId,
  streak,
  openingRef,
  onExit,
}: {
  sessionId: string;
  streak: number;
  openingRef: React.MutableRefObject<string | null>;
  onExit: () => void;
}) {
  const session = useQuery({ queryKey: ["session", sessionId], queryFn: () => api.getSession(sessionId) });
  const messages = useQuery({ queryKey: ["messages", sessionId], queryFn: () => api.listMessages(sessionId) });

  const [draft, setDraft] = useState("");
  const [live, setLive] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [tab, setTab] = useState<Tab>("exam");

  const stage = session.data?.current_stage ?? "GREETING";
  const sstatus = session.data?.status ?? "ACTIVE";
  const working = sstatus === "ACTIVE" && stage !== "MANAGEMENT";

  const streamTurn = useCallback(
    async (messageId: string) => {
      setLive("");
      await streamPatientTurn(sessionId, messageId, {
        onToken: (t) => setLive((p) => (p ?? "") + t),
        onDone: () => { setLive(null); messages.refetch(); },
        onError: () => setLive(null),
      });
    },
    [sessionId, messages],
  );

  const streamedOpening = useRef(false);
  useEffect(() => {
    if (streamedOpening.current) return;
    if (openingRef.current) {
      streamedOpening.current = true;
      streamTurn(openingRef.current);
    }
  }, [openingRef, streamTurn]);

  async function send() {
    const text = draft.trim();
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

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="absolute inset-0 z-20 flex flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between px-5 py-4">
        <button onClick={onExit} className="text-sm text-cream-card/80 hover:text-cream-card">← Leave</button>
        <div className="flex items-center gap-3">
          {streak > 0 && <span className="rounded-full border border-gold/40 bg-navy/40 px-3 py-1 text-sm text-gold-soft backdrop-blur">🔥 {streak}</span>}
          <span className="rounded-full bg-navy/50 px-3 py-1 text-xs text-cream-card/80 backdrop-blur">{sstatus} · {stage}</span>
          <button onClick={() => setDrawer(true)} className="btn-gold px-4 py-1.5 text-sm">Workspace</button>
        </div>
      </div>

      {/* Conversation transcript — speech boxes stack above the latest; older
          ones fade at the top edge but become crisp as you scroll to them. */}
      <div className="pointer-events-none flex flex-1 items-end">
        <div className="pointer-events-auto mb-3 w-full px-3 sm:ml-[clamp(170px,22vw,340px)] sm:w-auto">
          <Transcript messages={messages.data ?? []} live={live} />
        </div>
      </div>

      {/* Doctor input (your POV) */}
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
          <button onClick={send} disabled={!working || busy} className="btn-gold px-6">{busy ? "…" : "Ask"}</button>
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
  );
}

function Transcript({ messages, live }: { messages: MessageItem[]; live: string | null }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [messages, live]);

  const empty = messages.length === 0 && live === null;
  // Top-edge fade: ~3-4 turns sit crisp in view; older turns fade as they reach
  // the top, and become fully legible again when scrolled into the clear zone.
  const fade = "linear-gradient(to bottom, transparent 0, #000 16%, #000 100%)";

  return (
    <div
      ref={ref}
      className="w-full space-y-3 overflow-y-auto pr-1 sm:w-[clamp(300px,40vw,520px)]"
      style={{ maxHeight: "clamp(230px, 42vh, 440px)", maskImage: fade, WebkitMaskImage: fade }}
    >
      {empty ? (
        <div className="rounded-2xl border border-line bg-cream-card/90 px-4 py-3 text-sm text-ink-soft backdrop-blur">
          The patient settles in…
        </div>
      ) : (
        <>
          {messages.map((m) => (
            <ChatTurn key={m.id} role={m.role} text={m.message} />
          ))}
          {live !== null && <ChatTurn role="patient" text={live || "…"} typing={!live} latest />}
        </>
      )}
    </div>
  );
}

function ChatTurn({
  role,
  text,
  typing,
  latest,
}: {
  role: string;
  text: string;
  typing?: boolean;
  latest?: boolean;
}) {
  const isDoctor = role === "student";
  return (
    <motion.div
      initial={latest ? { opacity: 0, y: 10 } : false}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isDoctor ? "justify-end" : "justify-start"}`}
    >
      <div className="max-w-[88%]">
        <div
          className={`mb-0.5 text-[10px] uppercase tracking-wide ${
            isDoctor ? "text-right text-sky-200" : "text-gold-soft"
          }`}
        >
          {isDoctor ? "You" : "Patient"}
        </div>
        <div
          className={`rounded-2xl px-3.5 py-2 text-sm leading-relaxed shadow-lift ${
            isDoctor
              ? "rounded-tr-sm bg-sky text-navy"
              : "rounded-tl-sm border border-line bg-cream-card/95 text-navy backdrop-blur"
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
