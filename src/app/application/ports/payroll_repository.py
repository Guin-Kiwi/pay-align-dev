from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, time

from src.app.domain.hour_categories import MinuteTotals


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
class EmploymentTerms:
    hourly_wage_cents: int
    weekly_minutes: int
    holiday_weeks: int
    employment_start_date: date
    employment_end_date: date | None


@dataclass(frozen=True)
class StoredEmployment:
    employer_id: int
    employee_id: int
    terms: EmploymentTerms


@dataclass(frozen=True)
class RunSnapshot:
    employment: EmploymentTerms
    ruleset_version: str
    hours: MinuteTotals
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
    month: int
    holiday_balance_minutes: int


@dataclass(frozen=True)
class SavedPayrollRun:
    monthly_record_id: int
    payslip_id: int


class PayrollRepositoryPort(ABC):
    """Persistence port for explicit, integer-based payroll values."""

    @abstractmethod
    def save_payroll_run(
        self,
        record: MonthlyRecordInput,
        entries: tuple[WorkEntryInput, ...],
        snapshot: RunSnapshot,
        payslip: PayslipInput,
    ) -> SavedPayrollRun:
        ...

    @abstractmethod
    def run_snapshot(self, monthly_record_id: int) -> RunSnapshot | None:
        ...

    @abstractmethod
    def employee_gross_to_date(
        self, employee_id: int, year: int, before_month: int
    ) -> int:
        ...

    @abstractmethod
    def employer_gross_to_date(
        self, employer_id: int, year: int, before_month: int
    ) -> int:
        ...

    @abstractmethod
    def prior_run(self, employment_id: int) -> PriorRun | None:
        ...

    @abstractmethod
    def employment_terms(self, employment_id: int) -> StoredEmployment | None:
        ...
