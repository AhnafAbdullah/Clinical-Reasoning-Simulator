"""Lightweight structural types so AIOS components depend on shapes, not on the
infrastructure ``PromptTemplate`` concretely."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TemplateLike(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def version(self) -> int: ...

    @property
    def profile(self) -> str: ...

    @property
    def allowed_context(self) -> list[str]: ...

    @property
    def forbidden_context(self) -> list[str]: ...

    @property
    def memory_layers(self) -> list[str]: ...

    @property
    def output_contract(self) -> dict[str, Any]: ...
