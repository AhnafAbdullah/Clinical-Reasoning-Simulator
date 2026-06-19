# ADR-004: Immutable published cases (hash + DB trigger)

Status: Accepted · Refs: Volume 3 §8

## Context
Reproducible encounters require that a published case never changes underneath a
session. "Immutable by convention" is not enough.

## Decision
On publish, compute `content_hash` = SHA-256 of the canonical JSON and store it.
A Postgres trigger rejects UPDATE/DELETE on `status='Published'` rows except the
single transition `Published → Archived` with content unchanged. The application
layer mirrors this guard. Sessions persist `(case_id, version, content_hash)`.

## Consequences
+ Tamper-evident, reproducible-by-inputs encounters; enforced in two layers.
- Edits require publishing a new version (intended).
