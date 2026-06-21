"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ScoreBar } from "@/app/components/ui";
import { api, ApiError, type Evaluation, type InvestigationResult } from "@/lib/api";

export const EXAM_SYSTEMS = [
  "general",
  "vitals",
  "cardiovascular",
  "respiratory",
  "abdomen",
  "neurology",
  "extremities",
];

export function ExamPanel({ id, working }: { id: string; working: boolean }) {
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
      <p className="mb-2 text-xs text-ink-soft">Examine a system — findings come straight from the case.</p>
      <div className="flex flex-wrap gap-2">
        {EXAM_SYSTEMS.map((s) => (
          <button
            key={s}
            onClick={() => examine(s)}
            disabled={!working}
            className={`rounded-lg border px-2.5 py-1 text-xs capitalize transition-colors disabled:opacity-50 ${
              system === s ? "border-navy bg-navy text-cream-card" : "border-line bg-cream-card text-ink hover:bg-cream-deep"
            }`}
          >
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

export function TestsPanel({ id, working }: { id: string; working: boolean }) {
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
          <button
            key={c.name}
            onClick={() => order(c.name)}
            disabled={!working}
            className="flex w-full justify-between rounded-lg px-2.5 py-1.5 text-left text-sm text-ink transition-colors hover:bg-cream-deep disabled:opacity-50"
          >
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

export function CommitPanel({
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

export function EvaluationPanel({ id }: { id: string }) {
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
      {fb.strengths?.length ? <FeedbackList title="Strengths" items={fb.strengths} tone="text-emerald-700" /> : null}
      {fb.weaknesses?.length ? <FeedbackList title="To improve" items={fb.weaknesses} tone="text-amber-700" /> : null}
      {fb.teaching_points?.length ? <FeedbackList title="Teaching points" items={fb.teaching_points} tone="text-navy" /> : null}
    </div>
  );
}

function FeedbackList({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <div>
      <h4 className={`font-display font-semibold ${tone}`}>{title}</h4>
      <ul className="mt-1 list-inside list-disc space-y-0.5 text-ink-soft">
        {items.map((it, i) => <li key={i}>{it}</li>)}
      </ul>
    </div>
  );
}
