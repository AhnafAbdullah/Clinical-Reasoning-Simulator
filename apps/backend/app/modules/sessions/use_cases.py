"""Session lifecycle use cases (Vol 4D §6, Vol 5 §11).

Clinical truth is bound at session start: the session snapshots the case version
and content hash, and the hash is re-verified on load so a tampered or migrated
case can never be silently replayed (Vol 3 §8/§20).
"""

from __future__ import annotations

import uuid

from app.domain.entities import ClinicalSession
from app.domain.errors import NotFoundError, PermissionDeniedError
from app.domain.repositories import CaseRepository, SessionRepository


def start_session(
    cases: CaseRepository,
    sessions: SessionRepository,
    *,
    user_id: uuid.UUID,
    case_id: uuid.UUID,
) -> tuple[ClinicalSession, dict]:
    """Create an ACTIVE session for a published case. Returns the session and the
    immutable case JSON (so the caller can kick off the opening patient turn)."""
    case = cases.get(case_id)
    if case is None or not case.is_published:
        raise NotFoundError("Case not found or not available.")
    # Verify the stored hash matches the content we are about to run against.
    if case.content_hash != case.compute_hash():
        raise NotFoundError("Case content failed integrity verification.")
    session = ClinicalSession.start(user_id, case)
    saved = sessions.add(session)
    return saved, case.json_content


def load_owned_session(
    sessions: SessionRepository, *, session_id: uuid.UUID, user_id: uuid.UUID
) -> ClinicalSession:
    """Load a session, enforcing ownership. A non-owned session is reported as
    NOT_FOUND rather than FORBIDDEN to avoid leaking existence."""
    session = sessions.get(session_id)
    if session is None:
        raise NotFoundError("Clinical session not found.")
    if session.user_id != user_id:
        raise NotFoundError("Clinical session not found.")
    return session


def delete_session(
    sessions: SessionRepository, *, session_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Delete a session the caller owns, cascading its conversation, orders,
    submissions and evaluation. Non-owned/absent sessions report NOT_FOUND."""
    load_owned_session(sessions, session_id=session_id, user_id=user_id)
    sessions.delete(session_id)


def case_json_for_session(cases: CaseRepository, session: ClinicalSession) -> dict:
    case = cases.get(session.case_id)
    if case is None:
        raise NotFoundError("Case for session no longer exists.")
    return case.json_content


def require_admin_or_owner(session: ClinicalSession, *, user_id: uuid.UUID, is_admin: bool) -> None:
    if not is_admin and session.user_id != user_id:
        raise PermissionDeniedError("You do not have access to this session.")


_AFFECT_CUES: list[tuple[str, tuple[str, ...]]] = [
    ("in_pain", ("pain", "agony", "clutch", "writh", "grimac", "distress", "doubled over")),
    ("drowsy", ("drowsy", "confus", "lethargic", "sleepy", "obtunded", "groggy")),
    ("anxious", ("anxious", "worried", "frighten", "nervous", "panic", "scared", "fearful")),
    ("stoic", ("stoic", "plays down", "downplay", "matter-of-fact", "brief answers")),
    ("breathless", ("breathless", "short of breath", "gasping", "wheez", "pursed-lip")),
]


def _derive_affect(personality: str, communication: str) -> str:
    """A coarse, presentation-only mood for the avatar — never clinical truth."""
    blob = f"{personality} {communication}".lower()
    for affect, cues in _AFFECT_CUES:
        if any(c in blob for c in cues):
            return affect
    return "calm"


def patient_presentation(case_json: dict) -> dict:
    """Non-clinical presentation info for the avatar (name/age/gender + affect).
    The patient says these things anyway, so they are not a diagnostic spoiler."""
    p = case_json.get("patient", {}) or {}
    return {
        "name": p.get("name", "the patient"),
        "age": p.get("age"),
        "gender": (p.get("gender") or "").lower(),
        "affect": _derive_affect(
            str(p.get("personality", "")), str(p.get("communication_style", ""))
        ),
    }


def physical_exam_findings(case_json: dict, system: str) -> dict:
    """Return the structured findings for a body system straight from the case
    JSON — no AI invents findings (Vol 4D §8). Unknown systems raise NOT_FOUND."""
    exam = case_json.get("physical_exam", {}) or {}
    key = system.strip().lower()
    # Case sections are lower_snake keys (general, vitals, cardiovascular, ...).
    for section, findings in exam.items():
        if section.lower() == key:
            return {"system": section, "findings": findings}
    raise NotFoundError(f"No examination defined for system '{system}'.")
