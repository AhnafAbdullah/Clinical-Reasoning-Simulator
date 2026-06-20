"""Evaluation worker: Examiner extraction + aggregation + write-once persist
and the EVALUATING -> COMPLETED transition (Vol 4D §12)."""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager

from app.domain.ai import LLMRequest
from app.domain.entities import ClinicalSession
from app.domain.enums import Difficulty, InvestigationOutcome, MessageRole, SessionStatus
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
from app.modules.cases.use_cases import create_draft_case, publish_case
from app.modules.evaluation.service import EvaluationService


def _examiner_responder(satisfied_ids: set[str]):
    """A fake Examiner that returns valid detection JSON for the given items."""

    def responder(request: LLMRequest) -> str:
        # Pull the rubric item ids out of the rendered system prompt.
        system = request.messages[0].content
        ids = [
            line.split("id: ")[1].split(" ")[0] for line in system.splitlines() if "id: " in line
        ]
        return json.dumps(
            {"items": [{"id": i, "satisfied": i in satisfied_ids, "evidence": "x"} for i in ids]}
        )

    return responder


async def test_evaluation_completes_and_scores(
    session, sample_case, monkeypatch, fake_provider_cls
):
    @contextmanager
    def _scope():
        yield session

    monkeypatch.setattr("app.modules.evaluation.service.session_scope", _scope)

    case = publish_case(
        SqlAlchemyCaseRepository(session),
        create_draft_case(
            SqlAlchemyCaseRepository(session),
            title=sample_case["metadata"]["title"],
            difficulty=Difficulty.BASIC,
            specialty="Internal Medicine",
            json_content=sample_case,
        ).id,
        reviewed_by="Dr. Test",
    )

    s = ClinicalSession.start(user_id=uuid.uuid4(), case=case)
    s.submit_differential()
    s.submit_diagnosis()
    s.submit_management()  # EVALUATING
    srepo = SqlAlchemySessionRepository(session)
    s = srepo.add(s)

    sub = SqlAlchemySubmissionRepository(session)
    sub.save_differential(s.id, ["Unstable angina", "Aortic dissection", "Pericarditis", "GORD"])
    sub.save_diagnosis(s.id, "Acute inferior STEMI")
    sub.save_treatment(s.id, "Aspirin 300 mg and urgent primary PCI.")
    SqlAlchemyConversationRepository(session).add(
        session_id=s.id,
        role=MessageRole.STUDENT,
        message="Is the pain crushing and does it radiate to your arm? Do you smoke?",
        token_count=None,
    )
    SqlAlchemyPhysicalExamRepository(session).add(session_id=s.id, system="vitals")
    SqlAlchemyInvestigationRepository(session).add(
        session_id=s.id,
        investigation_name="ECG",
        normalized_name="ecg",
        indicated=True,
        outcome=InvestigationOutcome.INFORMATIVE,
    )

    all_ids = {
        "hpi_radiation",
        "hpi_character",
        "risk_smoking",
        "tx_aspirin",
        "tx_reperfusion",
        "comm_explained",
    }
    aios = AIOS(fake_provider_cls(responder=_examiner_responder(all_ids)))

    await EvaluationService(aios).run(s.id)

    evaluation = SqlAlchemyEvaluationRepository(session).get(s.id)
    assert evaluation is not None
    assert evaluation["overall_score"] >= 80
    assert evaluation["section_scores"]["diagnosis"] == 100
    assert evaluation["feedback"]["provenance"]["case_content_hash"] == s.case_content_hash

    assert srepo.get(s.id).status == SessionStatus.COMPLETED


async def test_evaluation_is_idempotent(session, sample_case, monkeypatch, fake_provider_cls):
    @contextmanager
    def _scope():
        yield session

    monkeypatch.setattr("app.modules.evaluation.service.session_scope", _scope)

    case = publish_case(
        SqlAlchemyCaseRepository(session),
        create_draft_case(
            SqlAlchemyCaseRepository(session),
            title=sample_case["metadata"]["title"],
            difficulty=Difficulty.BASIC,
            specialty="Internal Medicine",
            json_content=sample_case,
        ).id,
        reviewed_by="Dr. Test",
    )
    s = ClinicalSession.start(user_id=uuid.uuid4(), case=case)
    s.submit_differential()
    s.submit_diagnosis()
    s.submit_management()
    s = SqlAlchemySessionRepository(session).add(s)
    SqlAlchemySubmissionRepository(session).save_diagnosis(s.id, "STEMI")

    aios = AIOS(fake_provider_cls(responder=_examiner_responder(set())))
    service = EvaluationService(aios)
    await service.run(s.id)
    await service.run(s.id)  # second run must be a no-op (unique evaluation row)

    # Exactly one evaluation row exists (no IntegrityError raised).
    assert SqlAlchemyEvaluationRepository(session).get(s.id) is not None
