# docs/reference/calculations.md

## 1. 2026 Domain Constants (Rates)
All rates are applied against the AHV-liable Gross Wage unless otherwise specified.

**Employee Deductions (Withheld from pay):**
* AHV/IV/EO: 5.3%
* ALV: 1.1%
* Simplified-Procedure Tax: 5.0%
* VAvplus NBU (Non-occupational accident): 1.432% (Applied conditionally)

**Employer Costs (Paid in addition to gross wage):**
* AHV/IV/EO: 5.3%
* ALV: 1.1%
* FAK (Family Allowances): 1.65%
* AKBS Administration Charge: 5.0% of the calculated Employer AHV/IV/EO contribution
* VAvplus BU (Occupational accident): 0.505%

## 2. Calculation Logic & Formulas

### Step A: Calculate AHV-Liable Gross Wage
The foundation for all social deductions is the AHV-liable gross wage, which includes all worked hours, paid leave, holiday premiums, and cash bonuses. Expenses are strictly excluded from this calculation.

* Base Pay = (Hours Worked + Paid Holiday Hours + Paid Public-Holiday Hours) * Gross Hourly Wage
* Statutory Holiday Premium = Holiday Worked Hours * Gross Hourly Wage * 0.5
* **Gross Wage = Base Pay + Statutory Holiday Premium + Cash Bonus**

### Step B: Calculate Employee Deductions
Calculate individual deductions based on the Gross Wage.

* AHV Deduction = Gross Wage * 0.053
* ALV Deduction = Gross Wage * 0.011
* Tax Deduction = Gross Wage * 0.05
* NBU Deduction = Gross Wage * 0.01432 (Applies ONLY IF the Employment's regular weekly hours are 8 or greater)
* **Total Employee Deductions = AHV Deduction + ALV Deduction + Tax Deduction + (NBU Deduction if applicable)**

### Step C: Calculate Net Payout to Employee
Reimbursements are added after taxes and deductions are calculated.

* **Net Payout = Gross Wage - Total Employee Deductions + Documented Expense Reimbursements**

### Step D: Calculate Employer Costs
Calculate the employer's share of social contributions.

* Employer AHV = Gross Wage * 0.053
* Employer ALV = Gross Wage * 0.011
* Employer FAK = Gross Wage * 0.0165
* Employer BU = Gross Wage * 0.00505
* Admin Charge = Employer AHV * 0.05
* **Total Employer Social Costs = Employer AHV + Employer ALV + Employer FAK + Employer BU + Admin Charge**

### Step E: Calculate Total Monthly Administrative Cost
An administrative total summarizing the full cost to the employer for the month.

* **Total Employer Cost = Gross Wage + Total Employer Social Costs + Documented Expense Reimbursements**

## 3. Validation Rules & Guardrails
Before persisting a monthly payroll run, the service must validate the resulting cumulative totals against strict cantonal limits.

* **Employee Limit Check:** The cumulative `Gross Wage` for a single Employee within the calendar year must be <= CHF 22,680.
* **Employer Limit Check:** The cumulative `Gross Wage` across ALL Employees under the single Employer within the calendar year must be <= CHF 60,480.
* **Holiday Balance Tracker:** `Remaining Holiday Balance = Previous Balance - Paid Holiday Hours`. (Ensure the system tracks this accurately across months).
