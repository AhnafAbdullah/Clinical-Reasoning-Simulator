# case-schema

Language-neutral JSON Schema (Draft 2020-12) for an immutable **clinical case**
document, per `Documentation/Volume_3` §10–19 (corrected edition).

- `clinical_case.schema.json` — the canonical schema. Top-level keys are closed
  (`additionalProperties: false`); changing structure requires bumping
  `metadata.schema_version` and adding a migration (Vol 3 §30).
- `examples/` — fully-populated cases used for seeding and tests.

The backend validates every case against this file on load and before publish
(`app.infrastructure.case_schema`). Other languages (e.g. the TS frontend)
consume the same file.
