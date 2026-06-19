# ADR-005: TanStack Query for server state

Status: Accepted · Refs: Volume 6 §22

## Context
The frontend mirrors backend state (sessions, cases, evaluations) and must avoid
duplicating business logic.

## Decision
Server state → TanStack Query. Session state (active id, stage, stream status) →
React Context. Ephemeral UI state → local component state. Business truth always
comes from the backend.

## Consequences
+ Caching, refetch, and loading/error states handled consistently.
- Team convention needed to keep business logic out of components.
