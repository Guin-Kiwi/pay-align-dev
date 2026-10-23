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

## Next smallest step

`validate-uc002` (see Tasks).

## Tasks

One row per open task, under its owner. `After` lists the IDs that must be finished first,
and `By` is a deadline the team has agreed; leave either empty when it does not apply. Status
is `todo`, `doing` or `blocked`. Who adds and deletes rows is in `CONTRIBUTING.md`.
Feature freeze is Sat 24 October: fixes only from then.

### Ayla

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `project-endpoints` | todo | List the API endpoints in PROJECT.md (ADR-006 notes they are missing). | ADR-006 | | |
| `readme-template` | todo | Move the template text of the README to `docs/TEMPLATE.md`. | Capstone brief | | Sat 24 Oct |
| `payslip-response` | todo | Show the user the whole payslip. Today the 201 response of `POST /api/v1/monthly-payroll` has only `monthly_record_id`, `gross_wage` and `net_payout`, and no endpoint returns a payslip later, so the deductions are calculated and saved but never shown. Add to the response the employee deductions (`ahv_deduction`, `alv_deduction`, `nbu_deduction`, `tax_deduction`), the employer costs (`employer_ahv`, `employer_alv`, `employer_fak`, `employer_bu`, `admin_charge`, `total_employer_cost`) and the holiday balance after the month (`holiday_balance_minutes` of the run snapshot), with `PayslipResponse` as the response model instead of `dict`. Why: UC-002 promises a compliant payslip, and the Basel household NAV requires one with all deductions and the holiday balance. Done when UC-002 has an acceptance line for it and an API test checks every field. Aaron reviews. | UC-002 | | Sat 24 Oct |
| `db-choice` | todo | Decide which database the Render deployment uses, and record it in ADR-005. (a) SQLite: no code change; set `DATABASE_URL=sqlite:////tmp/payroll.db` on Render, because `data/` is not in the Docker image. The data is empty after every deploy and after every sleep of the free instance (15 minutes without visitors), so the demo starts empty. (b) Neon Postgres (neon.com, free, no credit card): the data stays, but it needs a Postgres driver in `requirements.txt`, `postgresql` in `SUPPORTED_BACKENDS`, the SQLite-only connection settings in `database.py` applied to SQLite only, a duplicate-month check in `sqlalchemy_payroll_repository.py` that also recognises the Postgres error, a test against Postgres and a PROJECT.md update. Someone signs up at Neon, and the connection URL goes into Render as a secret, never into a file. | ADR-005 | | Sat 24 Oct |

### Nano

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `decimal-wage` | todo | Make `Employment.hourly_wage` a `Decimal`, and remove the "Known exception" line in PROJECT.md in the same change. | ADR-003 | | |
| `setup-port` | todo | Decide whether `SetupRepository.get_employment` stays (only tests use it), then make the code and ADR-006 item 3 agree. | ADR-006 | | |
| `akbs-1890` | blocked | Ask AKBS (contact in `docs/reference/Employing_Household_Help_Basel.md`) about the monthly CHF 1,890: the AKBS page names it as a monthly limit, while Merkblatt 2.07 ties it to the pension-fund rule for jobs shorter than a year. Record the answer as a UC-002 decision, and as a constant if the app enforces it. | Merkblatt 2.07 | | |
| `demo-path` | todo | Prepare the demo of both use cases on the Render deployment. Proposed on 23 October 2026 (teammates who disagree say so before Sat 24 Oct): setup through the setup page (`/setup`, from `ui-merge`) and payroll through Swagger (`/docs`); no payroll page and no endpoint listing employments for v0.1.0. If the setup page is not merged, setup also goes through Swagger. Prepare the request bodies to paste (one setup, two or three payroll months) with made-up names and AHV numbers only, since anyone with the link can save data, and open the app two minutes before the demo so the free instance is awake. Done when the whole flow has run once on the Render URL. | Capstone brief | `payslip-response`, `deploy-render` | Wed 28 Oct |

### Aaron

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `dedupe-calc` | todo | Remove the duplicated functions in `payroll_calculation.py`. | calculations.md | `validate-uc002` | |
| `validate-uc002` | todo | Run the UC-002 saving slice through VALIDATE: confirm the golden payroll cases and the end-to-end API test on a clean checkout, then review the slice. | UC-002 | | |
| `min-wage-floor` | todo | Decide a minimum-wage floor by weekly hours (known limitation in UC-001). | UC-001 | | |

### Assvinth

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `arch-test` | todo | Make the layer check in `tests/unit/test_architecture.py` recognise `src.app` imports; it must fail on a deliberate inner-to-outer import and pass on `main`. | ADR-001 | | |
| `ui-merge` | doing | Finish the setup UI review and merge or close it. The UI branch also adds Node.js 22 to the PROJECT.md Commands and changes the devcontainer; CI and Release already install Node.js 22. | UC-001 | | Sat 24 Oct |
| `readme-final` | todo | Finish the README for the capstone. | Capstone brief | `readme-template`, `ui-merge` | Tue 27 Oct |
| `release-tag` | todo | Tag v0.1.0, which also exercises the tag-triggered release publication. | Capstone brief | `validate-uc002`, `readme-final` | Wed 28 Oct |
| `align-gating` | todo | Align `docs/INDEX.json` and `.github/CODEOWNERS` on which files are review-gated. | INDEX.json | | |

### Unassigned

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `deploy-render` | todo | Deploy the app to Render (capstone Task 2, steps 5 and 6). (1) One member signs up at render.com (free, no credit card), creates a web service from this repo with Docker on the free plan, turns auto-deploy off and sets `DATABASE_URL` as `db-choice` decides. (2) The repo owner adds Render's deploy hook URL as the GitHub secret `RENDER_DEPLOY_HOOK_URL`; it never goes into a file. (3) Add `scripts/deploy.sh`, which calls the hook, and `scripts/smoke-test.sh`, which waits until `/health` answers on the Render URL, then set the repository variable `CD_ENABLED=true`. (4) Proposed on 23 October 2026: deploy only on a release, not on every merged PR, so a half-finished merge cannot break the live app. `release.yml` calls `cd.yml` after a `v*` tag; before the first tag, a deploy is started by hand in the Actions tab. Both workflows need a code owner's approval. Render builds from the connected branch, not from the tag, so tag only when `main` is what should go live. (5) PROJECT.md says the app runs locally; add the Render URL. Done when `/health` answers on the Render URL. | Capstone brief | `db-choice` | Wed 28 Oct |
| `uc001-input-rules` | todo | Link UC-001's required fields to ADR-006 item 2 (input rules), with a human's approval; UC-001 is review-gated. | ADR-006 | | |
| `lifecycle-py` | todo | Decide whether `scripts/check-lifecycle.py` and `scripts/test-lifecycle.py` stay. BOOTSTRAP added them next to the template's `.sh` versions, which are the ones CI runs. | `.github/workflows/ci.yml` | | |

## Acceptance / validation cues

- Both use cases have an explicit component path through domain, application,
  interfaces, and infrastructure.
- Setup has ports for employer uniqueness and employment persistence, with
  foreign-key relationships preserved.
- Payroll has ports for employment lookup, cumulative annual gross checks, and
  atomic monthly record/payslip persistence.
- Invalid inputs and annual-limit breaches fail before persistence; success
  returns a confirmation after the transaction completes.
- The architecture remains consistent with ADR-001 through ADR-006 (see Evidence links).
- Evidence: the two use-case specifications, ADR-001 to ADR-006 and the tests
  under `tests/`.

## Validation approach

Each use case's tests are named in its Validation plan ([UC-001](specs/UC-001-Set-Up-an-Employment.md),
[UC-002](specs/UC-002-Process-the-Monthly-Employment.md)); trade-offs are in the ADR Consequences.

## Blockers / assumptions

- No architecture blocker found.
- Assumption: the first implementation slice uses HTTP delivery and a
  relational ORM adapter as described by `docs/PROJECT.md`.
- Human review remains required for the review-gated use-case specifications.

## Evidence links

- [UC-001 specification](specs/UC-001-Set-Up-an-Employment.md)
- [UC-002 specification](specs/UC-002-Process-the-Monthly-Employment.md)
- [ADR-001 Clean Architecture boundaries](adr/ADR-001-clean-architecture-boundaries.md)
- [ADR-002 Versioned AKBS payroll rules](adr/ADR-002-versioned-akbs-payroll-rules.md)
- [ADR-003 Monetary precision and rounding](adr/ADR-003-monetary-precision-and-rounding.md)
- [ADR-004 Payroll entry snapshots and holiday balance](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md)
- [ADR-005 SQLAlchemy persistence adapter](adr/ADR-005-sqlalchemy-persistence-adapter.md)
- [ADR-006 UC-001 setup API and wiring](adr/ADR-006-uc-001-setup-api-and-wiring.md)
- [PROJECT architecture](PROJECT.md)
- [Calculations: formulas](reference/calculations.md)
- [Constants: rates, limits and thresholds](../src/app/domain/constants.py)

Which file owns each kind of fact is under Collaboration in `AGENTS.md`; this file holds what
comes next.
