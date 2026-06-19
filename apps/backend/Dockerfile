FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# The case-schema package is read at runtime; copy it to the path config expects
# (repo_root/packages/case-schema). Container layout mirrors the monorepo.
COPY apps/backend/pyproject.toml /app/apps/backend/pyproject.toml
WORKDIR /app/apps/backend
RUN pip install --no-cache-dir -e .

COPY apps/backend /app/apps/backend
COPY packages/case-schema /app/packages/case-schema

EXPOSE 8000

# Apply migrations then serve. (In production prefer a separate migration job.)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
