"""Context Builder (Vol 4A §9).

Assembles only the case sections a template is allowed to see, and separately
extracts the *values* of forbidden sections so the renderer can assert they
never appear in the rendered prompt. This prevents unnecessary token usage and
enforces knowledge boundaries at the data layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .registry_types import TemplateLike

# Keys whose values are matching keywords / structural metadata, not narrative
# content. They are excluded from the forbidden-leak scan because individual cue
# words ("smoke", "character") collide with ordinary clinical vocabulary and
# template boilerplate, producing false positives. The Context Builder still
# never *injects* these sections — this only governs the defensive scan.
_METADATA_KEYS = frozenset(
    {
        "detection_cues",
        "expected",
        "not_indicated",
        "accepted",
        "acceptable_differentials",
        "weight",
        "id",
        "required",
        "red_flag",
        "schema_version",
    }
)


# Keys naming the diagnosis/differential. Their values are the high-signal terms
# a patient must never utter, so they drive *response* leak screening even though
# (being short/generic) they are excluded from the *prompt* boundary scan.
_NAMING_KEYS = frozenset(
    {"final_diagnosis", "differentials", "accepted", "acceptable_differentials"}
)


def _flatten_strings(
    value: Any, out: list[str], *, skip_keys: frozenset[str] = frozenset()
) -> None:
    """Collect every string leaf in a nested dict/list structure."""
    if isinstance(value, str):
        text = value.strip()
        if text:
            out.append(text)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in skip_keys:
                continue
            _flatten_strings(item, out, skip_keys=skip_keys)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _flatten_strings(item, out, skip_keys=skip_keys)


def _collect_under_keys(value: Any, keys: frozenset[str], out: list[str]) -> None:
    """Collect string leaves found anywhere under a key in ``keys``."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys:
                _flatten_strings(item, out)
            else:
                _collect_under_keys(item, keys, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_under_keys(item, keys, out)


@dataclass(frozen=True)
class BuiltContext:
    variables: dict[str, Any]
    forbidden_values: list[str]  # narrative content — prompt boundary scan
    leak_terms: list[str]  # diagnosis/differential names — response scan


class ContextBuilder:
    def build(
        self,
        case: dict[str, Any],
        template: TemplateLike,
        extra: dict[str, Any] | None = None,
    ) -> BuiltContext:
        variables: dict[str, Any] = {}
        allowed_strings: list[str] = []
        for section in template.allowed_context:
            if section in case:
                variables[section] = case[section]
                _flatten_strings(case[section], allowed_strings)

        forbidden_raw: list[str] = []
        for section in template.forbidden_context:
            if section in case:
                _flatten_strings(case[section], forbidden_raw, skip_keys=_METADATA_KEYS)

        # A forbidden value is only a *leak risk* if it is not also legitimately
        # part of the allowed context. Generic clinical words (e.g. a rubric
        # detection cue like "crushing") that also appear in the allowed history
        # are not leaks and would otherwise cause false positives.
        allowed_text = "\n".join(allowed_strings).lower()
        forbidden_values = _dedup_not_in(forbidden_raw, allowed_text)

        # Response leak terms: diagnosis/differential names from any forbidden
        # section, used to screen the model's reply (e.g. the patient blurting
        # out "STEMI"). Excluded if they legitimately appear in allowed context.
        leak_raw: list[str] = []
        for section in template.forbidden_context:
            if section in case:
                _collect_under_keys(case[section], _NAMING_KEYS, leak_raw)
        leak_terms = _dedup_not_in(leak_raw, allowed_text)

        if extra:
            variables.update(extra)
        return BuiltContext(
            variables=variables,
            forbidden_values=forbidden_values,
            leak_terms=leak_terms,
        )


def _dedup_not_in(values: list[str], allowed_text: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.strip().lower()
        if not key or key in seen or key in allowed_text:
            continue
        seen.add(key)
        result.append(value)
    return result
