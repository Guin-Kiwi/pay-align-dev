# PayAlign

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**PayAlign** is a payroll management system for private household employers in Basel-Stadt. It simplifies the process of calculating monthly pay, applying social insurance and tax deductions, and generating payslips.

### Monthly payroll saving (UC-002)

`POST /api/v1/monthly-payroll` calculates one month and saves the daily entries,
a run snapshot, the monthly record and the payslip in one transaction.
The request takes an `employment_id`, the year and month, the cash bonus, the expense
reimbursements and the work entries; the employment (employer, employee, wage, weekly
hours, holiday weeks and dates) is read from the saved setup in the `employments` table, and an unknown
`employment_id` is a 404 before anything is saved.
The run snapshot is defined in [ADR-004 Amendment 2](docs/adr/ADR-004-payroll-entry-snapshots-and-holiday-balance.md#amendment-2-2026-10-20).

Run order, empty months, daily entries, public holidays and the known limitations are
specified in [UC-002](docs/specs/UC-002-Process-the-Monthly-Employment.md); rates and
limits are in [calculations.md](docs/reference/calculations.md).
The saved-payslip view and its limitations are described in
[UC-003 Amendment 6](docs/specs/UC-003-Employer-Accounts-and-Secure-Access.md#known-limitations).

## Project documentation

- [Project context, setup and commands](docs/PROJECT.md)
- [Current tasks](docs/TASKS.md)
- [Employment setup (UC-001)](docs/specs/UC-001-Set-Up-an-Employment.md)

The [AI-SDLC template guidance](docs/TEMPLATE.md) is maintained separately.
Template credit: Andreas Martin and Sandro Schwander (FHNW), CC BY 4.0;
see [LICENSE](LICENSE).
