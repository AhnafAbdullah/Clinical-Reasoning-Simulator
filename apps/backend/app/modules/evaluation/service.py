"""Evaluation background worker (Vol 4D §11-12, §18).

Decoupled from the management-submission request: the student gets an immediate
202 while the Examiner pass + aggregation run asynchronously. Idempotent and
write-once — the unique evaluation row means a re-run is a no-op (Vol 4D §21).
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.core.db import session_scope
from app.infrastructure.repositories.case_repository import SqlAlchemyCaseRepository
from app.infrastructure.repositories.conversation_repository import (
    SqlAlchemyConversationRepository,
)
from app.infrastructure.repositories.investigation_repository import (
    SqlAlchemyInvestigationRepository,
)
from app.infrastructure.repositories.physical_exam_repository import (
    SqlAlchemyPhysicalExamRepository,
)
from app.infrastructure.repositories.session_repository import SqlAlchemySessionRepository
from app.infrastructure.repositories.submission_repository import (
    SqlAlchemyEvaluationRepository,
    SqlAlchemySubmissionRepository,
)
from app.modules.ai.aios import AIOS
from app.modules.conversation.service import records_to_chat
from app.modules.evaluation.use_cases import evaluate_session

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


class EvaluationService:
    def __init__(self, aios: AIOS) -> None:
        self.aios = aios

    def schedule(self, session_id: uuid.UUID) -> None:
        task = asyncio.create_task(self.run(session_id))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    async def run(self, session_id: uuid.UUID) -> None:
        """Gather inputs, run the Examiner pass, aggregate, persist write-once,
        then transition the session to COMPLETED."""
        try:
            with session_scope() as db:
                session = SqlAlchemySessionRepository(db).get(session_id)
                if session is None:
                    return
                if SqlAlchemyEvaluationRepository(db).exists(session_id):
                    return  # idempotent
                case = SqlAlchemyCaseRepository(db).get(session.case_id)
                if case is None:
                    return
                case_json = case.json_content
                rubric_version = case.version
                case_hash = session.case_content_hash
                user_id = session.user_id
                conversation = records_to_chat(
                    SqlAlchemyConversationRepository(db).list_for_session(session_id)
                )
                examined = SqlAlchemyPhysicalExamRepository(db).list_for_session(session_id)
                ordered = [
                    {
                        "normalized": r.normalized_name,
                        "name": r.investigation_name,
                        "outcome": r.outcome.value,
                    }
                    for r in SqlAlchemyInvestigationRepository(db).list_for_session(session_id)
                ]
                sub = SqlAlchemySubmissionRepository(db)
                differentials = sub.get_differential(session_id) or []
                diagnosis = sub.get_diagnosis(session_id) or ""
                plan = sub.get_treatment(session_id)

            # Network/model work outside any open DB transaction.
            result = await evaluate_session(
                self.aios,
                case_json=case_json,
                conversation=conversation,
                examined_systems=examined,
                ordered=ordered,
                student_differentials=differentials,
                student_diagnosis=diagnosis,
                management_plan=plan,
                session_id=str(session_id),
                user_id=str(user_id),
            )

            feedback = {
                **result.feedback,
                "provenance": {
                    "case_content_hash": case_hash,
                    "rubric_version": rubric_version,
                    "examiner_prompt": "examiner",
                },
            }
            with session_scope() as db:
                eval_repo = SqlAlchemyEvaluationRepository(db)
                if eval_repo.exists(session_id):
                    return
                eval_repo.save(
                    session_id=session_id,
                    overall=result.overall_score,
                    section_scores=result.section_scores,
                    differential=result.differential_score,
                    efficiency=result.efficiency_score,
                    rubric_version=rubric_version,
                    feedback=feedback,
                )
                srepo = SqlAlchemySessionRepository(db)
                session = srepo.get(session_id)
                if session is not None:
                    session.complete()  # EVALUATING -> COMPLETED
                    srepo.update(session)
        except Exception:  # evaluation must not crash the worker pool
            logger.exception("Evaluation failed for session %s", session_id)
