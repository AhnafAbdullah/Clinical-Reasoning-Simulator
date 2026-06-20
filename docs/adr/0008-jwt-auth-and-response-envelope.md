# ADR-008: JWT auth with refresh rotation, and a standard response envelope

Status: Accepted · Refs: Volume 5 §5/§6/§8/§24

## Context
Phase 3 introduces authenticated users and the public API surface. We need an
auth scheme that works for a stateless, horizontally scalable backend, and a
uniform response shape so the frontend handles success and errors consistently.

## Decision
- **Passwords:** Argon2 (`argon2-cffi`).
- **Access tokens:** short-lived JWT (HS256, ~15 min), carrying `sub` and `role`.
- **Refresh tokens:** opaque random strings; only their SHA-256 is stored.
  Refresh **rotates** — each use revokes the presented token and issues a new one,
  so a stolen refresh token is single-use.
- **Envelope:** every response is `{success, data, meta}` or
  `{success: false, error: {code, message}}`. Domain errors map to HTTP status +
  machine code in one place (`app/api/errors.py`); use cases stay framework-free.
- **Rate limiting:** Redis fixed-window counters per (action, principal), applied
  to login, session creation, messages and investigation ordering. Fail-open if
  Redis is unavailable — a throttle must not take down the API.
- **Roles:** Student / Admin (Faculty reserved). Google OAuth is behind the
  `enable_google_login` flag and not yet implemented.

## Consequences
+ Stateless verification (no session store on the hot path); revocation only
  needed for refresh tokens, which we persist.
+ Uniform client handling; errors are machine-readable.
- JWTs cannot be revoked before expiry — kept short to bound exposure.
- Fixed-window limiting allows bursts at window edges (acceptable for the MVP;
  a sliding window can replace it behind the same interface).
