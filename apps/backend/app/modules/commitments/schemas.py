"""Pydantic models for the commitment endpoints (Vol 5 §16-17)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DifferentialRequest(BaseModel):
    differentials: list[str] = Field(min_length=1, max_length=20)


class DiagnosisRequest(BaseModel):
    diagnosis: str = Field(min_length=1, max_length=300)


class ManagementRequest(BaseModel):
    plan: str = Field(min_length=1, max_length=4000)
