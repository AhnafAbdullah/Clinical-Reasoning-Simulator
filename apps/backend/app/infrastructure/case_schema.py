"""Loads and validates clinical-case JSON against the shared JSON Schema
(packages/case-schema). Translates failures into a domain error."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from app.core.config import get_settings
from app.domain.errors import CaseValidationError

SCHEMA_FILE = "clinical_case.schema.json"


@lru_cache
def _validator() -> Draft202012Validator:
    path = get_settings().case_schema_dir / SCHEMA_FILE
    with path.open(encoding="utf-8") as fh:
        schema = json.load(fh)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_case(content: dict[str, Any]) -> None:
    """Raise CaseValidationError if the case does not conform to the schema."""
    errors = sorted(_validator().iter_errors(content), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(
            f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors[:10]
        )
        raise CaseValidationError(f"Case failed schema validation: {details}")
