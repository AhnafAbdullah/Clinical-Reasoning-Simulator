"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Spinner } from "@/app/components/ui";
import { CommitPanel, ExamPanel, TestsPanel } from "@/app/components/workspace";
import { api, ApiError, streamPatientTurn, type MessageItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Tab = "exam" | "tests" | "commit";

export default function SessionPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  const session = useQuery({ queryKey: ["session", id], queryFn: () => api.getSession(id), enabled: !!user });
  const messages = useQuery({ queryKey: ["messages", id], queryFn: () => api.listMessages(id), enabled: !!user });

  const [tab, setTab] = useState<Tab>("exam");
  const [draft, setDraft] = useState("");
  const [live, setLive] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const stage = session.data?.current_stage ?? "GREETING";
  const status = session.data?.status ?? "ACTIVE";
  const working = status === "ACTIVE" && stage !== "MANAGEMENT";

  const scrollDown = useCallback(() => {
    requestAnimationFrame(() => scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight));
  }, []);
  useEffect(scrollDown, [messages.data, live, scrollDown]);

  const streamTurn = useCallback(
    async (messageId: string) => {
      setLive("");
      await streamPatientTurn(id, messageId, {
        onToken: (t) => setLive((p) => (p ?? "") + t),
        onDone: () => { setLive(null); messages.refetch(); },
        onError: () => { setLive(null); setBanner("The patient could not respond. Please try again."); },
      });
    },
    [id, messages],
  );

  const openedRef = useRef(false);
  useEffect(() => {
    if (!user || openedRef.current) return;
    const opening = new URLSearchParams(window.location.search).get("opening");
    if (opening) { openedRef.current = true; streamTurn(opening); }
  }, [user, streamTurn]);

  async function send() {
    const text = draft.trim();
    if (!text || busy) return;
    setBusy(true); setBanner(null); setDraft("");
    try {
      const { message_id } = await api.sendMessage(id, text);
      await messages.refetch();
      await streamTurn(message_id);
    } catch (err) {
      setBanner(err instanceof ApiError ? err.message : "Failed to send.");
    } finally {
      setBusy(false);
      session.refetch();
    }
  }

  if (loading || !user || !session.data) return <Spinner label="Loading session…" />;

  return (
    <main className="mx-auto flex h-screen max-w-6xl flex-col px-4 py-4">
      <header className="flex items-center justify-between pb-3">
        <button onClick={() => router.push("/")} className="btn-ghost px-3 py-1.5 text-xs">← Dashboard</button>
        <div className="flex items-center gap-2">
          <span className="gold-strip w-8" aria-hidden />
          <span className="chip-navy">{status} · {stage}</span>
        </div>
      </header>

      {banner && (
        <div role="alert" className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {banner}
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 md:grid-cols-3">
        {/* Conversation */}
        <section className="flex min-h-0 flex-col md:col-span-2">
          <div ref={scrollRef} className="card flex-1 space-y-3 overflow-y-auto p-4">
            {messages.data?.map((m: MessageItem) => <Bubble key={m.id} role={m.role} text={m.message} />)}
            {live !== null && <Bubble role="patient" text={live || "…"} typing={!live} />}
            {messages.data?.length === 0 && live === null && (
              <p className="grid h-full place-items-center text-sm text-ink-soft">
                The patient is waiting. Say hello to begin the consultation.
              </p>
            )}
          </div>
          <div className="mt-3 flex gap-2">
            <input
              className="input flex-1"
              placeholder={working ? "Ask the patient a question…" : "The consultation is closed."}
              value={draft}
              disabled={!working || busy}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
            />
            <button onClick={send} disabled={!working || busy} className="btn-primary px-5">
              {busy ? "…" : "Send"}
            </button>
          </div>
        </section>

        {/* Workspace */}
        <section className="card flex min-h-0 flex-col">
          <div className="flex border-b border-line text-sm">
            {(["exam", "tests", "commit"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`relative flex-1 px-3 py-2.5 capitalize transition-colors ${
                  tab === t ? "font-semibold text-navy" : "text-ink-soft hover:text-navy"
                }`}
              >
                {t}
                {tab === t && <span className="absolute inset-x-3 bottom-0 h-[2px] rounded-full bg-gold" aria-hidden />}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {tab === "exam" && <ExamPanel id={id} working={working} />}
            {tab === "tests" && <TestsPanel id={id} working={working} />}
            {tab === "commit" && <CommitPanel id={id} stage={stage} status={status} onChange={() => session.refetch()} />}
          </div>
        </section>
      </div>
    </main>
  );
}

function Bubble({ role, text, typing }: { role: string; text: string; typing?: boolean }) {
  const isStudent = role === "student";
  return (
    <div className={`flex ${isStudent ? "justify-end" : "justify-start"} animate-fade-up`}>
      <div className="max-w-[80%]">
        <div className={`mb-0.5 text-[11px] uppercase tracking-wide ${isStudent ? "text-right text-sky-700" : "text-ink-soft"}`}>
          {isStudent ? "You" : "Patient"}
        </div>
        <div
          className={`rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
            isStudent
              ? "rounded-tr-sm bg-sky text-navy"
              : "rounded-tl-sm border border-line bg-cream-card text-ink"
          }`}
        >
          {typing ? <span className="text-ink-soft">typing…</span> : text}
        </div>
      </div>
    </div>
  );
}
