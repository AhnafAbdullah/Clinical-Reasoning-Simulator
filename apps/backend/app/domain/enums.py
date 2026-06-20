"""Domain enumerations. These are canonical and must match Volume 3 / Volume 4 Part D."""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """Application roles (Vol 5 §8 / Implementation Plan Phase 3). Faculty reserved."""

    STUDENT = "Student"
    ADMIN = "Admin"


class Difficulty(str, Enum):
    BASIC = "Basic"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"
    EXTREMELY_HARD = "Extremely Hard"


class CaseStatus(str, Enum):
    DRAFT = "Draft"
    VALIDATED = "Validated"
    PUBLISHED = "Published"
    ARCHIVED = "Archived"


class SessionStatus(str, Enum):
    """Coarse lifecycle state (Vol 4D §5)."""

    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class ClinicalStage(str, Enum):
    """Fine-grained stage within an ACTIVE session (Vol 4D §5)."""

    GREETING = "GREETING"
    HISTORY = "HISTORY"
    PHYSICAL_EXAM = "PHYSICAL_EXAM"
    INVESTIGATIONS = "INVESTIGATIONS"
    DIFFERENTIAL = "DIFFERENTIAL"
    FINAL_DIAGNOSIS = "FINAL_DIAGNOSIS"
    MANAGEMENT = "MANAGEMENT"


class MessageRole(str, Enum):
    STUDENT = "student"
    PATIENT = "patient"
    SYSTEM = "system"


class InvestigationOutcome(str, Enum):
    """Three-outcome model for investigation ordering (Vol 4D §9, Vol 3 §15/§22)."""

    INFORMATIVE = "INFORMATIVE"  # indicated test -> real result
    LOW_YIELD = "LOW_YIELD"  # valid but not indicated -> low-yield response
    NOT_AVAILABLE = "NOT_AVAILABLE"  # not present in the case
