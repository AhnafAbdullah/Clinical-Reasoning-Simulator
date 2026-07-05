// Typed client for the Clinical Reasoning Simulator API (Vol 5).
// Unwraps the standard {success, data, meta} envelope, attaches the bearer
// token, and transparently refreshes it once on a 401.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ?? "http://localhost:8000";

const ACCESS_KEY = "crs_access";
const REFRESH_KEY = "crs_refresh";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

// ── Token storage (client-side only) ─────────────────────────────────────────────
export const tokens = {
  access: () => (typeof window === "undefined" ? null : localStorage.getItem(ACCESS_KEY)),
  refresh: () => (typeof window === "undefined" ? null : localStorage.getItem(REFRESH_KEY)),
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

async function rawFetch(path: string, init: RequestInit, withAuth: boolean): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const access = tokens.access();
  if (withAuth && access) headers.set("Authorization", `Bearer ${access}`);
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

// Refresh tokens rotate server-side (each use revokes the presented token), so
// concurrent 401s must share ONE refresh call: if each caller refreshed on its
// own, the first would win and the rest would present an already-spent token
// and fail. Single-flight: everyone awaits the same in-flight promise.
let refreshInFlight: Promise<boolean> | null = null;

function tryRefresh(): Promise<boolean> {
  refreshInFlight ??= doRefresh().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

async function doRefresh(): Promise<boolean> {
  const refresh = tokens.refresh();
  if (!refresh) return false;
  try {
    const res = await rawFetch(
      "/api/v1/auth/refresh",
      { method: "POST", body: JSON.stringify({ refresh_token: refresh }) },
      false,
    );
    if (!res.ok) return false;
    const body = await res.json().catch(() => null);
    if (!body?.data?.access_token || !body?.data?.refresh_token) return false;
    tokens.set(body.data.access_token, body.data.refresh_token);
    return true;
  } catch {
    return false; // network failure — let the original 401 surface
  }
}

async function request<T>(path: string, init: RequestInit = {}, withAuth = true): Promise<T> {
  let res = await rawFetch(path, init, withAuth);
  if (res.status === 401 && withAuth && (await tryRefresh())) {
    res = await rawFetch(path, init, withAuth);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok || !body?.success) {
    const err = body?.error ?? { code: "INTERNAL_ERROR", message: res.statusText };
    throw new ApiError(err.code, err.message, res.status);
  }
  return body.data as T;
}

// ── Types ────────────────────────────────────────────────────────────────────────
export interface TokenPair {
  access_token: string;
  refresh_token: string;
}
export interface UserProfile {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
}
export interface CaseSummary {
  id: string;
  title: string;
  difficulty: string;
  specialty: string;
  estimated_duration: number;
}
export interface SessionDetail {
  session_id: string;
  case_id: string;
  status: string;
  current_stage: string;
  difficulty: string;
  started_at: string;
  completed_at: string | null;
}
export interface MessageItem {
  id: string;
  role: string;
  message: string;
  timestamp: string;
}
export interface PatientPresentation {
  name: string;
  age: number | null;
  gender: string;
  affect: string;
}
export interface InvestigationResult {
  status: string;
  outcome: string;
  indicated: boolean | null;
  duplicate: boolean;
  result: Record<string, unknown>;
}
export interface Evaluation {
  overall_score: number;
  section_scores: Record<string, number>;
  differential_score: number;
  efficiency_score: number;
  feedback: Record<string, unknown>;
  generated_at: string;
}
export interface Analytics {
  cases_completed: number;
  average_score: number;
  by_difficulty: Record<string, { count: number; average_score: number }>;
  score_trend: { date: string; score: number }[];
  investigation_usage: { total_ordered: number; informative: number; informative_pct: number };
}
export interface DailyStatus {
  date: string;
  difficulty: string;
  specialty: string;
  estimated_duration: number;
  attempted: boolean;
  session_id: string | null;
  streak: number;
}
export interface DailyStart {
  session_id: string;
  status: string;
  opening_message_id: string | null;
  resumed: boolean;
  streak: number;
}

// ── Endpoints ──────────────────────────────────────────────────────────────────
export const api = {
  // auth
  register: (email: string, password: string, display_name?: string) =>
    request<TokenPair>(
      "/api/v1/auth/register",
      { method: "POST", body: JSON.stringify({ email, password, display_name }) },
      false,
    ),
  login: (email: string, password: string) =>
    request<TokenPair>(
      "/api/v1/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false,
    ),
  me: () => request<UserProfile>("/api/v1/auth/me"),
  logout: (refresh_token: string) =>
    request("/api/v1/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token }) }),

  // cases
  listCases: (difficulty?: string) =>
    request<CaseSummary[]>(`/api/v1/cases${difficulty ? `?difficulty=${difficulty}` : ""}`),
  getCase: (id: string) => request<CaseSummary>(`/api/v1/cases/${id}`),

  // sessions
  createSession: (case_id: string) =>
    request<{ session_id: string; status: string; opening_message_id: string }>(
      "/api/v1/sessions",
      { method: "POST", body: JSON.stringify({ case_id }) },
    ),
  getSession: (id: string) => request<SessionDetail>(`/api/v1/sessions/${id}`),
  getPatient: (id: string) => request<PatientPresentation>(`/api/v1/sessions/${id}/patient`),
  listSessions: () => request<SessionDetail[]>("/api/v1/sessions"),
  deleteSession: (id: string) =>
    request<{ deleted: boolean }>(`/api/v1/sessions/${id}`, { method: "DELETE" }),

  // conversation
  sendMessage: (id: string, message: string) =>
    request<{ message_id: string; status: string }>(`/api/v1/sessions/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  listMessages: (id: string) => request<MessageItem[]>(`/api/v1/sessions/${id}/messages`),

  // physical exam + investigations
  physicalExam: (id: string, system: string) =>
    request<{ system: string; findings: Record<string, unknown> }>(
      `/api/v1/sessions/${id}/physical-exam`,
      { method: "POST", body: JSON.stringify({ system }) },
    ),
  catalog: (search?: string) =>
    request<{ name: string; category: string }[]>(
      `/api/v1/investigations${search ? `?search=${encodeURIComponent(search)}` : ""}`,
    ),
  orderInvestigation: (id: string, investigation: string) =>
    request<InvestigationResult>(`/api/v1/sessions/${id}/investigations`, {
      method: "POST",
      body: JSON.stringify({ investigation }),
    }),

  // commitments + evaluation
  submitDifferentials: (id: string, differentials: string[]) =>
    request<{ current_stage: string }>(`/api/v1/sessions/${id}/differentials`, {
      method: "POST",
      body: JSON.stringify({ differentials }),
    }),
  submitDiagnosis: (id: string, diagnosis: string) =>
    request<{ current_stage: string }>(`/api/v1/sessions/${id}/diagnosis`, {
      method: "POST",
      body: JSON.stringify({ diagnosis }),
    }),
  submitManagement: (id: string, plan: string) =>
    request<{ status: string }>(`/api/v1/sessions/${id}/management`, {
      method: "POST",
      body: JSON.stringify({ plan }),
    }),
  getEvaluation: (id: string) =>
    request<Evaluation | { status: string }>(`/api/v1/sessions/${id}/evaluation`),

  // analytics
  analytics: () => request<Analytics>("/api/v1/users/me/analytics"),

  // daily challenge
  dailyStatus: () => request<DailyStatus>("/api/v1/daily"),
  startDaily: () => request<DailyStart>("/api/v1/daily/start", { method: "POST" }),
};

// ── Authenticated SSE (EventSource can't send headers) ───────────────────────────
// The server buffers each generation as a sequenced event log, so a dropped
// connection is resumed via the Last-Event-ID header instead of losing the turn.
const MAX_STREAM_RESUMES = 2;

export async function streamPatientTurn(
  sessionId: string,
  messageId: string,
  handlers: { onToken: (t: string) => void; onDone: () => void; onError: (m: string) => void },
  options: { signal?: AbortSignal } = {},
): Promise<void> {
  const { signal } = options;
  let lastSeq = -1;
  let resumes = 0;
  let refreshedOnce = false;

  for (;;) {
    try {
      const headers: Record<string, string> = { Accept: "text/event-stream" };
      if (lastSeq >= 0) headers["Last-Event-ID"] = String(lastSeq);
      const res = await rawFetch(
        `/api/v1/sessions/${sessionId}/stream?message_id=${messageId}`,
        { method: "GET", headers, signal },
        true,
      );
      if (res.status === 401 && !refreshedOnce) {
        refreshedOnce = true;
        if (await tryRefresh()) continue; // expired access token — retry with a fresh one
      }
      if (!res.ok || !res.body) return handlers.onError("stream failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";
        for (const evt of events) {
          let type = "message";
          let data = "";
          let seq = NaN;
          for (const line of evt.split("\n")) {
            if (line.startsWith("id:")) seq = parseInt(line.slice(3).trim(), 10);
            else if (line.startsWith("event:")) type = line.slice(6).trim();
            else if (line.startsWith("data:")) data += line.slice(5).trim();
          }
          if (!data) continue;
          let parsed: { token?: string; error?: string };
          try {
            parsed = JSON.parse(data);
          } catch {
            continue; // one malformed frame must not kill the whole stream
          }
          if (Number.isFinite(seq)) lastSeq = seq;
          if (type === "token") handlers.onToken(parsed.token ?? "");
          else if (type === "complete") return handlers.onDone();
          else if (type === "error") return handlers.onError(parsed.error ?? "error");
        }
      }
      // Closed without a terminal event: the connection dropped mid-generation.
      throw new Error("stream closed before completion");
    } catch (err) {
      if (signal?.aborted) return; // deliberate cancel (leaving the room) — no callbacks
      if (resumes++ >= MAX_STREAM_RESUMES) {
        return handlers.onError("Connection lost while the patient was replying.");
      }
      await new Promise((r) => setTimeout(r, 500));
      if (signal?.aborted) return;
    }
  }
}
