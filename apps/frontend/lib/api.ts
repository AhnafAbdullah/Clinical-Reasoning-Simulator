// Base URL for the backend API. In local dev the frontend runs on :3000 and the
// backend on :8000; behind nginx both share an origin and this is "/".
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ?? "http://localhost:8000";
