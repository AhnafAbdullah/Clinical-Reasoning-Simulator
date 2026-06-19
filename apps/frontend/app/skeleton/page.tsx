"use client";

import { useState } from "react";

import { API_BASE } from "@/lib/api";

// Phase 0B walking-skeleton demo: proves the POST -> message_id -> SSE plumbing
// against the backend's /api/v1/_skeleton endpoints. Replaced by the real
// conversation UI in Phase 5.
export default function SkeletonDemo() {
  const [message, setMessage] = useState("How long have you had chest pain?");
  const [output, setOutput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    setBusy(true);
    setOutput("");
    try {
      const res = await fetch(`${API_BASE}/api/v1/_skeleton/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const { message_id } = await res.json();

      await new Promise<void>((resolve) => {
        const es = new EventSource(
          `${API_BASE}/api/v1/_skeleton/stream?message_id=${message_id}`,
        );
        es.addEventListener("token", (e) => {
          setOutput((prev) => prev + JSON.parse((e as MessageEvent).data).token);
        });
        es.addEventListener("complete", () => {
          es.close();
          resolve();
        });
        es.addEventListener("error", () => {
          es.close();
          resolve();
        });
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-xl font-semibold">Streaming skeleton</h1>
      <div className="mt-4 flex gap-2">
        <input
          className="flex-1 rounded-md border border-neutral-300 px-3 py-2 text-sm"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
        <button
          onClick={send}
          disabled={busy}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {busy ? "Streaming…" : "Send"}
        </button>
      </div>
      <pre className="mt-4 min-h-16 whitespace-pre-wrap rounded-md bg-neutral-50 p-3 text-sm">
        {output}
      </pre>
    </main>
  );
}
