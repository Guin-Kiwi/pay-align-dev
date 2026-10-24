# PROJECT.md

## Purpose

- **Project name:** PayAlign
- **User or organisational problem:** Private individuals employing household help need a way to legally and accurately manage monthly payroll under the AKBS simplified settlement procedure without facing heavy corporate HR administration.
- **Intended users:** Private household employers in Basel-Stadt.
- **In scope:** Single-employer onboarding, employee registration and contract parameter generation, monthly payroll processing (gross-to-net calculations using 2026 rates), and payslip generation.
- **Out of scope:** The annual aggregation for the AKBS wage declaration (for v0.1.0), exception management (including sick pay, occupational accidents, property damage, and disputes), termination workflows, employer account closure, and the standard settlement procedure (Standard-Abrechnung). The normal-case monthly payroll use case does not record or calculate sick-pay hours.

## Architecture

We are using **Clean Architecture** to ensure the core payroll logic is completely isolated from the web framework and database. Dependencies strictly point inward:

`domain ← application ← interfaces ← infrastructure`

* **Domain:** Contains the five core entities (Employer, Employee, Employment, MonthlyRecord, Payslip) and the immutable 2026 AKBS payroll calculation rules. 
* **Application:** Contains the core services (`SetupService`, `PayrollService`) and defines the repository interfaces (Ports).
* **Interfaces:** Contains the web routing (e.g., FastAPI controllers) and request/response models.
* **Infrastructure:** Contains the ORM mappings (e.g., SQLAlchemy), database connection, and the web server wiring.

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
| Prepare SQLite bind-mount ownership (first run or upgrade from root) | `docker compose run --rm --no-deps --user root --entrypoint chown api -R 10001:10001 /app/data` |
| Start application | `docker compose up api` |
| Health check | `curl --fail --include http://localhost:8000/health` |
| Unit tests | `.venv/bin/python -m pytest tests/unit/` |
| Integration tests | `.venv/bin/python -m pytest tests/integration/` |
| End-to-end tests (start the app as a server) | `.venv/bin/python -m pytest tests/e2e/` |
| Tests against PostgreSQL (skipped without the variable) | `TEST_POSTGRES_URL=postgresql://user:password@host/dbname .venv/bin/python -m pytest` |
| All project checks | `bash scripts/test.sh` |
| Regenerate runtime lock (uv 0.13.5, generation only) | `uv pip compile requirements.in --python-version 3.12 --universal --generate-hashes --only-binary :all: -o requirements.txt` |
| Regenerate development lock (after runtime lock) | `uv pip compile requirements-dev.in --python-version 3.12 --universal --generate-hashes --only-binary :all: -o requirements-dev.txt` |
| Container runtime checks (after building) | `docker build -t payalign:local .` then `TEST_DOCKER_IMAGE=payalign:local .venv/bin/python -m pytest tests/e2e/test_docker_runtime.py` |
| Build image without cache | `docker compose build --no-cache api` |

Warning: PostgreSQL tests drop every table in the database pointed to by `TEST_POSTGRES_URL`. Use a throwaway database only; never use the Neon database used by Render.

Run tests outside the runtime container in the local `.venv` Python environment. Set up this environment with the dependencies from `requirements-dev.txt`, using `.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements-dev.txt`. `scripts/setup-python.sh` also selects the development lock when it exists. The Dockerfile explicitly copies `src/`, the runtime `requirements.txt` and LICENSE; it creates an empty data directory. `.dockerignore` also excludes local data, tests and process files from the build context.

The image runs as `payalign` (UID/GID 10001) and includes an empty, writable
`/app/data` directory. Compose retains the `./data:/app/data` bind mount, so host
ownership overrides the directory permissions in the image. After building,
run the ownership preparation command before starting Compose for the first
time or upgrading an existing root-owned database. Stop an existing API container
with `docker compose stop api` before preparing its storage. The one-time command
runs as root to assign the directory and existing database files to UID/GID 10001;
normal application startup uses the non-root image user.

Run the health check while the application is running. It should return HTTP 200 and `{"status":"ok"}`. This does not verify persistent data storage.

The release workflow runs the existing tests, builds and starts a Docker image for `linux/amd64` using an isolated in-memory database, and provides the verified image as `payalign-<Commit-ID>-linux-amd64.tar.gz`. The archive contains the image, not running containers or payroll data. After downloading it, load it with `docker load --input payalign-<Commit-ID>-linux-amd64.tar.gz`, replacing `<Commit-ID>` with the actual ID in the filename. The resulting image name is `payalign:<Commit-ID>`. This image is not native to ARM Macs; Docker requires support for running `linux/amd64` images.

Pushes of version tags matching `v*` publish the archive to a GitHub Release after successful checks. Manual runs only validate and store the archive as an Actions artifact by default. Manual publication requires explicitly selecting `publish_release` and running from a `v*` tag.

A published `v*` release calls the CD workflow after publication. When `CD_ENABLED=true`, `scripts/deploy.sh` calls the Render hook stored in `RENDER_DEPLOY_HOOK_URL` with `ref` set to the release commit, so Render builds that commit. A manual CD run from a branch (Actions → CD → Run workflow) calls the hook without `ref` and deploys the latest commit on Render's linked branch. Render builds its own image from source; it does not use the image archive published by the release workflow. `scripts/smoke-test.sh` checks that `/health` answers, but Render can serve the previous version during a new build, so this check shows availability rather than confirming the new version is live.

## Dependencies

* **Runtime:** Docker, Python 3.12 (`.python-version`, CI, the dev container and the container image)
* **Core Libraries:** FastAPI (Web Framework), SQLAlchemy (ORM), psycopg 3 (PostgreSQL driver), Pydantic (Validation)
* **Test Libraries:** pytest, httpx and packaging (build-input assertions)
* **Environment Variables:** `DATABASE_URL` (Required for infrastructure configuration). 
* Never commit `.env` credentials to version control.

`requirements.in` declares direct runtime dependencies; `requirements.txt` is the
generated runtime lock for Python 3.12, including transitive versions, platform
markers and artifact SHA-256 hashes. Docker and Render's Docker builds install this lock with hash
checking and wheels only, so source builds cannot fetch unpinned build tools.
`requirements-dev.in` includes those runtime declarations, constrains them to the
runtime lock, and adds the test libraries. `requirements-dev.txt` is the resulting
complete development lock. CI and release tests install it with hash checking and
wheels only. pytest and httpx are absent from the runtime image.
Hashes also enable pip's hash checking automatically
([pip hash-checking mode](https://pip.pypa.io/en/stable/topics/secure-installs/)).

Use uv 0.13.5 only to generate the lock; it is not an application dependency.
Edit direct requirements in the appropriate `.in` file, then regenerate the runtime
lock followed by the development lock.
Regeneration retains existing pins; add `--upgrade-package <name>` for a selected
update or `--upgrade` for a deliberate full refresh
([uv lock maintenance](https://docs.astral.sh/uv/pip/compile/)). Review the inputs and generated locks
and run the project and container checks after dependency changes.

The `Dockerfile` owns the Python base-image tag and multi-platform digest.
To update it, inspect the intended Python 3.12 tag with
`docker buildx imagetools inspect <tag>`, update the tag and digest together, and
repeat the image build and container checks. Pinning the digest keeps the base
fixed until this explicit update
([Docker digest pins](https://docs.docker.com/build/building/best-practices/#pin-base-image-versions)).
These pins fix dependency and base-image selection; they do not promise identical
image bytes across build tools or different target platforms. Render continues
to build from source using these inputs.

## Data conventions

* **`DATABASE_URL` format:** a SQLAlchemy URL, e.g. `sqlite:////app/data/payroll.db` (four slashes for an absolute path inside the container). It is required; there is no silent in-memory fallback. `sqlite` and `postgresql` URLs are accepted (for example `postgresql://user:password@host/dbname?sslmode=require`); any other scheme, including `postgres://`, fails at start-up.
* **Tables:** `employers`, `employees`, `employments`, `monthly_records`, `payslips`, `work_entries` and `payroll_snapshots`, one per core entity or persisted payroll run. `employments` stores integer `weekly_minutes` and `holiday_weeks` and a nullable `end_date`. `monthly_records` stores `employee_id` alongside `employment_id` and `employer_id`. The holiday balance is not stored on `employments`; it is derived from persisted runs ([ADR-004](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md)). `payroll_snapshots` stores the run snapshot ([ADR-004 Amendment 2](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-2-2026-10-20)).
* **Money type** ([ADR-003](adr/ADR-003-monetary-precision-and-rounding.md)): never a binary float. The APIs read amounts as `Decimal`, payroll calculation and `PayrollService` use `Decimal`, and the database stores integer centimes (columns suffixed `_cents`). Amounts become centimes once, before saving, rounding half-up and never truncating: in `PayrollService` for payroll, in `SqlAlchemySetupRepository` for setup. `cash_bonus` and `expense_reimbursements` are rounded half-up to CHF 0.01 once, on entry to `PayrollService`. Known exception in v0.1.0: setup's `Employment.hourly_wage` is still declared `float`. It holds the API's `Decimal` and is saved through `Decimal(str(...))`; `get_employment`, which only tests use, reads it back as centimes divided by 100, a `float`. Payroll does not use it: it reads the wage in centimes and calculates in `Decimal`.
* **`MonthlyRecord` fields:** `id`, `employment_id`, `employee_id`, `employer_id`, `month` (1-12), `year` (2026 only, the one year with a ruleset; ADR-002), `cash_bonus` and `expense_reimbursements` (stored as `_cents`). Hour totals are derived from persisted `work_entries`, not stored on `monthly_records`. A run names an `employment_id`; employer, employee and the employment terms are read from `employments` through the payroll port, and an unknown id is rejected before anything is saved (404).
* **Run sequence:** defined in [UC-002](specs/UC-002-Process-the-Monthly-Employment.md) (alternate flows). `PriorRun` carries `year` and `month`.
* **Time type** ([ADR-004 Amendment 1](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-1-2026-10-16)): whole minutes everywhere. `WorkEntry` carries a `category` and `paid_minutes`, plus optional `start_time`, `end_time` and `unpaid_break_minutes`; with times, `paid_minutes` is derived from them. `PayrollService` classifies and rejects entries as [UC-002](specs/UC-002-Process-the-Monthly-Employment.md) specifies (public holidays, overlaps, invalid category combinations); rejections are 400 responses. `work_entries` stores one row per submitted entry with its times and break; `payroll_snapshots` also keeps the `employment_start_date` and `employment_end_date`. The four categories ([ADR-004 Amendment 1](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-1-2026-10-16), item 6) are defined once in `src/app/domain/hour_categories.py` and mirrored by the `work_entries` CHECK constraint.
