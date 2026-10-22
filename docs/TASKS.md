# TASKS.md

PHASE: 3
STATUS: in-progress

(0=Bootstrap | 1=Specify | 2=Design | 3=Develop | 4=Validate | 5=Deploy)

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0 — Bootstrap | Done | Project foundation and development tooling established. |
| 1 — Specify | Established; review as needed | UC-001 and UC-002 are documented. |
| 2 — Design | Baseline established; decisions open | ADR-001 to ADR-004 form the working baseline. ADR-005 remains Proposed. |
| 3 — Develop | In progress | Payroll calculation and persistent payroll saving are being developed; the UC-002 database foundation is done, wiring next. |
| 4 — Validate | In progress alongside development | Golden payroll tests, CI and Docker/release validation are underway. |
| 5 — Deploy | Not started | Release readiness has not yet been established. |


## Active objective

Implement and validate the initial vertical slice for employment setup and monthly payroll,
following the accepted architecture decisions and use-case specifications.

## Current Use Case

docs/specs/UC-002-Process-the-Monthly-Employment.md

## Current slice

Initial implementation of the domain models, `SetupService`, and `PayrollService`, with unit tests for setup and payroll calculations.

The implementation must remain consistent with ADR-001 through ADR-004. Workbook-derived golden payroll cases
should be used to verify the calculated values. The discrepancy in `admin_charge` and `total_employer_cost` remains pending confirmation.

UC-001 employment input sub-slice (Nano, `uc-001-employment-setup`): weekly hours as H:MM kept as minutes,
holiday weeks (4 or 5) instead of days, an optional end date and 2026-only start dates.
See [UC-001](specs/UC-001-Set-Up-an-Employment.md).
- Specify (phase 1): done.
- Develop (phase 3): done, merged into `main` as PR #17. `POST /api/v1/setup` takes weekly hours as H:MM, holiday weeks
  (4 or 5, default 4) and an optional end date, and accepts only 2026 start dates
  (`tests/integration/test_setup_api.py`, `tests/unit/test_setup_service.py`). Weekly hours are whole minutes at the API
  and in the `weekly_minutes` column, and float
  hours inside `Employment`; `round(weekly_hours * 60)` converts exactly for every H:MM up to 99:59. Later:
  move all hour fields (weekly, worked, holiday) to whole minutes together, when the holiday balance is built.

UC-001 setup saving sub-slice (Nano, `uc-001-employment-setup`): setup data survives a restart.
- Specify (phase 1): done. Decided on 20 October 2026: an AHV number that is already saved reuses that employee
  (see [UC-001](specs/UC-001-Set-Up-an-Employment.md)).
- Develop (phase 3): done. `SqlAlchemySetupRepository` on the `employers`, `employees` and `employments`
  tables replaces `InMemorySetupRepository` in `create_app()`, which builds the engine from `DATABASE_URL`,
  keeps it on `app.state.engine` and disposes it on shutdown; start-up fails with `DatabaseConfigurationError`
  when the variable is unset. The port offers `get_employment(id)` so payroll can read the saved employment.
  `tests/conftest.py` gives tests an in-memory `DATABASE_URL` by default.
- Acceptance: the three rows are saved together or not at all; `6:30` is kept as 390 minutes and CHF 28.50
  as 2850 centimes; a second setup with the same employee AHV number links a new employment to the saved
  employee; data is still there after the app is created again on the same database file.
- Evidence: `tests/integration/test_sqlalchemy_setup_repository.py`, `tests/integration/test_setup_api.py`
  (`test_setup_survives_a_restart`, `test_app_does_not_start_without_database_url`),
  `tests/unit/test_setup_service.py`; `bash scripts/test.sh` passed (96 passed, 1 xfailed). Manual check
  with uvicorn on a SQLite file: the employer was still there after a restart, and a second setup reused employee 1.
- Review: [PR #28](https://github.com/Guin-Kiwi/pay-align-dev/pull/28) is open, waiting for Assvinth's review.
  Review fix: tests always use an in-memory database, even when the developer has `DATABASE_URL` set
  (`tests/conftest.py`; `tests/integration/test_test_database_isolation.py` failed before the fix).
- Open, owned by others: Ayla's payroll repository can use `app.state.engine`; `PRAGMA foreign_keys=ON` in
  `database.py` is due now that UC-001 persists employers and employments (ADR-005 item 6); the payroll router
  can look up the employment with `get_employment(id)` (Aaron).

Design sub-slice (phase 2): the persistence adapter for UC-002 saving, proposed in
[ADR-005](adr/ADR-005-sqlalchemy-persistence-adapter.md). It touches infrastructure
(one SQLAlchemy adapter, `work_entries` and `payroll_snapshots` tables, start-up
configuration), the application port and errors, and the payroll router error mapping.

## Acceptance / validation cues

- Both use cases have an explicit component path through domain, application,
  interfaces, and infrastructure.
- Setup has ports for employer uniqueness and employment persistence, with
  foreign-key relationships preserved.
- Payroll has ports for employment lookup, cumulative annual gross checks, and
  atomic monthly record/payslip persistence.
- Invalid inputs and annual-limit breaches fail before persistence; success
  returns a confirmation after the transaction completes.
- The architecture remains consistent with
  [ADR-001](adr/ADR-001-clean-architecture-boundaries.md),
  [ADR-002](adr/ADR-002-versioned-akbs-payroll-rules.md), and
  [ADR-003](adr/ADR-003-monetary-precision-and-rounding.md), and
  [ADR-004](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md).
- Evidence: this design record, the two linked use-case specifications, and
  the existing architecture ADRs.

## Risks / tradeoffs

- Keeping repository ports at the application boundary preserves testability,
  but requires explicit mapping between ORM records and domain entities.
- A single transaction for the monthly record and payslip prevents partial
  payroll saves, while making the persistence adapter responsible for
  transaction coordination.
- The 2026 ruleset is intentionally narrow; adding another year requires a
  new version rather than changing historical calculations.
- Replacing the sqlite3 repository with a SQLAlchemy adapter (ADR-005) removes
  the duplicate schema and the SQLite-only coupling, but means rewriting a
  repository that already has tests.
- Foreign keys are declared but not enforced until UC-001 persists employers
  and employments, so payroll rows can reference missing parents in the meantime.

## Validation approach

- During DEVELOP, unit tests will cover domain validation, exact payroll
  calculations, NBU eligibility, reimbursement separation, and annual-limit
  rejection.
- Integration tests will verify repository foreign keys, employer uniqueness,
  and atomic persistence of the monthly record and payslip.
- Architecture tests will continue to enforce inward dependency direction.
- ADR-005 slice: integration tests assert that a duplicate month raises
  `DuplicateMonthError` and persists nothing, that a failed save leaves no
  entries, snapshot, record or payslip, that the employee limit sums across
  employments of the same employee, that start-up fails clearly when
  `DATABASE_URL` is unset or unsupported, and that tests dispose their engines.

## Blockers / assumptions / decisions

- No architecture blocker found; `docs/PROJECT.md` is sufficient and needs no
  update.
- Assumption: the first implementation slice uses HTTP delivery and a
  relational ORM adapter as described by `docs/PROJECT.md`.
- Decision: ADR-004 defines entry snapshots, the three normal-case hour
  categories, derived holiday balance, and the exclusion of sick-pay and
  corrections.
- ADR-001 through ADR-004 are marked Accepted for implementation.
- Decision: database setup uses SQLAlchemy and reads `DATABASE_URL`, with skeleton tables for the five entities; the code is delivered on `uc-002-payroll-saving`. The money type and `DATABASE_URL` format are recorded in `docs/PROJECT.md`.
- Proposed: ADR-005 (single SQLAlchemy persistence adapter). Status stays
  Proposed until a human accepts it; `docs/PROJECT.md` is updated on acceptance,
  not before.
- Decided on 16 October 2026: `holiday_weeks` (4 or 5) replaces
  the `holiday_entitlement` days, and yearly holiday time is
  `holiday_weeks × weekly_minutes`. Still open: pro-rating for an employment
  that starts or ends during the year (see the UC-001 open questions).
- Decided on 16 October 2026: the app accepts only
  2026, the only year with a ruleset (ADR-002); the holiday pro-rating divides
  by 365. The payroll year check (`year >= 2026` in `interfaces/payroll.py` and
  `domain/monthly_record.py`) still has to change; Aaron owns those files.
- Assumption: the earlier float-column SQLite schema was never deployed, so the
  repository's legacy migration can be dropped.
- Human review remains required for the review-gated use-case specifications.

## Evidence links

- [UC-001 specification](specs/UC-001-Set-Up-an-Employment.md)
- [UC-002 specification](specs/UC-002-Process-the-Monthly-Employment.md)
- [ADR-001 Clean Architecture boundaries](adr/ADR-001-clean-architecture-boundaries.md)
- [ADR-002 Versioned AKBS payroll rules](adr/ADR-002-versioned-akbs-payroll-rules.md)
- [ADR-003 Monetary precision and rounding](adr/ADR-003-monetary-precision-and-rounding.md)
- [ADR-004 Payroll entry snapshots and holiday balance](adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md)
- [ADR-005 SQLAlchemy persistence adapter (Proposed)](adr/ADR-005-sqlalchemy-persistence-adapter.md)
- [PROJECT architecture](PROJECT.md)

## Person 4 — CI, Docker, Release and architecture tests

Documentation baseline: `origin/main` at `f6fdc84`.
The shared status remains `PHASE: 3`, `STATUS: in-progress`.

- **CI:** [PR #10](https://github.com/Guin-Kiwi/pay-align-dev/pull/10)
  is merged. The whitespace check covers changes in PRs
  and pushes; syntax and Git comparison tests are documented in the PR.
- **Docker:** [PR #11](https://github.com/Guin-Kiwi/pay-align-dev/pull/11)
  is merged. Image build, container startup and health checks
  passed. This does not verify persistent data storage.
- **Release workflow:** [PR #12](https://github.com/Guin-Kiwi/pay-align-dev/pull/12)
  was successfully validated manually at commit
  `7eeb7fb8fb26c734c8c607a61ec0f973dabffb7b`:
  [Release #3](https://github.com/Guin-Kiwi/pay-align-dev/actions/runs/39240966965).
  `verify` succeeded, the image artifact was uploaded,
  and `publish` was skipped as expected.
  The PR is not merged; human review and acceptance of the
  fixed integration baseline remain pending. Actual publication
  through a `v*` tag has not been tested.
- **Documentation cleanup:**
  [PR #22](https://github.com/Guin-Kiwi/pay-align-dev/pull/22)
  is merged. Commit `39ffed463d711ca4cf295f220fe5eb5c895e736b`
  removes exactly three trailing spaces.
- **Architecture tests:** Branch `delivery-architecture-tests` contains
  the local commits `b188fc8eb8b7ff4a58836f593c1d1b1acc57899b`
  (relative imports and package imports) and
  `02421b8ae6dd1014a32c09bc5d70e2f1a6492ad1`
  (literal dynamic imports). Together they add 58
  regression cases, all passing. They have not been pushed.

### Local architecture validation evidence

- Architecture tests: **75 passed, 1 failed**.
- `bash scripts/test.sh`: lifecycle tests and 32 tooling tests passed;
  pytest: **145 passed, 1 failed, 1 xfailed,
  41 subtests passed**, with one Starlette/HTTPX deprecation warning.
- `git diff --check`: passed.
- Only failing test:
  `test_project_follows_the_dependency_rule`.
  `src/app/interfaces/payroll.py` directly imports
  `src.app.infrastructure.sqlite_payroll_repository`.
  Ayla and Aaron are handling the payroll wiring.
- The architecture tests and the full suite on the
  architecture branch therefore still have a failure.
  The test remains enabled and unchanged.

Next steps for Person 4: support the review of PR #12,
coordinate architecture work with the payroll correction, and then
rerun the tests. Prepare presentation evidence from these results;
the presentation is not marked complete here.

## Next smallest step

A human reviews ADR-005. On acceptance, update `docs/PROJECT.md`,
then start DEVELOP on `uc-002-payroll-saving` with the first failing test for the new adapter.

Separately, on `uc-002-payroll-calculation`: implement and run golden payroll tests against `PayrollService` using the workbook-derived cases.
Resolve the pending `admin_charge` and `total_employer_cost` discrepancy before treating those expected values as final.

## UC-001 UI-Felder — vorherige Teilaufgabe auf `person4-ui-setup`

- Anforderung: Setup-Felder an den zusammengeführten UC-001-API-Vertrag anpassen;
  in dieser vorherigen Teilaufgabe blieben Übermittlung und Save deaktiviert. Keine Backend-Änderung.
- Phase 3, Teilaufgabe umgesetzt und geprüft; der gemeinsame Projektstatus bleibt
  `in-progress`, da UC-001 und UC-002 insgesamt noch nicht abgeschlossen sind.
- Wochenstunden: editierbares H:MM-Feld, exakt 0:01 bis 99:59; Ferienwochen:
  Auswahl 4 oder 5, Standard 4. Startdatum nur 2026; optionales Enddatum ab
  Startdatum, auch nach 2026. Stundenlohn in CHF, mindestens 22.20 und höchstens
  zwei Nachkommastellen. Hinweis auf gewöhnliche Besteuerung als Standard.
- The previously uncommitted test correction to `weekly_hours: "6:00"` was preserved
  and is included in commit `14fbaa5`.
- TDD-Nachweis: neue Feld-/Validierungsprüfungen zuerst rot (3 fehlgeschlagen),
  danach 7 UI-Tests grün. JavaScript-Grenzfälle, Datumsabhängigkeit und ausbleibende
  zusätzliche HTTP-Anfragen werden im vorhandenen Node-DOM-Harness geprüft.
- Historical validation for this field-only sub-slice: `bash scripts/test.sh`
  with an isolated Python environment under `/tmp`:
  89 bestanden, 1 erwarteter Fehlschlag, 70 Subtests; 32 Prozess-Tests und
  Lifecycle-Szenarien bestanden. `bash scripts/check-lifecycle.sh` und
  `git diff --check` bestanden. Bekannte Starlette/HTTPX-Abkündigungswarnung.
- Grenze: kein echter Browser-/Layout-Test in dieser Teilaufgabe.
- Follow-up completed: form submission and Save Setup are implemented in commit
  `14fbaa5`, as documented below.

## UC-001 Save Setup — implemented on `person4-ui-setup` (Draft PR #24)

- Quelle: UC-001, bestehender Setup-API-Vertrag und expliziter Auftrag zur
  UI-Übermittlung. Phase 3; Teilaufgabe implementiert und lokal geprüft.
  Der gemeinsame Projektstatus bleibt `in-progress`.
- The earlier field changes and test correction are included in commit `14fbaa5`.
  Save Setup submits to `POST /api/v1/setup`. This UI implementation did not change
  backend code or API contracts.
- Save wird erst nach bestätigtem Arbeitgeber-Lookup und gültigen Pflichtfeldern
  freigegeben. Nur der dokumentierte 404 erlaubt neue Arbeitgeberdaten;
  bei bestehendem Arbeitgeber entfällt die gesamte `employer`-Eigenschaft.
- JSON enthält H:MM als String, Ferienwochen als Zahl, CHF-Stundenlohn als
  Dezimalstring, leeres Enddatum als `null` und `tax_status: "ordinary"`.
- Formularevent verhindert die native Übermittlung; ein laufender POST sperrt
  weitere POSTs. Keine automatischen Wiederholungen. Netzwerkfehler, Timeout
  und unerwartete Antworten sperren erneutes Senden und erklären das ungewisse
  Ergebnis. HTTP 400/409/422 zeigen sicher als Text gerenderte Fehlermeldungen;
  alle Eingaben bleiben erhalten.
- HTTP 201 wird anhand von Nachricht und positiven ganzzahligen IDs geprüft.
  IDs werden nicht angezeigt. Danach Arbeitgeberstatus neu laden; eine weitere
  Einrichtung erfordert bewusst ein Neuladen der Seite. Der Hinweis auf den
  ausschließlich flüchtigen In-Memory-Speicher bleibt sichtbar.
- TDD: zuerst 20 rote UI-Prüfungen, danach grün; ergänzt um Timeout,
  unerwartetes HTTP 200 und fünf Ferienwochen. Der Node-DOM-Harness prüft
  Payloads, Validierungsgrenzen, Lookup-Fehler, Doppelübermittlung,
  Fehlerantworten, Texte mit HTML-Zeichen und Refresh-Fehler. Erzeugte
  Erfolgs-Payloads werden zusätzlich gegen die echte API im TestClient geprüft.
- Historical automated evidence for the implementation in commit `14fbaa5`:
  focused UI/API tests: 44 passed (23 subtests);
  vollständiges `bash scripts/test.sh` mit isolierter Python-Umgebung unter
  `/tmp`: 111 bestanden, 1 erwarteter Fehlschlag, 70 Subtests. 32 Prozess-Tests
  und Lifecycle-Szenarien bestanden. Lifecycle-Check und `git diff --check`
  bestanden. Bekannte Starlette/HTTPX-Abkündigungswarnung bleibt bestehen.
- Historical Person 4 manual browser validation (reported personally by the user):
  Safari on macOS; these observations are separate from the automated tests above.
  - The setup page loads correctly.
  - Saving a new employer and employment displays the success message.
  - Reloading the page displays the existing employer.
  - Saving a second employment for that employer succeeds.
  - Invalid weekly hours `6:60` display a validation error and keep Save disabled.
  - Tab navigation works and focused fields are visible.
  - The form remains usable in a narrow Safari window without horizontal scrolling.
- Validation limits: a full screenreader audit remains unverified. These checks
  do not establish usability on a physical mobile device or persistence across
  a server restart. At UI commit `14fbaa5`, setup records are stored only in memory
  and are lost after a server restart.
- PR #28 introduces persistent database storage and has not been integrated into
  this UI branch. Later integration requires updating the UI storage warning
  and renewed automated and manual validation.
- Related PRs #12 (release workflow), #23 (Person 4 progress), #25 (English project
  instructions), and #26 (Node.js 22 in CI) are merged into `main`. This UI branch
  has not yet integrated those changes.
- Implementation commit `14fbaa5` is committed and pushed in Draft PR #24.
  PR #24 remains Draft; integration with current `main` and review remain outstanding.

## Backlog

- docs/specs/UC-002-Employee-Registration.md
- docs/specs/UC-003-Monthly-Payroll-Processing.md
- Future: dedicated sick-pay and exception-management use case.

## Working agreement

- Keep one active use case small enough to deliver vertically.
- Keep one current slice small enough to finish or re-evaluate quickly.
- Prefer reality-based progress over placeholder completeness.
- Update this file when the lifecycle phase, active objective, or current use case changes.
- Record blockers, assumptions, and decisions when they affect delivery.
- Link validation evidence from the relevant project artefact instead of duplicating it here.
- End each work session with the next smallest step clearly stated.

## Fast Track: Datenbankhinweise der Setup-UI

- Quelle: ausdrücklicher Auftrag zur Rekonstruktion der Speicherhinweise nach
  der Worktree-Wiederherstellung; UC-001 verlangt Datenbankspeicherung.
- Phase 3, Teilaufgabe umgesetzt und geprüft. SPECIFY verkürzt; DESIGN entfällt, da nur Texte
  und zugehörige Assertions geändert werden. Der Projektstatus bleibt in-progress.
- Umfang und Akzeptanz: Formular und Erfolgsmeldung erklären auf Englisch,
  dass Setup-Datensätze in der konfigurierten Datenbank gespeichert werden
  und der Erhalt nach einem Serverneustart von deren Konfiguration abhängt.
  Keine Verbindungsdaten, Pfade oder Zugangsdaten; Validierung, Übermittlung,
  API und Backend bleiben unverändert. Historische Nachweise oben bleiben erhalten.
- Ausgangsprüfung: Branch person4-ui-setup, Commit eaabb89, sauberer Worktree;
  29 bestehende UI-Tests bestanden.
- Prüfungen nach der Korrektur: 29 UI-Tests bestanden; `bash scripts/test.sh`
  bestanden: 159 Tests, 1 erwarteter Fehlschlag, 78 Subtests; 32 Prozess-Tests
  und Lifecycle-Szenarien bestanden. Bekannte Starlette/HTTPX-Abkündigungswarnung.
- Die frühere Integrationsnotiz oben ist historisch: PR #28 ist im geprüften
  Stand eaabb89 bereits integriert. Die aktuellen UI-Texte berücksichtigen dies.
- Nächster Schritt: menschliche Prüfung des lokalen Commits; kein Push, Merge
  oder Rebase. PR #24 bleibt Draft.

## Fast Track: UI-/API-Persistenztest nach App-Neustart

- Quelle: Auftrag zur Rekonstruktion des verlorenen Regressionstests und
  UC-001-Akzeptanz zur Datenbankspeicherung. Phase 3, Teilaufgabe geprüft;
  Projektstatus bleibt in-progress. SPECIFY verkürzt; DESIGN entfällt, da
  ausschließlich bestehendes Verhalten durch einen Test abgesichert wird.
- Akzeptanz: Der vorhandene JavaScript-Harness erzeugt mit echtem setup.js
  eine Payload mit fünf Ferienwochen. Die erste App speichert sie über die API
  und wird per TestClient-Kontext geschlossen. Eine neue App liest dieselbe
  temporäre SQLite-Datei; Arbeitgeber, Arbeitnehmer, Anstellung, Verknüpfungen,
  2850 Rappen Stundenlohn, 390 Wochenminuten und fünf Ferienwochen bleiben erhalten.
- Isolation: tmp_path und monkeypatch; tests/conftest.py bleibt unverändert.
  Keine Entwicklerdatenbank; keine Änderung an Backend, API oder Dev Container.
- Prüfungen: UI/API 48 bestanden, 23 Subtests; `bash scripts/test.sh`
  bestanden: 160 Tests, 1 erwarteter Fehlschlag, 78 Subtests; 32 Prozess-Tests
  und Lifecycle-Szenarien bestanden. Bekannte Starlette/HTTPX-Abkündigungswarnung.
  Lifecycle-Check und `git diff --check` bestanden.
- Grenze: JavaScript läuft im vorhandenen DOM-/API-Harness, nicht in einem
  echten Browser. Der API-Neustart verwendet echte SQLite-Dateispeicherung.
- Nächster Schritt: menschliche Prüfung des lokalen Commits; PR #24 bleibt
  Draft. Kein Push, Merge oder Rebase.
