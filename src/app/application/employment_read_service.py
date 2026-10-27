from dataclasses import dataclass
from calendar import monthrange
from datetime import date
from decimal import Decimal

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


@dataclass(frozen=True)
class OverviewEmployment:
    employment: EmploymentOverview
    next_month: YearMonth | None
    payslip: SavedPayslip | None


@dataclass(frozen=True)
class PayrollOverview:
    employments: list[OverviewEmployment]
    eligible_count: int
    saved_count: int
    payout_due: Decimal
    estimated_set_aside: Decimal
    employer_cost: Decimal


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

    def payroll_overview(self, account_id: int, year: int, month: int) -> PayrollOverview:
        first = date(year, month, 1)
        last = date(year, month, monthrange(year, month)[1])
        items = []
        for employment in self.repository.list_employments(account_id):
            if employment.start_date > last or (employment.end_date and employment.end_date < first):
                continue
            history = self.month_history(account_id, employment.id)
            if history is None:
                continue
            saved = self.repository.get_payslip(account_id, employment.id, year, month)
            items.append(OverviewEmployment(employment, history.next_month, saved))
        saved_payslips = [item.payslip.payslip for item in items if item.payslip is not None]
        payout = sum((slip.net_payout for slip in saved_payslips), Decimal('0.00'))
        cost = sum((slip.total_employer_cost for slip in saved_payslips), Decimal('0.00'))
        return PayrollOverview(items, len(items), len(saved_payslips), payout, cost - payout, cost)
