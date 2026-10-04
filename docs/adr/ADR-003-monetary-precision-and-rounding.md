# ADR-003-monetary-precision-and-rounding

## Status
Proposed

## Context
Payroll calculations combine hourly wages, percentages, reimbursements, and annual limits. Binary floating-point arithmetic can produce non-reproducible cent values, while an undefined rounding point can make payslips and tests disagree.

## Alternatives
- Use binary floating-point values: rejected because small representation errors can affect statutory deductions and totals.
- Round only the final net payout: rejected because the displayed deduction lines would not necessarily sum to the displayed totals.
- Round to Swiss cash increments of CHF 0.05: rejected for now because payroll amounts and statutory deductions are accounting values, not cash-register change, and the requirements do not call for cash rounding.

## Decision
Use decimal arithmetic for all monetary calculations. Store and expose monetary values at centime precision. Round each monetary deduction or contribution line to CHF 0.01 using a single documented half-up policy, then calculate displayed subtotals and totals from those rounded lines. Expense reimbursements remain separate from the AHV-liable wage base and are added to the final payout without being included in statutory deduction calculations.

This ADR is proposed for human approval.

## Consequences
- Domain calculation code must not use binary floating-point for money.
- Tests can assert exact centime values and line-item reconciliation.
- The rounding policy must be applied consistently in domain, persistence, and presentation mappings.
- Changing the policy would be a compatibility decision requiring a new ADR or a superseding ADR.

## Supersedes
none
