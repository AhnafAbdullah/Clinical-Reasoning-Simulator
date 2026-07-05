/**
 * SDK unit tests: the token-refresh single-flight and the SSE stream reader.
 * These cover the two trickiest client behaviors — rotation-safe refresh under
 * concurrent 401s, and resumable stream parsing that survives bad frames.
 */
import { beforeEach, expect, it, vi } from "vitest";

import { api, streamPatientTurn, tokens } from "@crs/sdk";

// The SDK guards on `typeof window === "undefined"`; give it a window and a
// minimal localStorage so token storage works under Node.
const store = new Map<string, string>();
vi.stubGlobal("window", globalThis);
vi.stubGlobal("localStorage", {
  getItem: (k: string) => store.get(k) ?? null,
  setItem: (k: string, v: string) => void store.set(k, v),
  removeItem: (k: string) => void store.delete(k),
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function sseResponse(frames: string[]): Response {
  const enc = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(c) {
      for (const f of frames) c.enqueue(enc.encode(f));
      c.close();
    },
  });
  return new Response(stream, { status: 200 });
}

beforeEach(() => {
  store.clear();
});

it("shares a single refresh across concurrent 401s (rotation-safe)", async () => {
  tokens.set("stale-access", "refresh-1");
  let refreshCalls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith("/auth/refresh")) {
        refreshCalls += 1;
        // Linger so both 401 retries are waiting on the same in-flight refresh.
        await new Promise((r) => setTimeout(r, 20));
        return jsonResponse({
          success: true,
          data: { access_token: "fresh", refresh_token: "refresh-2" },
        });
      }
      const auth = new Headers(init?.headers).get("Authorization");
      if (auth === "Bearer fresh") {
        return jsonResponse({
          success: true,
          data: { id: "1", email: "a@b.c", display_name: null, role: "Student" },
        });
      }
      return jsonResponse(
        { success: false, error: { code: "UNAUTHORIZED", message: "expired" } },
        401,
      );
    }),
  );

  const [a, b] = await Promise.all([api.me(), api.me()]);
  // Refresh tokens rotate server-side: a second concurrent refresh would have
  // presented the already-spent token and failed. Exactly one may fire.
  expect(refreshCalls).toBe(1);
  expect(a.email).toBe("a@b.c");
  expect(b.email).toBe("a@b.c");
  expect(tokens.refresh()).toBe("refresh-2");
});

it("assembles tokens, skips malformed frames, and completes", async () => {
  tokens.set("access", "refresh");
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      sseResponse([
        'id: 0\nevent: token\ndata: {"token":"It hurts "}\n\n',
        "id: 1\nevent: token\ndata: {not json\n\n", // must not kill the stream
        'id: 2\nevent: token\ndata: {"token":"here."}\n\n',
        "id: 3\nevent: complete\ndata: {}\n\n",
      ]),
    ),
  );

  let text = "";
  let done = false;
  let error: string | null = null;
  await streamPatientTurn("s1", "m1", {
    onToken: (t) => (text += t),
    onDone: () => (done = true),
    onError: (m) => (error = m),
  });

  expect(text).toBe("It hurts here.");
  expect(done).toBe(true);
  expect(error).toBeNull();
});

it("resumes a dropped stream from the last seen sequence id", async () => {
  tokens.set("access", "refresh");
  const enc = new TextEncoder();
  let call = 0;
  let resumeHeader: string | null = null;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      call += 1;
      if (call === 1) {
        // First connection delivers one token, then dies mid-generation.
        // Pull-based so the token is actually consumed before the error —
        // controller.error() inside start() would discard the queued chunk.
        let delivered = false;
        const stream = new ReadableStream<Uint8Array>({
          pull(c) {
            if (!delivered) {
              delivered = true;
              c.enqueue(enc.encode('id: 0\nevent: token\ndata: {"token":"Since "}\n\n'));
            } else {
              c.error(new Error("connection reset"));
            }
          },
        });
        return new Response(stream, { status: 200 });
      }
      resumeHeader = new Headers(init?.headers).get("Last-Event-ID");
      return sseResponse([
        'id: 1\nevent: token\ndata: {"token":"Tuesday."}\n\n',
        "id: 2\nevent: complete\ndata: {}\n\n",
      ]);
    }),
  );

  let text = "";
  let done = false;
  await streamPatientTurn("s1", "m1", {
    onToken: (t) => (text += t),
    onDone: () => (done = true),
    onError: () => undefined,
  });

  expect(call).toBe(2);
  expect(resumeHeader).toBe("0"); // picked up exactly where it left off
  expect(text).toBe("Since Tuesday.");
  expect(done).toBe(true);
});
