# PROJECT.md

## Purpose

- **Project name:** PayAlign
- **User or organisational problem:** Private individuals employing household help need a way to legally and accurately manage monthly payroll and annual reporting under the AKBS simplified settlement procedure without facing heavy corporate HR administration.
- **Intended users:** Private household employers in Basel-Stadt.
- **In scope:** Single-employer onboarding, employee registration and contract parameter generation, monthly payroll processing (gross-to-net calculations using 2026 rates), payslip generation, and annual aggregation for the AKBS wage declaration.
- **Out of scope:** Exception management (including sick pay, occupational accidents, property damage, and disputes), termination workflows, employer account closure, and the standard settlement procedure (Standard-Abrechnung). The normal-case monthly payroll use case does not record or calculate sick-pay hours.

## Architecture

We are using **Clean Architecture** to ensure the core payroll logic is completely isolated from the web framework and database. Dependencies strictly point inward:

`domain ← application ← interfaces ← infrastructure`

* **Domain:** Contains the five core entities (Employer, Employee, Employment, MonthlyRecord, Payslip) and the immutable 2026 AKBS payroll calculation rules. 
* **Application:** Contains the core services (`BootService`, `SetupService`, `PayrollService`, `AnnualReportingService`) and defines the repository interfaces (Ports).
* **Interfaces:** Contains the web routing (e.g., FastAPI controllers) and request/response models.
* **Infrastructure:** Contains the ORM mappings (e.g., SQLAlchemy), database connection, and the web server wiring.

**Deployment & Data-store:** The application is a local, containerized full-stack web application. It uses a relational database (e.g., SQLite or PostgreSQL) via an ORM. It runs locally via Docker and is accessed via a local web browser.

## Structure

* `src/domain/`: Core entities and payroll calculation logic.
* `src/application/`: Use case services and repository interfaces (Ports).
* `src/interfaces/`: Web controllers and API routes.
* `src/infrastructure/`: Database adapters, ORM models, and framework wiring.
* `tests/unit/`: Fast, isolated tests for the Domain and Application layers.
* `tests/integration/`: Tests for the Infrastructure layer (database adapters and API endpoints).

## Resources

Where non-code material lives; link reference documents here so agents find them.

- Runtime files (templates, static files, seed data, migrations): inside `src/app/`, in the layer that uses them
- Test data: `tests/fixtures/`
- Reference material (brief, domain notes, glossary, diagrams): `docs/reference/`
  - `Employing_Household_Help_Basel.md`: The agent-friendly guide and ruleset for the 2026 AKBS simplified procedure.
  - `calculations.md`: The agent-friendly guide calculation file used as the mathematical reference for calculations.
  - `Employing_Household_Help_Basel.pdf`: The human-friendly guide and ruleset for the 2026 AKBS simplified procedure.
  - `Payslip_2026.xlsm`: The human-friendly workbook, the mathematical reference for calculations.
  - [AKBS Household Employment Overview](https://www.ak-bs.ch/ubersicht/beitrage-an-die-ahv-iv-eo/haushaltshilfen/)
  - [Basel AWA NAV Legal Text](https://gesetzessammlung.bs.ch/app/de/texts_of_law/215.700)
- Secrets and real config values: never in the repository; `.env` locally

## Commands

Run all commands from the project directory. Docker must be available for Docker commands, and port 8000 must be free when starting the application.

| Activity | Command |
|---|---|
| Build Docker image | `docker compose build api` |
| Start application | `docker compose up api` |
| Health check | `curl --fail --include http://localhost:8000/health` |
| Unit tests | `.venv/bin/python -m pytest tests/unit/` |
| Integration tests | `.venv/bin/python -m pytest tests/integration/` |
| End-to-end tests (start the app as a server) | `.venv/bin/python -m pytest tests/e2e/` |
| All project checks | `bash scripts/test.sh` |
| Build image without cache | `docker compose build --no-cache api` |

Run tests outside the runtime container in the local `.venv` Python environment. Set up this environment with the dependencies from `requirements.txt`, using `.venv/bin/python -m pip install -r requirements.txt`. `.dockerignore` excludes tests and process scripts from the runtime image.

Run the health check while the application is running. It should return HTTP 200 and `{"status":"ok"}`. This does not verify persistent data storage.

The release workflow runs the existing tests, builds and starts a Docker image for `linux/amd64` using an isolated in-memory database, and provides the verified image as `payalign-<Commit-ID>-linux-amd64.tar.gz`. The archive contains the image, not running containers or payroll data. After downloading it, load it with `docker load --input payalign-<Commit-ID>-linux-amd64.tar.gz`, replacing `<Commit-ID>` with the actual ID in the filename. The resulting image name is `payalign:<Commit-ID>`. This image is not native to ARM Macs; Docker requires support for running `linux/amd64` images.

Pushes of version tags matching `v*` publish the archive to a GitHub Release after successful checks. Manual runs only validate and store the archive as an Actions artifact by default. Manual publication requires explicitly selecting `publish_release` and running from a `v*` tag.

## Dependencies

* **Runtime:** Docker, Python 3.11+
* **Core Libraries:** FastAPI (Web Framework), SQLAlchemy (ORM), Pydantic (Validation), Pytest (Testing)
* **Environment Variables:** `DATABASE_URL` (Required for infrastructure configuration). 
* Never commit `.env` credentials to version control.

## Data conventions

* **`DATABASE_URL` format:** a SQLAlchemy URL, e.g. `sqlite:////app/data/payroll.db` (four slashes for an absolute path inside the container). It is required; there is no silent in-memory fallback.
* **Tables:** `employers`, `employees`, `employments`, `monthly_records`, `payslips`, `work_entries` and `payroll_snapshots`, one per core entity or persisted payroll run. `monthly_records` stores `employee_id` alongside `employment_id` and `employer_id`. The holiday balance is not stored on `employments`; it is derived from persisted runs ([ADR-004](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md)). `payroll_snapshots` stores the run snapshot ([ADR-004 Amendment 2](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-2-2026-10-20)).
* **Money type** ([ADR-003](adr/ADR-003-monetary-precision-and-rounding.md)): `Decimal` in domain and application code, integer centimes in the database (columns suffixed `_cents`). The domain and `PayrollService` use `Decimal`; the adapter converts at the boundary. `cash_bonus` and `expense_reimbursements` are rounded half-up to CHF 0.01 once, on entry to `PayrollService`, and converted to centimes by rounding, never truncating. An hourly wage with more than two decimals is rejected (UC-001).
* **`MonthlyRecord` fields:** `id`, `employment_id`, `employee_id`, `employer_id`, `month` (1-12), `year` (2026 or later), `cash_bonus` and `expense_reimbursements` (stored as `_cents`). Hour totals are derived from persisted `work_entries`, not stored on `monthly_records`. Duplicate `(employment_id, month, year)` is rejected. A run names an `employment_id`; employer, employee and the employment terms are read from `employments` through the payroll port, and an unknown id is rejected before anything is saved (404).
* **Run sequence:** an employment's first run is the month of its start date; each later run is the month after its last saved run (`PriorRun` carries `year` and `month`). An earlier or equal month is a duplicate; a later one is a skipped month and is rejected. A month without entries is still a run: it saves a payslip without hours and records the holiday balance.
* **Time type** ([ADR-004 Amendment 1](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-1-2026-10-16)): whole minutes everywhere. `WorkEntry` carries a `category` and `paid_minutes`, plus optional `start_time`, `end_time` and `unpaid_break_minutes`; with times, `paid_minutes` is derived from them and entries of one day may not overlap (several non-overlapping entries are valid). `PayrollService` classifies work on a public holiday (`is_public_holiday`) as `public_holiday_worked` and rejects `public_holiday_worked` and `public_holiday_taken` on other days, `annual_holiday_taken` on a public holiday (NAV Haushalt BS § 27 para 4), and `public_holiday_taken` on the same day as `public_holiday_worked` or `annual_holiday_taken`; all are 400 responses. `work_entries` stores one row per submitted entry with its times and break; `payroll_snapshots` also keeps the `employment_start_date` and `employment_end_date`. The four categories are `worked`, `public_holiday_worked`, `annual_holiday_taken` and `public_holiday_taken`, defined once in `src/app/domain/hour_categories.py` and mirrored by the `work_entries` CHECK constraint.
