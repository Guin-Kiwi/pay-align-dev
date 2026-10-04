# ADR-002-versioned-akbs-payroll-rules

## Status
Proposed

## Context
PayAlign calculates payroll under the Basel-Stadt AKBS simplified procedure. Contribution rates, annual limits, holiday treatment, and other legal rules can change over time. Recalculating historical payroll with silently changed constants would undermine auditability and user trust.

The current 2026 rules are described in `docs/reference/calculations.md` and supported by `docs/reference/Employing_Household_Help_Basel.md` and the 2026 workbook.

## Alternatives
- Keep rates as unversioned global constants: rejected because a later update could change the meaning of existing payroll records.
- Query external authorities during every calculation: rejected because calculations must remain deterministic and the application is local-first.
- Rebuild historical results whenever rates change: rejected because historical payroll must remain reproducible.

## Decision
Payroll calculations use an explicit ruleset version, initially the 2026 AKBS ruleset. The ruleset includes rates, annual limits, holiday and public-holiday treatment, eligibility thresholds, and the source-review date. A future ruleset is added as a new version; it must not silently alter results produced under an earlier version. The current 2026 values are maintained in the domain/reference artifacts and require human review when changed.

This ADR is proposed for human approval. The apparent source wording discrepancy around the employee AHV/IV/EO and ALV percentages must be resolved during review; the calculation reference and current use-case acceptance criteria currently use 5.3% plus 1.1%.

## Consequences
- Payroll records need to retain or resolve the ruleset version used for calculation.
- Domain tests can assert exact behavior for a named ruleset.
- Annual rule updates require a new ruleset and review rather than editing historical behavior in place.
- External legal-source verification remains a maintenance responsibility.

## Supersedes
none
