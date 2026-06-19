# Contributing

## Branches
`main` (stable) ← `develop` ← `feature/*`.

## Commits — Conventional Commits
Format: `type(scope): summary`, e.g. `feat(cases): add publish use case`.
Types: `feat, fix, docs, refactor, test, chore, ci, build, perf`.

## Quality gates (run before pushing; CI enforces)
Backend (`apps/backend`):
```bash
ruff check app tests scripts
black --check app tests scripts
mypy app
pytest                       # set CRS_TEST_PG_URL to also run the Postgres trigger tests
```
Frontend (`apps/frontend`): `npm run lint && npm run typecheck && npm run build`.

Install hooks once: `pip install pre-commit && pre-commit install`.

## Definition of Done (per feature)
Use case implemented · tests written · API documented · logging · errors handled ·
prompt/template versions tracked · architecture respected · CI green · docs updated.
