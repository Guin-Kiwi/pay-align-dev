# TASKS.md

PHASE: 3
STATUS: in-progress

(0=Bootstrap | 1=Specify | 2=Design | 3=Develop | 4=Validate | 5=Deploy)

## Active objective

Implement and validate the initial vertical slice for employment setup and monthly payroll, 
following the accepted architecture decisions and use-case specifications.

## Current Use Case

- [UC-001: Set Up an Employment](specs/UC-001-Set-Up-an-Employment.md)
- [UC-002: Process the Monthly Employment](specs/UC-002-Process-the-Monthly-Employment.md)

## Current slice

Initial implementation of the domain models, `SetupService`, and `PayrollService`, with unit tests for setup and payroll calculations.

The implementation must remain consistent with ADR-001 through ADR-004. Workbook-derived golden payroll cases 
should be used to verify the calculated values. The discrepancy in `admin_charge` and `total_employer_cost` remains pending confirmation.

## Acceptance / validation cues

- Both use cases have an explicit component path through domain, application,
  interfaces, and infrastructure.
- Setup has ports for employer uniqueness and employment persistence, with
  foreign-key relationships preserved.
- Payroll has ports for employment lookup, cumulative annual gross checks, and
  atomic monthly record/payslip persistence.
- Invalid inputs and annual-limit breaches fail before persistence; success
  returns a confirmation after the transaction completes.
- The architecture remains consistent with
  [ADR-001](adr/ADR-001-clean-architecture-boundaries.md),
  [ADR-002](adr/ADR-002-versioned-akbs-payroll-rules.md), and
  [ADR-003](adr/ADR-003-monetary-precision-and-rounding.md), and
  [ADR-004](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md).
- Evidence: this design record, the two linked use-case specifications, and
  the existing architecture ADRs.

## Risks / tradeoffs

- Keeping repository ports at the application boundary preserves testability,
  but requires explicit mapping between ORM records and domain entities.
- A single transaction for the monthly record and payslip prevents partial
  payroll saves, while making the persistence adapter responsible for
  transaction coordination.
- The 2026 ruleset is intentionally narrow; adding another year requires a
  new version rather than changing historical calculations.

## Validation approach

- During DEVELOP, unit tests will cover domain validation, exact payroll
  calculations, NBU eligibility, reimbursement separation, and annual-limit
  rejection.
- Integration tests will verify repository foreign keys, employer uniqueness,
  and atomic persistence of the monthly record and payslip.
- Architecture tests will continue to enforce inward dependency direction.

## Blockers / assumptions / decisions

- No architecture blocker found; `docs/PROJECT.md` is sufficient and needs no
  update.
- Assumption: the first implementation slice uses HTTP delivery and a
  relational ORM adapter as described by `docs/PROJECT.md`.
- Decision: ADR-004 defines entry snapshots, the three normal-case hour
  categories, derived holiday balance, and the exclusion of sick-pay and
  corrections.
- ADR-001 through ADR-004 are marked Accepted for implementation.
- Human review remains required for the review-gated use-case specifications.

## Evidence links

- [UC-001 specification](specs/UC-001-Set-Up-an-Employment.md)
- [UC-002 specification](specs/UC-002-Process-the-Monthly-Employment.md)
- [ADR-001 Clean Architecture boundaries](adr/ADR-001-clean-architecture-boundaries.md)
- [ADR-002 Versioned AKBS payroll rules](adr/ADR-002-versioned-akbs-payroll-rules.md)
- [ADR-003 Monetary precision and rounding](adr/ADR-003-monetary-precision-and-rounding.md)
- [ADR-004 Payroll entry snapshots and holiday balance](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md)
- [PROJECT architecture](PROJECT.md)

## Next smallest step

## Next smallest step

Implement and run golden payroll tests against `PayrollService` using the workbook-derived cases. 
Resolve the pending `admin_charge` and `total_employer_cost` discrepancy before treating those expected values as final.

## Backlog

- docs/specs/UC-002-Employee-Registration.md
- docs/specs/UC-003-Monthly-Payroll-Processing.md
- Future: dedicated sick-pay and exception-management use case.

## Working agreement

- Keep one active use case small enough to deliver vertically.
- Keep one current slice small enough to finish or re-evaluate quickly.
- Prefer reality-based progress over placeholder completeness.
- Update this file when the lifecycle phase, active objective, or current use case changes.
- Record blockers, assumptions, and decisions when they affect delivery.
- Link validation evidence from the relevant project artefact instead of duplicating it here.
- End each work session with the next smallest step clearly stated.
