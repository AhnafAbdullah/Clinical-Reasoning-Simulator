"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { GoldStrip, ScoreBar, Spinner } from "@/app/components/ui";
import {
  api,
  ApiError,
  streamPatientTurn,
  type Evaluation,
  type InvestigationResult,
  type MessageItem,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const EXAM_SYSTEMS = [
  "general",
  "vitals",
  "cardiovascular",
  "respiratory",
  "abdomen",
  "neurology",
  "extremities",
];
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

function ExamPanel({ id, working }: { id: string; working: boolean }) {
  const [system, setSystem] = useState<string | null>(null);
  const [findings, setFindings] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function examine(sys: string) {
    setErr(null);
    try {
      const res = await api.physicalExam(id, sys);
      setSystem(res.system); setFindings(res.findings);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Examination failed.");
    }
  }

  return (
    <div>
      <p className="mb-2 text-xs text-ink-soft">Examine a system — findings come straight from the case.</p>
      <div className="flex flex-wrap gap-2">
        {EXAM_SYSTEMS.map((s) => (
          <button key={s} onClick={() => examine(s)} disabled={!working}
            className={`rounded-lg border px-2.5 py-1 text-xs capitalize transition-colors disabled:opacity-50 ${
              system === s ? "border-navy bg-navy text-cream-card" : "border-line bg-cream-card text-ink hover:bg-cream-deep"
            }`}>
            {s}
          </button>
        ))}
      </div>
      {err && <p className="mt-3 text-sm text-amber-700">{err}</p>}
      {findings && (
        <div className="mt-3 rounded-lg border border-line bg-cream p-3 text-sm">
          <div className="gold-strip mb-2 w-8" />
          <h4 className="font-semibold capitalize text-navy">{system}</h4>
          <dl className="mt-1 space-y-1">
            {Object.entries(findings).map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs capitalize text-ink-soft">{k.replace(/_/g, " ")}</dt>
                <dd className="text-ink">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}

function TestsPanel({ id, working }: { id: string; working: boolean }) {
  const [q, setQ] = useState("");
  const [ordered, setOrdered] = useState<{ name: string; res: InvestigationResult }[]>([]);
  const catalog = useQuery({ queryKey: ["catalog", q], queryFn: () => api.catalog(q || undefined) });

  async function order(name: string) {
    const res = await api.orderInvestigation(id, name);
    setOrdered((prev) => [{ name, res }, ...prev.filter((o) => o.name !== name)]);
  }

  const tone = (s: string) =>
    s === "AVAILABLE" ? "text-emerald-700" : s === "LOW_YIELD" ? "text-amber-700" : "text-ink-soft";

  return (
    <div>
      <input className="input" placeholder="Search investigations…" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="mt-2 max-h-40 space-y-1 overflow-y-auto">
        {catalog.data?.map((c) => (
          <button key={c.name} onClick={() => order(c.name)} disabled={!working}
            className="flex w-full justify-between rounded-lg px-2.5 py-1.5 text-left text-sm text-ink transition-colors hover:bg-cream-deep disabled:opacity-50">
            <span>{c.name}</span>
            <span className="text-xs text-ink-soft">{c.category}</span>
          </button>
        ))}
      </div>
      <div className="mt-3 space-y-2">
        {ordered.map(({ name, res }) => (
          <div key={name} className="rounded-lg border border-line bg-cream p-2.5 text-sm">
            <div className="flex items-center justify-between">
              <span className="font-medium text-navy">{name}</span>
              <span className={`text-xs font-semibold ${tone(res.status)}`}>{res.status}</span>
            </div>
            <p className="text-ink-soft">{String(res.result.result ?? res.result.message ?? "")}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function CommitPanel({ id, stage, status, onChange }: { id: string; stage: string; status: string; onChange: () => void }) {
  const [differentials, setDifferentials] = useState("");
  const [diagnosis, setDiagnosis] = useState("");
  const [plan, setPlan] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const order = ["GREETING", "HISTORY", "PHYSICAL_EXAM", "INVESTIGATIONS", "DIFFERENTIAL", "FINAL_DIAGNOSIS", "MANAGEMENT"];
  const reached = (s: string) => order.indexOf(stage) >= order.indexOf(s);
  const evaluating = status === "EVALUATING" || status === "COMPLETED";

  async function run(fn: () => Promise<unknown>) {
    setErr(null);
    try { await fn(); onChange(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Submission failed."); }
  }

  if (evaluating) return <EvaluationPanel id={id} />;

  return (
    <div className="space-y-5 text-sm">
      {err && <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-800">{err}</p>}

      <Step n={1} title="Ranked differential" done={reached("FINAL_DIAGNOSIS")}>
        <textarea className="input" rows={3} placeholder="One diagnosis per line, most likely first"
          value={differentials} disabled={reached("FINAL_DIAGNOSIS")} onChange={(e) => setDifferentials(e.target.value)} />
        <button disabled={reached("FINAL_DIAGNOSIS")}
          onClick={() => run(() => api.submitDifferentials(id, differentials.split("\n").map((s) => s.trim()).filter(Boolean)))}
          className="btn-primary mt-2">
          {reached("FINAL_DIAGNOSIS") ? "Submitted ✓" : "Lock differential"}
        </button>
      </Step>

      <Step n={2} title="Final diagnosis" done={reached("MANAGEMENT")} locked={!reached("FINAL_DIAGNOSIS")}>
        <input className="input" value={diagnosis} disabled={!reached("FINAL_DIAGNOSIS") || reached("MANAGEMENT")}
          onChange={(e) => setDiagnosis(e.target.value)} placeholder="Your single best diagnosis" />
        <button disabled={!reached("FINAL_DIAGNOSIS") || reached("MANAGEMENT")}
          onClick={() => run(() => api.submitDiagnosis(id, diagnosis.trim()))} className="btn-primary mt-2">
          {reached("MANAGEMENT") ? "Submitted ✓" : "Lock diagnosis"}
        </button>
      </Step>

      <Step n={3} title="Management plan" locked={!reached("MANAGEMENT")}>
        <textarea className="input" rows={4} value={plan} disabled={!reached("MANAGEMENT")}
          onChange={(e) => setPlan(e.target.value)} placeholder="Your management plan…" />
        <button disabled={!reached("MANAGEMENT")} onClick={() => run(() => api.submitManagement(id, plan.trim()))}
          className="btn-gold mt-2">
          Submit &amp; get report
        </button>
      </Step>
    </div>
  );
}

function Step({ n, title, children, done, locked }: { n: number; title: string; children: React.ReactNode; done?: boolean; locked?: boolean }) {
  return (
    <div className={locked ? "opacity-55" : ""}>
      <h4 className="flex items-center gap-2 font-display font-semibold text-navy">
        <span className={`grid h-5 w-5 place-items-center rounded-full text-[11px] ${done ? "bg-navy text-cream-card" : "bg-cream-deep text-ink-soft"}`}>
          {done ? "✓" : n}
        </span>
        {title}
      </h4>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function EvaluationPanel({ id }: { id: string }) {
  const evaluation = useQuery({
    queryKey: ["evaluation", id],
    queryFn: () => api.getEvaluation(id),
    refetchInterval: (q) => ((q.state.data as { status?: string } | undefined)?.status === "PENDING" ? 2500 : false),
  });
  const data = evaluation.data as Evaluation | { status: string } | undefined;

  if (!data || "status" in data) {
    return (
      <div className="grid place-items-center gap-3 py-10 text-center">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-line border-t-navy" />
        <p className="text-sm text-ink-soft">Your consultant is reviewing the case…</p>
      </div>
    );
  }

  const fb = data.feedback as { strengths?: string[]; weaknesses?: string[]; teaching_points?: string[] };
  const tone = data.overall_score >= 75 ? "text-emerald-700" : data.overall_score >= 50 ? "text-amber-700" : "text-rose-700";
  return (
    <div className="space-y-5 text-sm">
      <div className="card-gold grid place-items-center p-5 text-center">
        <div className={`font-display text-5xl font-bold ${tone}`}>{data.overall_score}</div>
        <div className="text-xs uppercase tracking-wide text-ink-soft">Overall score</div>
      </div>

      <div className="space-y-2.5">
        {Object.entries(data.section_scores).map(([k, v]) => <ScoreBar key={k} label={k} value={v} />)}
        <ScoreBar label="differential" value={data.differential_score} />
        <ScoreBar label="efficiency" value={data.efficiency_score} />
      </div>

      {fb.strengths?.length ? <Section title="Strengths" items={fb.strengths} tone="text-emerald-700" /> : null}
      {fb.weaknesses?.length ? <Section title="To improve" items={fb.weaknesses} tone="text-amber-700" /> : null}
      {fb.teaching_points?.length ? <Section title="Teaching points" items={fb.teaching_points} tone="text-navy" /> : null}
    </div>
  );
}

function Section({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <div>
      <h4 className={`font-display font-semibold ${tone}`}>{title}</h4>
      <ul className="mt-1 list-inside list-disc space-y-0.5 text-ink-soft">
        {items.map((it, i) => <li key={i}>{it}</li>)}
      </ul>
    </div>
  );
}
