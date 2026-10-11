# TASKS.md

PHASE: 2
STATUS: done

(0=Bootstrap | 1=Specify | 2=Design | 3=Develop | 4=Validate | 5=Deploy)

## Active objective

The use cases for **UC-001: Set Up an Employment** and **UC-002: Process the Monthly Employment** have been specified and **approved after human review**. The next objective is to design the system components required to implement these use cases. This includes defining the domain models, application services, and interfaces.

## Current Use Case

docs/specs/UC-001-Set-Up-an-Employment.md
docs/specs/UC-002-Process-the-Monthly-Employment.md

## Current slice

Develop: Wire PayrollService to FastAPI endpoints

Create RESTful endpoints in `src/app/interfaces/` that expose the core payroll functionality:

- POST /employments (create employment record)
- POST /monthly-payroll (process monthly payroll for an employment)
- GET /payslips/{employment_id}/{year}/{month} (retrieve payslip)

Dependencies: PayrollService already implemented and tested. Focus on clean API design with proper error handling and validation.

## Acceptance / validation cues

- The application layer depends only on repository interfaces.
- Infrastructure owns ORM mappings, database sessions, and adapter wiring.
- A monthly payroll run can persist and retrieve its record and payslip together.
- Evidence: UC-002 integration tests for save/retrieve and annual-limit queries.

## Blockers / assumptions / decisions

- **Human review completed and approved**: The specs for UC-001 and UC-002 have been reviewed and approved, allowing progression to the Design phase.
- Persistence design: repository ports belong in `src/app/application/`; SQLAlchemy
	adapters and session wiring belong in `src/app/infrastructure/`.
- Blockers that stop progress.
- Assumptions currently being made.
- Decisions that changed direction, scope, or sequencing.

## Evidence links

- [UC-002 specification](specs/UC-002-Process-the-Monthly-Employment.md)
- [Project architecture](PROJECT.md)

## Next smallest step

- Implement the repository ports and one persistence adapter for `MonthlyRecord` and
	`Payslip`, starting with integration tests.

## Backlog

- docs/specs/UC-002-Employee-Registration.md
- docs/specs/UC-003-Monthly-Payroll-Processing.md

## Working agreement

- Keep one active use case small enough to deliver vertically.
- Keep one current slice small enough to finish or re-evaluate quickly.
- Prefer reality-based progress over placeholder completeness.
- Update this file when the lifecycle phase, active objective, or current use case changes.
- Record blockers, assumptions, and decisions when they affect delivery.
- Link validation evidence from the relevant project artefact instead of duplicating it here.
- End each work session with the next smallest step clearly stated.
