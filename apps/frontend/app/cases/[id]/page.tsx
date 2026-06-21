"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { GoldStrip, NavBar, Skeleton, Spinner } from "@/app/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const STAGES = ["History", "Examination", "Investigations", "Differential", "Diagnosis", "Management"];

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user, loading } = useAuth();
  const router = useRouter();
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  const detail = useQuery({ queryKey: ["case", id], queryFn: () => api.getCase(id), enabled: !!user });

  async function start() {
    setStarting(true);
    try {
      const s = await api.createSession(id);
      router.push(`/sessions/${s.session_id}?opening=${s.opening_message_id}`);
    } finally {
      setStarting(false);
    }
  }

  if (loading || !user) return <Spinner />;

  return (
    <>
      <NavBar />
      <main className="mx-auto max-w-2xl px-6 py-10">
        {detail.isLoading ? (
          <Skeleton className="h-56" />
        ) : detail.data ? (
          <div className="card-gold animate-fade-up p-7">
            <div className="flex items-center gap-2">
              <span className="chip-gold">{detail.data.difficulty}</span>
              <span className="text-xs text-ink-soft">{detail.data.specialty} · {detail.data.estimated_duration} min</span>
            </div>
            <GoldStrip className="mt-4" />
            <h1 className="mt-3 font-display text-3xl font-semibold leading-tight text-navy">{detail.data.title}</h1>
            <p className="mt-3 text-ink-soft">
              You will take a history from a live simulated patient, examine them, order investigations,
              then commit to a ranked differential, a final diagnosis and a management plan. A
              rubric-anchored consultant report is generated at the end.
            </p>

            <div className="mt-5 flex flex-wrap gap-2">
              {STAGES.map((s, i) => (
                <span key={s} className="chip">
                  <span className="font-semibold text-navy">{i + 1}</span> {s}
                </span>
              ))}
            </div>

            <div className="mt-7 flex gap-3">
              <button onClick={start} disabled={starting} className="btn-gold px-6">
                {starting ? "Starting…" : "Start case →"}
              </button>
              <button onClick={() => router.push("/")} className="btn-ghost">Back</button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-ink-soft">Case not found.</p>
        )}
      </main>
    </>
  );
}
