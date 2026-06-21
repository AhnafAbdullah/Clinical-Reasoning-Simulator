"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ClinicScene } from "@/app/components/clinic";
import { ConsultRoom } from "@/app/components/consult-room";
import { GoldStrip } from "@/app/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function DailyPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  const status = useQuery({ queryKey: ["daily"], queryFn: () => api.dailyStatus(), enabled: !!user });

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [opening, setOpening] = useState<string | null>(null);
  const [streak, setStreak] = useState(0);
  const [starting, setStarting] = useState(false);

  async function begin() {
    if (starting) return;
    setStarting(true);
    try {
      const res = await api.startDaily();
      setStreak(res.streak);
      setOpening(res.opening_message_id);
      setSessionId(res.session_id);
    } catch (err) {
      setStarting(false);
      alert(err instanceof ApiError ? err.message : "Could not start today's challenge.");
    }
  }

  if (loading || !user) return <div className="min-h-screen bg-navy" />;

  // Once started, the shared room takes over (with its own walk-in cinematic).
  if (sessionId) {
    return (
      <ConsultRoom sessionId={sessionId} openingMessageId={opening} streak={streak} onExit={() => router.push("/")} />
    );
  }

  return (
    <div className="fixed inset-0 overflow-hidden bg-navy">
      <div className="absolute inset-0" style={{ filter: "blur(12px)", transform: "scale(1.1)" }}>
        <ClinicScene className="h-full w-full" />
      </div>
      <div className="absolute inset-0 bg-navy/60" />
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="absolute inset-0 z-20 grid place-items-center px-6 text-center"
      >
        <div className="max-w-lg">
          <button onClick={() => router.push("/")} className="absolute left-5 top-5 text-sm text-cream-card/70 hover:text-cream-card">
            ← Dashboard
          </button>
          {(status.data?.streak ?? 0) > 0 && (
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-gold/40 bg-navy/40 px-3 py-1 text-sm text-gold-soft backdrop-blur">
              🔥 {status.data?.streak}-day streak — keep it alive
            </div>
          )}
          <h1 className="font-display text-5xl font-semibold text-cream-card drop-shadow">The Daily Challenge</h1>
          <p className="mx-auto mt-3 max-w-sm text-cream-card/75">
            One patient. One shot. Walk into the room, take the history, and reason your way to the
            diagnosis.{" "}
            {status.data?.difficulty ? (
              <>
                Today&apos;s case is <b className="text-gold-soft">{status.data.difficulty}</b>.
              </>
            ) : null}
          </p>

          <motion.button
            onClick={begin}
            disabled={starting}
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.97 }}
            className="group relative mt-9 inline-flex items-center gap-3 rounded-full px-9 py-4 text-lg font-semibold text-navy disabled:opacity-70"
            style={{ background: "linear-gradient(180deg,#dec987,#c2a14a)" }}
          >
            <span className="absolute inset-0 -z-10 animate-pulse rounded-full" style={{ boxShadow: "0 0 50px 8px rgba(194,161,74,0.55)" }} />
            {starting ? "Opening the door…" : status.data?.attempted ? "Resume today's patient →" : "Enter the room →"}
          </motion.button>
          <p className="mt-4 text-xs text-cream-card/50">Plays once per day · builds your streak</p>
        </div>
      </motion.div>

      {/* Hint of the GoldStrip identity */}
      <div className="pointer-events-none absolute bottom-6 left-1/2 -translate-x-1/2">
        <GoldStrip className="w-16" />
      </div>
    </div>
  );
}
