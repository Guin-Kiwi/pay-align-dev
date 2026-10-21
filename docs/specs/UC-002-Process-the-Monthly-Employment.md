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
   - Calculates **Deductions** (AHV/IV/EO, ALV, 5% tax, NBU if weekly hours ≥ 8).
   - Calculates **Net payout** (gross wage - deductions + expenses).
5. The system checks that the month is not after the employment's end month, that the month is the next run in sequence, that every entry is dated within the employment, if the monthly run exceeds annual limits, rejects duplicate months, and verifies the derived holiday balance is valid. The annual limits count the whole calendar year, whatever the month of the run:
   - Employee: CHF 22,680 gross. Only wages from this employer count, across all of the employee's employments with this employer. Wages from other employers do not.
   - Employer: CHF 60,480 gross. All of this employer's employees count.
6. The system saves the staged entries, run snapshot (ADR-004 Amendment 2), `MonthlyRecord`, and `Payslip` in one transaction.
7. The system displays a **confirmation message** (e.g., "Payroll processed successfully").

## Alternate / edge flows
- If the monthly run would take the calendar-year total above the employee or the employer limit, the system warns the employer and rejects the submission.
- If the requested month is after the month in which the employment ends, the system rejects the submission. The end month itself is still processed.
- If an entry is dated before the employment's start date or after its end date, the system rejects the submission. Both dates are inclusive: the start date is the first and the end date the last possible working day.
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
- Duplicate monthly run.
- Invalid or negative derived holiday balance.
- Corrections to a completed run are not supported.

## Acceptance criteria
- The system must accept and save **daily work details** as input.
- The system must represent worked, worked-on-a-public-holiday, paid holiday, and paid public-holiday leave hours as four distinct normal-case categories.
- The system must calculate **hours worked** for each day (end time - start time - unpaid breaks).
- The system must identify public holidays and apply the correct pay rate.
- The system must derive remaining holiday balance from the employment's entitlement and prior persisted runs, less paid holiday hours.
- The system must apply 2026 deduction rates (5.3% AHV/IV/EO, 1.1% ALV, 5% tax, 1.432% NBU if applicable).
- The system must reject a monthly run that takes the employee's calendar-year gross wage from this employer above CHF 22,680, counting every employment of that employee with this employer and no wages from other employers.
- The system must reject a monthly run that takes the calendar-year gross wage of all of this employer's employees above CHF 60,480.
- The system must count the whole calendar year for both limits.
- The system must reject duplicate monthly runs and skipped months.
- The system must reject a run for a month after the employment's end month.
- The system must reject entries dated before the employment's start date or after its end date, both dates inclusive.
- The system must accept a month without entries and produce a payslip without hours.
- The system must save the entries and a run snapshot (ADR-004 Amendment 2) together with the `MonthlyRecord` and `Payslip`.
- The system must not persist any part of a rejected run.
- Sick-pay and other exception-management workflows must not be implemented by this use case.
- The system must not provide corrections or reversals for completed runs.
- The system must display a confirmation message upon success.

## Security / trust-boundary notes
- All data is stored locally and not shared with external systems.
- The employer must authenticate to access the system (future consideration).

## Validation plan
- **Unit Tests**: Assert exact mathematical correctness of net pay calculation for employments *under* and *over* 8 hours/week.
- **Unit Tests**: Assert that expense reimbursements do not inflate the taxable/AHV-liable gross wage base.
- **Unit Tests**: Assert that the four normal-case hour categories are classified and that holiday balance starts from employment entitlement and decreases only by paid holiday hours.
- **Integration Tests**: Assert that submitted entries and the run snapshot (ADR-004 Amendment 2) are saved atomically with the monthly record and payslip.
- **Integration Tests**: Assert that duplicate months and rejected annual-limit checks persist no entries, snapshot, record, or payslip.
- **Unit Tests**: Assert that the service throws an `AnnualLimitExceededError` if a payroll run breaches the CHF 22,680 employee limit or the CHF 60,480 employer limit.
- **Integration Tests**: Assert on the real repository that the employee total ignores other employers' wages (two-employers test), that it adds up two employments of one employee with the same employer including months after the processed one (two-employments test), and that the employer total adds up all of its employees for the whole year.
- **Unit Tests**: Assert that a run after the employment's end month is rejected, that the end month itself is accepted, and that entries on the start date and end date are accepted while the day before the start and the day after the end are rejected.

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
- **Corrections:** a saved month is final. Corrections, reversals and overpayment adjustments are not supported.
- **Ruleset:** the run snapshot stores the ruleset version only. A run reproduces correctly only while a published ruleset is never edited in place (ADR-002).
- **Immutability:** it is enforced in the application. Direct SQL can still edit stored rows.
- **Period snapshots:** there are none. Each run starts from the previous run's closing holiday balance.
