"use client";

// The debrief: a post-consultation case reveal told as a story — the diagnosis,
// your reasoning beside the case's, every order annotated, the transcript
// replayed with the questions that scored. Content only exists server-side
// once the evaluation is written, so nothing here can spoil an active case.

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { GoldStrip, ScoreBar, Spinner } from "@/app/components/ui";
import { api, type Debrief } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { loadCaseNotes, type CaseNotes } from "@/lib/notes";
import { useSettings } from "@/lib/settings";

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const same = (a: string, b: string) => {
  const na = norm(a), nb = norm(b);
  return !!na && !!nb && (na === nb || na.includes(nb) || nb.includes(na));
};

const VERDICT = {
  correct: { label: "You called it", tone: "bg-emerald-600 text-white" },
  close: { label: "Close — it was in your differential", tone: "bg-amber-500 text-navy" },
  missed: { label: "A miss — study this one", tone: "bg-rose-600 text-white" },
} as const;

export default function DebriefPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  const debrief = useQuery({
    queryKey: ["debrief", id],
    queryFn: () => api.getDebrief(id),
    enabled: !!user,
    refetchInterval: (q) =>
      (q.state.data as { status?: string } | undefined)?.status === "PENDING" ? 2500 : false,
  });

  if (loading || !user || debrief.isLoading) return <Spinner label="Opening the case file…" />;

  const data = debrief.data as Debrief | { status: string } | undefined;
  if (!data) return <Spinner label="Opening the case file…" />;
  if ("status" in data) return <Reviewing />;

  return <DebriefStory sessionId={id} data={data} />;
}

/** Waiting room while the consultant (evaluation worker) finishes. */
function Reviewing() {
  return (
    <div className="grid min-h-screen place-items-center bg-navy text-cream-card">
      <div className="text-center">
        <span className="gold-strip mx-auto mb-4 block w-12" />
        <div className="mx-auto mb-5 h-6 w-6 animate-spin rounded-full border-2 border-cream-card/25 border-t-gold-soft" />
        <h1 className="font-display text-2xl font-semibold">Your consultant is reviewing the case…</h1>
        <p className="mt-2 text-sm text-cream-card/70">
          Grading your history, orders and reasoning against the rubric.
        </p>
      </div>
    </div>
  );
}

function DebriefStory({ sessionId, data }: { sessionId: string; data: Debrief }) {
  const { motion: motionOn } = useSettings();
  const reduce = !motionOn;
  const [notes, setNotes] = useState<CaseNotes | null>(null);
  useEffect(() => setNotes(loadCaseNotes(sessionId)), [sessionId]);

  const verdict = VERDICT[data.student.verdict] ?? VERDICT.missed;

  return (
    <div className="min-h-screen bg-cream">
      {/* ── The reveal ──────────────────────────────────────────────────── */}
      <header className="relative overflow-hidden bg-navy px-6 pb-14 pt-10 text-cream-card">
        <div
          className="pointer-events-none absolute inset-0 opacity-20"
          aria-hidden
          style={{
            backgroundImage:
              "radial-gradient(520px 260px at 85% 10%, #c2a14a, transparent 60%), radial-gradient(420px 260px at 8% 110%, #2f6ea5, transparent 60%)",
          }}
        />
        <div className="relative mx-auto max-w-3xl">
          <div className="flex items-center justify-between">
            <Link href="/" className="text-sm text-cream-card/70 hover:text-cream-card">← Back to clinic</Link>
            <span className="rounded-full bg-cream-card/10 px-3 py-1 text-xs text-cream-card/80">
              {data.case.specialty} · {data.case.difficulty}
            </span>
          </div>

          <motion.div
            initial={reduce ? false : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="mt-8"
          >
            <GoldStrip className="mb-3" />
            <p className="text-sm uppercase tracking-widest text-cream-card/60">Case debrief — {data.case.title}</p>
            <p className="mt-6 text-sm text-cream-card/70">The diagnosis was</p>
          </motion.div>

          <motion.h1
            initial={reduce ? false : { opacity: 0, scale: 0.96, filter: "blur(6px)" }}
            animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
            transition={{ duration: 0.7, delay: reduce ? 0 : 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="mt-1 font-display text-3xl font-bold text-gold-soft sm:text-4xl"
          >
            {data.reveal.diagnosis}
          </motion.h1>

          <motion.div
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: reduce ? 0 : 1.1 }}
          >
            <p className="mt-4 max-w-2xl text-sm leading-relaxed text-cream-card/80">{data.reveal.explanation}</p>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <span className={`rounded-full px-4 py-1.5 text-sm font-semibold ${verdict.tone}`}>{verdict.label}</span>
              <span className="text-sm text-cream-card/70">
                Your answer: <span className="font-medium text-cream-card">{data.student.diagnosis || "—"}</span>
              </span>
            </div>
          </motion.div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-12 px-6 py-12">
        {/* ── Scores ──────────────────────────────────────────────────────── */}
        <Section reduce={reduce} title="The consultant's marks">
          <div className="flex flex-col items-center gap-8 sm:flex-row">
            <ScoreRing value={data.scores.overall} reduce={reduce} />
            <div className="w-full flex-1 space-y-2.5">
              {Object.entries(data.scores.sections).map(([k, v]) => (
                <ScoreBar key={k} label={k} value={v} />
              ))}
              <ScoreBar label="differential" value={data.scores.differential} />
              <ScoreBar label="efficiency" value={data.scores.efficiency} />
            </div>
          </div>
        </Section>

        {/* ── Reasoning path ─────────────────────────────────────────────── */}
        <Section reduce={reduce} title="Your reasoning vs the case">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="card p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">Your differential</h3>
              <ol className="mt-2 space-y-1.5">
                {data.student.differentials.length ? (
                  data.student.differentials.map((d, i) => {
                    const hit =
                      same(d, data.reveal.diagnosis) ||
                      data.reveal.differentials.some((c) => same(c, d));
                    return (
                      <li key={i} className="flex items-baseline gap-2 text-sm text-ink">
                        <span className="font-mono text-xs text-ink-soft">{i + 1}.</span>
                        <span>{d}</span>
                        {hit && <span className="text-gold-deep" title="Also on the case's list">✓</span>}
                      </li>
                    );
                  })
                ) : (
                  <li className="text-sm text-ink-soft">No differential submitted.</li>
                )}
              </ol>
            </div>
            <div className="card-gold p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">The case&apos;s differential</h3>
              <ul className="mt-2 space-y-1.5">
                <li className="text-sm font-semibold text-navy">★ {data.reveal.diagnosis}</li>
                {data.reveal.differentials.map((d, i) => (
                  <li key={i} className="text-sm text-ink">{d}</li>
                ))}
              </ul>
            </div>
          </div>
        </Section>

        {/* ── Investigations ─────────────────────────────────────────────── */}
        <Section reduce={reduce} title="Every test, accounted for">
          <div className="space-y-2">
            {data.investigations.ordered.length === 0 && (
              <p className="text-sm text-ink-soft">You ordered no investigations.</p>
            )}
            {data.investigations.ordered.map((o, i) => (
              <InvestigationRow key={i} inv={o} />
            ))}
            {data.investigations.missed.map((m, i) => (
              <div key={`m-${i}`} className="rounded-xl border border-rose-200 bg-rose-50 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-rose-800">{m.name}</span>
                  <span className="text-xs font-semibold uppercase text-rose-600">Never ordered</span>
                </div>
                {m.significance && <p className="mt-1 text-xs text-rose-700">{m.significance}</p>}
              </div>
            ))}
          </div>
        </Section>

        {/* ── History ────────────────────────────────────────────────────── */}
        <Section reduce={reduce} title="The questions that mattered">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-emerald-700">You asked</h3>
              <ul className="mt-2 space-y-1.5">
                {data.history.asked.length ? (
                  data.history.asked.map((a) => (
                    <li key={a.id}>
                      {a.message_id ? (
                        <a
                          href={`#turn-${a.message_id}`}
                          className="text-sm text-ink underline decoration-gold decoration-2 underline-offset-4 hover:text-navy"
                        >
                          ✓ {a.description}
                        </a>
                      ) : (
                        <span className="text-sm text-ink">✓ {a.description}</span>
                      )}
                    </li>
                  ))
                ) : (
                  <li className="text-sm text-ink-soft">None of the key questions landed.</li>
                )}
              </ul>
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-rose-700">You didn&apos;t ask</h3>
              <ul className="mt-2 space-y-1.5">
                {data.history.missed.length ? (
                  data.history.missed.map((m) => (
                    <li key={m.id} className="text-sm text-ink-soft">✗ {m.description}</li>
                  ))
                ) : (
                  <li className="text-sm text-emerald-700">Nothing — a complete history. Well done.</li>
                )}
              </ul>
            </div>
          </div>
        </Section>

        {/* ── Management ─────────────────────────────────────────────────── */}
        <Section reduce={reduce} title="Management, compared">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="card p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">Your plan</h3>
              <p className="mt-2 whitespace-pre-wrap text-sm text-ink">{data.student.plan || "—"}</p>
              {(data.management.done.length > 0 || data.management.missed.length > 0) && (
                <ul className="mt-3 space-y-1 border-t border-line pt-3">
                  {data.management.done.map((d, i) => (
                    <li key={`d-${i}`} className="text-sm text-emerald-700">✓ {d}</li>
                  ))}
                  {data.management.missed.map((m, i) => (
                    <li key={`x-${i}`} className="text-sm text-rose-700">✗ {m}</li>
                  ))}
                </ul>
              )}
            </div>
            <div className="card-gold p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">The case&apos;s plan</h3>
              <PlanGroup label="Immediate" items={data.management.ideal.emergency} />
              <PlanGroup label="Definitive" items={data.management.ideal.definitive} />
              <PlanGroup label="Follow-up" items={data.management.ideal.follow_up} />
              <PlanGroup label="Patient education" items={data.management.ideal.patient_education} />
            </div>
          </div>
        </Section>

        {/* ── Your clipboard (local, same device) ────────────────────────── */}
        {notes && Object.values(notes).some((v) => v.trim()) && (
          <Section reduce={reduce} title="Your clipboard from the room">
            <div className="grid gap-3 sm:grid-cols-2">
              {(
                [
                  ["Subjective", notes.s],
                  ["Objective", notes.o],
                  ["Assessment", notes.a],
                  ["Plan", notes.p],
                ] as const
              ).map(
                ([label, text]) =>
                  text.trim() && (
                    <div key={label} className="card p-3">
                      <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">{label}</h3>
                      <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{text}</p>
                    </div>
                  ),
              )}
            </div>
          </Section>
        )}

        {/* ── Teaching points ────────────────────────────────────────────── */}
        {(data.teaching.pearls.length > 0 || data.teaching.pitfalls.length > 0) && (
          <Section reduce={reduce} title="Take these with you">
            <div className="grid gap-4 sm:grid-cols-2">
              {data.teaching.pearls.length > 0 && (
                <div className="card-gold p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-gold-deep">Pearls</h3>
                  <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-ink">
                    {data.teaching.pearls.map((p, i) => <li key={i}>{p}</li>)}
                  </ul>
                </div>
              )}
              {data.teaching.pitfalls.length > 0 && (
                <div className="card p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-amber-700">Pitfalls</h3>
                  <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-ink">
                    {data.teaching.pitfalls.map((p, i) => <li key={i}>{p}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </Section>
        )}

        {/* ── Transcript replay ──────────────────────────────────────────── */}
        <Section reduce={reduce} title="The consultation, replayed">
          <p className="-mt-2 mb-4 text-xs text-ink-soft">
            Gold-ringed turns are the questions that earned rubric marks.
          </p>
          <div className="space-y-3">
            {data.transcript.map((t) => (
              <TranscriptTurn key={t.id} turn={t} />
            ))}
          </div>
        </Section>

        {/* ── CTAs ───────────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center justify-center gap-3 border-t border-line pt-8">
          <Link href="/" className="btn-gold px-6 py-2.5">Take another case</Link>
          <Link href="/analytics" className="btn-ghost px-5 py-2.5">View your analytics</Link>
        </div>
      </main>
    </div>
  );
}

function Section({ title, reduce, children }: { title: string; reduce: boolean; children: ReactNode }) {
  return (
    <motion.section
      initial={reduce ? false : { opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.45, ease: "easeOut" }}
    >
      <div className="mb-4 flex items-center gap-3">
        <GoldStrip />
        <h2 className="font-display text-xl font-semibold text-navy">{title}</h2>
      </div>
      {children}
    </motion.section>
  );
}

function ScoreRing({ value, reduce }: { value: number; reduce: boolean }) {
  const v = Math.max(0, Math.min(100, value));
  const r = 52;
  const c = 2 * Math.PI * r;
  const tone = v >= 75 ? "#047857" : v >= 50 ? "#b45309" : "#be123c";
  return (
    <div className="relative h-36 w-36 shrink-0">
      <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
        <circle cx="60" cy="60" r={r} fill="none" stroke="#EFE8D6" strokeWidth="10" />
        <motion.circle
          cx="60" cy="60" r={r} fill="none" stroke={tone} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: reduce ? c * (1 - v / 100) : c }}
          whileInView={{ strokeDashoffset: c * (1 - v / 100) }}
          viewport={{ once: true }}
          transition={{ duration: reduce ? 0 : 1.1, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        <div className="text-center">
          <div className="font-display text-4xl font-bold text-navy">{value}</div>
          <div className="text-[10px] uppercase tracking-wide text-ink-soft">overall</div>
        </div>
      </div>
    </div>
  );
}

function InvestigationRow({ inv }: { inv: Debrief["investigations"]["ordered"][number] }) {
  const style =
    inv.outcome === "INFORMATIVE"
      ? { chip: "bg-emerald-50 text-emerald-700", label: "Informative" }
      : inv.outcome === "LOW_YIELD"
        ? { chip: "bg-amber-50 text-amber-800", label: "Low yield" }
        : { chip: "bg-cream-deep text-ink-soft", label: "Not available" };
  return (
    <div className="card p-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-navy">{inv.name}</span>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${style.chip}`}>{style.label}</span>
      </div>
      {inv.result && <p className="mt-1 text-xs text-ink">{inv.result}</p>}
      {inv.significance && (
        <p className="mt-1 text-xs text-ink-soft">
          <span className="font-semibold">{inv.indicated ? "Why it mattered:" : "Why it didn't:"}</span>{" "}
          {inv.significance}
        </p>
      )}
    </div>
  );
}

function PlanGroup({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-2 first:mt-0">
      <h4 className="text-[11px] font-semibold uppercase tracking-wide text-ink-soft">{label}</h4>
      <ul className="mt-0.5 list-inside list-disc space-y-0.5 text-sm text-ink">
        {items.map((it, i) => <li key={i}>{it}</li>)}
      </ul>
    </div>
  );
}

function TranscriptTurn({ turn }: { turn: Debrief["transcript"][number] }) {
  const isDoctor = turn.role === "student";
  const highlighted = turn.highlights.length > 0;
  return (
    <div id={`turn-${turn.id}`} className={`flex scroll-mt-24 ${isDoctor ? "justify-end" : "justify-start"}`}>
      <div className="max-w-[85%]">
        <div className={`mb-0.5 text-[10px] uppercase tracking-wide ${isDoctor ? "text-right text-navy-600" : "text-gold-deep"}`}>
          {isDoctor ? "You" : "Patient"}
        </div>
        <div
          className={`rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
            isDoctor ? "rounded-tr-sm bg-sky text-navy" : "rounded-tl-sm border border-line bg-cream-card text-navy"
          } ${highlighted ? "ring-2 ring-gold" : ""}`}
        >
          {turn.message}
        </div>
        {highlighted && (
          <div className="mt-1 flex flex-wrap justify-end gap-1">
            {turn.highlights.map((h, i) => (
              <span key={i} className="chip-gold text-[10px]">✓ {h}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
