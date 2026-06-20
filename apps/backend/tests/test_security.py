"""Password hashing and JWT issue/verify (Vol 5 §5)."""

from __future__ import annotations

import uuid

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.domain.errors import TokenError


def test_password_hash_roundtrip() -> None:
    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong", h)


def test_verify_is_safe_on_garbage_hash() -> None:
    assert verify_password("anything", "not-a-real-hash") is False


def test_access_token_roundtrip() -> None:
    uid = uuid.uuid4()
    token = create_access_token(uid, "Student")
    claims = decode_access_token(token)
    assert claims.user_id == uid
    assert claims.role == "Student"


def test_tampered_token_rejected() -> None:
    token = create_access_token(uuid.uuid4(), "Student")
    with pytest.raises(TokenError):
        decode_access_token(token + "tampered")


def test_refresh_token_hash_is_deterministic_and_opaque() -> None:
    raw = generate_refresh_token()
    assert hash_refresh_token(raw) == hash_refresh_token(raw)
    assert raw not in hash_refresh_token(raw)
