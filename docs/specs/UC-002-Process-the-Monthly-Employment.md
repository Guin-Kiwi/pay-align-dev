# UC-002: Process the Monthly Employment

## Goal
Calculate an employee's monthly pay, apply correct 2026 social insurance and tax deductions, generate a compliant payslip, and persist the data for annual AKBS reporting.

## Business value
This use case automates monthly payroll processing for private household employers, ensuring accurate deductions and compliance with AKBS requirements while reducing manual effort.

## Scope

### In scope
- Inputting and saving daily work details (start time, end time, breaks, and paid/unpaid status).
- Recording three normal-case hour categories: worked hours, paid holiday hours, and paid public-holiday hours.
- Calculating gross wage, deductions, and net payout.
- Detecting public holidays and applying correct pay rates.
- Saving the entries, a frozen per-run input snapshot, the `MonthlyRecord`, and the `Payslip` to the database.
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
2. The employer selects an active `Employment` and inputs **daily work details** (start time, end time, break duration, and paid/unpaid status) for the month.
3. The employer optionally enters a cash bonus and expense reimbursements.
4. The system:
   - Stages the daily entries for the run without persisting them.
   - Classifies the three normal-case hour categories: worked, paid holiday, and paid public-holiday.
   - Calculates **worked hours** for each day (end time - start time - unpaid breaks).
   - Identifies public holidays in the month and applies the correct pay rate.
   - Derives the remaining holiday balance from the employment's configured entitlement and prior persisted runs, less paid holiday hours.
   - Freezes a snapshot of the entries, employment parameters, and named ruleset version for this run.
   - Calculates **Gross wage** (worked and paid holiday/public-holiday hours × hourly rate + applicable supplements + bonus).
   - Calculates **Deductions** (AHV/IV/EO, ALV, 5% tax, NBU if weekly hours ≥ 8).
   - Calculates **Net payout** (gross wage - deductions + expenses).
5. The system checks if the monthly run exceeds annual limits (CHF 22,680 for employee, CHF 60,480 for employer), rejects duplicate months, and verifies the derived holiday balance is valid.
6. The system saves the staged entries, frozen snapshot, `MonthlyRecord`, and `Payslip` in one transaction.
7. The system displays a **confirmation message** (e.g., "Payroll processed successfully").

## Alternate / edge flows
- If the monthly run exceeds annual limits, the system warns the employer and rejects the submission.
- If entries overlap, contain negative durations, or contain invalid category combinations, the system rejects the submission before saving.
- If no prior monthly run exists, the system starts from the employment's configured holiday entitlement.
- If the requested month was already processed, the system rejects the submission because corrections are out of scope.

## Errors / failure cases
- Invalid input (e.g., negative hours).
- Missing required fields (e.g., daily work details).
- Exceeding annual limits.
- Duplicate monthly run.
- Invalid or negative derived holiday balance.
- Corrections to a completed run are not supported.

## Acceptance criteria
- The system must accept and save **daily work details** as input.
- The system must represent worked, paid holiday, and paid public-holiday hours as three distinct normal-case categories.
- The system must calculate **hours worked** for each day (end time - start time - unpaid breaks).
- The system must identify public holidays and apply the correct pay rate.
- The system must derive remaining holiday balance from the employment's entitlement and prior persisted runs, less paid holiday hours.
- The system must apply 2026 deduction rates (5.3% AHV/IV/EO, 1.1% ALV, 5% tax, 1.432% NBU if applicable).
- The system must reject monthly runs that exceed annual limits.
- The system must reject duplicate monthly runs.
- The system must save the entries and a frozen per-run snapshot together with the `MonthlyRecord` and `Payslip`.
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
- **Unit Tests**: Assert that the three normal-case hour categories are classified and that holiday balance starts from employment entitlement and decreases only by paid holiday hours.
- **Integration Tests**: Assert that submitted entries and the frozen per-run snapshot are saved atomically with the monthly record and payslip.
- **Integration Tests**: Assert that duplicate months and rejected annual-limit checks persist no entries, snapshot, record, or payslip.
- **Unit Tests**: Assert that the service throws an `AnnualLimitExceededError` if a payroll run breaches the CHF 22,680 employee limit.

## Open questions / assumptions
- Assumption: The employer has all required details (e.g., daily hours) at hand.
- Assumption: The first run uses the employment's configured holiday entitlement as its opening balance; later runs use the immediately prior persisted run for the same employment and calendar year.
- Assumption: A completed monthly run is immutable until a separate correction workflow is designed and approved.
- Open question: Should the system support bulk import of monthly hours in the future?

## Notes for implementation
- Use the `PayrollService` to handle payroll calculations.
- Ensure all validations are performed before saving to the database.
- Save and freeze the input snapshot in the same transaction as the monthly record and payslip.
- Keep sick-pay, accident, and other exception rules in a future dedicated use case; they are not normal-case payroll categories here.
