"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { NavBar, Skeleton, Spinner } from "@/app/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user, loading } = useAuth();
  const router = useRouter();
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  const detail = useQuery({
    queryKey: ["case", id],
    queryFn: () => api.getCase(id),
    enabled: !!user,
  });

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
          <Skeleton className="h-40" />
        ) : detail.data ? (
          <>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                {detail.data.difficulty}
              </span>
              <span className="text-xs text-neutral-500">
                {detail.data.specialty} · {detail.data.estimated_duration} min
              </span>
            </div>
            <h1 className="mt-3 text-2xl font-semibold">{detail.data.title}</h1>
            <p className="mt-2 text-sm text-neutral-600">
              You will take a history from the simulated patient, examine them, order
              investigations, then commit to a ranked differential, a final diagnosis and a
              management plan. A consultant report is generated at the end.
            </p>
            <div className="mt-6 flex gap-3">
              <button
                onClick={start}
                disabled={starting}
                className="rounded-md bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-50"
              >
                {starting ? "Starting…" : "Start case"}
              </button>
              <button
                onClick={() => router.push("/")}
                className="rounded-md border border-neutral-300 px-4 py-2 text-sm"
              >
                Back
              </button>
            </div>
          </>
        ) : (
          <p className="text-sm text-neutral-500">Case not found.</p>
        )}
      </main>
    </>
  );
}
