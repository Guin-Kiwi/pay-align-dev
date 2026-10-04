# UC-002: Process the Monthly Employment

## 1. Intent
Calculate an employee's monthly pay, apply correct 2026 social insurance and tax deductions, generate a compliant payslip, and persist the data to maintain annual totals for the AKBS declaration [cite: 7, 8, 9, 16].

## 2. Actors
- **Employer:** The user entering the monthly hours and expenses.

## 3. Inputs (`MonthlyRecord`)
- Target month and year.
- **Daily work details** for each day of the month:
  - Start time (e.g., `08:00`).
  - End time (e.g., `17:00`).
  - Break duration (e.g., `0.5` hours) and status (paid/unpaid).
- Cash bonus amount (optional) [cite: 7, 9].
- Documented expense reimbursements (optional) [cite: 7, 9].

## 4. Main Success Scenario (Flow)
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

## 5. Acceptance Criteria
- The system must accept **daily work details** (start time, end time, break duration, and paid/unpaid status) as input.
- The system must calculate **hours worked** for each day (end time - start time - unpaid breaks).
- The system must identify public holidays and apply the correct pay rate.
- The system must apply 2026 deduction rates (5.3% AHV/IV/EO, 1.1% ALV, 5% tax, 1.432% NBU if applicable).
- The system must reject monthly runs that exceed annual limits.
- The system must save all data to the database.
- The system must display a confirmation message upon success.

## 6. Out of Scope
- **PDF generation**: Payslips will not be generated as PDFs.
- **Email notifications**: No emails will be sent to the employer or employee.
- **Recurring inputs**: The system will not allow copying hours from previous months.
- **Partial payments**: The system will not handle partial payments for employees who quit mid-month.
- **Overpayment corrections**: The system will not allow corrections for overpayments.

## 7. Future Considerations
- **PDF generation**: May be added in a future iteration for local file storage.
- **In-app notifications**: May be added to remind the employer of pending payroll entries.
- **Recurring inputs**: May be added to simplify monthly payroll processing.
- **Public holiday database**: May be expanded to include regional holidays or custom holidays.

## 6. Test Intent (TDD)
- **Unit:** Assert exact mathematical correctness of net pay calculation for an employment *under* 8 hours/week (no NBU).
- **Unit:** Assert exact mathematical correctness of net pay calculation for an employment *over* 8 hours/week (with NBU).
- **Unit:** Assert that expense reimbursements do not inflate the taxable/AHV-liable gross wage base.
- **Unit:** Assert that the service throws an `AnnualLimitExceededError` if a payroll run breaches the CHF 22,680 employee limit.