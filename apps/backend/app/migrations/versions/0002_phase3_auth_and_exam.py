"""phase 3: user role + physical exam requests

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.domain import enums as E

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.DateTime(timezone=True)


def _enum(py_enum: type) -> sa.Enum:
    return sa.Enum(
        py_enum,
        native_enum=False,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )


def _uuid() -> sa.types.TypeEngine:
    return sa.Uuid(as_uuid=True)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            _enum(E.UserRole),
            nullable=False,
            server_default=E.UserRole.STUDENT.value,
        ),
    )
    op.create_table(
        "physical_exam_requests",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column(
            "session_id",
            _uuid(),
            sa.ForeignKey("clinical_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("system", sa.String(64), nullable=False),
        sa.Column("requested_at", _TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_physical_exam_requests_session_id", "physical_exam_requests", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_physical_exam_requests_session_id", table_name="physical_exam_requests")
    op.drop_table("physical_exam_requests")
    op.drop_column("users", "role")
