# ADR-001-clean-architecture-boundaries

## Status
Proposed

## Context
PayAlign must calculate payroll independently of the web framework and database. The application needs a stable boundary between payroll rules, use-case orchestration, delivery mechanisms, and persistence adapters.

## Alternatives
- Allow domain and application code to depend directly on FastAPI or SQLAlchemy: rejected because it would couple payroll behavior to replaceable infrastructure and make isolated testing harder.
- Use a single undivided application module: rejected because it would mix business rules, delivery, and persistence responsibilities.

## Decision
PayAlign uses Clean Architecture with dependencies pointing inward:

`domain <- application <- interfaces <- infrastructure`

The domain contains entities and payroll rules. The application contains use-case services and repository ports. Interfaces contain HTTP delivery models and routes. Infrastructure contains ORM mappings, database adapters, and server wiring. This ADR is proposed for human approval.

## Consequences
- Payroll rules can be tested without a database or web server.
- Adapters must translate between external representations and application/domain types.
- Cross-layer shortcuts require an explicit architecture decision.
- `docs/PROJECT.md` remains the concise architecture reference after approval.

## Supersedes
none
