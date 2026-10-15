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

Document the commands for the selected stack:

| Activity | Command |
|---|---|
| Install | `docker compose build` |
| Unit tests | `docker compose run --rm app pytest tests/unit/` |
| Integration tests | `docker compose run --rm app pytest tests/integration/` |
| Run locally | `docker compose up` |
| Build/release | `docker compose build --no-cache` |

*(Note: If running outside of Docker for fast local development, use standard `pip install -r requirements.txt` and `pytest` commands).*

## Dependencies

* **Runtime:** Docker, Python 3.11+
* **Core Libraries:** FastAPI (Web Framework), SQLAlchemy (ORM), Pydantic (Validation), Pytest (Testing)
* **Environment Variables:** `DATABASE_URL` (Required for infrastructure configuration). 
* Never commit `.env` credentials to version control.

## Data conventions

* **`DATABASE_URL` format:** a SQLAlchemy URL, e.g. `sqlite:////app/data/payroll.db` (four slashes for an absolute path inside the container). Until the database setup lands on `uc-002-payroll-saving`, the API still uses an in-memory SQLite connection and ignores the variable.
* **Tables:** `employers`, `employees`, `employments`, `monthly_records` and `payslips`, one per core entity. The holiday balance is not stored on `employments`; it is derived from persisted runs ([ADR-004](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md)).
* **Money type** ([ADR-003](adr/ADR-003-monetary-precision-and-rounding.md)): `Decimal` in domain and application code, integer centimes in the database (columns suffixed `_cents`). The domain and `PayrollService` still use `float`; the migration to `Decimal` belongs to the payroll-calculation slice.
* **`MonthlyRecord` fields:** `id`, `employment_id`, `month` (1-12), `year` (2026 or later), `hours_worked`, `holiday_hours` (paid holiday), `public_holiday_hours`, `cash_bonus` and `expense_reimbursements` (stored as `_cents`). The employer is stored alongside as `employer_id`. Duplicate `(employment_id, month, year)` is rejected.
