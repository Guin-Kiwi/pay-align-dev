# UC-001: Set Up an Employment

## Goal
Enable a private household employer to initialize their system profile and register a new employee. This establishes the legal and financial baseline required for payroll processing.

## Business value
This use case simplifies the onboarding process for private household employers in Basel-Stadt, ensuring compliance with AKBS requirements and reducing administrative burden.

## Scope

### In scope
- Initializing an `Employer` record if none exists.
- Registering an `Employee` and `Employment` with required details.
- Validating AHV numbers and required fields.
- Validating the employment input: start date, optional end date, hourly wage, weekly hours and holiday weeks.
- Saving all data to the database.

### Out of scope
- PDF generation for contracts or registration summaries.
- Email notifications to the employer or employee.
- Pre-filling employer or employee details from external sources.
- Legal compliance checks beyond format validation and the Basel-Stadt minimum wage.
- Support for cross-border employers or underage employees.
- Changing or ending an employment after setup (termination workflows are out of scope in `docs/PROJECT.md`).
- Checking the employee's age for the five-week holiday rule; no birth date is stored.
- Calculating or pro-rating the holiday entitlement (UC-002, ADR-004).

## Actors

**Primary**: Employer (a private individual employing household help under the AKBS simplified procedure).

**Secondary**: None.

## Preconditions
- The employer has access to the PayAlign application.
- The employer has the required details for themselves, the employee, and the employment contract.

## Trigger
The employer selects **"Set Up Employment"** in the application.

## Main flow

1. The employer opens the application and selects **"Set Up Employment"**. 
2. The system checks if an `Employer` record exists. If not, it prompts the employer to enter their details.
3. The employer enters the employee's details.
4. The employer enters the employment contract parameters: start date, end date (only for a fixed-term contract), gross hourly wage in CHF (e.g. `28.50`), weekly hours as H:MM (e.g. `6:30`) and holiday weeks (4 or 5).
5. The system validates the AHV number format, the required fields and the employment input.
6. The system saves the `Employer`, `Employee`, and `Employment` records to the database.
7. The system displays a **confirmation message** (e.g., "Employment set up successfully").

## Alternate / edge flows
- If the AHV number is invalid, the system displays an example (e.g., `756.XXXX.XXXX.XX`) and prompts the employer to retry.
- If the weekly hours are not in H:MM format, the system names the field, displays the example `6:30` and prompts the employer to retry.
- If no end date is entered, the employment has no end date.
- An end date equal to the start date is valid; the employment lasts one day.

## Errors / failure cases
- Invalid AHV number format.
- Missing required fields (e.g., employee address).
- Duplicate `Employer` record.
- Hourly wage below the Basel-Stadt minimum wage (CHF 22.20 in 2026) or with more than two decimal places.
- Weekly hours not in H:MM format, or `0:00`.
- Holiday weeks other than 4 or 5.
- End date before the start date.
- Start date outside 2026, the only year with a ruleset (ADR-002).

## Acceptance criteria
- The system must reject invalid AHV numbers (format: `756.XXXX.XXXX.XX`).
- The system must prevent duplicate `Employer` records.
- The system must save all data to the database.
- The system must display a confirmation message upon success.
- The system must accept weekly hours only as H:MM, with one or two digits for the hours and two digits from `00` to `59` for the minutes (e.g. `6:30`, `30:15`), and keep them as whole minutes (`6:30` → 390).
- The system must reject `6.5`, `6,5`, `6h30`, `6:75`, `6:5` and `0:00` as weekly hours with a 400 error that names the field and shows the example `6:30`.
- The system must accept only 4 or 5 holiday weeks.
- The system must accept a missing end date and an end date equal to the start date, and reject an end date before the start date.
- The system must reject an hourly wage below CHF 22.20 or with more than two decimal places.
- The system must reject a start date outside 2026.

## Security / trust-boundary notes
- All data is stored locally and not shared with external systems.
- The employer must authenticate to access the system (future consideration).
- Weekly hours are parsed once, at the API boundary, with one strict pattern; free text such as `1 hour 43 minutes` is rejected.

## Validation plan
- **Unit Tests**: Validate AHV string formatting and validation logic.
- **Unit Tests**: Ensure the `SetupService` throws an error if an `Employer` is created when one already exists.
- **Unit Tests**: Accept and reject tables for weekly hours (H:MM to minutes), holiday weeks and the end date rule.
- **API Tests**: `POST /api/v1/setup` with weekly hours `"6:30"` returns 201 and keeps 390 minutes; with `"6.5"` it returns 400 with the example.
- **Integration Tests**: Verify that persisting an `Employment` correctly links to the respective `Employee` and `Employer` via foreign keys.

## Open questions / assumptions
- Assumption: The employer has all required details (e.g., AHV number) at hand.
- Open question: Should the system support bulk import of employees in the future?
- Decided on 16 October 2026: weekly hours are kept as minutes, holiday weeks replace holiday days, and the end date is optional. Not yet confirmed for the UI and for the UC-002 NBU check, which becomes `weekly_minutes >= 480`.
- Assumption: Ayla's database PR (due Monday 19 October 2026) changes `employments` to integer `weekly_minutes` and `holiday_weeks` and a nullable `end_date`; until it merges, the in-memory setup repository holds them.
- Decided on 16 October 2026 (for UC-002, ADR-004): holiday for an employment that starts or ends during the year is pro-rated by days under contract (OR 329a para. 3): holiday weeks × weekly minutes × contract days in 2026 ÷ 365, counting the start and end dates, rounded once to whole minutes. Still open: the rounding mode.
- Decided on 16 October 2026: the app accepts only 2026. ADR-002 gives each year its own reviewed ruleset, and 2026 is the only one, so "2026 or later" would apply 2026 rates to 2027 without warning. A later year is added as a new ruleset with its own golden tests; employers do not enter legal rates.
- Assumption: the end date may fall after 2026, because setup calculates nothing for later years.

## Notes for implementation
- The API takes weekly hours as the string `"6:30"`; the setup router converts it to minutes, so the domain only sees whole minutes. The wage stays a decimal and the database keeps it in centimes.
- Yearly holiday time is holiday weeks × weekly minutes (4 × 6:30 = 26:00), the same unit as the UC-002 holiday balance.
- The UI offers holiday weeks as a choice of 4 or 5 and may hint that 5 weeks apply to employees under 20 or over 50 (`docs/reference/Employing_Household_Help_Basel.md`).
- Use the `SetupService` to handle the onboarding logic.
- Ensure all validations are performed before saving to the database.

## Fast Track: PR #13 merge leftovers

- **Scope:** delete the `TODO(PR #13 merge)` comment blocks in `employment.py` and `payroll.py`, and the second minimum wage check in `SetupService.create_employment` that the merge kept from PR #9. No feature, API, data or dependency change. Builds on PR #15.
- **Reason:** merging `main` into `uc-001-employment-setup` (cb4e085) brought old code back. PR #15 disabled it and left the decision to the UC-001 owner.
- **Acceptance:** the minimum wage rule lives only in `Employment`; a low wage error shows both amounts with two decimals; no `TODO(PR #13 merge)` is left.
- **Checks (phase 3):** regression test `test_low_wage_error_shows_both_amounts_with_two_decimals` failed before the fix and passes after it; `bash scripts/test.sh` passed (51 passed, 29 subtests); `git diff --check` clean. Required CI and review remain.