# ADR-005-sqlalchemy-persistence-adapter

## Status
Accepted

## Context
UC-002 must save daily entries, a frozen run snapshot, the `MonthlyRecord` and the `Payslip` in one transaction ([ADR-004](ADR-004-payroll-entry-snapshots-and-holiday-balance.md)). `docs/PROJECT.md` names a relational database reached through an ORM and configured by `DATABASE_URL`.

The first database setup and its review exposed gaps that this decision must close:

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
- Enforce foreign keys immediately: considered first and rejected at the time, because no use case persisted employers or employments, so every payroll run would have been rejected. Item 6 switches enforcement on now that UC-001 saves them.

## Decision
Infrastructure has one persistence adapter, built on SQLAlchemy 2.x, and the ORM models are the only schema definition.

The database foundation (`database.py`, `orm_models.py`, and the five skeleton
tables) is delivered separately. `work_entries`,
`payroll_snapshots`, and `monthly_records.employee_id` are not included in that
foundation.

1. **Adapter.** A SQLAlchemy repository implements the application port and uses one session per request as the unit of work. The raw DDL and legacy-migration code of `SQLitePayrollRepository` are removed (assumption: the earlier float-column schema was never deployed, so there is nothing to migrate).
2. **Port** (application layer, no framework imports):
   - gross wage of the calendar year for one employee with one employer, and for one employer (limits in [calculations.md §3](../reference/calculations.md));
   - the immediately prior run of an employment, whatever its year (ADR-004 Amendment 1, item 9);
   - save one run atomically: entries, snapshot, `MonthlyRecord`, `Payslip`.
3. **Errors.** The domain defines `DuplicateMonthError` and `InvalidHolidayBalanceError` in `src/app/domain/errors.py`, beside `AnnualLimitExceededError` and `InvalidPayrollInputError`. The adapter translates the unique-constraint failure on `(employment_id, month, year)` into `DuplicateMonthError`; any other `IntegrityError` becomes `InvalidPayrollInputError` with a fixed message; no raw database error text reaches the interfaces.
4. **Records.** `monthly_records` also stores `employee_id` (like `employer_id`), so the employee limit does not depend on employment persistence. New tables: `work_entries` (one row per submitted daily entry, belonging to a monthly record) and `payroll_snapshots` (one per monthly record). `payroll_snapshots` stores the run snapshot defined in ADR-004 Amendment 2: the employment terms (hourly wage, weekly minutes, holiday weeks, employment start and end dates), the ruleset version, the minute totals per hour category and the holiday balance after the run. The submitted entries are the record's `work_entries` and are not copied. Hour totals are not stored on `monthly_records`; they derive from `work_entries`; time is integer minutes ([ADR-004](ADR-004-payroll-entry-snapshots-and-holiday-balance.md)). Both tables are written in the run's transaction and have no update path. Money stays integer centimes ([ADR-003](ADR-003-monetary-precision-and-rounding.md)); the adapter converts from `Decimal`.
5. **Configuration.** `DATABASE_URL` is required and startup fails with a clear message if it is unset or has an unsupported scheme. The engine is created in `create_app()` (`src/app/infrastructure/web/app.py`), using the wiring pattern of [ADR-006](ADR-006-uc-001-setup-api-and-wiring.md), and disposed on application shutdown. Tests can replace it. In-memory SQLite is recognised from the parsed URL and uses a single shared connection; in-memory SQLite is for tests only; with `StaticPool` all requests share one connection. PostgreSQL: see [Amendment 1](#amendment-1-2026-10-23).
6. **Foreign keys.** Declared in the schema. Enforcement is now switched on (`PRAGMA foreign_keys=ON` per connection), because UC-001 saves employers and employments; a payroll row must reference an existing employment.
7. **Delivery.** The payroll router maps `AnnualLimitExceededError`, `InvalidPayrollInputError`, `DuplicateMonthError` and `InvalidHolidayBalanceError` to 4xx responses, never 500.

Holiday entitlement and the derived balance are defined by [ADR-004 Amendment 1](ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-1-2026-10-16).

Approval: Proposed by Ayla; accepted by a non-author reviewer's approval of the pull request that records this approval.

## Consequences
- `SQLitePayrollRepository` was replaced by the SQLAlchemy adapter; its tests moved to the new adapter first (TDD).
- SQLAlchemy imports stay in infrastructure; the architecture test keeps enforcing this.
- `requirements.txt` pins `sqlalchemy>=2.0`.
- `create_all` does not alter existing tables; an existing `data/payroll.db` on the Docker volume must be deleted until migrations are decided.
- Tests must dispose their engines so database files can be removed on Windows.
- Referential integrity is enforced (item 6): a payroll row cannot reference a missing employment.

## Supersedes
none

## Amendment 1 (2026-10-23)

Approval: Proposed by Ayla; accepted by a non-author reviewer's approval of the pull request that records this approval.

Decision: the Render deployment stores its data in a free Neon PostgreSQL database. SQLite stays for local runs, Docker Compose and the tests.

1. `DATABASE_URL` accepts `sqlite` and `postgresql` URLs (item 5). A `postgresql://` URL is opened with the psycopg 3 driver; `postgres://` is rejected.
2. The SQLite connection settings (`PRAGMA foreign_keys=ON`, `check_same_thread`, `StaticPool` for in-memory databases) apply to SQLite only. PostgreSQL enforces foreign keys itself, so item 6 holds for both.
3. The adapter recognises the unique-constraint failure of item 3 by the SQLite message or by PostgreSQL's SQLSTATE `23505`.
4. The repository-error tests and the end-to-end demo flow also run on PostgreSQL where `TEST_POSTGRES_URL` is set; CI sets it.

Why: on Render, SQLite lives in `/tmp`, so the data is lost on every deploy and whenever the free instance wakes up after sleeping. The grading criteria name "Render + PostgreSQL" as their example of a cloud deployment.

Not chosen: Render's free PostgreSQL, which expires 30 days after it is created; SQLite in `/tmp`, which loses the data.

Consequences:
- `requirements.txt` adds `psycopg[binary]`.
- The Neon connection URL contains a password. It is set only as `DATABASE_URL` in Render's environment, never in a file, pull request or chat.
- Neon's free compute pauses when idle, so the first request after a pause is slower; `pool_pre_ping` replaces connections that were closed meanwhile.
- `create_all` does not alter existing tables (see Consequences), so a later schema change needs the Neon tables dropped until migrations are decided.
