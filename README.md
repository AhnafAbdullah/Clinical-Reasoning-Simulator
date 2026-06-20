# Clinical Reasoning Simulator

An AI-powered platform where medical students practice clinical reasoning through
realistic, reproducible patient encounters with rubric-anchored consultant feedback.

See [`Documentation/`](Documentation) for the design volumes and
[`Implementation_Plan.md`](Implementation_Plan.md) for the build plan.

## Monorepo
```
apps/backend     FastAPI modular monolith (Python 3.13)
apps/frontend    Next.js (App Router, TypeScript)
packages/        case-schema (and later shared-types, prompt-registry, sdk)
infrastructure/  docker compose, nginx
docs/adr         architecture decision records
```

## Status
- **Phase 0** (foundation + critical spike) — done: monorepo, backend skeleton,
  CI, ADRs, Docker, frontend skeleton, a streaming "walking skeleton"
  (`/api/v1/_skeleton`), and the **0C grading/gating spike** (go/no-go in
  [`docs/spikes/grading_gating`](docs/spikes/grading_gating/FINDINGS.md)):
  consistent tier separation, zero score variance, and zero patient leakage
  under prompt injection against a live model.
- **Phase 1** (domain & data) — done: entities, full schema, immutable cases
  (hash + Postgres trigger), repositories, case JSON Schema, seed. Verified on
  Postgres (`pytest` passing incl. trigger tests).
- **Phase 2** (AIOS) — done: the AI Operating System every agent goes through —
  OpenRouter provider adapter, versioned prompt registry + Jinja2 renderer with
  enforced knowledge boundaries, Context Builder, Memory Manager, Model Router,
  hot-path Validator, Retry Manager, and a Redis-buffered resumable Stream
  Manager, with per-call metrics + audit. Provider key wired server-side; the
  whole subsystem is testable without a live LLM (fake provider).
- **Phase 3** (session & conversation) — done: JWT auth (Argon2, refresh
  rotation, Student/Admin roles), the session state machine (open working phase
  → ordered commitment points), session init, the conversation workflow (202 +
  `message_id`, Patient Agent via AIOS, *decide-then-stream* over the resumable
  SSE buffer), structured physical examination, three-outcome investigation
  ordering, case browsing (metadata only), Redis rate limiting, and a standard
  response envelope. Verified live against OpenRouter: the patient stays in
  character and refuses to leak the diagnosis under prompt injection.
- **Phase 4** (commitments & evaluation) — done: ordered, irreversible
  commitment points (differential → diagnosis → management); the decoupled
  evaluation worker (Examiner free-text extraction + **deterministic software
  aggregation** into section/overall/differential/efficiency scores) writing a
  write-once, provenance-stamped evaluation and a consultant report; the
  evaluation endpoint. A second hand-authored Advanced case (DKA) ships with it.

## Quick start
```bash
# Infrastructure
docker compose -f infrastructure/docker/docker-compose.yml up -d postgres redis

# Backend
cd apps/backend
python -m venv .venv && . .venv/Scripts/activate   # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head && python -m scripts.seed
uvicorn app.main:app --reload                       # http://localhost:8000

# Frontend (separate shell)
cd apps/frontend
npm install
npm run dev                                         # http://localhost:3000
```

Full stack via nginx: `docker compose -f infrastructure/docker/docker-compose.yml up -d --build` → http://localhost
