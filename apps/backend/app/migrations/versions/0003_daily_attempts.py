"""daily challenge attempts (one per user per day; basis for streaks)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.DateTime(timezone=True)


def _uuid() -> sa.types.TypeEngine:
    return sa.Uuid(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "daily_attempts",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column(
            "user_id", _uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("challenge_date", sa.Date, nullable=False),
        sa.Column("case_id", _uuid(), sa.ForeignKey("clinical_cases.id"), nullable=False),
        sa.Column(
            "session_id",
            _uuid(),
            sa.ForeignKey("clinical_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", _TS, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "challenge_date", name="uq_daily_user_date"),
    )
    op.create_index("ix_daily_attempts_user_id", "daily_attempts", ["user_id"])
    op.create_index("ix_daily_attempts_challenge_date", "daily_attempts", ["challenge_date"])


def downgrade() -> None:
    op.drop_index("ix_daily_attempts_challenge_date", table_name="daily_attempts")
    op.drop_index("ix_daily_attempts_user_id", table_name="daily_attempts")
    op.drop_table("daily_attempts")
