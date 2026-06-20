"""Pydantic request/response models for the auth endpoints."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.domain.entities import User


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    role: str

    @classmethod
    def from_entity(cls, user: User) -> "UserProfile":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role.value,
        )
