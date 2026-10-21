# src/app/application/payroll_service.py

from decimal import Decimal

from src.app.application.ports.payroll_repository import (
    EmploymentTerms,
    MonthlyRecordInput,
    PayrollRepositoryPort,
    PayslipInput,
    PriorRun,
    RunSnapshot,
    WorkEntryInput,
)
from src.app.domain.constants import RULES_YEAR
from src.app.domain.errors import (
    DuplicateMonthError,
    EmploymentNotFoundError,
    InvalidHolidayBalanceError,
    InvalidPayrollInputError,
)
from src.app.domain.holiday_balance import (
    holiday_entitlement_minutes,
    remaining_holiday_minutes,
)
from src.app.domain.hour_categories import MinuteTotals
from src.app.domain.monthly_record import MonthlyRecord
from src.app.domain.payroll_calculation import (
    calculate_monthly_totals,
    classify_public_holidays,
    generate_payslip_from_terms,
    round_money,
    validate_annual_limits,
)
from src.app.domain.payslip import Payslip
from src.app.domain.work_entry import WorkEntry, reject_overlapping_entries

RULESET_VERSION = str(RULES_YEAR)


def _to_cents(value: Decimal) -> int:
    return int(round_money(value).scaleb(2))


def _following_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


class PayrollService:
    """Handles monthly payroll processing for household employment."""

    def process_monthly_payroll(
        self,
        repository: PayrollRepositoryPort,
        employment_id: int,
        month: int,
        year: int,
        work_entries: list[WorkEntry],
        cash_bonus: Decimal = Decimal("0.00"),
        expense_reimbursements: Decimal = Decimal("0.00"),
    ) -> tuple[MonthlyRecord, Payslip]:
        """Calculate, validate and persist one monthly payroll run."""
        if year != RULES_YEAR:
            raise InvalidPayrollInputError(
                f"Payroll rules exist for {RULES_YEAR} only."
            )

        stored = repository.employment_terms(employment_id)
        if stored is None:
            raise EmploymentNotFoundError(f"Employment {employment_id} not found.")
        terms = stored.terms
        hourly_wage = Decimal(terms.hourly_wage_cents) / 100
        cash_bonus = round_money(cash_bonus)
        expense_reimbursements = round_money(expense_reimbursements)

        if any(
            (entry.work_date.month, entry.work_date.year) != (month, year)
            for entry in work_entries
        ):
            raise InvalidPayrollInputError(
                "Work entries must belong to the payroll month."
            )
        self._check_entries_within_employment(work_entries, terms)
        reject_overlapping_entries(work_entries)
        work_entries = classify_public_holidays(work_entries)
        totals = calculate_monthly_totals(work_entries)

        self._check_month_not_after_end(terms, month, year)
        prior = repository.prior_run(employment_id)
        self._check_run_sequence(prior, terms, month, year)

        payslip = generate_payslip_from_terms(
            totals=totals,
            hourly_wage=hourly_wage,
            weekly_minutes=terms.weekly_minutes,
            cash_bonus=cash_bonus,
            expense_reimbursements=expense_reimbursements,
        )

        validate_annual_limits(
            current_gross_wage=payslip.gross_wage,
            employee_gross_to_date=Decimal(
                repository.employee_gross_to_date(
                    stored.employee_id, stored.employer_id, year
                )
            ) / 100,
            employer_gross_to_date=Decimal(
                repository.employer_gross_to_date(stored.employer_id, year)
            ) / 100,
        )

        holiday_balance = self._holiday_balance_after_run(prior, terms, totals)

        record = MonthlyRecord(
            employment_id=employment_id,
            employee_id=stored.employee_id,
            employer_id=stored.employer_id,
            month=month,
            year=year,
            cash_bonus=cash_bonus,
            expense_reimbursements=expense_reimbursements,
        )

        saved = repository.save_payroll_run(
            record=MonthlyRecordInput(
                employment_id=employment_id,
                employee_id=stored.employee_id,
                employer_id=stored.employer_id,
                month=month,
                year=year,
                cash_bonus_cents=_to_cents(cash_bonus),
                expense_reimbursements_cents=_to_cents(expense_reimbursements),
            ),
            entries=tuple(
                WorkEntryInput(
                    work_date=entry.work_date,
                    category=entry.category.value,
                    start_time=entry.start_time,
                    end_time=entry.end_time,
                    unpaid_break_minutes=entry.unpaid_break_minutes,
                    paid_minutes=entry.paid_minutes,
                )
                for entry in work_entries
            ),
            snapshot=RunSnapshot(
                employment=terms,
                ruleset_version=RULESET_VERSION,
                hours=totals,
                holiday_balance_minutes=holiday_balance,
            ),
            payslip=PayslipInput(
                gross_wage_cents=_to_cents(payslip.gross_wage),
                ahv_deduction_cents=_to_cents(payslip.ahv_deduction),
                alv_deduction_cents=_to_cents(payslip.alv_deduction),
                tax_deduction_cents=_to_cents(payslip.tax_deduction),
                nbu_deduction_cents=_to_cents(payslip.nbu_deduction),
                net_payout_cents=_to_cents(payslip.net_payout),
                employer_ahv_cents=_to_cents(payslip.employer_ahv),
                employer_alv_cents=_to_cents(payslip.employer_alv),
                employer_fak_cents=_to_cents(payslip.employer_fak),
                employer_bu_cents=_to_cents(payslip.employer_bu),
                admin_charge_cents=_to_cents(payslip.admin_charge),
                total_employer_cost_cents=_to_cents(payslip.total_employer_cost),
            ),
        )

        record.id = saved.monthly_record_id
        payslip.id = saved.payslip_id
        payslip.monthly_record_id = saved.monthly_record_id
        return record, payslip

    @staticmethod
    def _check_month_not_after_end(
        terms: EmploymentTerms, month: int, year: int
    ) -> None:
        end = terms.employment_end_date
        if end is not None and (year, month) > (end.year, end.month):
            raise InvalidPayrollInputError(
                f"The employment ended on {end.isoformat()}; "
                f"no payroll run is possible for {month:02d}/{year}."
            )

    @staticmethod
    def _check_entries_within_employment(
        work_entries: list[WorkEntry], terms: EmploymentTerms
    ) -> None:
        start, end = terms.employment_start_date, terms.employment_end_date
        for entry in work_entries:
            if entry.work_date < start or (end is not None and entry.work_date > end):
                raise InvalidPayrollInputError(
                    f"Entry on {entry.work_date.isoformat()} is outside the employment "
                    f"({start.isoformat()} to {end.isoformat() if end else 'open end'})."
                )

    @staticmethod
    def _check_run_sequence(
        prior: PriorRun | None, terms: EmploymentTerms, month: int, year: int
    ) -> None:
        """First run: the start month. Later runs: the month after the last run."""
        if prior is None:
            expected = (
                terms.employment_start_date.year,
                terms.employment_start_date.month,
            )
        else:
            expected = _following_month(prior.year, prior.month)
            if (year, month) < expected:
                raise DuplicateMonthError("This month was already processed.")
        if (year, month) != expected:
            raise InvalidPayrollInputError(
                f"The next payroll run is for {expected[1]:02d}/{expected[0]}."
            )

    @staticmethod
    def _holiday_balance_after_run(
        prior: PriorRun | None,
        terms: EmploymentTerms,
        totals: MinuteTotals,
    ) -> int:
        opening_balance = (
            prior.holiday_balance_minutes
            if prior is not None
            else holiday_entitlement_minutes(
                holiday_weeks=terms.holiday_weeks,
                weekly_minutes=terms.weekly_minutes,
                start_date=terms.employment_start_date,
                end_date=terms.employment_end_date,
            )
        )
        try:
            return remaining_holiday_minutes(
                opening_balance, totals.annual_holiday_taken
            )
        except InvalidPayrollInputError as error:
            raise InvalidHolidayBalanceError(str(error)) from error
