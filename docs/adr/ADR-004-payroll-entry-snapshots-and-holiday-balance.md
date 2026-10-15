# ADR-004-payroll-entry-snapshots-and-holiday-balance

## Status
Accepted

## Context
Monthly payroll must remain reproducible after submission. The application
needs to retain the daily entries used for a run, preserve the exact inputs
and rules used to calculate the payslip, and prevent later changes from
silently changing an already processed payroll run.

Holiday entitlement is tracked across monthly runs, but a manually editable
balance can drift from the payroll entries. Sick pay is an exception workflow
and is not part of the normal-case monthly payroll slice. Corrections and
overpayment handling are outside the current use case.

## Alternatives

- Recalculate a prior run from the current entries and rules: rejected because
  later edits or rule updates would change historical payroll.
- Store only aggregate monthly hours: rejected because the daily source entries
  are required to explain and reproduce the run.
- Store a manually editable holiday balance: rejected because it can diverge
  from recorded paid holiday hours.
- Add sick-pay or correction workflows now: rejected because they are
  explicitly outside UC-002 and would expand the current slice.

## Decision

For each monthly payroll run, persist the submitted daily entries with exactly
three normal-case hour categories:

1. worked hours;
2. paid holiday hours;
3. paid public-holiday hours.

The run also stores a frozen snapshot of the submitted entries, the
employment parameters, and the named payroll-ruleset version used for the
calculation. The saved `MonthlyRecord` and `Payslip` are calculated from that
snapshot and are immutable through the current use case.

The first run starts from the holiday entitlement configured on the
employment. Each later run derives the remaining holiday balance from the
immediately prior persisted run for that employment and calendar year, less
the current run's persisted paid holiday hours:

`remaining balance = previous balance - paid holiday hours`

Duplicate months, missing prior runs after the first month, and a negative
derived balance are rejected. Sick pay, corrections, reversals, and
overpayment adjustments are out of scope and must not be implied by the
monthly payroll flow.

## Consequences

- Payroll persistence needs daily-entry records and a run snapshot boundary.
- Historical payslips can be reproduced without depending on mutable
  employment data or current rules.
- Holiday balance reporting is derived from recorded payroll history rather
  than maintained as an independent editable value.
- A future correction workflow requires a separate use case and ADR or an
  explicit amendment to this decision.
- The three categories must be validated so negative or overlapping entries
  cannot enter a run.
- Exception handling, including sick pay, requires a separate use case and
  design decision.

## Supersedes

none
