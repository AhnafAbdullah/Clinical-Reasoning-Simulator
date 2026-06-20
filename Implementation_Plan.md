# Clinical Reasoning Simulator — Implementation Plan

**Status:** Draft v1.0 · **Scope:** MVP (Internal Medicine, one specialty) · **Audience:** engineering + content
**Source of truth:** `Documentation/Volume_1…6` (corrected editions). This plan operationalises those volumes; where they conflict, the volumes win and this plan is updated.

---

## 0. How to read this plan

The work is organised into **phases** that each ship something demonstrable. Phases are ordered by dependency, not by document number. Two principles drive the ordering:

1. **De-risk the hard, product-defining problems first.** The product lives or dies on (a) reliable rubric-anchored grading of free-text reasoning and (b) the patient never leaking hidden information. We prove both in a throwaway spike *before* building the cathedral around them (Phase 0).
2. **Walking skeleton before features.** A thin end-to-end slice (browser → API → DB → OpenRouter → stream → browser) exists by end of Phase 0, then we thicken it.

Each phase lists: **Goal**, **Tasks**, **Deliverables**, **Exit criteria (DoD)**, and **Volume refs**.

Global Definition of Done for any feature (from Vol 2B §40): use case implemented · tests written · API documented (OpenAPI) · logging added · errors handled · prompt/template versions tracked · architecture respected · CI green · docs updated.

---

## 1. Target architecture (recap)

- **Monorepo** (Vol 2B §1). Backend is a **feature-first modular monolith** (Vol 5 close / Vol 2B §5).
- **Backend:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0, **Alembic** (migrations), PostgreSQL, Redis, **Jinja2** (prompt templates), JWT + Argon2, OpenRouter via one thin adapter.
- **Frontend:** Next.js (App Router), TypeScript, TailwindCSS, shadcn/ui, Lucide, TanStack Query, React Hook Form + Zod, SSE client.
- **Clean-ish layering** (Vol 2A): API → application/use-cases → domain → infrastructure. Domain imports nothing external.
- **AI = infrastructure** behind the AIOS. Clinical truth originates from the **immutable case JSON**, never the model (Vol 4A).

### Monorepo layout
```
clinical-reasoning-simulator/
├── apps/
│   ├── backend/          # FastAPI modular monolith
│   └── frontend/         # Next.js
├── packages/
│   ├── shared-types/     # TS types generated from OpenAPI
│   ├── prompt-registry/  # versioned .md templates + fragments (Vol 4B)
│   ├── case-schema/      # JSON Schema for clinical cases (Vol 3)
│   └── sdk/              # typed frontend API client
├── infrastructure/       # docker, nginx, scripts, deployment
├── docs/                 # ADRs + this plan
└── README.md
```

### Backend module layout (per module: `routers/ schemas/ use_cases/ domain/ repositories/ tests/`)
```
apps/backend/app/
├── api/            # middleware, exception handlers, router registration, deps
├── core/           # config, security, DI container, logging
├── modules/        # auth, users, cases, sessions, conversation,
│                   # investigations, evaluation, analytics, ai
├── domain/         # cross-cutting entities, value objects, interfaces
├── infrastructure/ # db, redis, storage, ai (OpenRouter), oauth, streaming
└── main.py
```

---

## 2. Phase plan

### Phase 0 — Foundations + Critical Spike  ⏱ ~1.5–2 weeks
**Goal:** repo, tooling, CI, a walking skeleton, and a *go/no-go* answer on grading & gating.

**0A. Repo & tooling**
- [ ] Init monorepo, package manager (pnpm for JS workspaces; uv or Poetry for Python).
- [ ] Backend skeleton: FastAPI app, `core/config` (env-driven, Vol 2A §16), structured logging with request/session/correlation IDs (Vol 2B §28).
- [ ] DB + migrations: Postgres via Docker, SQLAlchemy 2.0, Alembic initialised.
- [ ] Redis container; healthcheck wiring.
- [ ] `GET /health` (liveness) + `GET /ready` (checks Postgres, Redis, OpenRouter) (Vol 5 §20).
- [ ] Frontend skeleton: Next.js App Router, Tailwind, shadcn/ui, TanStack Query provider, base layout.
- [ ] Quality gates: Black, Ruff, mypy, pytest (backend); ESLint, Prettier, tsc, Vitest/Playwright (frontend); pre-commit hooks; Conventional Commits.
- [ ] CI (GitHub Actions): lint → typecheck → unit → build → docker (Vol 2B §36).
- [ ] Docker Compose: backend, frontend, postgres, redis, nginx (Vol 2B §37).
- [ ] ADRs seeded: Clean Architecture, OpenRouter, SSE streaming, immutable cases, React Query, **versioned-template prompts (supersedes PDL)**, **modular monolith** (Vol 2B §39).

**0B. Walking skeleton (thin vertical slice)**
- [ ] One use case end-to-end: a stub "echo patient" — `POST /sessions/{id}/messages` → OpenRouter call → SSE stream → rendered in a minimal page. No real case logic yet; proves the streaming/correlation-id plumbing (Vol 5 §12–13).

**0C. 🔴 Critical spike — grading & gating (throwaway, time-boxed)** — ✅ DONE (conditional GO; see `docs/spikes/grading_gating/FINDINGS.md`).
This is the single most important risk. *Do not skip.*
- [ ] Hand-author **2 full case JSONs** (1 Basic, 1 Advanced) including a real, itemised rubric (Vol 3 §18 schema).
- [ ] Build a minimal **Examiner harness** offline: feed a transcript + rubric → LLM detects which items are satisfied + evidence span → software aggregates score (Vol 4C "Scoring mechanism", Vol 3 §18).
- [ ] Create ~10 transcripts per case spanning strong/average/poor students.
- [ ] **Measure:** score variance on repeated runs of identical input; correctness of item detection vs a human key; can it reliably separate poor/average/strong?
- [ ] Build a minimal **gating screen**: run a patient prompt with renderer-enforced `forbidden_context`; attempt prompt-injection + "what's my diagnosis"; measure leakage rate.

**Exit criteria (go/no-go):**
- Examiner separates student tiers consistently; per-item detection agrees with human key at an agreed bar (e.g. ≥90% on structured items, ≥80% on history items); score variance within an agreed tolerance.
- Patient gating holds against the injection set with near-zero leakage after screening+regeneration.
- If criteria fail → revisit rubric format / detection prompt / decomposition **before** committing to the full build. Document findings in `docs/spikes/`.

**Volume refs:** Vol 2A, 2B, 4A, 4B, 4C §5–6, 3 §18.

---

### Phase 1 — Domain & Data  ⏱ ~1.5 weeks
**Goal:** persistent, validated, immutable data foundation.

**Tasks**
- [ ] Domain entities & value objects (Vol 2B §4): `User, ClinicalCase, ClinicalSession, ConversationMessage, InvestigationOrder, DifferentialSubmission, DiagnosisSubmission, TreatmentSubmission, Evaluation, AuditLog`.
- [ ] Alembic migrations for all tables (Vol 3 §7–27) including the **corrected schema**: session `case_version` + `case_content_hash`; case `content_hash, reviewed_by, reviewer_credentials, reviewed_at, medical_signoff`; `differential_submissions`; evaluation `differential_score, efficiency_score, rubric_version`; investigation order `normalized_name, indicated, outcome`.
- [ ] Indexes (Vol 3 §31) incl. `differential_submissions.session_id`.
- [ ] **Case JSON Schema** package (`packages/case-schema`) with `schema_version`; validation on load/publish (Vol 3 §10–19, §30).
- [ ] **Immutability enforcement** (Vol 3 §8): DB trigger blocking UPDATE/DELETE on `status='Published'` except `→ Archived`; SHA-256 `content_hash` computed at publish + verified on load; sessions bind to `(case_id, version, content_hash)`.
- [ ] Soft-delete convention + **erasure path** for personal data (Vol 3 §4 Principle 6 exception).
- [ ] Repository interfaces (domain) + SQLAlchemy implementations (infra) (Vol 2B §13).
- [ ] Seed the 2 spike cases as real published cases (manual sign-off for now).

**Exit criteria:** migrations apply/rollback cleanly; publishing a case computes+stores hash; editing a published row is rejected by the DB; case JSON validates against schema; repos unit-tested.

**Volume refs:** Vol 3 (all), Vol 2B §4/§13.

---

### Phase 2 — AI Subsystem (AIOS core)  ⏱ ~2 weeks
**Goal:** the orchestration layer every agent goes through.

**Tasks** (Vol 4A components; Vol 4B templates)
- [ ] **OpenRouter adapter** implementing `generate() / stream() / health_check() / estimate_cost()` — the single MVP `LLMProvider` (Vol 4A §15, Vol 2A §9).
- [ ] **Prompt registry + renderer** (`packages/prompt-registry`): Markdown + YAML frontmatter + Jinja2; `StrictUndefined`; includes for fragments; **renderer enforces `allowed/forbidden_context`** and asserts no forbidden section in output (Vol 4B §9, §11).
- [ ] **Context Builder** (loads only required case sections) + **Memory Manager** (recent messages, session summary, extracted facts) (Vol 4A §9–11).
- [ ] **Model Router** (policy: reasoning vs latency profiles → OpenRouter model) (Vol 4A §14, Vol 4C table).
- [ ] **Validator**: fast deterministic hot-path checks only (format/length/structure/role-stage/forbidden-content screens) — **no extra LLM calls in the turn path** (Vol 4A §17).
- [ ] **Retry Manager** (same model → alt model → alt route → graceful) with backoff (Vol 4A §18).
- [ ] **Stream Manager**: SSE, Redis-buffered, keyed by `message_id`, one active generation/session, resumable (Vol 4A §16, Vol 4D §13, Vol 5 §13).
- [ ] **Metrics + Audit logging** per AI call (Vol 4A §19–20).
- [ ] Config-driven everything; feature flags `ENABLE_STREAMING/GOOGLE_LOGIN/EVALUATION/ANALYTICS` (Vol 2B §31–32).

**Exit criteria:** a template renders with enforced boundaries; injection test fails to leak; retries/fallbacks exercised in tests; streaming resumes after a dropped connection; every call audited with versions.

**Volume refs:** Vol 4A, 4B, 4C §10–13.

---

### Phase 3 — Clinical Session & Conversation  ⏱ ~2 weeks
**Goal:** start a case and conduct gated history/exam/investigations.

**Tasks** (Vol 4D workflows; Vol 5 endpoints)
- [ ] **Auth module**: register/login, Google OAuth, JWT + refresh rotation, Argon2 (Vol 2B §22, Vol 5 §8). Roles Student/Admin (Faculty reserved).
- [ ] **Session state machine** — canonical: `status ∈ {CREATED,ACTIVE,EVALUATING,COMPLETED,ARCHIVED}`, `current_stage ∈ {GREETING,HISTORY,PHYSICAL_EXAM,INVESTIGATIONS,DIFFERENTIAL,FINAL_DIAGNOSIS,MANAGEMENT}` (Vol 4D §4–5, Vol 3 §20).
- [ ] **Session init workflow** with rollback-on-failure; opening patient statement streamed (Vol 4D §6).
- [ ] **Conversation workflow**: `POST /messages` → 202 + `message_id`; Patient Agent via AIOS; persist before complete; update memory (Vol 4D §7, Vol 5 §12).
- [ ] **Physical exam workflow**: structured selection → findings from case JSON, no AI invention (Vol 4D §8).
- [ ] **Investigation workflow** with **three outcomes** (informative / valid-but-low-yield / not-in-case), persisting `normalized_name/indicated/outcome` (Vol 4D §9, Vol 3 §15/§22).
- [ ] Progression rules: open working phase (interleave/revisit) vs sequential commitment points (Vol 4D §4).
- [ ] Rate limiting (Redis) on messages/session creation/investigations (Vol 5 §24).

**Exit criteria:** a full history→exam→investigations playthrough on a seeded case; patient never reveals forbidden info; investigation outcomes correct; stage transitions enforced server-side.

**Volume refs:** Vol 4D §4–9, Vol 5 §5/§11–15.

---

### Phase 4 — Commitments & Evaluation  ⏱ ~2 weeks — ✅ DONE
**Goal:** close the loop with differential → diagnosis → management → consultant report.

**Tasks**
- [ ] **Differential** then **final diagnosis** then **management** workflows; each validated, persisted, locked; no grading at submit (Vol 4D §10–11, Vol 5 §16–17).
- [ ] On management submit → enter `EVALUATING`, **queue background evaluation** (Vol 4D §11, §18).
- [ ] **Examiner / evaluation workflow** (productionise the spike): load transcript + orders + differential + diagnosis + management + rubric → detect items + evidence → **software aggregates** section + overall + efficiency + differential scores → consultant report JSON → write-once evaluation recording rubric/prompt/model/case-hash (Vol 4D §12, Vol 4C §6, Vol 3 §25).
- [ ] **Evaluation endpoint** available after completion (Vol 5 §18).
- [ ] **Background worker** (idempotent, retryable) for evaluation/email/analytics (Vol 4D §18, §21).

**Exit criteria:** end-to-end case from greeting to consultant report; identical-input evaluation variance within tolerance; every deduction traceable to a rubric item + transcript moment; evaluation immutable + reconstructable.

**Volume refs:** Vol 4D §10–12/§18, Vol 4C §6, Vol 5 §16–18.

---

### Phase 5 — Frontend  ⏱ ~2.5 weeks
**Goal:** the immersive EMR-like experience (Vol 6).

**Tasks**
- [ ] API client + SSE management in `packages/sdk` (attach by `message_id`, resume) (Vol 6 §23).
- [ ] Auth screens + protected routes; token refresh.
- [ ] Dashboard (continue session, cases, performance summary) (Vol 6 §9).
- [ ] Case browser: search + difficulty filter (difficulty is case-intrinsic), metadata only (Vol 6 §10).
- [ ] **Session 3-panel layout** (patient / conversation / workspace) (Vol 6 §11).
- [ ] Workspace tabs: Physical Exam · Investigations · **Differential** · Diagnosis · Management (Vol 6 §15–19).
- [ ] Streaming chat with typing/retry states; structured exam & investigation results; searchable investigation catalog.
- [ ] **Differential & Diagnosis UI**: ranked differential first (locks), then final diagnosis (locks) (Vol 6 §18).
- [ ] Evaluation screen with collapsible sections (Vol 6 §20).
- [ ] State split: TanStack Query (server) · Context (session) · local (UI) (Vol 6 §22). Accessibility + skeleton loaders (Vol 6 §24/§27).

**Exit criteria:** a student completes a full case in the UI; no business logic in components; Lighthouse/a11y pass on key screens; perf targets approached (Vol 6 §29).

**Volume refs:** Vol 6 (all).

---

### Phase 6 — Analytics, Content Pipeline & Governance, Hardening  ⏱ ~2 weeks
**Goal:** production-readiness + a way to make more cases safely.

**Tasks**
- [ ] Analytics module + `GET /users/me/analytics` (Vol 3 §26, Vol 5 §19).
- [ ] **Case generation pipeline (internal/admin)**: Generator → schema validation → Validator → **human review & medical sign-off** (recorded `reviewed_by/medical_signoff`) → publish → version (Vol 4D §16, Vol 3 §8). Agents are assistive; SME sign-off is mandatory.
- [ ] **Prompt deployment workflow**: draft → render & validate against fixtures → regression suite → approval → registry publish → monitor; rollback = repoint version (Vol 4B §17, Vol 4D §17).
- [ ] Security pass (Vol 2A §17, Vol 5 §25): secrets handling, CORS, HTTPS, input sanitisation, request-size limits, rate limits, audit on sensitive actions.
- [ ] Observability: dashboards for latency/TTFT/cost/retries/leakage incidents (Vol 4A §19, Vol 4B §16).
- [ ] Backups (nightly PG, daily object storage) (Vol 3 §33).

**Exit criteria:** a new case can be authored, SME-signed-off, published, and played without code changes; a prompt change is regression-gated and rollback works; security checklist green.

---

### Phase 7 — MVP Content & Beta  ⏱ ongoing
- [ ] Author + SME-sign-off an MVP case library (target set — agree count, e.g. 20–30 across the 4 difficulty levels).
- [ ] Closed beta with students; collect feedback; track eval consistency in the wild.
- [ ] Triage, polish, performance tuning.

---

## 3. Cross-cutting workstreams (run continuously)

| Workstream | What | Refs |
|---|---|---|
| **Testing** | Unit (domain/use-cases) · integration (API+DB+Redis) · e2e (Playwright) · **prompt regression + eval harness** with benchmark fixtures and regression gating | Vol 2B §33, 4B §15 |
| **Prompt/eval quality** | Benchmark transcripts per agent; track variance, leakage, latency, cost; LLM-judge + sampled human review (honest about variance) | Vol 4B §15–16 |
| **Observability** | Correlation IDs end-to-end; per-AI-call audit; metrics | Vol 4A §19–20 |
| **Security** | Provider keys server-side only; never trust frontend; injection defence in renderer | Vol 2A §17, 4A §24 |
| **Docs/ADRs** | One ADR per significant decision; keep this plan + volumes in sync | Vol 2B §39 |

---

## 4. Dependency order (critical path)

```
Phase 0 (skeleton + spike)
   └─> Phase 1 (data + immutable cases)
          └─> Phase 2 (AIOS: renderer, adapter, stream, validator)
                 └─> Phase 3 (session + conversation + exam + investigations)
                        └─> Phase 4 (differential/diagnosis/management + evaluation)
                               └─> Phase 5 (frontend)  ── can start against mocked API after Phase 2 contracts freeze
                                      └─> Phase 6 (analytics, content pipeline, hardening)
                                             └─> Phase 7 (content + beta)
```
Frontend (Phase 5) can begin in parallel once API contracts/OpenAPI are frozen at end of Phase 2/3 — build against the generated `sdk` + mocks.

Indicative MVP timeline: **~13–16 weeks** for a small team, dominated by Phases 2–5. The spike result may move this.

---

## 5. Week-1 concrete checklist

- [ ] Create monorepo + workspaces; commit `.editorconfig`, lint/format/type configs, pre-commit, CI lint+test.
- [ ] `docker-compose.yml` up: postgres + redis + backend + frontend.
- [ ] Backend boots; `/health` + `/ready` green; Alembic baseline migration.
- [ ] Frontend boots with base layout + TanStack Query provider.
- [ ] OpenRouter key wired server-side; trivial `generate()` smoke test behind the adapter interface.
- [ ] Stand up the **grading/gating spike** repo area (`docs/spikes/`) and hand-author the first case JSON.
- [ ] Write ADR-001…007.

---

## 6. Key risks & mitigations

| Risk | Mitigation |
|---|---|
| **Examiner grading is noisy/inconsistent** (product-defining) | Phase-0 spike with go/no-go; model detects items + software aggregates; low-temp + rubric anchoring; regression-gate variance | 
| **Patient leaks hidden info** | Renderer-enforced `forbidden_context` + screening + regenerate; injection benchmark suite; near-zero target, not assumed | 
| **Latency/cost blowout** | Hot-path validation is non-LLM; heavy validation async; context minimisation; model routing by profile | 
| **Over-engineering stalls shipping** | Versioned templates (not a DSL); one OpenRouter adapter; build features over the skeleton, not vice-versa | 
| **Medical inaccuracy** | Mandatory recorded SME sign-off gate before publish; generator/validator assistive only | 
| **Reproducibility misunderstood** | "Replayable inputs," not deterministic outputs — record case/prompt/model/params/hash on every interaction |

---

## 7. Open decisions to confirm before/at Phase 0

- Python dependency manager (uv vs Poetry) and JS package manager (pnpm assumed).
- Hosting/deploy target (affects Phase 6 infra).
- MVP case-library size and which sub-topics of Internal Medicine.
- Who are the SME reviewers and what credential bar counts as sign-off.
- Eval acceptance thresholds (item-detection accuracy %, score-variance tolerance) — set numbers at the spike.
