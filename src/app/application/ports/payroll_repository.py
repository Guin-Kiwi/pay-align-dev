from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True)
class MonthlyRecordInput:
    employment_id: int
    employee_id: int
    employer_id: int
    month: int
    year: int
    cash_bonus_cents: int
    expense_reimbursements_cents: int


@dataclass(frozen=True)
class WorkEntryInput:
    work_date: date
    category: str
    start_time: time | None
    end_time: time | None
    unpaid_break_minutes: int
    paid_minutes: int


@dataclass(frozen=True)
class PayrollSnapshotInput:
    hourly_wage_cents: int
    weekly_minutes: int
    holiday_weeks: int
    ruleset_version: str
    worked_minutes: int
    worked_public_holiday_minutes: int
    paid_holiday_minutes: int
    paid_public_holiday_minutes: int
    holiday_balance_minutes: int


@dataclass(frozen=True)
class PayslipInput:
    gross_wage_cents: int
    ahv_deduction_cents: int
    alv_deduction_cents: int
    tax_deduction_cents: int
    nbu_deduction_cents: int
    net_payout_cents: int
    employer_ahv_cents: int
    employer_alv_cents: int
    employer_fak_cents: int
    employer_bu_cents: int
    admin_charge_cents: int
    total_employer_cost_cents: int


@dataclass(frozen=True)
class PriorRun:
    monthly_record_id: int
    year: int
    holiday_balance_minutes: int


@dataclass(frozen=True)
class SavedPayrollRun:
    monthly_record_id: int
    payslip_id: int


class PayrollRepositoryPort:
    """Persistence port for explicit, integer-based payroll values."""

    def save_payroll_run(
        self,
        record: MonthlyRecordInput,
        entries: tuple[WorkEntryInput, ...],
        snapshot: PayrollSnapshotInput,
        payslip: PayslipInput,
    ) -> SavedPayrollRun:
        raise NotImplementedError

    def save_snapshot(
        self, record_id: int, snapshot: PayrollSnapshotInput
    ) -> int:
        raise NotImplementedError

    def employee_gross_to_date(self, employee_id: int, year: int) -> int:
        raise NotImplementedError

    def employer_gross_to_date(self, employer_id: int, year: int) -> int:
        raise NotImplementedError

    def prior_run(self, employment_id: int) -> PriorRun | None:
        raise NotImplementedError