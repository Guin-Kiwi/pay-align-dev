# TASKS.md

PHASE: 3
STATUS: in-progress

(0=Bootstrap | 1=Specify | 2=Design | 3=Develop | 4=Validate | 5=Deploy)

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0 — Bootstrap | Done | Project foundation and development tooling established. |
| 1 — Specify | Established; review as needed | UC-001 and UC-002 are documented. |
| 2 — Design | Baseline established; decisions open | ADR-001 to ADR-004 form the working baseline. ADR-005 remains Proposed. |
| 3 — Develop | In progress | Payroll calculation and persistent payroll saving are being developed; the UC-002 database foundation slice is Implemented, awaiting review. |
| 4 — Validate | In progress alongside development | Golden payroll tests, CI and Docker/release validation are underway. |
| 5 — Deploy | Not started | Release readiness has not yet been established. |


## Active objective

Implement and validate the initial vertical slice for employment setup and monthly payroll, 
following the accepted architecture decisions and use-case specifications.

## Current Use Case

docs/specs/UC-002-Process-the-Monthly-Employment.md

## Current slice

Initial implementation of the domain models, `SetupService`, and `PayrollService`, with unit tests for setup and payroll calculations.

The implementation must remain consistent with ADR-001 through ADR-004. Workbook-derived golden payroll cases 
should be used to verify the calculated values. The discrepancy in `admin_charge` and `total_employer_cost` remains pending confirmation.

Design sub-slice (phase 2): the persistence adapter for UC-002 saving, proposed in
[ADR-005](adr/ADR-005-sqlalchemy-persistence-adapter.md). It touches infrastructure
(one SQLAlchemy adapter, `work_entries` and `payroll_snapshots` tables, start-up
configuration), the application port and errors, and the payroll router error mapping.

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
- Replacing the sqlite3 repository with a SQLAlchemy adapter (ADR-005) removes
  the duplicate schema and the SQLite-only coupling, but means rewriting a
  repository that already has tests.
- Foreign keys are declared but not enforced until UC-001 persists employers
  and employments, so payroll rows can reference missing parents in the meantime.

## Validation approach

- During DEVELOP, unit tests will cover domain validation, exact payroll
  calculations, NBU eligibility, reimbursement separation, and annual-limit
  rejection.
- Integration tests will verify repository foreign keys, employer uniqueness,
  and atomic persistence of the monthly record and payslip.
- Architecture tests will continue to enforce inward dependency direction.
- ADR-005 slice: integration tests assert that a duplicate month raises
  `DuplicateMonthError` and persists nothing, that a failed save leaves no
  entries, snapshot, record or payslip, that the employee limit sums across
  employments of the same employee, that start-up fails clearly when
  `DATABASE_URL` is unset or unsupported, and that tests dispose their engines.

## Blockers / assumptions / decisions

- No architecture blocker found; `docs/PROJECT.md` is sufficient and needs no
  update.
- Assumption: the first implementation slice uses HTTP delivery and a
  relational ORM adapter as described by `docs/PROJECT.md`.
- Decision: ADR-004 defines entry snapshots, the three normal-case hour
  categories, derived holiday balance, and the exclusion of sick-pay and
  corrections.
- ADR-001 through ADR-004 are marked Accepted for implementation.
- Decision: database setup uses SQLAlchemy and reads `DATABASE_URL`, with skeleton tables for the five entities; the code is delivered on `uc-002-payroll-saving`. The money type and `DATABASE_URL` format are recorded in `docs/PROJECT.md`.
- Proposed: ADR-005 (single SQLAlchemy persistence adapter). Status stays
  Proposed until a human accepts it; `docs/PROJECT.md` is updated on acceptance,
  not before.
- Open question for a human: how `holiday_entitlement` (days) converts to the
  hours used by the derived holiday balance in ADR-004. Not decided by ADR-005.
- Assumption: the earlier float-column SQLite schema was never deployed, so the
  repository's legacy migration can be dropped.
- Human review remains required for the review-gated use-case specifications.

## Evidence links

- [UC-001 specification](specs/UC-001-Set-Up-an-Employment.md)
- [UC-002 specification](specs/UC-002-Process-the-Monthly-Employment.md)
- [ADR-001 Clean Architecture boundaries](adr/ADR-001-clean-architecture-boundaries.md)
- [ADR-002 Versioned AKBS payroll rules](adr/ADR-002-versioned-akbs-payroll-rules.md)
- [ADR-003 Monetary precision and rounding](adr/ADR-003-monetary-precision-and-rounding.md)
- [ADR-004 Payroll entry snapshots and holiday balance](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md)
- [ADR-005 SQLAlchemy persistence adapter (Proposed)](adr/ADR-005-sqlalchemy-persistence-adapter.md)
- [PROJECT architecture](PROJECT.md)

## Next smallest step

A human reviews ADR-005 and answers the days-to-hours question. On acceptance, update `docs/PROJECT.md`,
then start DEVELOP on `uc-002-payroll-saving` with the first failing test for the new adapter.

Separately, on `uc-002-payroll-calculation`: implement and run golden payroll tests against `PayrollService` using the workbook-derived cases.
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
