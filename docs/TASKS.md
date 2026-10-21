# TASKS.md

PHASE: 3
STATUS: in-progress

(0=Bootstrap | 1=Specify | 2=Design | 3=Develop | 4=Validate | 5=Deploy)

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0 — Bootstrap | Done | Project foundation and development tooling established. |
| 1 — Specify | Established; review as needed | UC-001 and UC-002 are documented. |
| 2 — Design | Established; amend as needed | ADR-001 to ADR-006 are Accepted. |
| 3 — Develop | In progress | Payroll calculation, persistent payroll saving and the wiring of the payroll router to the app's database are implemented; the slice goes through VALIDATE next. |
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
should be used to verify the calculated values. Formulas, rates and limits are in
[calculations.md](reference/calculations.md).

UC-001 employment input sub-slice (Nano, `uc-001-employment-setup`): weekly hours as H:MM kept as minutes,
holiday weeks (4 or 5) instead of days, an optional end date and 2026-only start dates.
See [UC-001](specs/UC-001-Set-Up-an-Employment.md).
- Specify (phase 1): done.
- Develop (phase 3): done, merged into `main` as PR #17. `POST /api/v1/setup` takes weekly hours as H:MM, holiday weeks
  (4 or 5, default 4) and an optional end date, and accepts only 2026 start dates
  (`tests/integration/test_setup_api.py`, `tests/unit/test_setup_service.py`). Weekly hours are whole minutes at the API
  and in the `weekly_minutes` column, and float
  hours inside `Employment`; `round(weekly_hours * 60)` converts exactly for every H:MM up to 99:59. Later:
  move all hour fields (weekly, worked, holiday) to whole minutes together, when the holiday balance is built.

UC-001 setup saving sub-slice (Nano, `uc-001-employment-setup`): setup data survives a restart.
- Specify (phase 1): done. Decided on 20 October 2026: an AHV number that is already saved reuses that employee
  (see [UC-001](specs/UC-001-Set-Up-an-Employment.md)).
- Develop (phase 3): done. `SqlAlchemySetupRepository` on the `employers`, `employees` and `employments`
  tables replaces `InMemorySetupRepository` in `create_app()`, which builds the engine from `DATABASE_URL`,
  keeps it on `app.state.engine` and disposes it on shutdown; start-up fails with `DatabaseConfigurationError`
  when the variable is unset. The port offers `get_employment(id)` so payroll can read the saved employment.
  `tests/conftest.py` gives tests an in-memory `DATABASE_URL` by default.
- Acceptance: the three rows are saved together or not at all; `6:30` is kept as 390 minutes and CHF 28.50
  as 2850 centimes; a second setup with the same employee AHV number links a new employment to the saved
  employee; data is still there after the app is created again on the same database file.
- Evidence: `tests/integration/test_sqlalchemy_setup_repository.py`, `tests/integration/test_setup_api.py`
  (`test_setup_survives_a_restart`, `test_app_does_not_start_without_database_url`),
  `tests/unit/test_setup_service.py`; `bash scripts/test.sh` passed (96 passed, 1 xfailed). Manual check
  with uvicorn on a SQLite file: the employer was still there after a restart, and a second setup reused employee 1.
- Review: merged into `main` as [PR #28](https://github.com/Guin-Kiwi/pay-align-dev/pull/28) on 20 October 2026.
  Review fix: tests always use an in-memory database, even when the developer has `DATABASE_URL` set
  (`tests/conftest.py`; `tests/integration/test_test_database_isolation.py` failed before the fix).
- Payroll wiring (done, [ADR-005](adr/ADR-005-sqlalchemy-persistence-adapter.md) items 5 and 6): the payroll request
  takes only an `employment_id`; `PayrollService` reads the employment's stored terms through its own port
  (`employment_terms(id)`; see [PROJECT.md](PROJECT.md), `MonthlyRecord` fields).

AKBS alignment check (Nano, `docs-uc-001-akbs-alignment`, Fast Track): on 20 October 2026, UC-001,
`calculations.md` and the code on PRs #28 and #29 were checked against the 2026 AKBS household-help pages, the
[AKBS 2026 gross-to-net example](https://cms.ak-bs.ch/fileadmin/downloads/2026hd-beispiel-bruttonetto.pdf),
[Merkblatt 2.07](https://www.ahv-iv.ch/p/2.07.d) and the Basel-Stadt minimum-wage FAQ. The contribution and tax
rates, FAK, BU, NBU from 8 hours a week, the annual limits and the 30 January report match.
- Admin fee (agreed, fix on PR #29 before the 24 October freeze): AKBS charges 5% of the whole AHV/IV/EO
  contribution (gross × 10.6% × 5%; on CHF 880 the example shows 4.70). `calculations.md` and
  `calculate_employer_costs` take the employer half (gross × 5.3% × 5%), so the fee is half. This settles the
  pending `admin_charge` discrepancy above in favour of the workbook. Decided on 21 October 2026: the fix goes
  into PR #29 (Ayla), reviewed by Aaron. With 1-Rappen rounding (ADR-003), CHF 880 gives 4.66, not 4.70.
- Minimum wage (decided, UC-001): CHF 22.20 is the legal minimum only below 5 hours a week. Decided on
  21 October 2026: setup keeps it as a single floor in v0.1.0, as a known limitation; see UC-001.
- Age rules (not applied in v0.1.0): no birth date is stored, so the AHV rules from reference age (CHF 1,400 a
  month allowance, no ALV) and up to age 25 (no contributions up to CHF 750 a year) are not applied. UC-001 lists
  them as out of scope; UC-002 should say the same (UC-002 owners).
- Annual wage report: no use case covers the annual aggregation for the AKBS wage declaration. Decided on
  21 October 2026: it is out of scope for v0.1.0; Ayla updates the scope in `docs/PROJECT.md`.
- Exclusions (not checked): the employer's spouse or children, and cross-border workers living in France;
  listed in UC-001.
- Monthly CHF 1,890 (open question for AKBS, 061 685 22 22): the AKBS page names it as a monthly limit, while
  Merkblatt 2.07 ties it to the pension-fund rule for jobs shorter than a year.
- Rounding (no change): AKBS rounds its example to 5 Rappen; ADR-003 keeps 1 Rappen, and AKBS bills from the
  annual gross.

Design sub-slice (phase 2): the persistence adapter for UC-002 saving, decided in
[ADR-005](adr/ADR-005-sqlalchemy-persistence-adapter.md), now Accepted.

UC-002 saving sub-slice (phase 3): implemented end to end. Behaviour is in
[UC-002](specs/UC-002-Process-the-Monthly-Employment.md), persistence and error mapping in ADR-005, the
run snapshot in [ADR-004 Amendment 2](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-2-2026-10-20).
- `SQLitePayrollRepository` is replaced by `SqlAlchemyPayrollRepository`; its tests
  moved to `tests/integration/test_sqlalchemy_payroll_repository.py` first.
- `WorkEntry` now carries `category` and `paid_minutes`; `MonthlyRecord` dropped its
  hour fields and gained `employee_id`.
- Human decisions of 20 October 2026 (run order, empty months, daily entries, public-holiday
  category combinations) are recorded in UC-002, with its Known limitations section.

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
- Foreign keys are enforced (ADR-005 item 6).

## Validation approach

- During DEVELOP, unit tests will cover domain validation, exact payroll
  calculations, NBU eligibility, reimbursement separation, and annual-limit
  rejection.
- Integration tests will verify repository foreign keys, employer uniqueness,
  and atomic persistence of the monthly record and payslip.
- Architecture tests will continue to enforce inward dependency direction.
- ADR-005 slice: integration tests cover the persistence cases of the UC-002
  validation plan (duplicate month, failed save, annual limits per
  [calculations.md §3](reference/calculations.md)), that start-up fails clearly when
  `DATABASE_URL` is unset or unsupported, and that tests dispose their engines.

## Blockers / assumptions / decisions

- No architecture blocker found.
- Assumption: the first implementation slice uses HTTP delivery and a
  relational ORM adapter as described by `docs/PROJECT.md`.
- Decision: ADR-004 defines entry snapshots, the four normal-case hour
  categories (Amendment 1), derived holiday balance, and the exclusion of sick-pay and
  corrections.
- ADR-001 through ADR-004 are marked Accepted for implementation.
- Accepted: ADR-005 (single SQLAlchemy persistence adapter, `DATABASE_URL`). The tables, the
  `DATABASE_URL` format and the money type are in [PROJECT.md](PROJECT.md).
- Decided on 16 October 2026: holiday weeks (4 or 5) replace the holiday entitlement
  days, and holiday for an employment that starts or ends during the year is
  pro-rated; see [ADR-004 Amendment 1](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-1-2026-10-16)
  (items 2 and 3).
- Decided on 16 October 2026: the app accepts only 2026, the only year with a
  ruleset (ADR-002); see UC-001.
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
- [ADR-005 SQLAlchemy persistence adapter](adr/ADR-005-sqlalchemy-persistence-adapter.md)
- [PROJECT architecture](PROJECT.md)

## Person 4 — CI, Docker, Release and architecture tests

Documentation baseline: `origin/main` at `f6fdc84`.
The shared status remains `PHASE: 3`, `STATUS: in-progress`.

- **CI:** [PR #10](https://github.com/Guin-Kiwi/pay-align-dev/pull/10)
  is merged. The whitespace check covers changes in PRs
  and pushes; syntax and Git comparison tests are documented in the PR.
- **Docker:** [PR #11](https://github.com/Guin-Kiwi/pay-align-dev/pull/11)
  is merged. Image build, container startup and health checks
  passed. This does not verify persistent data storage.
- **Release workflow:** [PR #12](https://github.com/Guin-Kiwi/pay-align-dev/pull/12)
  was successfully validated manually at commit
  `7eeb7fb8fb26c734c8c607a61ec0f973dabffb7b`:
  [Release #3](https://github.com/Guin-Kiwi/pay-align-dev/actions/runs/39240966965).
  `verify` succeeded, the image artifact was uploaded,
  and `publish` was skipped as expected.
  The PR is not merged; human review and acceptance of the
  fixed integration baseline remain pending. Actual publication
  through a `v*` tag has not been tested.
- **Documentation cleanup:**
  [PR #22](https://github.com/Guin-Kiwi/pay-align-dev/pull/22)
  is merged. Commit `39ffed463d711ca4cf295f220fe5eb5c895e736b`
  removes exactly three trailing spaces.
- **Architecture tests:** Branch `delivery-architecture-tests` contains
  the local commits `b188fc8eb8b7ff4a58836f593c1d1b1acc57899b`
  (relative imports and package imports) and
  `02421b8ae6dd1014a32c09bc5d70e2f1a6492ad1`
  (literal dynamic imports). Together they add 58
  regression cases, all passing. They have not been pushed.

### Local architecture validation evidence

- Architecture tests: **75 passed, 1 failed**.
- `bash scripts/test.sh`: lifecycle tests and 32 tooling tests passed;
  pytest: **145 passed, 1 failed, 1 xfailed,
  41 subtests passed**, with one Starlette/HTTPX deprecation warning.
- `git diff --check`: passed.
- Only failing test:
  `test_project_follows_the_dependency_rule`.
  `src/app/interfaces/payroll.py` directly imports
  `src.app.infrastructure.sqlite_payroll_repository`.
  Ayla and Aaron are handling the payroll wiring.
- The architecture tests and the full suite on the
  architecture branch therefore still have a failure.
  The test remains enabled and unchanged.

Next steps for Person 4: support the review of PR #12,
coordinate architecture work with the payroll correction, and then
rerun the tests. Prepare presentation evidence from these results;
the presentation is not marked complete here.

## Next smallest step

Run the UC-002 saving slice through VALIDATE: confirm the golden payroll cases and
the end-to-end API test on a clean checkout, then review the slice.

Run snapshot slice (phase 3): done. The run snapshot is defined in
[ADR-004 Amendment 2](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-2-2026-10-20);
the limit of its immutability is in the UC-002 Known limitations.

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
