# ADR-006: Versioned prompt templates (supersedes PDL)

Status: Accepted · Supersedes the original "Prompt Definition Language" · Refs: Volume 4B

## Context
The original design proposed a bespoke Prompt Definition Language with a custom
compiler, inheritance, and fragment-merging — a product in its own right.

## Decision
Prompts are versioned Markdown templates with YAML frontmatter, rendered with
Jinja2. Reuse via includes (partials); knowledge boundaries via
`allowed_context`/`forbidden_context` enforced by the renderer; output contracts
in frontmatter. Every version is immutable; sessions record the version used.

## Consequences
+ Same discipline (versioning, reuse, testing, boundaries) with standard tooling.
+ No language/compiler to build or maintain.
- Revisit a DSL only if standard templating demonstrably fails.
