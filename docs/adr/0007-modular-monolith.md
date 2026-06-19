# ADR-007: Feature-first modular monolith

Status: Accepted · Refs: Volume 2B §5, Volume 5 (closing note)

## Context
The MVP is one deployable, but is expected to grow and may later extract services.

## Decision
Organise the backend by feature module (auth, users, cases, sessions,
conversation, investigations, evaluation, analytics, ai), each owning its
routers/schemas/use-cases/repositories/tests. Shared cross-cutting code lives in
`domain/`, `core/`, and `infrastructure/`.

## Consequences
+ Related code stays together; clear seams for future extraction.
+ One build, one deploy, one CI pipeline for now.
- Requires discipline to avoid cross-module coupling (enforced in review).
