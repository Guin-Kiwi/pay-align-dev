# TASKS.md

PHASE: 2
STATUS: in-progress

(0=Bootstrap | 1=Specify | 2=Design | 3=Develop | 4=Validate | 5=Deploy)

## Active objective

The use cases for **UC-001: Set Up an Employment** and **UC-002: Process the Monthly Employment** have been specified and **approved after human review**. The next objective is to design the system components required to implement these use cases. This includes defining the domain models, application services, and interfaces.

## Current Use Case

docs/specs/UC-001-Set-Up-an-Employment.md
docs/specs/UC-002-Process-the-Monthly-Employment.md

## Current slice

Describe the smallest vertical step being worked right now.

## Acceptance / validation cues

- What should be true when this slice is done?
- What evidence will show that it is done?
- Which artefact, test, review note, or document should hold that evidence?

## Blockers / assumptions / decisions

- **Human review completed and approved**: The specs for UC-001 and UC-002 have been reviewed and approved, allowing progression to the Design phase.
- Blockers that stop progress.
- Assumptions currently being made.
- Decisions that changed direction, scope, or sequencing.

## Evidence links

- Link to the relevant spec, design note, test result, PR note, or review comment.

## Next smallest step

- **UC-001**: `SetupService` has been implemented and committed. Proceed to unit tests and repository integration.
- **UC-002**: Design the `PayrollService` to handle monthly payroll processing, including gross wage calculations, deductions, and payslip generation.

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
