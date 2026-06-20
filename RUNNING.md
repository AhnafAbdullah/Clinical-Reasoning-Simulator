# Running the Clinical Reasoning Simulator

This guide gets the full stack running locally: PostgreSQL, Redis, the FastAPI
backend, and the Next.js frontend. Two paths are described — **local dev**
(recommended while developing) and **Docker Compose** (one command, prod-like).

---

## Prerequisites

- **Docker Desktop** (for PostgreSQL + Redis, and the all-in-one option)
- **Python 3.13+** (backend)
- **Node.js 18+** (frontend)
- An **OpenRouter API key** — free to create at <https://openrouter.ai/keys>.
  The app talks to LLMs only through OpenRouter (server-side only).

---

## 1. Configure the API key (one time)

```bash
cd apps/backend
cp .env.example .env            # then edit .env
```

Set your key and the free-tier models in `apps/backend/.env`:

```ini
CRS_OPENROUTER_API_KEY=sk-or-v1-...your key...
CRS_MODEL_DEFAULT=openai/gpt-oss-20b:free
CRS_MODEL_LATENCY=openai/gpt-oss-20b:free
CRS_MODEL_REASONING=openai/gpt-oss-120b:free
```

> The `openai/gpt-oss-*:free` models are reliable on the free tier. Llama/Qwen
> `:free` models are frequently rate-limited (HTTP 429). The app still runs
> without a key — you just can't generate live patient/examiner turns.

---

## 2A. Local dev (recommended)

**Start infrastructure (Postgres + Redis):**

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d postgres redis
```

**Backend:**

```bash
cd apps/backend
python -m venv .venv
. .venv/Scripts/activate          # Windows
# source .venv/bin/activate       # macOS/Linux
pip install -e ".[dev]"

alembic upgrade head              # create the schema
python -m scripts.seed            # publish the 2 example cases (ACS, DKA)

uvicorn app.main:app --reload     # http://localhost:8000
```

Check it's healthy: <http://localhost:8000/ready> (database, redis, ai_provider).
API docs (Swagger): <http://localhost:8000/docs>.

**Frontend (separate terminal):**

```bash
cd apps/frontend
npm install
npm run dev                       # http://localhost:3000
```

Open <http://localhost:3000>, register an account, pick a case, and start.

> The frontend talks to `http://localhost:8000` by default. To point elsewhere,
> set `NEXT_PUBLIC_API_BASE` before `npm run dev`.

---

## 2B. Docker Compose (full stack behind nginx) — one command

Put your key in `apps/backend/.env` (step 1), then:

```bash
docker compose -f infrastructure/docker/docker-compose.yml up --build
```

That's it. This builds and runs **postgres, redis, backend, frontend and nginx**.
On startup the backend automatically **applies migrations and seeds** the example
cases (idempotent), so there are no manual follow-up steps. Open the app at
<http://localhost>.

Notes:
- The backend reads `apps/backend/.env` (via compose `env_file`) for
  `CRS_OPENROUTER_API_KEY` and any overrides; `CRS_DATABASE_URL` and
  `CRS_REDIS_URL` are set to the in-network services automatically.
- The frontend is built with `NEXT_PUBLIC_API_BASE=/` so the browser calls the
  API same-origin through nginx.
- Stop with `docker compose -f infrastructure/docker/docker-compose.yml down`
  (add `-v` to also drop the database volume).
- **Needs free disk space** for the image build — if `docker build` fails with
  `input/output error` writing containerd/buildkit metadata, your Docker disk is
  full; free space (or `docker system prune`) and retry.

---

## 3. Using the app

1. **Register / sign in** at `/login`.
2. **Dashboard** — browse published cases (filter by difficulty) and resume
   in-progress sessions.
3. **Start a case** — the patient opens with their complaint (streamed live).
4. **Take a history** — chat with the patient; they answer in character and
   never reveal the diagnosis.
5. **Workspace tabs:**
   - **Exam** — examine body systems; findings come from the case.
   - **Tests** — search and order investigations (informative / low-yield /
     not-available outcomes).
   - **Commit** — submit a ranked **differential**, then a **final diagnosis**,
     then a **management plan** (each locks in order).
6. **Evaluation** — after the management plan, a consultant report is generated
   (section scores, strengths, areas to improve, teaching points).

---

## 4. Verifying things work

```bash
# Backend tests + quality gates
cd apps/backend
pytest                            # 101 passed, a few skipped without Postgres/key
ruff check app tests scripts && black --check app tests scripts && mypy app

# Frontend
cd apps/frontend
npm run typecheck && npm run lint && npm run build

# Grading/gating spike (needs CRS_OPENROUTER_API_KEY in the environment)
python docs/spikes/grading_gating/run_spike.py
```

The 3 Postgres trigger tests run only when `CRS_TEST_PG_URL` is set; the live
OpenRouter smoke test runs only when `CRS_OPENROUTER_API_KEY` is set.

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `/ready` shows `ai_provider: unconfigured` | Set `CRS_OPENROUTER_API_KEY` in `apps/backend/.env` and restart. |
| Patient/examiner returns an error or empty text | Free model rate-limited (429) or out of tokens — retry, or check the model ids exist via `GET https://openrouter.ai/api/v1/models`. |
| `relation "clinical_cases" does not exist` | Run `alembic upgrade head` (and `python -m scripts.seed`). |
| Frontend 401s / can't log in | Backend not running on `:8000`, or `NEXT_PUBLIC_API_BASE` misconfigured. |
| No cases on the dashboard | Run the seed script; cases must be Published. |
| Evaluation stays "Evaluating…" | The examiner needs a valid key; check backend logs for the evaluation worker. |
