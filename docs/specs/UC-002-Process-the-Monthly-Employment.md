# UC-002: Process the Monthly Employment

## Goal
Calculate an employee's monthly pay, apply correct 2026 social insurance and tax deductions, generate a compliant payslip, and persist the data for annual AKBS reporting.

## Business value
This use case automates monthly payroll processing for private household employers, ensuring accurate deductions and compliance with AKBS requirements while reducing manual effort.

## Scope

### In scope
- Inputting daily work details (start time, end time, breaks).
- Calculating gross wage, deductions, and net payout.
- Detecting public holidays and applying correct pay rates.
- Saving the `MonthlyRecord` and `Payslip` to the database.

### Out of scope
- PDF generation for payslips.
- Email notifications to the employer or employee.
- Recurring inputs (e.g., copying hours from previous months).
- Partial payments for employees who quit mid-month.
- Overpayment corrections.

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
   - Calculates **hours worked** for each day (end time - start time - unpaid breaks).
   - Identifies public holidays in the month and applies the correct pay rate.
   - Calculates **Gross wage** (total hours × hourly rate + bonus).
   - Calculates **Deductions** (AHV/IV/EO, ALV, 5% tax, NBU if weekly hours ≥ 8).
   - Calculates **Net payout** (gross wage - deductions + expenses).
5. The system checks if the monthly run exceeds annual limits (CHF 22,680 for employee, CHF 60,480 for employer).
6. The system saves the `MonthlyRecord` and `Payslip` to the database.
7. The system displays a **confirmation message** (e.g., "Payroll processed successfully").

## Alternate / edge flows
- If the monthly run exceeds annual limits, the system warns the employer and rejects the submission.

## Errors / failure cases
- Invalid input (e.g., negative hours).
- Missing required fields (e.g., daily work details).
- Exceeding annual limits.

## Acceptance criteria
- The system must accept **daily work details** as input.
- The system must calculate **hours worked** for each day (end time - start time - unpaid breaks).
- The system must identify public holidays and apply the correct pay rate.
- The system must apply 2026 deduction rates (5.3% AHV/IV/EO, 1.1% ALV, 5% tax, 1.432% NBU if applicable).
- The system must reject monthly runs that exceed annual limits.
- The system must save all data to the database.
- The system must display a confirmation message upon success.

## Security / trust-boundary notes
- All data is stored locally and not shared with external systems.
- The employer must authenticate to access the system (future consideration).

## Validation plan
- **Unit Tests**: Assert exact mathematical correctness of net pay calculation for employments *under* and *over* 8 hours/week.
- **Unit Tests**: Assert that expense reimbursements do not inflate the taxable/AHV-liable gross wage base.
- **Unit Tests**: Assert that the service throws an `AnnualLimitExceededError` if a payroll run breaches the CHF 22,680 employee limit.

## Open questions / assumptions
- Assumption: The employer has all required details (e.g., daily hours) at hand.
- Open question: Should the system support bulk import of monthly hours in the future?

## Notes for implementation
- Use the `PayrollService` to handle payroll calculations.
- Ensure all validations are performed before saving to the database.