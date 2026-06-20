"""Standard response envelope (Vol 5 §6).

Every successful response is ``{success, data, meta}``; every error is
``{success: false, error: {code, message}}``. A single shape keeps frontend
handling uniform (Vol 5 §28).
"""

from __future__ import annotations

from typing import Any


def ok(data: Any, *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": True, "data": data, "meta": meta or {}}


def page_meta(*, page: int, page_size: int, total_items: int) -> dict[str, Any]:
    total_pages = (total_items + page_size - 1) // page_size if page_size else 0
    return {
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


def error_body(code: str, message: str) -> dict[str, Any]:
    return {"success": False, "error": {"code": code, "message": message}}
