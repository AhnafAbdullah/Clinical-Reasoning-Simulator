"""Prompt registry: loads versioned Markdown+YAML templates (Vol 4B §6).

Each template is one file ``{agent}/{id}_v{n}.md`` with a YAML frontmatter block
and a Jinja2 body. Versions are immutable; the registry simply indexes whatever
files are present and serves them by ``(id, version)``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings
from app.domain.errors import PromptNotFoundError, PromptRenderError

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_FILENAME_RE = re.compile(r"^(?P<id>[a-z0-9_]+)_v(?P<version>\d+)\.md$")


@dataclass(frozen=True)
class PromptTemplate:
    id: str
    version: int
    frontmatter: dict[str, Any]
    body: str
    relpath: str  # path relative to the registry root, for the Jinja2 loader

    @property
    def agent(self) -> str:
        return str(self.frontmatter.get("agent", self.id))

    @property
    def profile(self) -> str:
        return str(self.frontmatter.get("profile", "default"))

    @property
    def allowed_context(self) -> list[str]:
        return list(self.frontmatter.get("allowed_context", []) or [])

    @property
    def forbidden_context(self) -> list[str]:
        return list(self.frontmatter.get("forbidden_context", []) or [])

    @property
    def memory_layers(self) -> list[str]:
        return list(self.frontmatter.get("memory", []) or [])

    @property
    def output_contract(self) -> dict[str, Any]:
        return dict(self.frontmatter.get("output", {}) or {})


def _parse(path: Path, root: Path) -> PromptTemplate:
    raw = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        raise PromptRenderError(f"Template {path} is missing a YAML frontmatter block.")
    frontmatter = yaml.safe_load(match.group(1)) or {}
    body = match.group(2)
    if "id" not in frontmatter or "version" not in frontmatter:
        raise PromptRenderError(f"Template {path} frontmatter must declare id and version.")
    return PromptTemplate(
        id=str(frontmatter["id"]),
        version=int(frontmatter["version"]),
        frontmatter=frontmatter,
        body=body,
        relpath=path.relative_to(root).as_posix(),
    )


class PromptRegistry:
    """Indexes all templates under a registry root."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._by_key: dict[tuple[str, int], PromptTemplate] = {}
        self._latest: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        if not self.root.exists():
            raise PromptNotFoundError(f"Prompt registry root not found: {self.root}")
        for path in self.root.rglob("*.md"):
            if path.parent.name == "fragments" or path.name.upper() == "README.MD":
                continue
            if not _FILENAME_RE.match(path.name):
                continue
            tmpl = _parse(path, self.root)
            self._by_key[(tmpl.id, tmpl.version)] = tmpl
            self._latest[tmpl.id] = max(self._latest.get(tmpl.id, 0), tmpl.version)

    def get(self, prompt_id: str, version: int | None = None) -> PromptTemplate:
        if version is None:
            version = self._latest.get(prompt_id)
            if version is None:
                raise PromptNotFoundError(f"No template registered for id={prompt_id!r}.")
        try:
            return self._by_key[(prompt_id, version)]
        except KeyError as exc:
            raise PromptNotFoundError(
                f"No template for id={prompt_id!r} version={version}."
            ) from exc

    def latest_version(self, prompt_id: str) -> int:
        return self.get(prompt_id).version

    def all_templates(self) -> list[PromptTemplate]:
        return list(self._by_key.values())


@lru_cache
def get_registry() -> PromptRegistry:
    return PromptRegistry(get_settings().prompt_registry_dir)
