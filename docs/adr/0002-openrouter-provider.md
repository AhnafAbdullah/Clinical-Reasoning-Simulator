# ADR-002: OpenRouter as the sole LLM adapter (MVP)

Status: Accepted · Refs: Volume 2A §9, Volume 4A §15

## Context
OpenRouter already normalises OpenAI/Anthropic/Google/etc. behind one API and
routes across them. A bespoke adapter per vendor would be abstraction over an
abstraction.

## Decision
Define one thin `LLMProvider` interface (`generate/stream/health_check/estimate_cost`)
and ship exactly one implementation, `OpenRouterProvider`. Direct per-vendor or
local-LLM adapters are added later behind the same interface only if a concrete
need arises.

## Consequences
+ Provider independence retained at the interface; far less code to maintain.
- Tied to OpenRouter availability/pricing for the MVP (acceptable, reversible).
