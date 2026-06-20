FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Container layout mirrors the monorepo so config's repo-root-relative paths
# (packages/case-schema, packages/prompt-registry) resolve at runtime.
COPY apps/backend/pyproject.toml /app/apps/backend/pyproject.toml
WORKDIR /app/apps/backend
RUN pip install --no-cache-dir -e .

COPY apps/backend /app/apps/backend
COPY packages/case-schema /app/packages/case-schema
COPY packages/prompt-registry /app/packages/prompt-registry

EXPOSE 8000

# Apply migrations, seed the published example cases (idempotent), then serve.
# In production prefer a separate migration/seed job; this keeps one-command dev simple.
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
