# ADR-001: Layered (clean-ish) architecture

Status: Accepted · Refs: Volume 2A

## Context
Business rules must outlive frameworks (FastAPI, SQLAlchemy, the LLM provider).

## Decision
Four layers with dependencies pointing inward: API → application (use cases) →
domain → infrastructure. The domain imports nothing external. Repositories are
Protocols in the domain; implementations live in infrastructure.

## Consequences
+ Domain is unit-testable in isolation; infra is swappable.
+ Mapping boilerplate between ORM rows and domain entities (accepted cost).
- Slightly more indirection than a flat CRUD app.
