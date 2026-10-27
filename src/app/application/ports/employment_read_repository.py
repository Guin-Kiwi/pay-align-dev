from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.app.domain.payslip import Payslip


@dataclass(frozen=True)
class EmploymentOverview:
    id: int
    employee_name: str
    employee_ahv_number: str
    start_date: date
    end_date: date | None


@dataclass(frozen=True)
class CompletedMonth:
    monthly_record_id: int
    year: int
    month: int


@dataclass(frozen=True)
class SavedPayslip:
    payslip: Payslip
    holiday_balance_minutes: int
    hourly_wage: Decimal
    cash_bonus: Decimal
    expense_reimbursements: Decimal
    worked_minutes: int
    public_holiday_worked_minutes: int
    annual_holiday_taken_minutes: int
    public_holiday_taken_minutes: int


class EmploymentReadRepository(ABC):
    @abstractmethod
    def list_employments(self, account_id: int) -> list[EmploymentOverview]:
        ...

    @abstractmethod
    def get_employment(
        self, account_id: int, employment_id: int
    ) -> EmploymentOverview | None:
        ...

    @abstractmethod
    def list_months(self, account_id: int, employment_id: int) -> list[CompletedMonth]:
        ...

    @abstractmethod
    def get_payslip(
        self, account_id: int, employment_id: int, year: int, month: int
    ) -> SavedPayslip | None:
        ...
