"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { GoldStrip, NavBar, Skeleton, Spinner } from "@/app/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const DIFFICULTIES = ["Basic", "Intermediate", "Advanced", "Extremely Hard"];

const DIFF_STYLE: Record<string, string> = {
  Basic: "bg-emerald-50 text-emerald-700",
  Intermediate: "bg-sky text-sky-700",
  Advanced: "bg-amber-50 text-amber-800",
  "Extremely Hard": "bg-rose-50 text-rose-700",
};

export default function Dashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [difficulty, setDifficulty] = useState<string>("");
  const [starting, setStarting] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  const cases = useQuery({
    queryKey: ["cases", difficulty],
    queryFn: () => api.listCases(difficulty || undefined),
    enabled: !!user,
  });
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: () => api.listSessions(), enabled: !!user });
  const analytics = useQuery({ queryKey: ["analytics"], queryFn: () => api.analytics(), enabled: !!user });

  async function start(caseId: string) {
    setStarting(caseId);
    try {
      const s = await api.createSession(caseId);
      router.push(`/sessions/${s.session_id}?opening=${s.opening_message_id}`);
    } finally {
      setStarting(null);
    }
  }

  async function remove(sessionId: string) {
    if (!confirm("Delete this session and its report? This cannot be undone.")) return;
    setDeleting(sessionId);
    try {
      await api.deleteSession(sessionId);
      await Promise.all([sessions.refetch(), analytics.refetch()]);
    } finally {
      setDeleting(null);
    }
  }

  if (loading || !user) return <Spinner />;
  const firstName = user.display_name?.split(" ")[0] || user.email.split("@")[0];

  return (
    <>
      <NavBar />
      <main className="mx-auto max-w-6xl px-6 py-8">
        {/* Welcome + performance summary */}
        <header className="animate-fade-up">
          <GoldStrip className="mb-3" />
          <h1 className="font-display text-3xl font-semibold text-navy">
            Welcome back, {firstName}
          </h1>
          <p className="mt-1 text-ink-soft">Pick a case and step into the consultation room.</p>
        </header>

        {/* Daily Challenge hero */}
        <Link
          href="/daily"
          className="group relative mt-6 block overflow-hidden rounded-xl2 bg-navy p-6 text-cream-card shadow-card transition-shadow hover:shadow-lift"
        >
          <div className="pointer-events-none absolute inset-0 opacity-25" aria-hidden
            style={{ backgroundImage: "radial-gradient(420px 200px at 88% 20%, #c2a14a, transparent 60%), radial-gradient(360px 220px at 10% 120%, #2f6ea5, transparent 60%)" }} />
          <div className="relative flex items-center justify-between gap-4">
            <div>
              <span className="gold-strip mb-3 w-12" />
              <h2 className="font-display text-2xl font-semibold">The Daily Challenge</h2>
              <p className="mt-1 max-w-md text-sm text-cream-card/75">
                A patient walks in. One case, one shot — take the history and reason it out. Build your streak.
              </p>
            </div>
            <span className="hidden shrink-0 rounded-full px-5 py-2.5 font-semibold text-navy transition-transform group-hover:-translate-y-0.5 sm:inline-block"
              style={{ background: "linear-gradient(180deg,#dec987,#c2a14a)" }}>
              Enter the room →
            </span>
          </div>
        </Link>

        <Link href="/analytics" className="card-gold mt-6 block p-5 transition-shadow hover:shadow-lift">
          {analytics.isLoading ? (
            <Skeleton className="h-8 w-72" />
          ) : (
            <div className="flex flex-wrap items-center gap-x-10 gap-y-3">
              <Stat value={analytics.data?.cases_completed ?? 0} label="cases completed" />
              <Stat value={analytics.data?.average_score ?? 0} label="average score" />
              <Stat value={`${analytics.data?.investigation_usage.informative_pct ?? 0}%`} label="useful tests" />
              <span className="ml-auto text-sm font-medium text-navy">View analytics →</span>
            </div>
          )}
        </Link>

        {/* Continue */}
        <section className="mt-10">
          <h2 className="font-display text-xl font-semibold text-navy">Continue a session</h2>
          <div className="mt-3 space-y-2">
            {sessions.isLoading ? (
              <Skeleton className="h-14" />
            ) : sessions.data?.length ? (
              sessions.data.map((s) => (
                <div
                  key={s.session_id}
                  className="card flex items-center justify-between gap-3 px-4 py-3 transition-shadow hover:shadow-lift"
                >
                  <button
                    onClick={() =>
                      router.push(
                        s.status === "COMPLETED"
                          ? `/sessions/${s.session_id}/debrief`
                          : `/sessions/${s.session_id}`,
                      )
                    }
                    className="flex flex-1 items-center justify-between gap-3 text-left"
                  >
                    <span className="text-sm text-ink">
                      Session <span className="font-mono text-ink-soft">{s.session_id.slice(0, 8)}</span> · {s.difficulty}
                    </span>
                    {s.status === "COMPLETED" ? (
                      <span className="chip-gold">View debrief →</span>
                    ) : (
                      <span className="chip-navy">{s.status} · {s.current_stage}</span>
                    )}
                  </button>
                  <button
                    onClick={() => remove(s.session_id)}
                    disabled={deleting === s.session_id}
                    aria-label="Delete session"
                    title="Delete session"
                    className="rounded-lg border border-line p-1.5 text-ink-soft transition-colors hover:border-rose-300 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-50"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m2 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 5v6m4-6v6" />
                    </svg>
                  </button>
                </div>
              ))
            ) : (
              <p className="text-sm text-ink-soft">No sessions yet — start a case below.</p>
            )}
          </div>
        </section>

        {/* Cases */}
        <section className="mt-10">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-xl font-semibold text-navy">Cases</h2>
            <label className="text-sm">
              <span className="sr-only">Filter by difficulty</span>
              <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}
                className="input w-auto py-1.5">
                <option value="">All difficulties</option>
                {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </label>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {cases.isLoading
              ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-44" />)
              : cases.data?.map((c) => (
                  <article key={c.id} className="card-gold flex flex-col p-5 transition-all hover:-translate-y-1 hover:shadow-lift">
                    <div className="flex items-center gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${DIFF_STYLE[c.difficulty] ?? "bg-cream-deep text-ink-soft"}`}>
                        {c.difficulty}
                      </span>
                      <span className="text-xs text-ink-soft">{c.estimated_duration} min</span>
                    </div>
                    <Link href={`/cases/${c.id}`} className="mt-3 font-display text-lg font-semibold leading-snug text-navy hover:underline decoration-gold decoration-2 underline-offset-4">
                      {c.title}
                    </Link>
                    <p className="mt-1 text-sm text-ink-soft">{c.specialty}</p>
                    <button onClick={() => start(c.id)} disabled={starting === c.id} className="btn-primary mt-4 w-full">
                      {starting === c.id ? "Starting…" : "Start case"}
                    </button>
                  </article>
                ))}
            {cases.data?.length === 0 && (
              <p className="text-sm text-ink-soft">No published cases for this filter.</p>
            )}
          </div>
        </section>
      </main>
    </>
  );
}

function Stat({ value, label }: { value: number | string; label: string }) {
  return (
    <div>
      <div className="font-display text-2xl font-semibold text-navy">{value}</div>
      <div className="text-xs uppercase tracking-wide text-ink-soft">{label}</div>
    </div>
  );
}
