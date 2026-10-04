# UC-002: Process the Monthly Employment

## 1. Intent
Calculate an employee's monthly pay, apply correct 2026 social insurance and tax deductions, generate a compliant payslip, and persist the data to maintain annual totals for the AKBS declaration [cite: 7, 8, 9, 16].

## 2. Actors
- **Employer:** The user entering the monthly hours and expenses.

## 3. Inputs (`MonthlyRecord`)
- Target month and year.
- Hours worked, paid holiday hours, and paid public-holiday hours [cite: 7].
- Cash bonus amount (optional) [cite: 7, 9].
- Documented expense reimbursements (optional) [cite: 7, 9].

## 4. Main Success Scenario (Flow)
1. User selects an active `Employment` and inputs the `MonthlyRecord` variables.
2. System calculates the **Gross Wage** (Total paid hours × gross hourly wage + cash bonuses) [cite: 7, 9].
3. System calculates **Employee Deductions** based on 2026 rates (AHV/IV/EO, ALV, 5% Tax) [cite: 16].
4. System conditionally applies the NBU deduction if the employment's regular weekly hours are ≥ 8 [cite: 11, 16].
5. System calculates the **Net Payout** (Gross - Deductions + Expense reimbursements) [cite: 7, 9].
6. System calculates **Employer Costs** (AHV/IV/EO, ALV, FAK, Admin charge, VAvplus BU) [cite: 16].
7. System updates the running holiday balance by subtracting the used holiday hours [cite: 8].
8. System persists the `MonthlyRecord` and generated `Payslip`.

## 5. Acceptance Criteria
- **Legal Rate Application:** Calculations must strictly apply the 2026 percentages: 5.3% AHV/IV/EO, 1.1% ALV, and 5% simplified tax for the employee [cite: 16].
- **NBU Threshold Logic:** The 1.432% NBU premium must be deducted *only* if the `Employment` entity specifies 8 or more regular weekly hours [cite: 11, 16].
- **Expense Handling:** Expense reimbursements must be added to the final payout but must *not* be included in the gross wage subject to AHV/IV/EO deductions [cite: 9].
- **Annual Limit Guardrails:** The system must reject the monthly run if the new gross wage causes the employee's annual total to exceed CHF 22,680, or the employer's total annual payroll to exceed CHF 60,480 [cite: 3].
- **Payslip Deliverable:** The output must itemize all allowances, deductions, and display the remaining holiday balance [cite: 8].

## 6. Test Intent (TDD)
- **Unit:** Assert exact mathematical correctness of net pay calculation for an employment *under* 8 hours/week (no NBU).
- **Unit:** Assert exact mathematical correctness of net pay calculation for an employment *over* 8 hours/week (with NBU).
- **Unit:** Assert that expense reimbursements do not inflate the taxable/AHV-liable gross wage base.
- **Unit:** Assert that the service throws an `AnnualLimitExceededError` if a payroll run breaches the CHF 22,680 employee limit.