"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { NavBar, Skeleton, Spinner } from "@/app/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const DIFFICULTIES = ["Basic", "Intermediate", "Advanced", "Extremely Hard"];

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
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api.listSessions(),
    enabled: !!user,
  });
  const analytics = useQuery({
    queryKey: ["analytics"],
    queryFn: () => api.analytics(),
    enabled: !!user,
  });

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

  return (
    <>
      <NavBar />
      <main className="mx-auto max-w-5xl px-6 py-8">
        {/* Performance summary (Vol 6 §9) */}
        <Link
          href="/analytics"
          className="block rounded-lg border border-neutral-200 p-4 hover:bg-neutral-50"
        >
          {analytics.isLoading ? (
            <Skeleton className="h-6 w-64" />
          ) : (
            <div className="flex flex-wrap items-center gap-x-8 gap-y-1 text-sm">
              <span className="font-medium">Your performance →</span>
              <span>
                <b>{analytics.data?.cases_completed ?? 0}</b> completed
              </span>
              <span>
                avg <b>{analytics.data?.average_score ?? 0}</b>
              </span>
              <span>
                tests informative <b>{analytics.data?.investigation_usage.informative_pct ?? 0}%</b>
              </span>
            </div>
          )}
        </Link>

        <section className="mt-8">
          <h2 className="text-lg font-medium">Continue a session</h2>
          <div className="mt-3 space-y-2">
            {sessions.isLoading ? (
              <Skeleton className="h-12" />
            ) : sessions.data?.length ? (
              sessions.data.map((s) => (
                <button
                  key={s.session_id}
                  onClick={() => router.push(`/sessions/${s.session_id}`)}
                  className="flex w-full items-center justify-between rounded-md border border-neutral-200 px-4 py-3 text-left text-sm hover:bg-neutral-50"
                >
                  <span>
                    Session {s.session_id.slice(0, 8)} · {s.difficulty}
                  </span>
                  <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs">
                    {s.status} / {s.current_stage}
                  </span>
                </button>
              ))
            ) : (
              <p className="text-sm text-neutral-500">No sessions yet — start a case below.</p>
            )}
          </div>
        </section>

        <section className="mt-10">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium">Cases</h2>
            <label className="text-sm">
              <span className="sr-only">Filter by difficulty</span>
              <select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
                className="rounded-md border border-neutral-300 px-2 py-1 text-sm"
              >
                <option value="">All difficulties</option>
                {DIFFICULTIES.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {cases.isLoading
              ? Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-36" />)
              : cases.data?.map((c) => (
                  <div key={c.id} className="rounded-lg border border-neutral-200 p-4">
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                        {c.difficulty}
                      </span>
                      <span className="text-xs text-neutral-500">{c.estimated_duration} min</span>
                    </div>
                    <Link href={`/cases/${c.id}`} className="mt-2 block font-medium hover:underline">
                      {c.title}
                    </Link>
                    <p className="text-sm text-neutral-500">{c.specialty}</p>
                    <button
                      onClick={() => start(c.id)}
                      disabled={starting === c.id}
                      className="mt-3 rounded-md bg-neutral-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                    >
                      {starting === c.id ? "Starting…" : "Start case"}
                    </button>
                  </div>
                ))}
            {cases.data?.length === 0 && (
              <p className="text-sm text-neutral-500">No published cases for this filter.</p>
            )}
          </div>
        </section>
      </main>
    </>
  );
}
