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
                <button
                  key={s.session_id}
                  onClick={() => router.push(`/sessions/${s.session_id}`)}
                  className="card flex w-full items-center justify-between px-4 py-3 text-left transition-shadow hover:shadow-lift"
                >
                  <span className="text-sm text-ink">
                    Session <span className="font-mono text-ink-soft">{s.session_id.slice(0, 8)}</span> · {s.difficulty}
                  </span>
                  <span className="chip-navy">{s.status} · {s.current_stage}</span>
                </button>
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
