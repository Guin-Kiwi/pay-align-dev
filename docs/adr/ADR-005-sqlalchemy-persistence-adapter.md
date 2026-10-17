# ADR-005-sqlalchemy-persistence-adapter

## Status
Proposed

## Context
UC-002 must save daily entries, a frozen run snapshot, the `MonthlyRecord` and the `Payslip` in one transaction ([ADR-004](ADR-004-payroll-entry-snapshots-and-holiday-balance.md)). `docs/PROJECT.md` names a relational database reached through an ORM and configured by `DATABASE_URL`.

The first database setup on `uc-002-payroll-saving` and its review exposed gaps that this decision must close:

- The schema for `monthly_records` and `payslips` is defined twice: in the ORM models and in the raw DDL of `SQLitePayrollRepository`. The two differ (foreign keys) and the repository's legacy migration recreates tables without them.
- The repository is SQLite-only but `DATABASE_URL` accepts any URL. It is also handed the raw driver connection of a pooled SQLAlchemy connection, so pool resets and threads can interfere with its transactions.
- The engine is built when the interfaces module is imported, so tests cannot inject a database and a bad URL fails at import.
- An unset `DATABASE_URL` silently falls back to an in-memory database, although `PROJECT.md` calls the variable required.
- Foreign keys point at `employers` and `employments`, which nothing persists yet.
- The employee annual limit is checked per employment, because `monthly_records` has no `employee_id`.

## Alternatives
- Keep the sqlite3 repository next to the ORM skeleton: rejected because the schema would keep two sources of truth and the adapter would stay SQLite-only.
- Drop SQLAlchemy and keep only sqlite3: rejected because `PROJECT.md` specifies an ORM and a configurable database URL; it would need its own amendment and loses portability.
- Keep the silent in-memory fallback: rejected because payroll data would be lost without any signal when the variable is missing or misspelled.
- Enforce foreign keys immediately: rejected for now because no use case persists employers or employments, so every payroll run would be rejected.

## Decision
Infrastructure has one persistence adapter, built on SQLAlchemy 2.x, and the ORM models are the only schema definition.

The database foundation (`database.py`, `orm_models.py`, and the five skeleton
tables) is delivered separately in PR #18. `work_entries`,
`payroll_snapshots`, and `monthly_records.employee_id` are not included in that
foundation.

1. **Adapter.** A SQLAlchemy repository implements the application port and uses one session per request as the unit of work. The raw DDL and legacy-migration code of `SQLitePayrollRepository` are removed (assumption: the earlier float-column schema was never deployed, so there is nothing to migrate).
2. **Port** (application layer, no framework imports):
   - gross wage to date per employee and per employer for a year;
   - the immediately prior run of an employment for the same calendar year;
   - save one run atomically: entries, snapshot, `MonthlyRecord`, `Payslip`.
3. **Errors.** The domain defines `DuplicateMonthError` and `InvalidHolidayBalanceError` in `src/app/domain/errors.py`, beside `AnnualLimitExceededError` and `InvalidPayrollInputError`. The adapter translates the unique-constraint failure on `(employment_id, month, year)` into `DuplicateMonthError`; no raw database error reaches the interfaces.
4. **Records.** `monthly_records` also stores `employee_id` (like `employer_id`), so the employee limit does not depend on employment persistence. New tables: `work_entries` (one row per submitted daily entry, belonging to a monthly record) and `payroll_snapshots` (one per monthly record). A snapshot holds the employment parameters at the time (hourly wage, weekly minutes, holiday weeks), the ruleset version, the minute totals per hour category and the derived holiday balance in whole minutes. The submitted entries are the record's `work_entries` and are not copied. Hour totals are not stored on `monthly_records`; they derive from `work_entries`; time is integer minutes ([ADR-004](ADR-004-payroll-entry-snapshots-and-holiday-balance.md)). Both tables are written in the run's transaction and have no update path. Money stays integer centimes ([ADR-003](ADR-003-monetary-precision-and-rounding.md)); the adapter converts from `Decimal`.
5. **Configuration.** `DATABASE_URL` is required and startup fails with a clear message if it is unset or has an unsupported scheme. The engine is created in `create_app()` (`src/app/infrastructure/web/app.py`), using the wiring pattern of [ADR-006](ADR-006-uc-001-setup-api-and-wiring.md), and disposed on application shutdown. Tests can replace it. In-memory SQLite is recognised from the parsed URL and uses a single shared connection; in-memory SQLite is for tests only; with `StaticPool` all requests share one connection.
6. **Foreign keys.** Declared in the schema. Enforcement is switched on when UC-001 persists employers and employments; until then payroll rows may reference parents that do not exist.
7. **Delivery.** The payroll router maps `AnnualLimitExceededError`, `InvalidPayrollInputError`, `DuplicateMonthError` and `InvalidHolidayBalanceError` to 4xx responses, never 500.

Holiday entitlement and the derived balance are defined by [ADR-004 Amendment 1](ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-1-2026-10-16).

Approval: AYLA PROPOSES

## Consequences
- `SQLitePayrollRepository` is replaced during DEVELOP on `uc-002-payroll-saving`; its tests move to the new adapter first (TDD).
- SQLAlchemy imports stay in infrastructure; the architecture test keeps enforcing this.
- `requirements.txt` pins `sqlalchemy>=2.0`.
- `create_all` does not alter existing tables; an existing `data/payroll.db` on the Docker volume must be deleted until migrations are decided.
- On acceptance, `docs/PROJECT.md` is updated: `DATABASE_URL` required with no fallback, the two new tables, `employee_id` on `monthly_records`.
- Tests must dispose their engines so database files can be removed on Windows.
- Until UC-001 persists parents, referential integrity is declared but not enforced.

## Supersedes
none
