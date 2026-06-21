"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ConsultRoom } from "@/app/components/consult-room";
import { Spinner } from "@/app/components/ui";
import { useAuth } from "@/lib/auth";

export default function SessionPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user, loading } = useAuth();
  const opening = useRef<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  // Read ?opening= once (set when the case was just started) and clean the URL.
  useEffect(() => {
    opening.current = new URLSearchParams(window.location.search).get("opening");
    setReady(true);
  }, []);

  if (loading || !user || !ready) return <Spinner label="Entering the room…" />;

  return <ConsultRoom sessionId={id} openingMessageId={opening.current} onExit={() => router.push("/")} />;
}
