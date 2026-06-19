"""Canonical content hashing for clinical cases (Vol 3 §8).

The hash binds a published case to its exact bytes. It is computed over a
canonical JSON serialization so semantically-identical documents hash equally
regardless of key ordering or insignificant whitespace.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(content: dict[str, Any]) -> str:
    return json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(content: dict[str, Any]) -> str:
    """Return the SHA-256 hex digest of the canonical JSON form."""
    return hashlib.sha256(canonical_json(content).encode("utf-8")).hexdigest()
