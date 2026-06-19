"""Postgres-only test for the published-case immutability trigger (Vol 3 §8).

Skipped unless CRS_TEST_PG_URL points at a disposable Postgres database, e.g.:
    CRS_TEST_PG_URL=postgresql+psycopg://crs:crs@localhost:5432/crs_test pytest

It issues raw UPDATE/DELETE (bypassing the application-level guard) to prove the
database itself rejects mutating a published case.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

PG_URL = os.environ.get("CRS_TEST_PG_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="CRS_TEST_PG_URL not set")


@pytest.fixture
def pg_engine():
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings

    os.environ["CRS_DATABASE_URL"] = PG_URL
    get_settings.cache_clear()
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    engine = create_engine(PG_URL, future=True)
    try:
        yield engine
    finally:
        command.downgrade(cfg, "base")
        engine.dispose()
        get_settings.cache_clear()


def _insert_published(conn) -> uuid.UUID:
    cid = uuid.uuid4()
    conn.execute(
        text("""
            INSERT INTO clinical_cases
              (id, title, difficulty, specialty, status, estimated_duration,
               json_content, version, content_hash, medical_signoff,
               created_at, updated_at, published_at)
            VALUES
              (:id, 'imm', 'Basic', 'Internal Medicine', 'Published', 25,
               '{}'::jsonb, 1, 'deadbeef', true, now(), now(), now())
            """),
        {"id": cid},
    )
    return cid


def test_update_published_is_rejected(pg_engine):
    with pg_engine.begin() as conn:
        cid = _insert_published(conn)
    with pytest.raises(Exception):
        with pg_engine.begin() as conn:
            conn.execute(text("UPDATE clinical_cases SET title='x' WHERE id=:id"), {"id": cid})


def test_delete_published_is_rejected(pg_engine):
    with pg_engine.begin() as conn:
        cid = _insert_published(conn)
    with pytest.raises(Exception):
        with pg_engine.begin() as conn:
            conn.execute(text("DELETE FROM clinical_cases WHERE id=:id"), {"id": cid})


def test_archive_transition_is_allowed(pg_engine):
    with pg_engine.begin() as conn:
        cid = _insert_published(conn)
        conn.execute(text("UPDATE clinical_cases SET status='Archived' WHERE id=:id"), {"id": cid})
    with pg_engine.connect() as conn:
        status = conn.execute(
            text("SELECT status FROM clinical_cases WHERE id=:id"), {"id": cid}
        ).scalar_one()
    assert status == "Archived"
