"""Exception handlers mapping domain/HTTP errors to the standard envelope (Vol 5 §6-7).

Domain code raises framework-agnostic errors; this layer is the single place that
knows their HTTP status and machine-readable code. Keeping the mapping here means
use cases never import FastAPI.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.envelope import error_body
from app.domain.errors import (
    CaseValidationError,
    DomainError,
    EmailAlreadyRegisteredError,
    GenerationExhaustedError,
    InvalidCredentialsError,
    InvalidStateTransition,
    NotFoundError,
    PermissionDeniedError,
    ProviderError,
    RateLimitedError,
    SessionCompletedError,
    TokenError,
)

logger = logging.getLogger(__name__)

# Domain error -> (HTTP status, machine code). Order doesn't matter; lookup is by type.
_MAPPING: dict[type[Exception], tuple[int, str]] = {
    InvalidCredentialsError: (401, "UNAUTHORIZED"),
    TokenError: (401, "UNAUTHORIZED"),
    PermissionDeniedError: (403, "FORBIDDEN"),
    NotFoundError: (404, "NOT_FOUND"),
    EmailAlreadyRegisteredError: (409, "VALIDATION_ERROR"),
    CaseValidationError: (422, "VALIDATION_ERROR"),
    InvalidStateTransition: (409, "VALIDATION_ERROR"),
    SessionCompletedError: (409, "SESSION_COMPLETED"),
    RateLimitedError: (429, "RATE_LIMITED"),
    ProviderError: (503, "AI_PROVIDER_UNAVAILABLE"),
    GenerationExhaustedError: (503, "AI_PROVIDER_UNAVAILABLE"),
}


def _resolve(exc: Exception) -> tuple[int, str]:
    for exc_type, mapped in _MAPPING.items():
        if isinstance(exc, exc_type):
            return mapped
    return 400, "INVALID_REQUEST"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        status, code = _resolve(exc)
        if status >= 500:
            logger.exception("Domain error -> %s", code, exc_info=exc)
        return JSONResponse(status_code=status, content=error_body(code, str(exc)))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "Request validation failed."),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            429: "RATE_LIMITED",
        }.get(exc.status_code, "INVALID_REQUEST" if exc.status_code < 500 else "INTERNAL_ERROR")
        return JSONResponse(status_code=exc.status_code, content=error_body(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "An unexpected error occurred."),
        )
