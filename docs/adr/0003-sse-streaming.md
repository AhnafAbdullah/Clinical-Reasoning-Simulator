# ADR-003: Server-Sent Events for AI streaming

Status: Accepted · Refs: Volume 4D §13, Volume 5 §12-13

## Context
Patient responses stream token-by-token. The channel is one-way (server → client).

## Decision
`POST /sessions/{id}/messages` returns `202` with a `message_id` (correlation id);
the client opens `GET /sessions/{id}/stream?message_id=…` (SSE) to receive
`token`/`complete`/`error` events. At most one active generation per session;
tokens buffered in Redis so a dropped connection can re-attach and resume.
WebSockets are reserved for future bidirectional features.

## Consequences
+ Simple, proxy-friendly, resumable.
- Two calls per turn; requires correlation-id plumbing (proven in the 0B skeleton).
