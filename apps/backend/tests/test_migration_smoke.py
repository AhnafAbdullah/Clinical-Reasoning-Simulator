"""Smoke-test that the Alembic migration applies and rolls back on SQLite.

The Postgres-only immutability trigger is skipped by dialect guard, so this
exercises table/index creation and the up/down path end-to-end. Full trigger
behaviour is covered by Postgres integration tests (see test_immutability_pg).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _run(args, db_url):
    env = {**os.environ, "CRS_DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
    )


def test_migration_up_and_down(tmp_path):
    db_file = tmp_path / "smoke.db"
    db_url = "sqlite:///" + db_file.as_posix()

    up = _run(["upgrade", "head"], db_url)
    assert up.returncode == 0, up.stderr
    assert db_file.exists()

    down = _run(["downgrade", "base"], db_url)
    assert down.returncode == 0, down.stderr
