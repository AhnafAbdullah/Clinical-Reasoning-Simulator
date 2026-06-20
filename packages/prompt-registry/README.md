# Prompt Registry

Versioned prompt templates for the Clinical Reasoning Simulator (Vol 4 Part B).

A template is a single Markdown file: a **YAML frontmatter** block (metadata and
contracts — never sent to the model) followed by a **Jinja2 body** (the text that
becomes the prompt). Templates are rendered by `app/infrastructure/ai/renderer.py`
with `StrictUndefined`; an undefined variable is a render-time error, never a
silent blank.

## Layout
```
prompt-registry/
  patient/    patient_v1.md, ...
  examiner/   examiner_v1.md, ...
  fragments/  shared includes (never_reveal_diagnosis.md, ...)
```

## Rules (Vol 4B §20 — absolute)
- Prompts are versioned templates, rendered at run time — never hardcoded strings.
- Every version is **immutable**: a change is a new file `{id}_v{n+1}.md`. Older
  versions are never edited, so any past session can be reconstructed.
- `(id, version)` is the stable identity recorded on every interaction.
- Knowledge injection is explicit: `allowed_context` lists the case sections the
  renderer may inject; `forbidden_context` is asserted absent from the rendered
  prompt **before generation**.
- Reuse is via Jinja2 `{% include "fragments/..." %}`, not duplication.
- Every template declares an `output` contract checked by the Validator.

## Frontmatter fields
- `id` — logical name, stable across versions.
- `version` — integer; incremented on every change.
- `agent` — patient | examiner | generator | validator.
- `status` — draft | staging | production.
- `profile` — abstract model preference (default | reasoning | latency); the
  Model Router maps it to a concrete OpenRouter model.
- `allowed_context` / `forbidden_context` — knowledge boundaries.
- `memory` — which memory layers the Memory Manager must supply.
- `output` — `{type: plain_text, max_words: N}` or `{type: json, schema: NAME}`.
