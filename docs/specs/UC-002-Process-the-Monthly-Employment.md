# UC-002: Process the Monthly Employment

## Goal
Calculate an employee's monthly pay, apply correct 2026 social insurance and tax deductions, generate a compliant payslip, and persist the data for annual AKBS reporting.

## Business value
This use case automates monthly payroll processing for private household employers, ensuring accurate deductions and compliance with AKBS requirements while reducing manual effort.

## Scope

### In scope
- Inputting and saving daily work details (start time, end time, breaks, and paid/unpaid status).
- Recording four normal-case hour categories: worked, worked on a public holiday (50% premium), paid holiday, and paid public-holiday leave (no work done).
- Calculating gross wage, deductions, and net payout.
- Detecting public holidays and applying correct pay rates.
- Saving the entries, a run snapshot (ADR-004 Amendment 2), the `MonthlyRecord`, and the `Payslip` to the database.
- Deriving the remaining holiday balance from employment entitlement and prior persisted runs.

### Out of scope
- PDF generation for payslips.
- Email notifications to the employer or employee.
- Recurring inputs (e.g., copying hours from previous months).
- Sick-pay and other exception-management workflows.
- Corrections, reversals, and overpayment adjustments.
- Partial payments for employees who quit mid-month.

## Actors

**Primary**: Employer (the user entering the monthly hours and expenses).

**Secondary**: None.

## Preconditions
- The employer has access to the PayAlign application.
- An `Employment` record exists for the employee.
- The employer has the monthly work details (hours, bonuses, expenses).

## Trigger
The employer selects **"Process Monthly Payroll"** in the application.

## Main flow

1. The employer opens the application and selects **"Process Monthly Payroll"**.
2. The employer selects an active `Employment` and inputs **daily work details** (start time, end time, break duration, and paid/unpaid status) for the month. Several non-overlapping entries on one day are valid.
3. The employer optionally enters a cash bonus and expense reimbursements.
4. The system:
   - Stages the daily entries for the run without persisting them.
   - Classifies the four normal-case hour categories: worked, worked on a public holiday, paid holiday, and paid public-holiday leave.
   - Calculates **worked hours** for each day (end time - start time - unpaid breaks).
   - Identifies public holidays in the month, classifies work on a public holiday as the second category, and applies the correct pay rate.
   - Derives the remaining holiday balance from the employment's configured entitlement and prior persisted runs, less paid holiday hours.
   - Prepares the run snapshot: the employment terms, the ruleset version, the hour totals and the holiday balance after the run. The entries are saved as `work_entries`.
   - Calculates **Gross wage** (worked and paid holiday/public-holiday hours × hourly rate + applicable supplements + bonus).
   - Calculates **Deductions** (AHV/IV/EO, ALV, tax, and NBU when it applies), as in [calculations.md Step B](../reference/calculations.md#step-b-calculate-employee-deductions).
   - Calculates **Net payout** (gross wage - deductions + expenses).
5. The system checks that the month is not after the employment's end month, that the month is the next run in sequence, that every entry is dated within the employment, if the monthly run exceeds annual limits, rejects duplicate months, and verifies the derived holiday balance is valid. The annual limits count the whole calendar year, whatever the month of the run:
   - Employee limit ([`EMPLOYEE_GROSS_LIMIT`](../../src/app/domain/constants.py), gross wage): only wages from this employer count, across all of the employee's employments with this employer. Wages from other employers do not.
   - Employer limit ([`EMPLOYER_GROSS_LIMIT`](../../src/app/domain/constants.py), gross wage): all of this employer's employees count.
6. The system saves the staged entries, run snapshot (ADR-004 Amendment 2), `MonthlyRecord`, and `Payslip` in one transaction.
7. The system displays a **confirmation message** (e.g., "Payroll processed successfully").

## Alternate / edge flows
- If the monthly run would take the calendar-year total above the employee or the employer limit, the system warns the employer and rejects the submission.
- If the requested month is after the month in which the employment ends, the system rejects the submission. The end month itself is still processed.
- If an entry is dated before the employment's start date or after its end date, the system rejects the submission. Both dates are inclusive: the start date is the first and the end date the last possible working day.
- If the database refuses the save because of a constraint other than the duplicate month, the system rejects the submission with a fixed message. Text from the database is never shown to the employer.
- If entries overlap, contain negative durations, or contain invalid category combinations, the system rejects the submission before saving. Invalid combinations are: public-holiday work or leave on a day that is not a public holiday; paid holiday on a public holiday (NAV Haushalt BS § 27 para 4); and public-holiday leave on the same day as public-holiday work or paid holiday.
- An employment's first run is the month of its start date, starting from the employment's configured holiday entitlement. Each later run is the month after its last saved run. A month that is not the next one is rejected: an earlier or equal month as already processed, a later month as a skipped month.
- A month without entries is still a run. The system produces a payslip without hours and records the holiday balance.
- If the requested month was already processed, the system rejects the submission because corrections are out of scope.

## Errors / failure cases
- Invalid input (e.g., negative hours).
- Missing required fields (e.g., start or end time of a worked entry).
- Skipped month (a run for a month other than the next one).
- Exceeding annual limits.
- Run for a month after the employment's end month.
- Entry dated before the start date or after the end date of the employment.
- Save refused by a database constraint (reported without the database's text).
- Duplicate monthly run.
- Invalid or negative derived holiday balance.
- Corrections to a completed run are not supported.

## Acceptance criteria
- The system must accept and save **daily work details** as input.
- The system must represent worked, worked-on-a-public-holiday, paid holiday, and paid public-holiday leave hours as four distinct normal-case categories.
- The system must calculate **hours worked** for each day (end time - start time - unpaid breaks).
- The system must identify public holidays and apply the correct pay rate.
- The system must derive remaining holiday balance from the employment's entitlement and prior persisted runs, less paid holiday hours.
- The system must apply the 2026 deduction rates in [`constants.py`](../../src/app/domain/constants.py) (5.3% AHV/IV/EO, 1.1% ALV, 5% tax, 1.432% NBU if applicable).
- The system must reject a monthly run that takes the employee's calendar-year gross wage from this employer above CHF 22,680 ([`EMPLOYEE_GROSS_LIMIT`](../../src/app/domain/constants.py)), counting every employment of that employee with this employer and no wages from other employers.
- The system must reject a monthly run that takes the calendar-year gross wage of all of this employer's employees above CHF 60,480 ([`EMPLOYER_GROSS_LIMIT`](../../src/app/domain/constants.py)).
- The system must count the whole calendar year for both limits.
- The system must reject duplicate monthly runs and skipped months.
- The system must reject a run for a month after the employment's end month.
- The system must reject entries dated before the employment's start date or after its end date, both dates inclusive.
- The system must not show database error text in a rejection.
- The system must accept a month without entries and produce a payslip without hours.
- The system must save the entries and a run snapshot (ADR-004 Amendment 2) together with the `MonthlyRecord` and `Payslip`.
- The system must not persist any part of a rejected run.
- Sick-pay and other exception-management workflows must not be implemented by this use case.
- The system must not provide corrections or reversals for completed runs.
- The system must display a confirmation message upon success.

## Security / trust-boundary notes
- Payroll data is stored in the app's own database and not shared with external systems.
- The employer must be signed in to run or view payroll, and can only reach their own employments and months; see [UC-003](UC-003-Employer-Accounts-and-Secure-Access.md).

## Validation plan
- **Acceptance: daily work details are accepted and saved [SQLite; unit (no database)]**: `tests/integration/test_payroll_api.py::test_entries_are_stored_as_submitted`; `tests/unit/test_payroll_service.py::TestPayrollService::test_entries_are_saved_as_submitted`.
- **Acceptance: four normal-case hour categories are distinct [SQLite; unit (no database)]**: `tests/integration/test_sqlalchemy_payroll_repository.py::test_every_agreed_category_is_accepted_by_the_constraint`; `tests/unit/test_payroll_calculation.py::TestPayrollCalculation::test_monthly_totals_sum_each_category`.
- **Acceptance: hours are calculated from times minus unpaid breaks [unit (no database); SQLite]**: `tests/unit/test_payroll_calculation.py::TestPayrollCalculation::test_entry_from_times_derives_the_paid_minutes_and_keeps_the_times`; `tests/integration/test_payroll_api.py::test_entries_are_stored_as_submitted`.
- **Acceptance: public holidays are identified and paid at the correct rate [unit (no database); SQLite]**: `tests/unit/test_payroll_calculation.py::TestPayrollCalculation::test_work_on_a_public_holiday_is_classified_as_public_holiday_worked`; `tests/integration/test_payroll_api.py::test_public_holiday_work_is_stored_with_the_holiday_category`.
- **Acceptance: remaining holiday balance is derived from entitlement and prior runs [unit (no database); SQLite]**: `tests/unit/test_payroll_service.py::TestPayrollService::test_first_run_starts_from_the_prorated_entitlement`; `tests/unit/test_payroll_service.py::TestPayrollService::test_later_run_continues_from_the_prior_balance`; `tests/integration/test_payroll_api.py::test_the_balance_carries_from_one_run_to_the_next`.
- **Acceptance: 2026 deduction rates are applied [unit (no database)]**: `tests/unit/test_payroll_golden.py::TestPayrollGolden::test_payslip_lines_match_workbook`; `tests/unit/test_payroll_calculation.py::TestPayrollCalculation::test_calculate_employee_deductions`.
- **Unit test: NBU threshold boundary [unit (no database)]**: `tests/unit/test_minutes_and_holiday.py::TestNbuThreshold::test_threshold_is_480_minutes` (479 minutes is false, 480 and 600 minutes are true).
- **Unit test: expense reimbursements do not inflate the AHV-liable gross wage [unit (no database)]**: `tests/unit/test_payroll_calculation.py::TestPayrollCalculation::test_generate_payslip` (it uses a CHF 50 expense reimbursement; gross wage and the AHV deduction are calculated without it, and it is added to the net payout).
- **Acceptance: employee annual gross limit is enforced for this employer [unit (no database); SQLite]**: `tests/unit/test_payroll_service.py::TestPayrollService::test_rejects_a_run_that_exceeds_the_employee_limit`; `tests/integration/test_payroll_api.py::test_wages_from_another_employer_do_not_count_towards_the_employee_limit`; `tests/integration/test_payroll_api.py::test_a_second_employments_later_months_count_towards_the_employee_limit`.
- **Acceptance: employer annual gross limit is enforced [unit (no database); SQLite]**: `tests/unit/test_payroll_service.py::TestPayrollService::test_rejects_a_run_that_exceeds_the_employer_limit`; `tests/integration/test_sqlalchemy_payroll_repository.py::test_employer_limit_sums_all_of_its_employees`.
- **Acceptance: both limits count the whole calendar year [SQLite]**: `tests/integration/test_sqlalchemy_payroll_repository.py::test_gross_to_date_counts_every_month_of_the_year`; `tests/integration/test_sqlalchemy_payroll_repository.py::test_gross_to_date_ignores_other_years`.
- **Acceptance: duplicate months and skipped months are rejected [SQLite; unit (no database)]**: `tests/integration/test_payroll_api.py::test_posting_the_same_month_again_is_a_4xx_and_duplicates_nothing`; `tests/integration/test_payroll_api.py::test_months_must_follow_one_another`; `tests/unit/test_payroll_service.py::TestPayrollService::test_a_skipped_month_is_rejected`.
- **Acceptance: a run after the employment end month is rejected [SQLite; unit (no database)]**: `tests/integration/test_payroll_api.py::test_a_run_after_the_end_month_is_a_4xx_and_saves_nothing`; `tests/unit/test_payroll_service.py::TestPayrollService::test_a_run_after_the_end_month_is_rejected_and_nothing_is_saved`.
- **Acceptance: entry dates use inclusive employment boundaries [SQLite; unit (no database)]**: `tests/integration/test_payroll_api.py::test_entries_on_the_first_and_last_day_of_the_employment_are_saved`; `tests/integration/test_payroll_api.py::test_an_entry_outside_the_employment_is_a_4xx_and_saves_nothing`; `tests/unit/test_payroll_service.py::TestPayrollService::test_entries_on_the_start_and_end_dates_are_accepted`; `tests/unit/test_payroll_service.py::TestPayrollService::test_an_entry_before_the_start_date_is_rejected_and_nothing_is_saved`; `tests/unit/test_payroll_service.py::TestPayrollService::test_an_entry_after_the_end_date_is_rejected_and_nothing_is_saved`.
- **Acceptance: database error text is not shown [SQLite; the PostgreSQL variant was skipped locally (no TEST_POSTGRES_URL) and is run by CI]**: `tests/integration/test_payroll_repository_errors.py::test_invalid_category_raises_invalid_payroll_input_and_persists_nothing`; `tests/integration/test_sqlalchemy_payroll_repository.py::test_a_constraint_failure_does_not_pass_on_the_database_text`. PARTLY covered: no test asserts the fixed message, and one test would pass on an empty message.
- **Acceptance: an empty month produces a payslip without hours [SQLite; unit (no database)]**: `tests/integration/test_payroll_api.py::test_an_empty_month_is_saved_with_a_snapshot_and_a_zero_payslip`; `tests/unit/test_payroll_service.py::TestPayrollService::test_a_month_without_entries_is_still_a_run_with_an_empty_payslip`.
- **Acceptance: entries, snapshot, monthly record and payslip are saved together [SQLite]**: `tests/integration/test_payroll_api.py::test_posting_a_month_saves_entries_snapshot_record_and_payslip`; `tests/integration/test_sqlalchemy_payroll_repository.py::test_saves_explicit_run_inputs_atomically`.
- **Acceptance: rejected runs persist nothing [SQLite]**: `tests/integration/test_payroll_api.py::test_annual_limit_breach_is_a_4xx_and_saves_nothing`; `tests/integration/test_payroll_api.py::test_overlapping_entries_are_a_4xx_and_save_nothing`; `tests/integration/test_sqlalchemy_payroll_repository.py::test_invalid_holiday_balance_rolls_back_everything`.
- **Acceptance: sick-pay and other exception-management workflows are not implemented**: scope statement, not testable. No runtime test is claimed.
- **Acceptance: corrections and reversals are not provided**: scope statement, not testable. No runtime test is claimed.
- **Acceptance: a confirmation message is displayed upon success**: not covered. The endpoint currently returns `monthly_record_id`, `gross_wage` and `net_payout` only. This is an open gap tracked by the `payslip-response` task.

## Open questions / assumptions
- Assumption: The employer has all required details (e.g., daily hours) at hand.
- Assumption: The first run uses the employment's configured holiday entitlement as its opening balance; later runs use the immediately prior persisted run for the same employment, whatever its year (ADR-004 Amendment 1 item 9; dormant while only the 2026 ruleset exists).
- Assumption: A completed monthly run is immutable until a separate correction workflow is designed and approved.
- Open question: Should the system support bulk import of monthly hours in the future?

## Notes for implementation
- Use the `PayrollService` to handle payroll calculations.
- Ensure all validations are performed before saving to the database.
- Save and freeze the run snapshot (ADR-004 Amendment 2) in the same transaction as the monthly record and payslip.
- Keep sick-pay, accident, and other exception rules in a future dedicated use case; they are not normal-case payroll categories here.

## Known limitations
- **Sunday work:** NAV Haushalt BS § 27 requires a 50% supplement for work on a Sunday. The app does not apply it; a Sunday entry is paid at the normal rate, and the app does not validate Sunday entries.
- **Written-contract exception:** the app does not support a written contract in which the supplement is built into a higher wage.
- **Age-dependent AHV rules:** no birth date is stored, so the AHV rules from reference age and up to age 25 are not applied; every employee gets the full contributions. UC-001 lists them as out of scope.
- **Sick pay:** the app has no category for sick-leave hours. The Basel household NAV requires the employer to keep paying the wage while the employee is ill (one month in the first service year, more later; see [the reference guide](../reference/Employing_Household_Help_Basel.md#if-your-employee-is-ill-sick-pay)), so in a month with sick days the gross wage, the deductions, the payslip and the annual totals are too low.
- **Monthly CHF 1,890:** the AKBS household-help page names CHF 1,890 a month as a limit, while [Merkblatt 2.07](https://www.ahv-iv.ch/p/2.07.d) ties it to the pension-fund rule for jobs shorter than a year. The app does not check it, and the question to AKBS (contact in [the reference guide](../reference/Employing_Household_Help_Basel.md)) is open.
- **Corrections:** a saved month is final. Corrections, reversals and overpayment adjustments are not supported.
- **Ruleset:** the run snapshot stores the ruleset version only. A run reproduces correctly only while a published ruleset is never edited in place (ADR-002).
- **Immutability:** it is enforced in the application. Direct SQL can still edit stored rows.
- **Period snapshots:** there are none. Each run starts from the previous run's closing holiday balance.
