from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.app.application.employment_read_service import EmploymentReadService, YearMonth
from src.app.application.ports.employment_read_repository import SavedPayslip
from src.app.application.ports.payroll_repository import PayrollRepositoryPort
from src.app.domain.constants import EMPLOYEE_GROSS_LIMIT, EMPLOYER_GROSS_LIMIT, RULES_YEAR

CENT = Decimal("0.01")
PAYSLIP_SUMS = (
    "net_payout", "employer_ahv", "employer_alv", "employer_fak", "employer_bu",
    "admin_charge", "total_employer_cost",
)


@dataclass(frozen=True)
class EmployeeEmployment:
    id: int
    start_date: date
    end_date: date | None
    hourly_wage: Decimal
    weekly_minutes: int
    holiday_weeks: int
    saved_months: int
    next_month: YearMonth | None
    months_due: int


@dataclass(frozen=True)
class YearTotals:
    saved_months: int
    gross_wage: Decimal
    net_payout: Decimal
    cash_bonus: Decimal
    expense_reimbursements: Decimal
    employer_ahv: Decimal
    employer_alv: Decimal
    employer_fak: Decimal
    employer_bu: Decimal
    admin_charge: Decimal
    total_employer_cost: Decimal
    worked_minutes: int
    annual_holiday_taken_minutes: int
    public_holiday_taken_minutes: int


@dataclass(frozen=True)
class WageLimit:
    used: Decimal
    limit: Decimal
    remaining: Decimal


@dataclass(frozen=True)
class EmployeeOverview:
    id: int
    name: str
    employments: list[EmployeeEmployment]
    totals: YearTotals
    holiday_balance_minutes: int | None
    months_due: int
    wage_limit: WageLimit


@dataclass(frozen=True)
class EmployeesOverview:
    employees: list[EmployeeOverview]
    household: WageLimit | None


def months_due(next_month: YearMonth | None, end_date: date | None, today: date) -> int:
    if next_month is None:
        return 0
    last = min(
        (today.year, today.month),
        (RULES_YEAR, 12),
        *([(end_date.year, end_date.month)] if end_date else []),
    )
    return max(0, (last[0] - next_month.year) * 12 + last[1] - next_month.month + 1)


def _wage_limit(used_cents: int, limit: int) -> WageLimit:
    used = Decimal(used_cents).scaleb(-2)
    limit_amount = Decimal(limit).quantize(CENT)
    return WageLimit(used, limit_amount, limit_amount - used)


def _totals(slips: list[SavedPayslip], gross_cents: int) -> YearTotals:
    zero = Decimal("0.00")
    sums = {name: sum((getattr(slip.payslip, name) for slip in slips), zero) for name in PAYSLIP_SUMS}
    return YearTotals(
        saved_months=len(slips),
        gross_wage=Decimal(gross_cents).scaleb(-2),
        cash_bonus=sum((slip.cash_bonus for slip in slips), zero),
        expense_reimbursements=sum((slip.expense_reimbursements for slip in slips), zero),
        worked_minutes=sum(slip.worked_minutes + slip.public_holiday_worked_minutes for slip in slips),
        annual_holiday_taken_minutes=sum(slip.annual_holiday_taken_minutes for slip in slips),
        public_holiday_taken_minutes=sum(slip.public_holiday_taken_minutes for slip in slips),
        **sums,
    )


class EmployeeOverviewService:
    """One overview per person, composed from the existing reads and gross-to-date sums."""

    def __init__(self, reads: EmploymentReadService, payroll: PayrollRepositoryPort):
        self.reads = reads
        self.payroll = payroll

    def overview(self, account_id: int, today: date) -> EmployeesOverview:
        people: dict[int, dict] = {}
        for employment in self.reads.list_employments(account_id):
            stored = self.payroll.employment_terms(employment.id, account_id)
            history = self.reads.month_history(account_id, employment.id)
            if stored is None or history is None:
                continue
            slips = [
                slip
                for month in history.months
                if month.year == RULES_YEAR
                and (slip := self.reads.saved_payslip(account_id, employment.id, month.year, month.month))
            ]
            terms = stored.terms
            due = months_due(history.next_month, employment.end_date, today)
            person = people.setdefault(
                stored.employee_id,
                {"name": employment.employee_name, "employer_id": stored.employer_id, "employments": [], "slips": []},
            )
            person["employments"].append(
                (
                    terms.employment_start_date,
                    employment.id,
                    EmployeeEmployment(
                        id=employment.id,
                        start_date=terms.employment_start_date,
                        end_date=terms.employment_end_date,
                        hourly_wage=Decimal(terms.hourly_wage_cents).scaleb(-2),
                        weekly_minutes=terms.weekly_minutes,
                        holiday_weeks=terms.holiday_weeks,
                        saved_months=len(slips),
                        next_month=history.next_month,
                        months_due=due,
                    ),
                    slips,
                )
            )
        employees = [self._person(employee_id, person) for employee_id, person in people.items()]
        household = None
        if people:
            employer_id = next(iter(people.values()))["employer_id"]
            household = _wage_limit(self.payroll.employer_gross_to_date(employer_id, RULES_YEAR), EMPLOYER_GROSS_LIMIT)
        return EmployeesOverview(employees, household)

    def _person(self, employee_id: int, person: dict) -> EmployeeOverview:
        entries = person["employments"]
        gross = self.payroll.employee_gross_to_date(employee_id, person["employer_id"], RULES_YEAR)
        slips = [slip for *_, month_slips in entries for slip in month_slips]
        latest_with_months = [entry for entry in sorted(entries, key=lambda entry: entry[:2], reverse=True) if entry[3]]
        balance = latest_with_months[0][3][-1].holiday_balance_minutes if latest_with_months else None
        employments = [entry[2] for entry in entries]
        return EmployeeOverview(
            id=employee_id,
            name=person["name"],
            employments=employments,
            totals=_totals(slips, gross),
            holiday_balance_minutes=balance,
            months_due=sum(employment.months_due for employment in employments),
            wage_limit=_wage_limit(gross, EMPLOYEE_GROSS_LIMIT),
        )
