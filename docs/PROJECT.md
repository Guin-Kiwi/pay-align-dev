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

**Deployment & Data-store:** The application is a containerized full-stack web application that uses a relational database via an ORM. The code on `main` supports SQLite for local runs, Docker Compose and tests, and PostgreSQL on Neon for the Render deployment ([ADR-005 Amendment 1](adr/ADR-005-sqlalchemy-persistence-adapter.md#amendment-1-2026-10-23)). Render builds the `Dockerfile` from the release commit on a release, or from the latest commit on `main` on a manual deploy. Render's active database is selected by its `DATABASE_URL` environment variable, which points to the Neon database (a `postgresql://` URL, checked in the Render dashboard on 24 October 2026), so saved data no longer lives in the container's `/tmp`. Set the required `SESSION_SECRET_KEY` in Render's environment before deploying the account-enabled build, and keep `SESSION_COOKIE_SECURE=true` for Render's HTTPS URL (see Dependencies).

The first account-enabled deployment requires a new, empty database schema ([UC-003 scope](specs/UC-003-Employer-Accounts-and-Secure-Access.md#scope)). `create_all` creates missing tables but does not alter existing ones ([ADR-005](adr/ADR-005-sqlalchemy-persistence-adapter.md#consequences)); it cannot add `employers.account_id` or `employees.employer_id` to pre-account tables. Before deploying that build against the existing Neon database, the deployment owner must obtain authorization to drop the pre-account application tables and recreate them with the new schema; this deletes their saved employer and payroll data. No existing-data migration is provided.

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
  - [AKBS Household Employment Overview](https://ak-bs.ch/themen/beitraege/haushaltshilfen)
  - [Basel AWA NAV Legal Text](https://gesetzessammlung.bs.ch/app/de/texts_of_law/215.700)
- Secrets and real config values: never in the repository; `.env` locally

## Commands

Run all commands from the project directory. Docker must be available for Docker commands, and port 8000 must be free when starting the application.

| Activity | Command |
|---|---|
| Build Docker image | `docker compose build api` |
| Prepare SQLite bind-mount ownership (first run or upgrade from root) | `docker compose run --rm --no-deps --user root --entrypoint chown api -R 10001:10001 /app/data` |
| Start application | Set `SESSION_SECRET_KEY` in `.env` to a random value from `python -c "import secrets; print(secrets.token_urlsafe(32))"`, then run `docker compose up api` |
| Health check | `curl --fail --include http://localhost:8000/health` |
| Demo data (running app, empty local database; refuses non-local URLs) | `python3 scripts/seed_demo.py`, then log in as `demo@example.com` / `demo-pass1`: one employment up to date, one with months due |
| Unit tests | `.venv/bin/python -m pytest tests/unit/` |
| Integration tests | `.venv/bin/python -m pytest tests/integration/` |
| End-to-end tests (start the app as a server) | `.venv/bin/python -m pytest tests/e2e/` |
| Tests against PostgreSQL (skipped without the variable) | `TEST_POSTGRES_URL=postgresql://user:password@host/dbname .venv/bin/python -m pytest` |
| All project checks | `bash scripts/test.sh` |
| Regenerate runtime lock (uv 0.13.5, generation only) | `uv pip compile requirements.in --python-version 3.12 --universal --generate-hashes --only-binary :all: -o requirements.txt` |
| Regenerate development lock (after runtime lock) | `uv pip compile requirements-dev.in --python-version 3.12 --universal --generate-hashes --only-binary :all: -o requirements-dev.txt` |
| Container runtime and persistence checks (after building) | `docker build -t payalign:local .` then `TEST_DOCKER_IMAGE=payalign:local .venv/bin/python -m pytest tests/e2e/test_docker_runtime.py` |
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

The release workflow runs the existing tests, builds a Docker image for `linux/amd64`, and runs the container runtime and persistence checks against that image before providing it as `payalign-<Commit-ID>-linux-amd64.tar.gz`. The archive contains the image, not running containers or payroll data. After downloading it, load it with `docker load --input payalign-<Commit-ID>-linux-amd64.tar.gz`, replacing `<Commit-ID>` with the actual ID in the filename. The resulting image name is `payalign:<Commit-ID>`. This image is not native to ARM Macs; Docker requires support for running `linux/amd64` images.

The container checks verify the runtime file allowlist and absence of test
libraries, then register a made-up account and save setup data through the API
with a prepared, isolated SQLite bind mount. They remove the first container and
create a second one using the same storage. Both run as the image's non-root user
and must become healthy; the second must accept login to the saved account,
return its employer through the API and retain identical account, employer,
employee and employment database rows. Each container gets a freshly generated
test-only session secret and HTTP test cookies (`SESSION_COOKIE_SECURE=false`);
state-changing requests send CSRF tokens. The checks also verify that anonymous
employer reads and setup without a CSRF token are rejected, and that logout ends
the current session. Failures print container logs.
The checks remove their containers and test storage on success and failure;
they use neither the Compose database nor any deployment database. The release
step runs these checks from the host's development environment, with a five-minute
timeout; pytest and httpx remain outside the runtime image.

Pushes of version tags matching `v*` publish the archive to a GitHub Release after successful checks. Manual runs only validate and store the archive as an Actions artifact by default. Manual publication requires explicitly selecting `publish_release` and running from a `v*` tag.

A published `v*` release calls the CD workflow after publication. When `CD_ENABLED=true`, `scripts/deploy.sh` calls the Render hook stored in `RENDER_DEPLOY_HOOK_URL` with `ref` set to the release commit, so Render builds that commit. A manual CD run from a branch (Actions → CD → Run workflow) calls the hook without `ref` and deploys the latest commit on Render's linked branch. Render builds its own image from source; it does not use the image archive published by the release workflow. `scripts/smoke-test.sh` checks that `/health` answers, but Render can serve the previous version during a new build, so this check shows availability rather than confirming the new version is live.

## Dependencies

* **Runtime:** Docker, Python 3.12 (`.python-version`, CI, the dev container and the container image)
* **UI test prerequisite:** Node.js 22 runs the browser JavaScript regression harnesses; it is installed by the dev container, CI and release workflows.
* **Core Libraries:** FastAPI (Web Framework), SQLAlchemy (ORM), psycopg 3 (PostgreSQL driver), Pydantic (Validation), pwdlib with Argon2 (password hashing), itsdangerous (Starlette signed sessions)
* **Test Libraries:** pytest, httpx and packaging (build-input assertions)
* **Environment Variables:** `DATABASE_URL` (required for infrastructure configuration), `SESSION_SECRET_KEY` (required, random secret of at least 32 characters), `SESSION_COOKIE_SECURE` (set to `true` when serving over HTTPS; Docker Compose defaults it to `false` for local HTTP development).
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
* **Tables:** `accounts`, `employers`, `employees`, `employments`, `monthly_records`, `payslips`, `work_entries` and `payroll_snapshots`, one per core entity or persisted payroll run. `accounts` stores normalized login email, adaptive password hash and account first/last name; it does not store passwords. Each `employers` row has one unique `account_id`; employer AHV numbers are not globally unique, and matching AHV numbers never share a profile across accounts ([UC-003 Amendment 5](specs/UC-003-Employer-Accounts-and-Secure-Access.md#amendment-5--2026-10-24-account-isolation-corrections)). Each `employees` row belongs to an employer, with AHV unique within that employer; an employment links an employee of the same employer. `employments` stores integer `weekly_minutes` and `holiday_weeks` and a nullable `end_date`. `monthly_records` stores `employee_id` alongside `employment_id` and `employer_id`. The holiday balance is not stored on `employments`; it is derived from persisted runs ([ADR-004](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md)). `payroll_snapshots` stores the run snapshot ([ADR-004 Amendment 2](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-2-2026-10-20)).

Authentication endpoints are under `/api/v1/auth`: `GET /csrf` issues a CSRF token; `POST /register`, `POST /login` and `POST /logout` change authentication state; `GET /me` returns the current account. Registration and login create a four-hour signed session cookie containing only the account ID. The cookie is HttpOnly and SameSite=Lax; configure `SESSION_COOKIE_SECURE=true` over HTTPS. Registration and login return the rotated CSRF cookie value as `csrf_token` alongside the account fields in JSON; the client sends it in `X-CSRF-Token` on subsequent state-changing requests. Registration password validation is defined in [UC-003 Amendment 4](specs/UC-003-Employer-Accounts-and-Secure-Access.md#amendment-4--2026-10-24-registration-policy-and-csrf-token-return). Session limits and known copied-cookie behavior are recorded in [ADR-007](adr/ADR-007-employer-accounts-and-secure-access.md).

The `/login` page is view 0 of [UC-003 Amendment 3](specs/UC-003-Employer-Accounts-and-Secure-Access.md#amendment-3--2026-10-23-minimum-browser-views). It is static HTML, CSS and JavaScript under `src/app/interfaces/static/` (`login.html`, `login.js`, `login.css`) and calls the endpoints above; `login.css` adds to `base.css`, which loads first. The script checks `GET /api/v1/auth/me` first. Logging in, or creating an account in the sign-up dialog, fetches a fresh token from `GET /api/v1/auth/csrf` and sends it in `X-CSRF-Token` to `/api/v1/auth/login` or `/api/v1/auth/register`. Whenever the page knows the account (after either of those, or on opening `/login` already signed in) it asks `GET /api/v1/employer`, which answers only for the employer linked to the signed-in account (one employer per account, taken from the session), and replaces the page: both an existing employer and a 404 "No employer is set up yet." open `/home`; any other answer stops with a message asking for a reload. An employer that belongs to another account never counts. The redirects replace the history entry, so Back does not return to `/login`. If the employer lookup fails while the sign-up dialog is open, the reload message appears both inside the dialog and in `#account-error`, where it remains visible after the dialog closes. The sign-up dialog always lists the three registration password requirements under the password field and turns each green as the typed password meets it. When the user leaves a non-empty field, the page flags a malformed email (on both forms) or an unmet password requirement with a red outline; email notes use reserved space, so nothing moves. Empty required fields get a red outline and note only on form submission, which checks every field at once. The page holds its own copy of the email pattern and the password rules; tests tie the minimum length to `MIN_PASSWORD_LENGTH` and compare both copies with the real registration API, and the server stays the authority (its message is shown if it rejects what the page accepted). The login form never applies the password policy. Arriving at `/login#signup` opens the sign-up dialog.

`/home` is the authenticated browser home. Its header selects the payroll month;
the household strip shows the wage limit and selected-month costs. The left column
hosts the employment and month-entry workspace, which does not render payslips; the right column
shows per-employment tasks. The Timesheets and Employees pages remain available
from the shared navigation. [UC-004](specs/UC-004-UI-AND-USER-FLOW.md) owns the
browser journey and presentation; the navigation decisions are in
[UC-003 Amendment 6](specs/UC-003-Employer-Accounts-and-Secure-Access.md#amendment-6--2026-10-27-minimum-browser-navigation),
[Amendment 11](specs/UC-003-Employer-Accounts-and-Secure-Access.md#amendment-11--2026-10-27-welcome-page-employer-setup-and-payslip-handoff),
and [Amendment 12](specs/UC-003-Employer-Accounts-and-Secure-Access.md#amendment-12--2026-10-28-browser-page-url-cleanup-issue-55). The pages use shared JavaScript helpers and
rules supplied by `constants.py`; the employment workspace retains its own scoped
handlers so its form controls do not conflict with Home.

The authenticated `/employees` page lists every employee, one bound box per person
([UC-004](specs/UC-004-UI-AND-USER-FLOW.md)). Two boxes sit on the left: the
agreement (each employment's wage, weekly hours and holiday weeks, a month picker with
View payslip, and an Employee details button that opens a dialog loaded only when asked)
and To do (the months to enter, each with an Enter button to `/timesheets`). A larger box
on the right shows the year so far: pay, employer cost with its contributions, hours and
leave, and the wage limit used and remaining for that person; the household's is on Home. It reads
`GET /api/v1/employees`, which composes the existing month-history and saved-payslip reads and the
gross-to-date sums that UC-002 uses for the limit check
([UC-003 Amendment 10](specs/UC-003-Employer-Accounts-and-Secure-Access.md#amendment-10--2026-10-27-employee-overview-and-details-reads)); it adds no payroll
rule.

The authenticated `/payslips` page is the saved-payslip view and the only payslip renderer. It lets the employer select an
employment and completed month, read the saved payroll detail, and use the browser's print or
save-as-PDF dialog. It uses the existing employer, employment, month-history and
saved-month reads, including the employee AHV number from the account-scoped
employment detail. It opens the latest saved month across employments by default, or the latest for a selected employment. When the selected employment has a next month to enter, an Enter timesheet button
opens `/timesheets` for it. A direct link can preselect a saved month using
`/payslips?employment_id=ID&year=YYYY&month=M`; the server still checks ownership.
Home, Timesheets and the Employees page link to selected saved months there. After a successful save, the Home workspace stores `{url, message}` in `sessionStorage` under `payalign-saved-confirmation` and opens that month's `/payslips` URL; `/payslips` shows the message once when `url` matches the page's address and then removes it. If the saved-month read then fails, the message stays visible and the page's retry reads the month again without submitting the payroll.

The current HTTP endpoints are:

| Method and path | Purpose |
|---|---|
| `GET /` | Serve the public welcome page with login and sign-up links. |
| `GET /health` | Health check. |
| `GET /login` | Browser page to log in or create an account. |
| `GET /employment-setup` | Serve employment setup; redirect to login if unauthenticated or home if no employer profile exists. |
| `GET /account-details` | Serve the authenticated employer profile form. |
| `GET /employees` | Serve the authenticated Employees page, one box per person; unauthenticated browsers are redirected to `/login`. |
| `GET /timesheets` | Serve the authenticated Timesheets page: the landing, or with `?employment_id=ID` that employment's entry page; unauthenticated browsers are redirected to `/login`. |
| `GET /payslips` | Serve the authenticated saved-payslip view; unauthenticated browsers are redirected to `/login`. |
| `GET /home` | Serve the authenticated Home page (the Household overview with Add employment and Account details, the Cost overview, and the Task overview); unauthenticated browsers are redirected to `/login`. |
| `GET /setup-assets/constants.js` | Serve, without a session, the rules the pages use (rules year and its dates, minimum password length, minimum and maximum hourly wage, allowed holiday weeks), generated from `src/app/domain/constants.py` on each request. |
| `GET /setup-assets/*` | Serve static CSS and JavaScript assets with `Cache-Control: no-cache` and an ETag for browser revalidation. |
| `GET /api/v1/auth/csrf` | Issue a CSRF token. |
| `POST /api/v1/auth/register` | Register an account and start its session. |
| `POST /api/v1/auth/login` | Start an account session. |
| `GET /api/v1/auth/me` | Read the signed-in account. |
| `POST /api/v1/auth/logout` | End the account session. |
| `GET /api/v1/employer` | Read the signed-in account's employer profile. |
| `POST /api/v1/employer` | Create the signed-in account's employer profile. |
| `PUT /api/v1/employer` | Update the signed-in account's employer profile. |
| `GET /api/v1/payroll-overview?year=YYYY&month=M` | Summarize saved payroll for the selected month and account. |
| `POST /api/v1/setup` | Create an employer profile and first employment, or add an employment under the signed-in employer. |
| `GET /api/v1/public-holidays?year=YYYY` | Return the configured rules-year public holidays to a signed-in account. |
| `GET /api/v1/public-holidays/{year}` | Path form of the route above for the same calendar; returns `{year, dates}`. |
| `GET /api/v1/employees` | One overview per person of the signed-in account's employer: their employments with terms, saved months, next month and months due; the year's totals; the stored holiday balance; and the wage limit used and remaining, with the household's. Never another account's people. |
| `GET /api/v1/employees/{employee_id}` | Read one person's address, AHV number, nationality and tax status, on request only; an absent id and another account's id both answer 404. |
| `GET /api/v1/employments` | List the signed-in employer's employments. |
| `GET /api/v1/employments/{employment_id}` | Read one owned employment's summary. |
| `GET /api/v1/employments/{employment_id}/months` | List saved months and the next eligible 2026 month. |
| `GET /api/v1/employments/{employment_id}/months/{year}/{month}` | Read an owned month's saved payslip, holiday balance, bonus and reimbursements, and the run's hourly rate and four hour-category totals for the payslip view ([UC-003 Amendment 7](specs/UC-003-Employer-Accounts-and-Secure-Access.md#amendment-7--2026-10-26-payslip-view-design)). |
| `POST /api/v1/monthly-payroll` | Save the next monthly run and return its saved payslip detail and confirmation message. |

Employment and month reads require a session and return 404 for absent or other-account records. `PayrollService.process_monthly_payroll` and the payroll port's `employment_terms` require an account ID; neither provides an unscoped fallback. Completed months have no update or delete endpoint; the scope decision is in [UC-003 Amendment 3](specs/UC-003-Employer-Accounts-and-Secure-Access.md#amendment-3--2026-10-23-minimum-browser-views).

FastAPI also provides Swagger UI at `/docs`, ReDoc at `/redoc` and the OpenAPI
schema at `/openapi.json`. Setup behavior is defined in [ADR-006](adr/ADR-006-uc-001-setup-api-and-wiring.md#decision);
monthly payroll behavior is defined in [UC-002](specs/UC-002-Process-the-Monthly-Employment.md).

* **Money type** ([ADR-003](adr/ADR-003-monetary-precision-and-rounding.md)): never a binary float. The APIs read amounts as `Decimal`, payroll calculation and `PayrollService` use `Decimal`, and the database stores integer centimes (columns suffixed `_cents`). Amounts become centimes once, before saving, rounding half-up and never truncating: in `PayrollService` for payroll, in `SqlAlchemySetupRepository` for setup. `cash_bonus` and `expense_reimbursements` are rounded half-up to CHF 0.01 once, on entry to `PayrollService`. Known exception in v0.1.0: setup's `Employment.hourly_wage` is still declared `float`. It holds the API's `Decimal` and is saved through `Decimal(str(...))`; `get_employment`, which only tests use, reads it back as centimes divided by 100, a `float`. Payroll does not use it: it reads the wage in centimes and calculates in `Decimal`.
* **`MonthlyRecord` fields:** `id`, `employment_id`, `employee_id`, `employer_id`, `month` (1-12), `year` (2026 only, the one year with a ruleset; ADR-002), `cash_bonus` and `expense_reimbursements` (stored as `_cents`). Hour totals are derived from persisted `work_entries`, not stored on `monthly_records`. A run names an `employment_id`; employer, employee and the employment terms are read from `employments` through the payroll port, and an unknown id is rejected before anything is saved (404).
* **Run sequence:** defined in [UC-002](specs/UC-002-Process-the-Monthly-Employment.md) (alternate flows). `PriorRun` carries `year` and `month`.
* **Time type** ([ADR-004 Amendment 1](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-1-2026-10-16)): whole minutes everywhere. `WorkEntry` carries a `category` and `paid_minutes`, plus optional `start_time`, `end_time` and `unpaid_break_minutes`; with times, `paid_minutes` is derived from them. `PayrollService` classifies and rejects entries as [UC-002](specs/UC-002-Process-the-Monthly-Employment.md) specifies (public holidays, overlaps, invalid category combinations); rejections are 400 responses. `work_entries` stores one row per submitted entry with its times and break; `payroll_snapshots` also keeps the `employment_start_date` and `employment_end_date`. The four categories ([ADR-004 Amendment 1](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-1-2026-10-16), item 6) are defined once in `src/app/domain/hour_categories.py` and mirrored by the `work_entries` CHECK constraint.
