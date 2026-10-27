# TASKS.md

PHASE: 4
STATUS: in-progress

(0=Bootstrap | 1=Specify | 2=Design | 3=Develop | 4=Validate | 5=Deploy)

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0 — Bootstrap | Done | Project foundation and development tooling established. |
| 1 — Specify | Done | UC-003 Amendment 2 specifies session and CSRF behaviour; ADR-007 Amendment 1 selects Starlette `SessionMiddleware` and links to the owning requirements. |
| 2 — Design | Done | UC-003 Amendment 3 defines the five view boundaries for application logic. Presentation and navigation stay with the UI owner. ADR-007 sets the account-scoped read boundary; no new domain rule or ADR is needed. |
| 3 — Develop | Done | PR #50 review changes implement a reviewed whole-month submission, expose the backend-owned 2026 public-holiday dates through a narrow authenticated read endpoint, and simplify setup success navigation. Focused tests, the full suite and a local Chrome journey pass. |
| 4 — Validate | In progress alongside development | UC-002 was re-validated after the account backend merged. The open gap and the partly covered criterion are in the [UC-002 Validation plan](specs/UC-002-Process-the-Monthly-Employment.md). |
| 5 — Deploy | In progress | CD deploys to Render. On 24 October 2026 the first manual CD run started the deploy and passed its smoke test. A `v*` release deploys its own commit; that path runs first with `release-tag`. |

## Active objective

Deliver the rest of the UC-003 browser flow, so that a new account gets from registration to a saved payslip without Swagger, in time for the demo on Wed 28 October and submission on Thu 29 October.

## Current Use Case

docs/specs/UC-003-Employer-Accounts-and-Secure-Access.md

## Next smallest step

Obtain Ayla's review of the narrow holiday-calendar endpoint and the whole-month browser revision recorded in proposed UC-003 Amendment 6, then exercise the flow on the demo environment under `demo-path`. Completed months remain view-only. The owning use cases exclude employment changes or endings and completed-month corrections, so no persisted update or delete work is implied by these views.

## Tasks

One row per open task, under its owner. `After` lists the IDs that must be finished first,
and `By` is a deadline the team has agreed; leave either empty when it does not apply. Status
is `todo`, `doing` or `blocked`. Who adds and deletes rows is in `CONTRIBUTING.md`.

The feature freeze (Sat 24 October) is a guide, not a hard stop: from then, prefer fixes and
the work the demo needs. Every open row below is agreed work. Do not refuse or defer a row
because of the freeze; if a row looks too risky to finish in time, say why and ask its owner.

Until submission on Thu 29 October, every task has a named owner. If you can't finish one of
yours, hand it to a named teammate rather than moving it to Unassigned.

### Ayla

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `limit-message` | todo | When a monthly run exceeds an annual limit, the 400 message says only "Employee annual gross wage limit (CHF 22680) exceeded." (or the employer one, CHF 60480). Make it say what that means for the employer: the simplified procedure no longer applies, and the employer has to contact AKBS about the ordinary procedure, which this app does not support. Change the two messages in `payroll_calculation.py`, say in UC-002 what the warning tells the employer, and check the text in a test (no test checks it today). Aaron reviews. | UC-002 | | Wed 28 Oct |

### Nano

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `demo-path` | todo | Prepare the demo of all three use cases on the Render deployment, through the browser flow in UC-003 Amendment 3. Use made-up names and AHV numbers only; open the free instance before the demo. Done when the whole flow has run once on the Render URL. | Capstone brief, UC-003 | `uc003-ui`, `payslip-response` | Wed 28 Oct |
| `uc001-input-rules` | todo | Link UC-001's required fields to ADR-006 item 2 (input rules), with a human's approval; UC-001 is review-gated. | ADR-006 | | |

### Aaron

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `payslip-response` | todo | Return the whole payslip directly from `POST /api/v1/monthly-payroll`. Its 201 response has only `monthly_record_id`, `gross_wage` and `net_payout`. Add the employee deductions (`ahv_deduction`, `alv_deduction`, `nbu_deduction`, `tax_deduction`), the employer costs (`employer_ahv`, `employer_alv`, `employer_fak`, `employer_bu`, `admin_charge`, `total_employer_cost`), the holiday balance after the month (`holiday_balance_minutes` of the run snapshot) and a `message` confirming the month was saved, with `PayslipResponse` as the response model instead of `dict`. This closes the confirmation-message gap in the UC-002 Validation plan on the API side; the UI shows it. Why: UC-002 promises a compliant payslip, and the Basel household NAV requires all deductions and the holiday balance. Done when UC-002 has an acceptance line for it and an API test checks every field. Aaron sets the date, before Wed 28 Oct, because `demo-path` waits on it. Ayla reviews. | UC-002 | | |
| `payslip-pdf` | todo | Decide whether v0.1.0 includes a printable or PDF payslip. If it does, write its spec first, then build it. | UC-002 | `payslip-response` | |
| `dedupe-calc` | todo | Remove the duplicated functions in `payroll_calculation.py`. | calculations.md | | |
| `lifecycle-py` | todo | Decide whether `scripts/check-lifecycle.py` and `scripts/test-lifecycle.py` stay. BOOTSTRAP added them next to the template's `.sh` versions, which are the ones CI runs. | `.github/workflows/ci.yml` | | |

### Assvinth

| ID | Status | Task | Defined by | After | By |
|---|---|---|---|---|---|
| `uc003-ui` | doing | Address PR #50 review with a whole-month browser form: generate staged entries from one interval per selected weekday, handle public and annual holidays, allow edits/removal/manual and split-shift additions, review totals, and confirm one CSRF-protected monthly submission. Expose 2026 public-holiday dates from the backend constant through a narrow authenticated read endpoint. Keep completed months view-only and simplify setup success navigation. | UC-003 Amendments 3 and 6, UC-001, UC-002 | | Tue 27 Oct, 19:00 |
| `readme-final` | todo | Finish the README for the capstone, with a diagram of the four layers and the main components (the grading criteria ask for a clear architecture presentation; PROJECT.md describes the layers only in text). | Capstone brief | | Tue 27 Oct |
| `release-tag` | todo | Tag v0.1.0, which also exercises the tag-triggered release publication. | Capstone brief | `readme-final` | Wed 28 Oct |
| `arch-test` | todo | Make the layer check in `tests/unit/test_architecture.py` recognise `src.app` imports; it must fail on a deliberate inner-to-outer import and pass on `main`. An extended check exists separately and is not on `main`; it was validated against an earlier payroll router, so re-validate it against the current wiring before reporting it passing. | ADR-001 | | |
| `align-gating` | todo | Align `docs/INDEX.json` and `.github/CODEOWNERS` on which files are review-gated. | INDEX.json | | |

## Acceptance / validation cues

- All three use cases have an explicit component path through domain, application,
  interfaces and infrastructure.
- Setup has ports for employer uniqueness and employment persistence, with
  foreign-key relationships preserved.
- Payroll has ports for employment lookup, cumulative annual gross checks, and
  atomic monthly record and payslip persistence.
- Invalid inputs and annual-limit breaches fail before persistence; success
  returns a confirmation after the transaction completes.
- Setup and payroll writes need a signed-in session and an `X-CSRF-Token`; reads
  are scoped to the signed-in account.
- A new account gets from registration to a saved payslip in the browser,
  without Swagger (UC-003 acceptance criteria).
- The architecture stays consistent with ADR-001 to ADR-007.
- Evidence: the three use-case specifications, ADR-001 to ADR-007 and the tests
  under `tests/`.

## Validation approach

Each use case's tests are named in its Validation plan ([UC-001](specs/UC-001-Set-Up-an-Employment.md),
[UC-002](specs/UC-002-Process-the-Monthly-Employment.md), [UC-003](specs/UC-003-Employer-Accounts-and-Secure-Access.md)); trade-offs are in the ADR Consequences.

## Blockers / assumptions

- Open decision: whether `release-tag` also waits on the browser views and `payslip-response`, or v0.1.0 ships without them.
- The browser UI feasibility check, deferred when ADR-007 was accepted on 23 October 2026, happens in the review of `uc003-ui`.
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
