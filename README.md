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
- **Phase 0** (foundation) — done: monorepo, backend skeleton, CI, ADRs, Docker,
  frontend skeleton, and a streaming "walking skeleton" (`/api/v1/_skeleton`).
- **Phase 1** (domain & data) — done: entities, full schema, immutable cases
  (hash + Postgres trigger), repositories, case JSON Schema, seed. Verified on
  Postgres (`pytest` passing incl. trigger tests).
- **Phase 2** (AIOS) — done: the AI Operating System every agent goes through —
  OpenRouter provider adapter, versioned prompt registry + Jinja2 renderer with
  enforced knowledge boundaries, Context Builder, Memory Manager, Model Router,
  hot-path Validator, Retry Manager, and a Redis-buffered resumable Stream
  Manager, with per-call metrics + audit. Provider key wired server-side; the
  whole subsystem is testable without a live LLM (fake provider).

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
