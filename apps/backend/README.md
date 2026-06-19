# CRS Backend

FastAPI modular monolith for the Clinical Reasoning Simulator. **Phase 1** delivers
the domain + data foundation (entities, full schema, immutable cases, repositories,
case JSON Schema validation, seed). API surface so far is `/health` and `/ready`.

## Layout
```
app/
├── core/            # config, db engine/session, logging
├── domain/          # pure entities, enums, repository ports, hashing, errors
├── infrastructure/  # SQLAlchemy models, repositories, case-schema validator
├── modules/         # feature modules (cases: create/publish use cases)
├── migrations/      # Alembic (0001 = initial schema + immutability trigger)
└── main.py
```

## Develop
```bash
python -m venv .venv && . .venv/Scripts/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env

# Local Postgres + Redis
docker compose -f ../../infrastructure/docker/docker-compose.yml up -d

alembic upgrade head            # apply migrations
python -m scripts.seed          # seed example published case(s)
uvicorn app.main:app --reload   # http://localhost:8000/health
```

## Test
```bash
pytest                                   # unit + migration smoke (SQLite)
CRS_TEST_PG_URL=postgresql+psycopg://crs:crs@localhost:5432/crs_test pytest \
    tests/test_immutability_pg.py        # DB-level immutability trigger (needs Postgres)
```

## Key invariants (Volume 3 §8)
- Published cases are immutable: enforced by the app (`SqlAlchemyCaseRepository.update`)
  **and** a Postgres trigger (`clinical_cases_immutable`). Only `Published -> Archived`
  with unchanged content is allowed.
- A case publishes only with recorded medical sign-off (`medical_signoff`, `reviewed_by`).
- `content_hash` = SHA-256 of canonical JSON; sessions bind to `(case_id, version, content_hash)`.
