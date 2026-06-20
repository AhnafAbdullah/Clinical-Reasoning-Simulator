"""Pydantic models for investigation endpoints (Vol 5 §15)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InvestigationOrderRequest(BaseModel):
    investigation: str = Field(min_length=1, max_length=128)
