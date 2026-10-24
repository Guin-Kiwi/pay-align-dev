# TASKS.md

PHASE: 3
STATUS: in-progress

(0=Bootstrap | 1=Specify | 2=Design | 3=Develop | 4=Validate | 5=Deploy)

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0 — Bootstrap | Done | Project foundation and development tooling established. |
| 1 — Specify | Done | UC-003 Amendment 2 specifies session and CSRF behavior; ADR-007 Amendment 1 selects Starlette `SessionMiddleware` and links to the owning requirements. |
| 2 — Design | Done | UC-003 Amendment 3 defines the five view boundaries for application logic. Presentation details remain with the UI implementation task. ADR-007 already sets the account-scoped read boundary; no new domain rule or ADR is needed. |
| 3 — Develop | In progress | UC-003 account-scoped logic and backend slices are complete and locally verified; the browser UI slice remains open. Existing payroll validation work remains tracked under its own tasks. Existing payroll calculation, persistent payroll saving and payroll-router database wiring are implemented; that slice goes through VALIDATE next. |
| 4 — Validate | In progress alongside development | Golden payroll tests, CI and Docker/release validation are underway. |
| 5 — Deploy | Not started | Release readiness has not yet been established. |

Phase status records verified phase outputs, not final UC-003 acceptance. UC-003 acceptance is pending until the reviewed PR is merged to `main` and its checks are confirmed there.

## Active objective

Specify and deliver employer accounts, login and employer-scoped access for PayAlign through the repository lifecycle.

## Current Use Case

docs/specs/UC-003-Employer-Accounts-and-Secure-Access.md

## Next smallest step

Request human review of the UC-003 authentication, ownership and release
configuration corrections, and confirm the team's decision on including UC-003
in the release. The corrected authentication and ownership contracts are in
[UC-003 Amendments 4 and 5](specs/UC-003-Employer-Accounts-and-Secure-Access.md#amendment-4--2026-10-24-registration-policy-and-csrf-token-return).
The release workflow supplies its own test-only session secret; Render still
needs the deployment configuration documented in [PROJECT.md](PROJECT.md#architecture).
Container hardening remains separate. These corrections do not complete the
browser UI or accept UC-003.

Assign the `uc003-ui` task, test the browser journey across the five UC-003 view boundaries, then connect it to the account-scoped setup, employment, month and payroll interfaces. Completed months remain view-only.

UC-003 TDD slices:
1. Account persistence, password hashing, registration/login/logout and four-hour session; tests-only RED checkpoint is committed and the implementation passes focused tests.
2. Employer-to-account onboarding, authenticated setup ownership and CSRF on setup/payroll writes; tests-only RED checkpoint committed (6 failing), implementation passes focused and full project checks.
3. Employer-scoped employee identity and payroll access; tests-only RED checkpoint committed (one failing), implementation passes focused and full project checks.
4. Account-scoped employment list/detail, month-history and saved-payslip reads for the five views; tests-only RED checkpoint committed (2 failing), implementation passes focused and full project checks.
5. Browser views defined by UC-003 Amendment 3; the UI owner chooses presentation and navigation details, adds failing end-to-end coverage, then implements. Completed months are view-only. The owning use cases exclude employment changes/endings and completed-month corrections; no update or delete work is implied by these views.
6. Run the full project validation after all slices; record results in the validation commit and PR evidence.
7. After the reviewed UC-003 PR is merged to `main`, confirm its checks on `main` and record UC-003 acceptance. Passing local or PR checks alone does not accept the use case.

## Tasks

One row per open task, under its owner. `After` lists the IDs that must be finished first,
and `By` is a deadline the team has agreed; leave either empty when it does not apply. Status
is `todo`, `doing` or `blocked`. Who adds and deletes rows is in `CONTRIBUTING.md`.
Feature freeze is Sat 24 October: fixes only from then.

### Ayla

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `readme-template` | todo | Move the template text of the README to `docs/TEMPLATE.md`. | Capstone brief | | Sat 24 Oct |
| `payslip-response` | todo | Return the whole payslip directly from `POST /api/v1/monthly-payroll`. Its 201 response still has only `monthly_record_id`, `gross_wage` and `net_payout`; the new account-scoped `GET /api/v1/employments/{employment_id}/months/{year}/{month}` can retrieve the saved deductions, employer costs and holiday balance afterward. Add those fields to the 201 response with `PayslipResponse` as the response model instead of `dict`. Why: UC-002 promises a compliant payslip, and the Basel household NAV requires one with all deductions and the holiday balance. Done when UC-002 has an acceptance line for it and an API test checks every field. Aaron reviews. | UC-002 | | Sat 24 Oct |
| `limit-message` | todo | When a monthly run exceeds an annual limit, the 400 message says only "Employee annual gross wage limit (CHF 22680) exceeded." (or the employer one, CHF 60480). Make it say what that means for the employer: the simplified procedure no longer applies, and the employer has to contact AKBS about the ordinary procedure, which this app does not support. Change the two messages in `payroll_calculation.py`, say in UC-002 what the warning tells the employer, and check the text in a test (no test checks it today). Aaron reviews. | UC-002 | | Wed 28 Oct |

### Nano

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `demo-path` | todo | Prepare the demo of both use cases on the Render deployment using the five-view browser flow in UC-003 Amendment 3. The earlier Swagger-only payroll and no-list proposal is superseded. Use made-up names and AHV numbers only; open the free instance before the demo. Done when the whole flow has run once on the Render URL. | Capstone brief, UC-003 | `uc003-ui`, `deploy-render` | Wed 28 Oct |
| `deploy-render` | doing | Deploy the app to Render (capstone Task 2, steps 5 and 6). Done: the free Render web service `pay-align-dev` builds the `Dockerfile` from `main` with auto-deploy off and `DATABASE_URL=sqlite:////tmp/payroll.db`, and setup and payroll work at https://pay-align-dev.onrender.com/docs. Left: (1) Ayla has added Render's deploy hook as the GitHub secret `RENDER_DEPLOY_HOOK_URL` (her statement; a secret cannot be checked in the repository) and sets the repository variable `CD_ENABLED=true` once the CD change is merged. (2) Merge the CD change: `scripts/deploy.sh` calls the hook, `scripts/smoke-test.sh` waits until `/health` answers, and `release.yml` calls `cd.yml` after a `v*` tag. Proposed on 23 October 2026: deploy only on a release, not on every merged PR, so a half-finished merge cannot break the live app. Once the PostgreSQL code has been deployed to Render by a release or a manual CD run (not merely merged), Nano first checks in the Render dashboard that the live commit is the commit that merged the PostgreSQL code; the smoke test only confirms that the app answers. Then Nano switches Render's `DATABASE_URL` to the Neon connection URL Ayla passes to him privately. Switching earlier restarts the old SQLite-only build with a PostgreSQL URL, and the app does not start ([ADR-005 Amendment 1](adr/ADR-005-sqlalchemy-persistence-adapter.md#amendment-1-2026-10-23)). Done when a CD run has deployed and its smoke test passed. | Capstone brief | | Wed 28 Oct |

### Aaron

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `dedupe-calc` | todo | Remove the duplicated functions in `payroll_calculation.py`. | calculations.md | `validate-uc002` | |
| `validate-uc002` | todo | Run the UC-002 saving slice through VALIDATE: confirm the golden payroll cases and the end-to-end API test on a clean checkout, then review the slice. | UC-002 | | Mon 26 Oct |
| `uc003-payroll-review` | todo | Review the UC-003 PR's payroll boundary before merge: check that setup and monthly writes, employment/month reads and saved payslips stay within the signed-in employer; foreign IDs reveal no records, and completed months remain view-only. Report findings in the PR. | UC-003, ADR-007 | | |

### Assvinth

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `arch-test` | todo | Make the layer check in `tests/unit/test_architecture.py` recognise `src.app` imports; it must fail on a deliberate inner-to-outer import and pass on `main`. An extended check exists separately and is not integrated into `main`; it was validated against an earlier payroll router, so re-validate it against the current wiring before reporting it passing. | ADR-001 | | |
| `ui-merge` | doing | Finish the setup UI review and merge or close it. Before merging, change two lines in `setup.html`: (1) delete "Employee tax status defaults to ordinary taxation.", because the simplified procedure takes 5% source tax from every employee, which is what payroll does; (2) extend the wage note with the known limitation of UC-001, for example: "Minimum CHF 22.20 per hour, with at most two decimal places. From 5 hours a week, the NAV Hauswirtschaft minimum applies instead (CHF 20.35, or 22.30 with 4 years' experience or EBA, or 24.55 with EFZ); this version accepts only CHF 22.20 or more and does not check the NAV category." Assvinth reported manual Safari checks (page load, saving, employer lookup after reload, invalid weekly hours, keyboard focus, a narrow window); they are unverified, and are not browser automation, a screenreader audit, a device test or proof of persistence across restarts. The UI branch also adds Node.js 22 to the PROJECT.md Commands and changes the devcontainer; CI and Release already install Node.js 22. | UC-001 | | Sat 24 Oct |
| `readme-final` | todo | Finish the README for the capstone, with a diagram of the four layers and the main components (the grading criteria ask for a clear architecture presentation; PROJECT.md describes the layers only in text). | Capstone brief | `readme-template`, `ui-merge` | Tue 27 Oct |
| `release-tag` | todo | Tag v0.1.0, which also exercises the tag-triggered release publication. | Capstone brief | `validate-uc002`, `readme-final` | Wed 28 Oct |
| `align-gating` | todo | Align `docs/INDEX.json` and `.github/CODEOWNERS` on which files are review-gated. | INDEX.json | | |
| `docker-312` | todo | Change the `Dockerfile` from `python:3.11-slim` to `python:3.12-slim`, so the image that runs on Render uses the same Python as CI and the tests. The release check tests only `/health` in the container, so a difference between 3.11 and 3.12 would show up only live. Update the Runtime line in PROJECT.md in the same change. | PROJECT.md | | Wed 28 Oct |
| `docker-nonroot` | todo | The container runs as root. Add a non-root user to the `Dockerfile`, make `/app/data` writable by it, and remove the TODO comment at the top of the `Dockerfile` in the same change. Check with the release check that `/health` still answers and that setup saves to the database. | `AGENTS.md` (least privilege) | `docker-312` | |

### Unassigned

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `uc003-ui` | todo | Assign an owner to choose presentation and navigation for the five UC-003 Amendment 3 views, coordinating with the existing setup UI work. Build against the account-scoped read and write contracts; end-to-end tests cover registration/login, first and later setup, employment selection, month entry, completed-month/payslip viewing and two-account isolation. Completed months can be viewed but not changed or deleted. Employment changes/endings and completed-month corrections remain outside UC-001/UC-002. | UC-003 Amendment 3, UC-001, UC-002 | `ui-merge` | |
| `uc003-acceptance` | todo | After the reviewed UC-003 PR merges to `main`, confirm the merged implementation and required checks on `main`; only then record use-case acceptance and remove this task. ADR-007 decision approval is separate from use-case acceptance. | UC-003, human direction 2026-10-23 | `uc003-ui` | |
| `uc001-input-rules` | todo | Link UC-001's required fields to ADR-006 item 2 (input rules), with a human's approval; UC-001 is review-gated. | ADR-006 | | |
| `lifecycle-py` | todo | Decide whether `scripts/check-lifecycle.py` and `scripts/test-lifecycle.py` stay. BOOTSTRAP added them next to the template's `.sh` versions, which are the ones CI runs. | `.github/workflows/ci.yml` | | |

## Acceptance / validation cues

These cues guide review and validation. UC-003 acceptance is recorded only after its reviewed PR is merged to `main` and the merged result is checked there; branch-local results are evidence for the PR, not final acceptance.

- Both use cases have an explicit component path through domain, application,
  interfaces, and infrastructure.
- Setup has ports for employer uniqueness and employment persistence, with
  foreign-key relationships preserved.
- Payroll has ports for employment lookup, cumulative annual gross checks, and
  atomic monthly record/payslip persistence.
- Invalid inputs and annual-limit breaches fail before persistence; success
  returns a confirmation after the transaction completes.
- The architecture remains consistent with ADR-001 through ADR-007 (see Evidence links); UC-003's architecture is recorded in ADR-007.
- Previously tracked design acceptance cue: the architecture remains consistent with ADR-001 through ADR-006; UC-003's architecture will be recorded during DESIGN. This cue is now satisfied by ADR-007.
- UC-003 records account registration, browser-isolated identity, employer ownership and the initial empty-database assumption.
- Branch-local tests verify authenticated setup/payroll writes, account-scoped employment and month reads, and view-only completed payslips. The browser journey remains under `uc003-ui`; UC-003 acceptance remains pending merge to `main`.
- Evidence: the three use-case specifications, ADR-001 to ADR-006 and the tests
  under `tests/`.
- Additional UC-003 design evidence: ADR-007 and UC-003 Amendment 1.

## Validation approach

Each use case's tests are named in its Validation plan ([UC-001](specs/UC-001-Set-Up-an-Employment.md),
[UC-002](specs/UC-002-Process-the-Monthly-Employment.md), [UC-003](specs/UC-003-Employer-Accounts-and-Secure-Access.md)); trade-offs are in the ADR Consequences.

## Blockers / assumptions

- ADR-007 was accepted on 23 October 2026. The browser UI feasibility check was deferred to implementation review.
- Assumption: the first implementation slice uses HTTP delivery and a
  relational ORM adapter as described by `docs/PROJECT.md`.
- Human review remains required for the review-gated use-case specifications.

## Evidence links

- [UC-001 specification](specs/UC-001-Set-Up-an-Employment.md)
- [UC-002 specification](specs/UC-002-Process-the-Monthly-Employment.md)
- [UC-003 specification](specs/UC-003-Employer-Accounts-and-Secure-Access.md)
- [ADR-001 Clean Architecture boundaries](adr/ADR-001-clean-architecture-boundaries.md)
- [ADR-002 Versioned AKBS payroll rules](adr/ADR-002-versioned-akbs-payroll-rules.md)
- [ADR-003 Monetary precision and rounding](adr/ADR-003-monetary-precision-and-rounding.md)
- [ADR-004 Payroll entry snapshots and holiday balance](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md)
- [ADR-005 SQLAlchemy persistence adapter](adr/ADR-005-sqlalchemy-persistence-adapter.md)
- [ADR-006 UC-001 setup API and wiring](adr/ADR-006-uc-001-setup-api-and-wiring.md)
- [ADR-007 employer accounts and secure access](adr/ADR-007-employer-accounts-and-secure-access.md)
- [PROJECT architecture](PROJECT.md)
- [Calculations: formulas](reference/calculations.md)
- [Constants: rates, limits and thresholds](../src/app/domain/constants.py)

Which file owns each kind of fact is under Collaboration in `AGENTS.md`; this file holds what
comes next.
