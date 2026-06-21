"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { GoldStrip, NavBar, ScoreBar, Skeleton, Spinner } from "@/app/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function AnalyticsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  const analytics = useQuery({ queryKey: ["analytics"], queryFn: () => api.analytics(), enabled: !!user });

  if (loading || !user) return <Spinner />;

  return (
    <>
      <NavBar />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <header className="animate-fade-up">
          <GoldStrip className="mb-3" />
          <h1 className="font-display text-3xl font-semibold text-navy">Your performance</h1>
          <p className="mt-1 text-ink-soft">Track how your clinical reasoning is improving.</p>
        </header>

        {analytics.isLoading ? (
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>
        ) : analytics.data ? (
          <div className="mt-6 space-y-8">
            <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Cases completed" value={analytics.data.cases_completed} />
              <Stat label="Average score" value={analytics.data.average_score} />
              <Stat label="Tests ordered" value={analytics.data.investigation_usage.total_ordered} />
              <Stat label="Useful tests %" value={analytics.data.investigation_usage.informative_pct} />
            </section>

            <section className="card p-5">
              <h2 className="font-display text-lg font-semibold text-navy">By difficulty</h2>
              {Object.keys(analytics.data.by_difficulty).length ? (
                <div className="mt-3 space-y-3">
                  {Object.entries(analytics.data.by_difficulty).map(([d, s]) => (
                    <ScoreBar key={d} label={`${d} (${s.count})`} value={s.average_score} />
                  ))}
                </div>
              ) : <Empty />}
            </section>

            <section className="card p-5">
              <h2 className="font-display text-lg font-semibold text-navy">Recent scores</h2>
              {analytics.data.score_trend.length ? (
                <div
                  className="mt-4 flex items-end gap-2 border-b border-line pb-0.5"
                  style={{ height: 140 }}
                  aria-label="Recent scores"
                >
                  {analytics.data.score_trend.map((p, i) => (
                    <div
                      key={i}
                      className="flex flex-1 flex-col items-center justify-end gap-1"
                      title={`${new Date(p.date).toLocaleDateString()}: ${p.score}`}
                    >
                      <span className="text-[10px] font-semibold text-ink-soft">{p.score}</span>
                      <div
                        className="w-full max-w-[28px] rounded-t bg-navy transition-colors hover:bg-navy-700"
                        style={{ height: Math.max(6, Math.round((p.score / 100) * 104)) }}
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <Empty />
              )}
            </section>
          </div>
        ) : (
          <p className="mt-6 text-sm text-ink-soft">Could not load analytics.</p>
        )}
      </main>
    </>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="card-gold p-4">
      <div className="font-display text-3xl font-semibold text-navy">{value}</div>
      <div className="text-xs uppercase tracking-wide text-ink-soft">{label}</div>
    </div>
  );
}

function Empty() {
  return <p className="mt-2 text-sm text-ink-soft">Complete a case to see this.</p>;
}
