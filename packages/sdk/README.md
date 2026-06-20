# @crs/sdk

Typed API client for the Clinical Reasoning Simulator backend (Vol 5 / Vol 6 §23).

The single source of truth for: the request envelope, token storage with
refresh-on-401, all endpoint calls, the resource types, and `streamPatientTurn`
(authenticated SSE). The frontend consumes it via the `@crs/sdk` path alias
(`apps/frontend/lib/api.ts` re-exports it), with `experimental.externalDir`
enabling the cross-package import without a full JS workspace.
