"""initial schema (Volume 3, corrected edition)

Revision ID: 0001
Revises:
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.domain import enums as E
from app.infrastructure.db.base import JSONType

revision: str = "0001"
down_revision: Union[str, None] = None
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
    op.create_table(
        "users",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("google_id", sa.String(255), unique=True),
        sa.Column("display_name", sa.String(255)),
        sa.Column("profile_picture", sa.String(1024)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", _TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", _TS, nullable=False, server_default=sa.func.now()),
        sa.Column("last_login", _TS),
        sa.Column("deleted_at", _TS),
    )

    op.create_table(
        "clinical_cases",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("difficulty", _enum(E.Difficulty), nullable=False),
        sa.Column("specialty", sa.String(128), nullable=False),
        sa.Column("status", _enum(E.CaseStatus), nullable=False),
        sa.Column("estimated_duration", sa.Integer, nullable=False, server_default="25"),
        sa.Column("json_content", JSONType, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("reviewed_by", sa.String(255)),
        sa.Column("reviewer_credentials", sa.String(255)),
        sa.Column("reviewed_at", _TS),
        sa.Column("medical_signoff", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", _TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", _TS, nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", _TS),
    )
    op.create_index("ix_clinical_cases_difficulty", "clinical_cases", ["difficulty"])
    op.create_index("ix_clinical_cases_specialty", "clinical_cases", ["specialty"])
    op.create_index("ix_clinical_cases_status", "clinical_cases", ["status"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column(
            "user_id", _uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", _TS, nullable=False),
        sa.Column("created_at", _TS, nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", _TS),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "clinical_sessions",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column(
            "user_id", _uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("case_id", _uuid(), sa.ForeignKey("clinical_cases.id"), nullable=False),
        sa.Column("case_version", sa.Integer, nullable=False),
        sa.Column("case_content_hash", sa.String(64), nullable=False),
        sa.Column("status", _enum(E.SessionStatus), nullable=False),
        sa.Column("current_stage", _enum(E.ClinicalStage), nullable=False),
        sa.Column("difficulty", _enum(E.Difficulty), nullable=False),
        sa.Column("started_at", _TS, nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", _TS),
    )
    op.create_index("ix_clinical_sessions_user_id", "clinical_sessions", ["user_id"])
    op.create_index("ix_clinical_sessions_case_id", "clinical_sessions", ["case_id"])

    op.create_table(
        "conversations",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column(
            "session_id",
            _uuid(),
            sa.ForeignKey("clinical_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", _enum(E.MessageRole), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer),
        sa.Column("timestamp", _TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_conversations_session_id", "conversations", ["session_id"])

    op.create_table(
        "investigation_orders",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column(
            "session_id",
            _uuid(),
            sa.ForeignKey("clinical_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("investigation_name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("indicated", sa.Boolean),
        sa.Column("outcome", _enum(E.InvestigationOutcome), nullable=False),
        sa.Column("ordered_at", _TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_investigation_orders_session_id", "investigation_orders", ["session_id"])

    op.create_table(
        "differential_submissions",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column(
            "session_id",
            _uuid(),
            sa.ForeignKey("clinical_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("differentials", JSONType, nullable=False),
        sa.Column("submitted_at", _TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_differential_submissions_session_id", "differential_submissions", ["session_id"]
    )

    op.create_table(
        "diagnosis_submissions",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column(
            "session_id",
            _uuid(),
            sa.ForeignKey("clinical_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("student_answer", sa.Text, nullable=False),
        sa.Column("submitted_at", _TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_diagnosis_submissions_session_id", "diagnosis_submissions", ["session_id"])

    op.create_table(
        "treatment_submissions",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column(
            "session_id",
            _uuid(),
            sa.ForeignKey("clinical_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("student_plan", sa.Text, nullable=False),
        sa.Column("submitted_at", _TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_treatment_submissions_session_id", "treatment_submissions", ["session_id"])

    op.create_table(
        "evaluations",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column(
            "session_id",
            _uuid(),
            sa.ForeignKey("clinical_sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("overall_score", sa.Integer, nullable=False),
        sa.Column("history_score", sa.Integer, nullable=False),
        sa.Column("exam_score", sa.Integer, nullable=False),
        sa.Column("investigation_score", sa.Integer, nullable=False),
        sa.Column("differential_score", sa.Integer, nullable=False),
        sa.Column("diagnosis_score", sa.Integer, nullable=False),
        sa.Column("treatment_score", sa.Integer, nullable=False),
        sa.Column("communication_score", sa.Integer, nullable=False),
        sa.Column("efficiency_score", sa.Integer, nullable=False),
        sa.Column("rubric_version", sa.Integer),
        sa.Column("feedback_json", JSONType, nullable=False),
        sa.Column("generated_at", _TS, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("user_id", _uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource", sa.String(128), nullable=False),
        sa.Column("resource_id", sa.String(64)),
        sa.Column("metadata", JSONType),
        sa.Column("timestamp", _TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])

    _create_immutability_trigger()


def _create_immutability_trigger() -> None:
    """Postgres-only: forbid mutating a Published case except Published -> Archived
    (with content unchanged). Enforces Vol 3 §8 at the database level."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
        CREATE OR REPLACE FUNCTION crs_clinical_cases_immutable()
        RETURNS trigger AS $$
        BEGIN
            IF (TG_OP = 'DELETE') THEN
                IF OLD.status = 'Published' THEN
                    RAISE EXCEPTION 'Published clinical cases are immutable (DELETE forbidden).';
                END IF;
                RETURN OLD;
            END IF;
            IF OLD.status = 'Published' THEN
                IF NEW.status = 'Archived'
                   AND NEW.json_content IS NOT DISTINCT FROM OLD.json_content
                   AND NEW.content_hash IS NOT DISTINCT FROM OLD.content_hash
                   AND NEW.title       IS NOT DISTINCT FROM OLD.title
                   AND NEW.difficulty  IS NOT DISTINCT FROM OLD.difficulty
                   AND NEW.version     IS NOT DISTINCT FROM OLD.version THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION
                    'Published clinical cases are immutable (only Published->Archived allowed).';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)
    op.execute("""
        CREATE TRIGGER clinical_cases_immutable
        BEFORE UPDATE OR DELETE ON clinical_cases
        FOR EACH ROW EXECUTE FUNCTION crs_clinical_cases_immutable();
        """)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS clinical_cases_immutable ON clinical_cases;")
        op.execute("DROP FUNCTION IF EXISTS crs_clinical_cases_immutable();")
    for table in (
        "audit_logs",
        "evaluations",
        "treatment_submissions",
        "diagnosis_submissions",
        "differential_submissions",
        "investigation_orders",
        "conversations",
        "clinical_sessions",
        "refresh_tokens",
        "clinical_cases",
        "users",
    ):
        op.drop_table(table)
