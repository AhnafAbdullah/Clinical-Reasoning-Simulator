"""Seed the database with the example case(s) as Published cases.

Run after migrations:  python -m scripts.seed
Idempotent: skips cases whose metadata.case_id already exists (by title match).
"""

from __future__ import annotations

import json

from app.core.config import get_settings
from app.core.db import session_scope
from app.domain.enums import Difficulty
from app.infrastructure.repositories.case_repository import SqlAlchemyCaseRepository
from app.modules.cases.use_cases import create_draft_case, publish_case

EXAMPLES_DIR = get_settings().case_schema_dir / "examples"


def _load_examples() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(EXAMPLES_DIR.glob("*.json"))]


def seed() -> None:
    examples = _load_examples()
    with session_scope() as session:
        repo = SqlAlchemyCaseRepository(session)
        existing_titles = {c.title for c in repo.list_published(limit=1000)}
        for content in examples:
            meta = content["metadata"]
            if meta["title"] in existing_titles:
                print(f"skip (exists): {meta['title']}")
                continue
            draft = create_draft_case(
                repo,
                title=meta["title"],
                difficulty=Difficulty(meta["difficulty"]),
                specialty=meta["specialty"],
                json_content=content,
                estimated_duration=int(meta.get("estimated_time", 25)),
            )
            published = publish_case(
                repo,
                draft.id,
                reviewed_by=meta.get("reviewed_by", "seed reviewer"),
                reviewer_credentials=meta.get("reviewer_credentials"),
            )
            print(f"published: {published.title}  hash={published.content_hash[:12]}...")


if __name__ == "__main__":
    seed()
