"""Response Validator (Vol 4A §17).

Hot-path validation uses only fast, deterministic checks — format, length,
required structure, role/stage heuristics, and string/pattern screens for
forbidden content. It makes NO additional model calls, to protect latency.

Heavier, model-based semantic validation runs off the hot path (generation,
evaluation, sampled traffic) and is not implemented here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.domain.ai import RenderedPrompt

# Cheap "the patient is breaking character / leaking" screens (Vol 4C §5).
_LEAK_PATTERNS = [
    re.compile(r"\byour (?:diagnosis|differential) (?:is|are)\b", re.IGNORECASE),
    re.compile(r"\bthe (?:diagnosis|rubric|teaching points?)\b", re.IGNORECASE),
    re.compile(r"\bas an? (?:ai|language model|assistant)\b", re.IGNORECASE),
    re.compile(r"\b(?:scoring|rubric|simulation|simulator)\b", re.IGNORECASE),
]


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    status: str  # "ok" | "rejected"
    reason: str = ""
    parsed: Any = None  # parsed JSON when the contract is json


class ResponseValidator:
    def validate(
        self,
        text: str,
        prompt: RenderedPrompt,
        *,
        forbidden_values: tuple[str, ...] = (),
    ) -> ValidationResult:
        if prompt.output_type == "json":
            return self._validate_json(text)
        return self._validate_text(text, prompt, forbidden_values)

    def _validate_text(
        self,
        text: str,
        prompt: RenderedPrompt,
        forbidden_values: tuple[str, ...],
    ) -> ValidationResult:
        stripped = text.strip()
        if not stripped:
            return ValidationResult(False, "rejected", "empty response")

        if prompt.max_words is not None:
            # Allow some slack over the declared limit before rejecting.
            word_count = len(stripped.split())
            if word_count > prompt.max_words * 2:
                return ValidationResult(
                    False, "rejected", f"too long ({word_count} words > 2x limit)"
                )

        haystack = stripped.lower()
        for value in forbidden_values:
            needle = value.strip().lower()
            if len(needle) >= 4 and needle in haystack:
                return ValidationResult(False, "rejected", "forbidden content in response")

        for pattern in _LEAK_PATTERNS:
            if pattern.search(stripped):
                return ValidationResult(False, "rejected", f"leakage pattern: {pattern.pattern}")

        return ValidationResult(True, "ok", parsed=stripped)

    def _validate_json(self, text: str) -> ValidationResult:
        candidate = _strip_code_fence(text.strip())
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            return ValidationResult(False, "rejected", f"invalid JSON: {exc}")
        if not isinstance(parsed, (dict, list)):
            return ValidationResult(False, "rejected", "JSON root must be object or array")
        return ValidationResult(True, "ok", parsed=parsed)


def _strip_code_fence(text: str) -> str:
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()
