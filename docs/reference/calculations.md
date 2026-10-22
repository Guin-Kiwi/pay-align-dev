# docs/reference/calculations.md

## 1. 2026 Domain Constants (Rates)
The values are defined once, in [`src/app/domain/constants.py`](../../src/app/domain/constants.py); the formulas below use their names. Why a value is what it is lives in its source ([Employing_Household_Help_Basel.md](Employing_Household_Help_Basel.md)) or in the use case or ADR that decided it.

All rates are applied against the AHV-liable Gross Wage unless otherwise specified.

**Employee Deductions (Withheld from pay):**
* AHV/IV/EO: `AHV_RATE`
* ALV: `ALV_RATE`
* Simplified-Procedure Tax: `TAX_RATE`
* VAvplus NBU (Non-occupational accident): `NBU_RATE` (Applied conditionally)

**Employer Costs (Paid in addition to gross wage):**
* AHV/IV/EO: `AHV_RATE`
* ALV: `ALV_RATE`
* FAK (Family Allowances): `FAK_RATE`
* AKBS Administration Charge: `ADMIN_CHARGE_RATE` of the total AHV/IV/EO contribution (employee plus employer, `AHV_TOTAL_RATE`), estimating AKBS's invoice, which AKBS rounds to 5 Rappen ([example sheet](https://cms.ak-bs.ch/fileadmin/downloads/2026hd-beispiel-bruttonetto.pdf))
* VAvplus BU (Occupational accident): `BU_RATE`

## 2. Calculation Logic & Formulas

### Step A: Calculate AHV-Liable Gross Wage
The foundation for all social deductions is the AHV-liable gross wage, which includes all worked hours, paid leave, holiday premiums, and cash bonuses. Expenses are strictly excluded from this calculation.

* Base Pay = (Hours Worked + Paid Holiday Hours + Paid Public-Holiday Hours) * Gross Hourly Wage
* Statutory Holiday Premium = Holiday Worked Hours * Gross Hourly Wage * 0.5
* **Gross Wage = Base Pay + Statutory Holiday Premium + Cash Bonus**

Hours Worked includes both categories of work: normal worked hours and hours worked on a public holiday (Holiday Worked Hours). The app records them as separate categories ([ADR-004 Amendment 1](../adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-1-2026-10-16), item 6). The Statutory Holiday Premium is the extra 50% on Holiday Worked Hours only, so those hours are paid at 1.5 times the hourly wage in total.

In terms of the entry categories in `src/app/domain/hour_categories.py` ([ADR-004 Amendment 1](../adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-1-2026-10-16), item 6), Hours Worked is `worked` together with `public_holiday_worked`, Holiday Worked Hours is `public_holiday_worked`, Paid Holiday Hours is `annual_holiday_taken`, and Paid Public-Holiday Hours is `public_holiday_taken`.

### Step B: Calculate Employee Deductions
Calculate individual deductions based on the Gross Wage.

* AHV Deduction = Gross Wage * `AHV_RATE`
* ALV Deduction = Gross Wage * `ALV_RATE`
* Tax Deduction = Gross Wage * `TAX_RATE`
* NBU Deduction = Gross Wage * `NBU_RATE` (Applies ONLY IF the Employment's regular weekly minutes are `NBU_MIN_WEEKLY_MINUTES` or more)
* **Total Employee Deductions = AHV Deduction + ALV Deduction + Tax Deduction + (NBU Deduction if applicable)**

### Step C: Calculate Net Payout to Employee
Reimbursements are added after taxes and deductions are calculated.

* **Net Payout = Gross Wage - Total Employee Deductions + Documented Expense Reimbursements**

### Step D: Calculate Employer Costs
Calculate the employer's share of social contributions.

* Employer AHV = Gross Wage * `AHV_RATE`
* Employer ALV = Gross Wage * `ALV_RATE`
* Employer FAK = Gross Wage * `FAK_RATE`
* Employer BU = Gross Wage * `BU_RATE`
* Admin Charge = Gross Wage * `AHV_TOTAL_RATE` * `ADMIN_CHARGE_RATE`
* **Total Employer Social Costs = Employer AHV + Employer ALV + Employer FAK + Employer BU + Admin Charge**

### Step E: Calculate Total Monthly Administrative Cost
An administrative total summarizing the full cost to the employer for the month.

* **Total Employer Cost = Gross Wage + Total Employer Social Costs + Documented Expense Reimbursements**

## 3. Validation Rules & Guardrails
Before persisting a monthly payroll run, the service must validate the resulting cumulative totals against strict cantonal limits.

* **Employee Limit Check:** The cumulative `Gross Wage` paid to a single Employee by the Employer (across all of that Employee's Employments with this Employer) within the calendar year must be <= `EMPLOYEE_GROSS_LIMIT`. Wages paid by other employers are not counted.
* **Employer Limit Check:** The cumulative `Gross Wage` across ALL Employees under the single Employer within the calendar year must be <= `EMPLOYER_GROSS_LIMIT`.
* **Holiday Balance:** `Remaining Holiday Balance = Previous Balance - Paid Holiday Minutes`; a run that takes the balance below zero is rejected.

## 4. Holiday Entitlement
Decided in [ADR-004 Amendment 1](../adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-1-2026-10-16), items 1 to 5; implemented in `src/app/domain/holiday_balance.py`. All values are whole minutes.

* **Contract Days** = days of the employment in `RULES_YEAR`, counting both the start and the end date (no end date: up to 31 December)
* **Yearly Entitlement** = Holiday Weeks (one of `ALLOWED_HOLIDAY_WEEKS`) * Weekly Minutes * Contract Days / `DAYS_IN_RULES_YEAR`, rounded half-up once to whole minutes (OR 329a para. 3)
* An employment that covers the whole year gets the full Holiday Weeks * Weekly Minutes (4 × 6:30 = 26:00).
* The first run starts from the Yearly Entitlement; later runs start from the previous run's Remaining Holiday Balance.
