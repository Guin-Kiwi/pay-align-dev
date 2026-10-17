# ADR-004-payroll-entry-snapshots-and-holiday-balance

## Status
Accepted (amended: see Amendment 1)

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

## Amendment 1 (2026-10-16)

Approval: AYLA PROPOSES; review by Nano and Aaron in this PR.

The following decisions amend this ADR:

1. Holiday entitlement and the derived holiday balance are counted in whole
   minutes, not float hours.
2. Yearly entitlement is `holiday_weeks` (4 or 5) × `weekly_minutes`. This
   replaces the day-based `holiday_entitlement`, and the first run starts from
   this figure.
3. For an employment starting or ending during the year, entitlement is
  pro-rated by the days under contract in the calendar year, with both the
  start and end dates counted, divided by 365, and rounded half-up once to
  whole minutes (OR 329a para. 3). Source: team decision of 16 October 2026,
  recorded in the UC-001 spec (PR #17).
4. The app accepts 2026 only (ADR-002). Later years, including 366 days in
   2028, are a known limitation; cross-year carry-over remains dormant until a
   second ruleset exists.
5. The pro-rated entitlement is rounded half-up once to whole minutes, as
  specified by ADR-003.
6. There are four hour categories, not three: worked; worked on a public
  holiday (50% premium); paid holiday; paid public-holiday leave (no work
  done).
7. Hours live only in the daily entries (`work_entries`); monthly hour totals
  are derived from them and are not stored on `monthly_records`. Time is
  recorded in whole minutes.
8. The snapshot refers to the run's persisted `work_entries`, which are
  immutable once saved, instead of copying them. It freezes the employment
  parameters, the ruleset version, the minute totals per category and the
  holiday balance after the run.
9. Carry-over: the next run reads the previous run for the same employment,
  whatever its year. The first run of a new year adds that year's pro-rated
  entitlement, and the entitlement of any skipped year, to the previous
  closing balance. Unused holiday does not lapse at year end. This amends the
  "same calendar year" wording in the Decision. It stays dormant while only
  the 2026 ruleset exists (see item 4).

### Assumptions

- The 4-or-5 rule for `holiday_weeks` is determined in the domain and API, not
  by a database CHECK.
- Cross-year carry-over is not active while only the 2026 ruleset exists.

### Amendment consequences

- Holiday entitlement and derived balances require integer-minute arithmetic
  and persistence rather than float-hour arithmetic.
- The employment snapshot must retain `holiday_weeks`, `weekly_minutes`,
  `start_date`, and `end_date` so the pro-rated entitlement can be reproduced.
- The calendar-year denominator is fixed at 365 for the 2026-only application;
  leap-year handling is deferred with later rulesets.
- The payroll domain code that treats `public_holiday_hours` as hours worked on
  a holiday changes to the category model.
