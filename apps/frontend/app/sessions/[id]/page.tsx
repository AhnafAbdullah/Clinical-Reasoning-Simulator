"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

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

  const session = useQuery({
    queryKey: ["session", id],
    queryFn: () => api.getSession(id),
    enabled: !!user,
  });
  const messages = useQuery({
    queryKey: ["messages", id],
    queryFn: () => api.listMessages(id),
    enabled: !!user,
  });

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
        onDone: () => {
          setLive(null);
          messages.refetch();
        },
        onError: () => {
          setLive(null);
          setBanner("The patient could not respond. Please try again.");
        },
      });
    },
    [id, messages],
  );

  // Stream the opening patient statement once, if we arrived with its id.
  const openedRef = useRef(false);
  useEffect(() => {
    if (!user || openedRef.current) return;
    const opening = new URLSearchParams(window.location.search).get("opening");
    if (opening) {
      openedRef.current = true;
      streamTurn(opening);
    }
  }, [user, streamTurn]);

  async function send() {
    const text = draft.trim();
    if (!text || busy) return;
    setBusy(true);
    setBanner(null);
    setDraft("");
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

  if (loading || !user || !session.data)
    return <div className="p-10 text-sm text-neutral-500">Loading session…</div>;

  return (
    <main className="mx-auto flex h-screen max-w-6xl flex-col px-4 py-4">
      <header className="flex items-center justify-between pb-3">
        <button onClick={() => router.push("/")} className="text-sm text-neutral-600 underline">
          ← Dashboard
        </button>
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">
          {status} · {stage}
        </span>
      </header>

      {banner && (
        <div className="mb-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">{banner}</div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 md:grid-cols-3">
        {/* Conversation (Vol 6 §11) */}
        <section className="flex min-h-0 flex-col md:col-span-2">
          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto rounded-lg border border-neutral-200 p-4">
            {messages.data?.map((m: MessageItem) => <Bubble key={m.id} role={m.role} text={m.message} />)}
            {live !== null && <Bubble role="patient" text={live || "…"} />}
            {messages.data?.length === 0 && live === null && (
              <p className="text-sm text-neutral-400">The patient is waiting. Say hello to begin.</p>
            )}
          </div>
          <div className="mt-3 flex gap-2">
            <input
              className="flex-1 rounded-md border border-neutral-300 px-3 py-2 text-sm disabled:bg-neutral-50"
              placeholder={working ? "Ask the patient a question…" : "The consultation is closed."}
              value={draft}
              disabled={!working || busy}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
            />
            <button
              onClick={send}
              disabled={!working || busy}
              className="rounded-md bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-50"
            >
              {busy ? "…" : "Send"}
            </button>
          </div>
        </section>

        {/* Workspace (Vol 6 §15-19) */}
        <section className="flex min-h-0 flex-col rounded-lg border border-neutral-200">
          <div className="flex border-b border-neutral-200 text-sm">
            {(["exam", "tests", "commit"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 px-3 py-2 capitalize ${tab === t ? "border-b-2 border-neutral-900 font-medium" : "text-neutral-500"}`}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {tab === "exam" && <ExamPanel id={id} working={working} />}
            {tab === "tests" && <TestsPanel id={id} working={working} />}
            {tab === "commit" && (
              <CommitPanel
                id={id}
                stage={stage}
                status={status}
                onChange={() => session.refetch()}
              />
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function Bubble({ role, text }: { role: string; text: string }) {
  const isStudent = role === "student";
  return (
    <div className={`flex ${isStudent ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${isStudent ? "bg-neutral-900 text-white" : "bg-neutral-100 text-neutral-900"}`}
      >
        {text}
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
      setSystem(res.system);
      setFindings(res.findings);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Examination failed.");
    }
  }

  return (
    <div>
      <p className="mb-2 text-xs text-neutral-500">Examine a system — findings come from the case.</p>
      <div className="flex flex-wrap gap-2">
        {EXAM_SYSTEMS.map((s) => (
          <button
            key={s}
            onClick={() => examine(s)}
            disabled={!working}
            className="rounded-md border border-neutral-300 px-2 py-1 text-xs capitalize hover:bg-neutral-50 disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>
      {err && <p className="mt-3 text-sm text-amber-700">{err}</p>}
      {findings && (
        <div className="mt-3 rounded-md bg-neutral-50 p-3 text-sm">
          <h4 className="font-medium capitalize">{system}</h4>
          <dl className="mt-1 space-y-1">
            {Object.entries(findings).map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs capitalize text-neutral-500">{k.replace(/_/g, " ")}</dt>
                <dd>{String(v)}</dd>
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

  return (
    <div>
      <input
        className="w-full rounded-md border border-neutral-300 px-2 py-1 text-sm"
        placeholder="Search investigations…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="mt-2 max-h-40 space-y-1 overflow-y-auto">
        {catalog.data?.map((c) => (
          <button
            key={c.name}
            onClick={() => order(c.name)}
            disabled={!working}
            className="flex w-full justify-between rounded-md px-2 py-1 text-left text-sm hover:bg-neutral-50 disabled:opacity-50"
          >
            <span>{c.name}</span>
            <span className="text-xs text-neutral-400">{c.category}</span>
          </button>
        ))}
      </div>
      <div className="mt-3 space-y-2">
        {ordered.map(({ name, res }) => (
          <div key={name} className="rounded-md bg-neutral-50 p-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="font-medium">{name}</span>
              <span
                className={`text-xs ${res.status === "AVAILABLE" ? "text-green-700" : res.status === "LOW_YIELD" ? "text-amber-700" : "text-neutral-500"}`}
              >
                {res.status}
              </span>
            </div>
            <p className="text-neutral-700">
              {String(res.result.result ?? res.result.message ?? "")}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function CommitPanel({
  id,
  stage,
  status,
  onChange,
}: {
  id: string;
  stage: string;
  status: string;
  onChange: () => void;
}) {
  const [differentials, setDifferentials] = useState("");
  const [diagnosis, setDiagnosis] = useState("");
  const [plan, setPlan] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const order = ["GREETING", "HISTORY", "PHYSICAL_EXAM", "INVESTIGATIONS", "DIFFERENTIAL", "FINAL_DIAGNOSIS", "MANAGEMENT"];
  const reached = (s: string) => order.indexOf(stage) >= order.indexOf(s);
  const evaluating = status === "EVALUATING" || status === "COMPLETED";

  async function run(fn: () => Promise<unknown>) {
    setErr(null);
    try {
      await fn();
      onChange();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Submission failed.");
    }
  }

  if (evaluating) return <EvaluationPanel id={id} />;

  return (
    <div className="space-y-4 text-sm">
      {err && <p className="text-amber-700">{err}</p>}

      <div>
        <h4 className="font-medium">1 · Ranked differential</h4>
        <textarea
          className="mt-1 w-full rounded-md border border-neutral-300 px-2 py-1"
          rows={3}
          placeholder="One diagnosis per line, most likely first"
          value={differentials}
          disabled={reached("FINAL_DIAGNOSIS")}
          onChange={(e) => setDifferentials(e.target.value)}
        />
        <button
          onClick={() =>
            run(() =>
              api.submitDifferentials(
                id,
                differentials.split("\n").map((s) => s.trim()).filter(Boolean),
              ),
            )
          }
          disabled={reached("FINAL_DIAGNOSIS")}
          className="mt-1 rounded-md bg-neutral-900 px-3 py-1 text-white disabled:opacity-50"
        >
          {reached("FINAL_DIAGNOSIS") ? "Submitted ✓" : "Lock differential"}
        </button>
      </div>

      <div>
        <h4 className="font-medium">2 · Final diagnosis</h4>
        <input
          className="mt-1 w-full rounded-md border border-neutral-300 px-2 py-1"
          value={diagnosis}
          disabled={!reached("FINAL_DIAGNOSIS") || reached("MANAGEMENT")}
          onChange={(e) => setDiagnosis(e.target.value)}
        />
        <button
          onClick={() => run(() => api.submitDiagnosis(id, diagnosis.trim()))}
          disabled={!reached("FINAL_DIAGNOSIS") || reached("MANAGEMENT")}
          className="mt-1 rounded-md bg-neutral-900 px-3 py-1 text-white disabled:opacity-50"
        >
          {reached("MANAGEMENT") ? "Submitted ✓" : "Lock diagnosis"}
        </button>
      </div>

      <div>
        <h4 className="font-medium">3 · Management plan</h4>
        <textarea
          className="mt-1 w-full rounded-md border border-neutral-300 px-2 py-1"
          rows={4}
          value={plan}
          disabled={!reached("MANAGEMENT")}
          onChange={(e) => setPlan(e.target.value)}
        />
        <button
          onClick={() => run(() => api.submitManagement(id, plan.trim()))}
          disabled={!reached("MANAGEMENT")}
          className="mt-1 rounded-md bg-neutral-900 px-3 py-1 text-white disabled:opacity-50"
        >
          Submit &amp; evaluate
        </button>
      </div>
    </div>
  );
}

function EvaluationPanel({ id }: { id: string }) {
  const evaluation = useQuery({
    queryKey: ["evaluation", id],
    queryFn: () => api.getEvaluation(id),
    refetchInterval: (q) =>
      (q.state.data as { status?: string } | undefined)?.status === "PENDING" ? 2000 : false,
  });
  const data = evaluation.data as Evaluation | { status: string } | undefined;

  if (!data || "status" in data)
    return <p className="text-sm text-neutral-500">Evaluating your consultation…</p>;

  const fb = data.feedback as {
    strengths?: string[];
    weaknesses?: string[];
    teaching_points?: string[];
  };
  return (
    <div className="space-y-4 text-sm">
      <div className="text-center">
        <div className="text-3xl font-semibold">{data.overall_score}</div>
        <div className="text-xs text-neutral-500">Overall score</div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {Object.entries(data.section_scores).map(([k, v]) => (
          <div key={k} className="rounded-md bg-neutral-50 p-2">
            <div className="text-xs capitalize text-neutral-500">{k.replace(/_/g, " ")}</div>
            <div className="font-medium">{v}</div>
          </div>
        ))}
        <div className="rounded-md bg-neutral-50 p-2">
          <div className="text-xs text-neutral-500">differential</div>
          <div className="font-medium">{data.differential_score}</div>
        </div>
        <div className="rounded-md bg-neutral-50 p-2">
          <div className="text-xs text-neutral-500">efficiency</div>
          <div className="font-medium">{data.efficiency_score}</div>
        </div>
      </div>
      {fb.strengths?.length ? (
        <Section title="Strengths" items={fb.strengths} tone="text-green-700" />
      ) : null}
      {fb.weaknesses?.length ? (
        <Section title="To improve" items={fb.weaknesses} tone="text-amber-700" />
      ) : null}
      {fb.teaching_points?.length ? (
        <Section title="Teaching points" items={fb.teaching_points} tone="text-neutral-700" />
      ) : null}
    </div>
  );
}

function Section({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <div>
      <h4 className={`font-medium ${tone}`}>{title}</h4>
      <ul className="mt-1 list-inside list-disc space-y-0.5 text-neutral-700">
        {items.map((it, i) => (
          <li key={i}>{it}</li>
        ))}
      </ul>
    </div>
  );
}
