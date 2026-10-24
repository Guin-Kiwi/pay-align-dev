# PROJECT.md

## Purpose

- **Project name:** PayAlign
- **User or organisational problem:** Private individuals employing household help need a way to legally and accurately manage monthly payroll under the AKBS simplified settlement procedure without facing heavy corporate HR administration.
- **Intended users:** Private household employers in Basel-Stadt.
- **In scope:** Employer accounts and login, employer onboarding, employee registration and contract parameter generation, monthly payroll processing (gross-to-net calculations using 2026 rates), and payslip generation.
- **Out of scope:** The annual aggregation for the AKBS wage declaration (for v0.1.0), exception management (including sick pay, occupational accidents, property damage, and disputes), termination workflows, employer account closure, and the standard settlement procedure (Standard-Abrechnung). The normal-case monthly payroll use case does not record or calculate sick-pay hours.

## Architecture

We are using **Clean Architecture** to ensure the core payroll logic is completely isolated from the web framework and database. Dependencies strictly point inward:

`domain ← application ← interfaces ← infrastructure`

* **Domain:** Contains Account, Employer, Employee, Employment, MonthlyRecord and Payslip, plus the immutable 2026 AKBS payroll calculation rules.
* **Application:** Contains the core services (`SetupService`, `PayrollService`, `AccountService`) and defines repository and password-hashing interfaces (Ports).
* **Interfaces:** Contains the web routing (e.g., FastAPI controllers), request/response models, authentication boundary and CSRF checks.
* **Infrastructure:** Contains the ORM mappings (e.g., SQLAlchemy), database connection, Argon2 password-hasher adapter, signed-cookie session middleware and web server wiring.

**Deployment & Data-store:** The application is a containerized full-stack web application that uses a relational database via an ORM. The code on `main` supports SQLite for local runs, Docker Compose and tests, and PostgreSQL on Neon for the Render deployment ([ADR-005 Amendment 1](adr/ADR-005-sqlalchemy-persistence-adapter.md#amendment-1-2026-10-23)). Render builds the `Dockerfile` from the release commit on a release, or from the latest commit on `main` on a manual deploy. Render's active database is selected by its `DATABASE_URL` environment variable; until it is switched to the Neon URL, it points to `/tmp`, so data is lost on every deploy and restart, including when the free instance wakes up after a time without visitors.

## Structure

* `src/app/domain/`: Core entities and payroll calculation logic.
* `src/app/application/`: Use case services and repository interfaces (Ports).
* `src/app/interfaces/`: Web controllers and API routes.
* `src/app/infrastructure/`: Database adapters, ORM models, and framework wiring.
* `tests/unit/`: Fast, isolated tests for the Domain and Application layers.
* `tests/integration/`: Tests for the Infrastructure layer (database adapters and API endpoints).

## Resources

Where non-code material lives; link reference documents here so agents find them.

- Runtime files (templates, static files, seed data, migrations): inside `src/app/`, in the layer that uses them
- Test data: `tests/fixtures/`
- Values: `src/app/domain/constants.py` holds every rate, limit and threshold the app applies, once. Why each value is what it is lives in the sources under `docs/reference/` or in the UC or ADR that decided it.
- Reference material (brief, domain notes, glossary, diagrams): `docs/reference/`
  - Formulas: `calculations.md` holds the formulas the app applies, using the constant names.
  - Source: `Employing_Household_Help_Basel.pdf`, the guide to the 2026 AKBS simplified procedure, as published.
  - Source: `Employing_Household_Help_Basel.md`, an agent-readable summary of that guide, with citations.
  - Source: `Payslip_2026.xlsm`, the payslip workbook the golden payroll test cases (`tests/fixtures/payroll_golden_cases.json`) are derived from.
  - [AKBS Household Employment Overview](https://www.ak-bs.ch/ubersicht/beitrage-an-die-ahv-iv-eo/haushaltshilfen/)
  - [Basel AWA NAV Legal Text](https://gesetzessammlung.bs.ch/app/de/texts_of_law/215.700)
- Secrets and real config values: never in the repository; `.env` locally

## Commands

Run all commands from the project directory. Docker must be available for Docker commands, and port 8000 must be free when starting the application.

| Activity | Command |
|---|---|
| Build Docker image | `docker compose build api` |
| Start application | Set `SESSION_SECRET_KEY` in `.env` to a random value from `python -c "import secrets; print(secrets.token_urlsafe(32))"`, then run `docker compose up api` |
| Health check | `curl --fail --include http://localhost:8000/health` |
| Unit tests | `.venv/bin/python -m pytest tests/unit/` |
| Integration tests | `.venv/bin/python -m pytest tests/integration/` |
| End-to-end tests (start the app as a server) | `.venv/bin/python -m pytest tests/e2e/` |
| Tests against PostgreSQL (skipped without the variable) | `TEST_POSTGRES_URL=postgresql://user:password@host/dbname .venv/bin/python -m pytest` |
| All project checks | `bash scripts/test.sh` |
| Build image without cache | `docker compose build --no-cache api` |

Warning: PostgreSQL tests drop every table in the database pointed to by `TEST_POSTGRES_URL`. Use a throwaway database only; never use the Neon database used by Render.

Run tests outside the runtime container in the local `.venv` Python environment. Set up this environment with the dependencies from `requirements.txt`, using `.venv/bin/python -m pip install -r requirements.txt`. `.dockerignore` excludes tests and process scripts from the runtime image.

Run the health check while the application is running. It should return HTTP 200 and `{"status":"ok"}`. This does not verify persistent data storage.

The release workflow runs the existing tests, builds and starts a Docker image for `linux/amd64` using an isolated in-memory database, and provides the verified image as `payalign-<Commit-ID>-linux-amd64.tar.gz`. The archive contains the image, not running containers or payroll data. After downloading it, load it with `docker load --input payalign-<Commit-ID>-linux-amd64.tar.gz`, replacing `<Commit-ID>` with the actual ID in the filename. The resulting image name is `payalign:<Commit-ID>`. This image is not native to ARM Macs; Docker requires support for running `linux/amd64` images.

Pushes of version tags matching `v*` publish the archive to a GitHub Release after successful checks. Manual runs only validate and store the archive as an Actions artifact by default. Manual publication requires explicitly selecting `publish_release` and running from a `v*` tag.

A published `v*` release calls the CD workflow after publication. When `CD_ENABLED=true`, `scripts/deploy.sh` calls the Render hook stored in `RENDER_DEPLOY_HOOK_URL` with `ref` set to the release commit, so Render builds that commit. A manual CD run from a branch (Actions → CD → Run workflow) calls the hook without `ref` and deploys the latest commit on Render's linked branch. Render builds its own image from source; it does not use the image archive published by the release workflow. `scripts/smoke-test.sh` checks that `/health` answers, but Render can serve the previous version during a new build, so this check shows availability rather than confirming the new version is live.

## Dependencies

* **Runtime:** Docker, Python 3.11+ (`.python-version` pins 3.12 for CI and the dev container; the container image uses 3.11)
* **Core Libraries:** FastAPI (Web Framework), SQLAlchemy (ORM), psycopg 3 (PostgreSQL driver), Pydantic (Validation), pwdlib with Argon2 (password hashing), itsdangerous (Starlette signed sessions), Pytest (Testing)
* **Environment Variables:** `DATABASE_URL` (required for infrastructure configuration), `SESSION_SECRET_KEY` (required, random secret of at least 32 characters), `SESSION_COOKIE_SECURE` (set to `true` when serving over HTTPS; Docker Compose defaults it to `false` for local HTTP development).
* Never commit `.env` credentials to version control.

## Data conventions

* **`DATABASE_URL` format:** a SQLAlchemy URL, e.g. `sqlite:////app/data/payroll.db` (four slashes for an absolute path inside the container). It is required; there is no silent in-memory fallback. `sqlite` and `postgresql` URLs are accepted (for example `postgresql://user:password@host/dbname?sslmode=require`); any other scheme, including `postgres://`, fails at start-up.
* **Tables:** `accounts`, `employers`, `employees`, `employments`, `monthly_records`, `payslips`, `work_entries` and `payroll_snapshots`, one per core entity or persisted payroll run. `accounts` stores normalized login email, adaptive password hash and account first/last name; it does not store passwords. Each `employers` row has one unique `account_id`; employer AHV numbers are not globally unique, and matching AHV numbers never share a profile across accounts ([UC-003 Amendment 5](specs/UC-003-Employer-Accounts-and-Secure-Access.md#amendment-5--2026-10-24-account-isolation-corrections)). Each `employees` row belongs to an employer, with AHV unique within that employer; an employment links an employee of the same employer. `employments` stores integer `weekly_minutes` and `holiday_weeks` and a nullable `end_date`. `monthly_records` stores `employee_id` alongside `employment_id` and `employer_id`. The holiday balance is not stored on `employments`; it is derived from persisted runs ([ADR-004](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md)). `payroll_snapshots` stores the run snapshot ([ADR-004 Amendment 2](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-2-2026-10-20)).

Authentication endpoints are under `/api/v1/auth`: `GET /csrf` issues a CSRF token; `POST /register`, `POST /login` and `POST /logout` change authentication state; `GET /me` returns the current account. Registration and login create a four-hour signed session cookie containing only the account ID. The cookie is HttpOnly and SameSite=Lax; configure `SESSION_COOKIE_SECURE=true` over HTTPS. Registration and login return the rotated CSRF cookie value as `csrf_token` alongside the account fields in JSON; the client sends it in `X-CSRF-Token` on subsequent state-changing requests. Registration password validation is defined in [UC-003 Amendment 4](specs/UC-003-Employer-Accounts-and-Secure-Access.md#amendment-4--2026-10-24-registration-policy-and-csrf-token-return). Session limits and known copied-cookie behavior are recorded in [ADR-007](adr/ADR-007-employer-accounts-and-secure-access.md).

The current HTTP endpoints are:

| Method and path | Purpose |
|---|---|
| `GET /health` | Health check. |
| `GET /api/v1/auth/csrf` | Issue a CSRF token. |
| `POST /api/v1/auth/register` | Register an account and start its session. |
| `POST /api/v1/auth/login` | Start an account session. |
| `GET /api/v1/auth/me` | Read the signed-in account. |
| `POST /api/v1/auth/logout` | End the account session. |
| `GET /api/v1/employer` | Read the signed-in account's employer profile. |
| `POST /api/v1/setup` | Create an employer profile and first employment, or add an employment under the signed-in employer. |
| `GET /api/v1/employments` | List the signed-in employer's employments. |
| `GET /api/v1/employments/{employment_id}` | Read one owned employment's summary. |
| `GET /api/v1/employments/{employment_id}/months` | List saved months and the next eligible 2026 month. |
| `GET /api/v1/employments/{employment_id}/months/{year}/{month}` | Read an owned month's saved payslip and holiday balance. |
| `POST /api/v1/monthly-payroll` | Save the next monthly run. |

Employment and month reads require a session and return 404 for absent or other-account records. `PayrollService.process_monthly_payroll` and the payroll port's `employment_terms` require an account ID; neither provides an unscoped fallback. Completed months have no update or delete endpoint; the scope decision is in [UC-003 Amendment 3](specs/UC-003-Employer-Accounts-and-Secure-Access.md#amendment-3--2026-10-23-minimum-browser-views).
* **Money type** ([ADR-003](adr/ADR-003-monetary-precision-and-rounding.md)): never a binary float. The APIs read amounts as `Decimal`, payroll calculation and `PayrollService` use `Decimal`, and the database stores integer centimes (columns suffixed `_cents`). Amounts become centimes once, before saving, rounding half-up and never truncating: in `PayrollService` for payroll, in `SqlAlchemySetupRepository` for setup. `cash_bonus` and `expense_reimbursements` are rounded half-up to CHF 0.01 once, on entry to `PayrollService`. Known exception in v0.1.0: setup's `Employment.hourly_wage` is still declared `float`. It holds the API's `Decimal` and is saved through `Decimal(str(...))`; `get_employment`, which only tests use, reads it back as centimes divided by 100, a `float`. Payroll does not use it: it reads the wage in centimes and calculates in `Decimal`.
* **`MonthlyRecord` fields:** `id`, `employment_id`, `employee_id`, `employer_id`, `month` (1-12), `year` (2026 only, the one year with a ruleset; ADR-002), `cash_bonus` and `expense_reimbursements` (stored as `_cents`). Hour totals are derived from persisted `work_entries`, not stored on `monthly_records`. A run names an `employment_id`; employer, employee and the employment terms are read from `employments` through the payroll port, and an unknown id is rejected before anything is saved (404).
* **Run sequence:** defined in [UC-002](specs/UC-002-Process-the-Monthly-Employment.md) (alternate flows). `PriorRun` carries `year` and `month`.
* **Time type** ([ADR-004 Amendment 1](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-1-2026-10-16)): whole minutes everywhere. `WorkEntry` carries a `category` and `paid_minutes`, plus optional `start_time`, `end_time` and `unpaid_break_minutes`; with times, `paid_minutes` is derived from them. `PayrollService` classifies and rejects entries as [UC-002](specs/UC-002-Process-the-Monthly-Employment.md) specifies (public holidays, overlaps, invalid category combinations); rejections are 400 responses. `work_entries` stores one row per submitted entry with its times and break; `payroll_snapshots` also keeps the `employment_start_date` and `employment_end_date`. The four categories ([ADR-004 Amendment 1](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-1-2026-10-16), item 6) are defined once in `src/app/domain/hour_categories.py` and mirrored by the `work_entries` CHECK constraint.
