"""SQLAlchemy implementations of SubmissionRepository and EvaluationRepository.

Commitments are write-once and locked; the latest row per session is the binding
one. The evaluation row is unique per session (Vol 3 §25) — write-once unless an
admin explicitly regenerates.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db import models as m


class SqlAlchemySubmissionRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save_differential(self, session_id: uuid.UUID, differentials: list[str]) -> uuid.UUID:
        row = m.DifferentialSubmission(session_id=session_id, differentials=differentials)
        self._s.add(row)
        self._s.flush()
        return row.id

    def save_diagnosis(self, session_id: uuid.UUID, answer: str) -> uuid.UUID:
        row = m.DiagnosisSubmission(session_id=session_id, student_answer=answer)
        self._s.add(row)
        self._s.flush()
        return row.id

    def save_treatment(self, session_id: uuid.UUID, plan: str) -> uuid.UUID:
        row = m.TreatmentSubmission(session_id=session_id, student_plan=plan)
        self._s.add(row)
        self._s.flush()
        return row.id

    def get_differential(self, session_id: uuid.UUID) -> list[str] | None:
        stmt = (
            select(m.DifferentialSubmission)
            .where(m.DifferentialSubmission.session_id == session_id)
            .order_by(m.DifferentialSubmission.submitted_at.desc())
        )
        row = self._s.scalars(stmt).first()
        return list(row.differentials) if row else None

    def get_diagnosis(self, session_id: uuid.UUID) -> str | None:
        stmt = (
            select(m.DiagnosisSubmission)
            .where(m.DiagnosisSubmission.session_id == session_id)
            .order_by(m.DiagnosisSubmission.submitted_at.desc())
        )
        row = self._s.scalars(stmt).first()
        return row.student_answer if row else None

    def get_treatment(self, session_id: uuid.UUID) -> str | None:
        stmt = (
            select(m.TreatmentSubmission)
            .where(m.TreatmentSubmission.session_id == session_id)
            .order_by(m.TreatmentSubmission.submitted_at.desc())
        )
        row = self._s.scalars(stmt).first()
        return row.student_plan if row else None


class SqlAlchemyEvaluationRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def exists(self, session_id: uuid.UUID) -> bool:
        stmt = select(m.Evaluation.id).where(m.Evaluation.session_id == session_id)
        return self._s.scalars(stmt).first() is not None

    def save(
        self,
        *,
        session_id: uuid.UUID,
        overall: int,
        section_scores: dict[str, int],
        differential: int,
        efficiency: int,
        rubric_version: int | None,
        feedback: dict,
    ) -> None:
        row = m.Evaluation(
            session_id=session_id,
            overall_score=overall,
            history_score=section_scores.get("history", 0),
            exam_score=section_scores.get("physical_exam", 0),
            investigation_score=section_scores.get("investigations", 0),
            differential_score=differential,
            diagnosis_score=section_scores.get("diagnosis", 0),
            treatment_score=section_scores.get("treatment", 0),
            communication_score=section_scores.get("communication", 0),
            efficiency_score=efficiency,
            rubric_version=rubric_version,
            feedback_json=feedback,
        )
        self._s.add(row)
        self._s.flush()

    def get(self, session_id: uuid.UUID) -> dict | None:
        stmt = select(m.Evaluation).where(m.Evaluation.session_id == session_id)
        row = self._s.scalars(stmt).first()
        if row is None:
            return None
        return {
            "overall_score": row.overall_score,
            "section_scores": {
                "history": row.history_score,
                "physical_exam": row.exam_score,
                "investigations": row.investigation_score,
                "diagnosis": row.diagnosis_score,
                "treatment": row.treatment_score,
                "communication": row.communication_score,
            },
            "differential_score": row.differential_score,
            "efficiency_score": row.efficiency_score,
            "feedback": row.feedback_json,
            "generated_at": row.generated_at.isoformat(),
        }
