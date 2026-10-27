# UC-004: UI and User Flow

Status: **Draft.** The Employees design, saved-months presentation and final Home layout were approved by Guin-Kiwi on 2026-10-27 and checked against code and tests that day. The revised Home layout and other proposed decisions still require human review. This document describes the intended browser journey; implementation is in progress.
Payroll and employment rules remain owned by [UC-002](UC-002-Process-the-Monthly-Employment.md) and [UC-001](UC-001-Set-Up-an-Employment.md); account and session rules belong to [UC-003](UC-003-Employer-Accounts-and-Secure-Access.md).

## Goal

Give household employers a clear journey from sign-in through setup, monthly payroll and a printable payslip.

## Business value

Employers can find the next action and complete payroll without developer tools.

## Scope

The browser provides login, Home, employer details, employment setup, Timesheets, Employees and saved payslips. It does not add payroll rules, persistent drafts, editing of employees or employments, payroll corrections, app-generated PDFs or payslip delivery.

## Actors

A visitor registering or signing in and the signed-in household employer.

## Preconditions

The employer has the details needed for the chosen task. Monthly payroll requires an employment and follows UC-002's run order.

## Trigger

The employer opens PayAlign to manage household payroll.

## Main flow

1. The public welcome page introduces PayAlign and offers **Log in** and **Sign up** in its header. Register or sign in and open Home. Home is available before an employer profile exists; employment setup is gated until it is saved. Employer details may later be edited.
2. Add an employment using the existing setup rules. Saving an employment requires confirmation because its terms and a new employee's details cannot later be edited.
3. Home shows a month selector beside **Payroll overview**. A wide section shows the household wage limit, account-details button and selected-month payout, estimated set-aside and employer cost, with saved-payroll completeness. The left column holds the employment workspace: select an employee, view saved months or enter and review the next month. The right column shows each employment's saved payout, employer cost, holiday balance, payslip and pending timesheet action. No separate set-aside breakdown is shown on Home.
4. Timesheets lists each employment's saved months and next month to enter. Its entry page collects regular work schedules, extra days, annual holidays, bonuses and expenses, with a table of entries and totals. Fill month keeps existing rows; several non-overlapping visits per date are allowed. Dates and public holidays come from the server's configured rules. On a public holiday the user chooses worked or paid time off; annual holiday is not offered for that day. Worked time is submitted as `worked` for server classification; paid time off is submitted as `public_holiday_taken` using the schedule duration.
The separate Timesheets entry page presents inputs on the left and the month table and totals on the right. A schedule supplies weekdays, start, end and unpaid break. Fill month adds matching dates within the employment and reports skipped dates. Extra days begin with a date; worked rows take start, end and break. Annual-holiday rows take paid minutes, prefilled from the schedule, and cannot share a date with work. Overlaps are reported before submission. A scheduled public holiday gets a row; other public holidays get one only if added.

5. Review and confirm the whole month before its single save. A month without work can be entered empty. On the Timesheets page, bonus and expenses must be added before saving. Drafts and patterns are not persisted.
6. Employees groups employments by person. Each person has agreement details, a payslip picker and on-demand employee details on the left, their pending timesheets, and saved yearly totals, holiday balance and wage limit on the right. The personal detail read is account-scoped.
7. Open a saved payslip at `/payslips` or from the relevant month. The general Payslips page opens the latest saved month across employments; selecting another employment opens its latest saved month. A link to a specific employment and month opens that payslip. Employer costs appear separately on screen and are omitted from the employee printout; the browser supplies print or save-as-PDF. UC-003 describes the payslip data and limitations.
8. Signed-in navigation offers Home, Timesheets, Employees, Payslips and logout. A Back button appears outside Home. When unsaved timesheet entries or amounts would be lost, Back, navigation, logout and Cancel ask for confirmation.

## Alternate / edge flows

The Home workspace retains weekday-specific patterns. Refilling after manually editing work asks before replacing work rows, and adding annual holiday replaces entries on that date. Scheduled public holidays default to paid time off and can be changed to worked. The separate Timesheets page retains its own non-destructive fill and explicit public-holiday choice.

Empty states explain what to do next. Saved months are view-only. A month cannot be skipped; a future month may still be saved when it is next in sequence. The last saved month's holiday balance is shown in hours and minutes, or a dash when absent. An employment cannot be ended after setup, and an employee's details cannot be edited. Employments have no name or role and are distinguished by their dates.

## Errors / failure cases

Show actionable validation and authentication errors. Missing and other-account records have the same not-found outcome. Do not expose database errors. A successful payroll save stays confirmed if the later detail read fails; for an uncertain save, tell the employer to check the saved state before trying again. Never retry a state-changing request automatically.

## Acceptance criteria

- Registration and login lead to Home; session, CSRF and account isolation follow UC-003.
- Profile creation and editing are account-scoped; adding an employment is gated on a profile and does not ask for the employer details again.
- Home and Employees show the employer's saved information and pending timesheets; their task rows use the same `months_due` data.
- Timesheets supports valid entries, empty months, public holidays and review before an irreversible save.
- The saved payslip shows the saved values and excludes employer costs from the printed employee copy.
- Irreversible saves warn what will be kept and cannot be changed. The Timesheets and employment-setup dialogs trap focus, close on Escape except while saving, and disable their buttons while saving; the Home workspace offers an inline review and explicit confirmation.

## Security / trust-boundary notes

Session, CSRF and account isolation belong to UC-003 and ADR-007. Browser controls and identifiers do not authorize access. Employer and employee details, including AHV numbers, are account-scoped.

## Validation plan

Exercise onboarding and two-account isolation, whole-month entry and recovery, saved payslips and the UI tests under `tests/`. Inspect the journey on narrow and wide screens and the A4 print preview in a real browser. PostgreSQL checks require a throwaway test database.

## Open questions / assumptions

The remaining proposed UI and supporting decision amendments require human review. Reopened payslips use current identity details, rather than historical identity snapshots, as described in UC-003.

## Notes for implementation

UC-004 owns presentation and navigation. The underlying behavior and rules stay with their owning use cases and ADRs.
