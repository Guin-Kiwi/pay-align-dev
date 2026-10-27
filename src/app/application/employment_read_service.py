from dataclasses import dataclass

from src.app.application.ports.employment_read_repository import (
    CompletedMonth,
    EmployeeDetails,
    EmploymentOverview,
    EmploymentReadRepository,
    SavedPayslip,
)
from src.app.domain.constants import RULES_YEAR


@dataclass(frozen=True)
class YearMonth:
    year: int
    month: int


@dataclass(frozen=True)
class MonthHistory:
    months: list[CompletedMonth]
    next_month: YearMonth | None


class EmploymentReadService:
    def __init__(self, repository: EmploymentReadRepository):
        self.repository = repository

    def list_employments(self, account_id: int) -> list[EmploymentOverview]:
        return self.repository.list_employments(account_id)

    def get_employment(
        self, account_id: int, employment_id: int
    ) -> EmploymentOverview | None:
        return self.repository.get_employment(account_id, employment_id)

    def get_employee(self, account_id: int, employee_id: int) -> EmployeeDetails | None:
        return self.repository.get_employee(account_id, employee_id)

    def month_history(
        self, account_id: int, employment_id: int
    ) -> MonthHistory | None:
        employment = self.repository.get_employment(account_id, employment_id)
        if employment is None:
            return None
        months = self.repository.list_months(account_id, employment_id)
        if months:
            latest = months[-1]
            year, month = (
                (latest.year + 1, 1)
                if latest.month == 12
                else (latest.year, latest.month + 1)
            )
        else:
            year, month = employment.start_date.year, employment.start_date.month
        end = employment.end_date
        next_month = (
            YearMonth(year, month)
            if year == RULES_YEAR and (end is None or (year, month) <= (end.year, end.month))
            else None
        )
        return MonthHistory(months=months, next_month=next_month)

    def saved_payslip(
        self, account_id: int, employment_id: int, year: int, month: int
    ) -> SavedPayslip | None:
        return self.repository.get_payslip(account_id, employment_id, year, month)
