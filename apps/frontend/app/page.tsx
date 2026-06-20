"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const DIFFICULTIES = ["Basic", "Intermediate", "Advanced", "Extremely Hard"];

export default function Dashboard() {
  const { user, loading, logout } = useAuth();
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

  async function start(caseId: string) {
    setStarting(caseId);
    try {
      const s = await api.createSession(caseId);
      router.push(`/sessions/${s.session_id}?opening=${s.opening_message_id}`);
    } finally {
      setStarting(null);
    }
  }

  if (loading || !user) return <div className="p-10 text-sm text-neutral-500">Loading…</div>;

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-neutral-500">Signed in as {user.email}</p>
        </div>
        <button onClick={logout} className="text-sm text-neutral-600 underline">
          Sign out
        </button>
      </header>

      <section className="mt-8">
        <h2 className="text-lg font-medium">Continue a session</h2>
        <div className="mt-3 space-y-2">
          {sessions.data?.length ? (
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
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {cases.data?.map((c) => (
            <div key={c.id} className="rounded-lg border border-neutral-200 p-4">
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                  {c.difficulty}
                </span>
                <span className="text-xs text-neutral-500">{c.estimated_duration} min</span>
              </div>
              <h3 className="mt-2 font-medium">{c.title}</h3>
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
  );
}
