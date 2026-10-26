# src/app/domain/payroll_calculation.py

from dataclasses import replace
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from src.app.domain.constants import (
    AHV_RATE, AHV_TOTAL_RATE, ALV_RATE, TAX_RATE, NBU_RATE, FAK_RATE, BU_RATE,
    ADMIN_CHARGE_RATE,
    EMPLOYEE_GROSS_LIMIT, EMPLOYER_GROSS_LIMIT, PUBLIC_HOLIDAYS
)
from src.app.domain.constants import NBU_MIN_WEEKLY_MINUTES
from src.app.domain.employment import Employment
from src.app.domain.errors import AnnualLimitExceededError, InvalidPayrollInputError
from src.app.domain.hour_categories import HourCategory, MinuteTotals
from src.app.domain.payslip import Payslip
from src.app.domain.work_entry import WorkEntry, calculate_paid_minutes  # noqa: F401

CENT = Decimal("0.01")


def round_money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def is_public_holiday(work_date: date) -> bool:
    """Return whether a date is a configured Basel-Stadt holiday."""
    return work_date in PUBLIC_HOLIDAYS


def classify_public_holidays(entries: list[WorkEntry]) -> list[WorkEntry]:
    """Apply the public-holiday categories of ADR-004 Amendment 1, item 6.

    Work on a public holiday is classified as public-holiday work (50% premium).
    Rejected: public-holiday work and leave on any other day, paid holiday on a
    public holiday (NAV Haushalt BS § 27 para 4), and public-holiday leave on
    the same day as work or paid holiday.
    """
    classified = []
    for entry in entries:
        holiday = is_public_holiday(entry.work_date)
        day = entry.work_date.isoformat()
        if entry.category == HourCategory.WORKED and holiday:
            entry = replace(entry, category=HourCategory.PUBLIC_HOLIDAY_WORKED)
        elif entry.category == HourCategory.ANNUAL_HOLIDAY_TAKEN and holiday:
            raise InvalidPayrollInputError(
                f"{day} is a public holiday and cannot be taken as paid holiday."
            )
        elif not holiday and entry.category in (
            HourCategory.PUBLIC_HOLIDAY_WORKED,
            HourCategory.PUBLIC_HOLIDAY_TAKEN,
        ):
            raise InvalidPayrollInputError(f"{day} is not a public holiday.")
        classified.append(entry)

    leave_days = {
        entry.work_date
        for entry in classified
        if entry.category == HourCategory.PUBLIC_HOLIDAY_TAKEN
    }
    for entry in classified:
        if entry.work_date in leave_days and entry.category in (
            HourCategory.PUBLIC_HOLIDAY_WORKED,
            HourCategory.ANNUAL_HOLIDAY_TAKEN,
        ):
            raise InvalidPayrollInputError(
                f"{entry.work_date.isoformat()} has public-holiday leave and "
                f"{entry.category.value} entries."
            )
    return classified


def calculate_monthly_totals(entries: list[WorkEntry]) -> MinuteTotals:
    """Sum the entries of one calendar month into per-category minute totals."""
    months = {(entry.work_date.month, entry.work_date.year) for entry in entries}
    if len(months) > 1:
        raise InvalidPayrollInputError("Work entries must belong to one calendar month.")

    sums = {category: 0 for category in HourCategory}
    for entry in entries:
        sums[HourCategory(entry.category)] += entry.paid_minutes
    return MinuteTotals(
        worked=sums[HourCategory.WORKED],
        public_holiday_worked=sums[HourCategory.PUBLIC_HOLIDAY_WORKED],
        annual_holiday_taken=sums[HourCategory.ANNUAL_HOLIDAY_TAKEN],
        public_holiday_taken=sums[HourCategory.PUBLIC_HOLIDAY_TAKEN],
    )


def nbu_applies(weekly_minutes: int) -> bool:
    """Return whether NBU is deducted."""
    return weekly_minutes >= NBU_MIN_WEEKLY_MINUTES


def calculate_gross_wage_from_minutes(
    totals: MinuteTotals,
    hourly_wage: Decimal,
    cash_bonus: Decimal = Decimal("0"),
) -> Decimal:
    """Gross wage in CHF from whole minutes, as Decimal (ADR-003, ADR-004)."""
    if not isinstance(hourly_wage, Decimal) or not isinstance(cash_bonus, Decimal):
        raise InvalidPayrollInputError("Hourly wage and cash bonus must be Decimal values.")
    if hourly_wage < 0:
        raise InvalidPayrollInputError("Hourly wage cannot be negative.")
    if cash_bonus < 0:
        raise InvalidPayrollInputError("Cash bonus cannot be negative.")

    weighted_half_minutes = (
        2 * (totals.worked + totals.annual_holiday_taken + totals.public_holiday_taken)
        + 3 * totals.public_holiday_worked
    )
    hourly_pay = (hourly_wage * weighted_half_minutes / Decimal(120)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return hourly_pay + cash_bonus.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def nbu_applies(weekly_minutes: int) -> bool:
    """Return whether NBU is deducted."""
    return weekly_minutes >= NBU_MIN_WEEKLY_MINUTES


def calculate_gross_wage_from_minutes(
    totals: MinuteTotals,
    hourly_wage: Decimal,
    cash_bonus: Decimal = Decimal("0"),
) -> Decimal:
    """Gross wage in CHF from whole minutes, as Decimal (ADR-003, ADR-004)."""
    if not isinstance(hourly_wage, Decimal) or not isinstance(cash_bonus, Decimal):
        raise InvalidPayrollInputError("Hourly wage and cash bonus must be Decimal values.")
    if hourly_wage < 0:
        raise InvalidPayrollInputError("Hourly wage cannot be negative.")
    if cash_bonus < 0:
        raise InvalidPayrollInputError("Cash bonus cannot be negative.")

    # Work in half-minutes so the 50% premium stays an integer.
    weighted_half_minutes = (
        2 * (totals.worked + totals.annual_holiday_taken + totals.public_holiday_taken)
        + 3 * totals.public_holiday_worked
    )
    hourly_pay = (hourly_wage * weighted_half_minutes / Decimal(120)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return hourly_pay + cash_bonus.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_employee_deductions(
    gross_wage: Decimal,
    weekly_minutes: int,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Return the rounded AHV, ALV, tax and NBU deduction lines."""
    ahv_deduction = round_money(gross_wage * Decimal(str(AHV_RATE)))
    alv_deduction = round_money(gross_wage * Decimal(str(ALV_RATE)))
    tax_deduction = round_money(gross_wage * Decimal(str(TAX_RATE)))
    nbu_deduction = (
        round_money(gross_wage * Decimal(str(NBU_RATE))) if nbu_applies(weekly_minutes)
        else Decimal("0.00")
    )
    return ahv_deduction, alv_deduction, tax_deduction, nbu_deduction


def calculate_employer_costs(
    gross_wage: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    """Return the rounded employer contribution lines."""
    employer_ahv = round_money(gross_wage * Decimal(str(AHV_RATE)))
    employer_alv = round_money(gross_wage * Decimal(str(ALV_RATE)))
    employer_fak = round_money(gross_wage * Decimal(str(FAK_RATE)))
    employer_bu = round_money(gross_wage * Decimal(str(BU_RATE)))
    admin_charge = round_money(
        gross_wage * Decimal(str(AHV_TOTAL_RATE)) * Decimal(str(ADMIN_CHARGE_RATE))
    )
    return employer_ahv, employer_alv, employer_fak, employer_bu, admin_charge


def generate_payslip(
    totals: MinuteTotals,
    employment: Employment,
    cash_bonus: Decimal = Decimal("0"),
    expense_reimbursements: Decimal = Decimal("0"),
) -> Payslip:
    """Build the payslip lines from the run's minute totals."""
    return generate_payslip_from_terms(
        totals=totals,
        hourly_wage=Decimal(str(employment.hourly_wage)),
        weekly_minutes=round(employment.weekly_hours * 60),
        cash_bonus=cash_bonus,
        expense_reimbursements=expense_reimbursements,
    )


def generate_payslip_from_terms(
    totals: MinuteTotals,
    hourly_wage: Decimal,
    weekly_minutes: int,
    cash_bonus: Decimal = Decimal("0"),
    expense_reimbursements: Decimal = Decimal("0"),
) -> Payslip:
    """Build the payslip lines from stored wage and weekly minutes."""
    gross_wage = calculate_gross_wage_from_minutes(totals, hourly_wage, cash_bonus)

    ahv_deduction, alv_deduction, tax_deduction, nbu_deduction = (
        calculate_employee_deductions(gross_wage, weekly_minutes)
    )
    expense_reimbursements = round_money(expense_reimbursements)

    net_payout = round_money(
        gross_wage - (ahv_deduction + alv_deduction + tax_deduction + nbu_deduction)
        + expense_reimbursements
    )

    employer_ahv, employer_alv, employer_fak, employer_bu, admin_charge = (
        calculate_employer_costs(gross_wage)
    )
    total_employer_cost = round_money(
        gross_wage + employer_ahv + employer_alv + employer_fak + employer_bu
        + admin_charge + expense_reimbursements
    )

    return Payslip(
        gross_wage=gross_wage,
        ahv_deduction=ahv_deduction,
        alv_deduction=alv_deduction,
        tax_deduction=tax_deduction,
        nbu_deduction=nbu_deduction,
        net_payout=net_payout,
        employer_ahv=employer_ahv,
        employer_alv=employer_alv,
        employer_fak=employer_fak,
        employer_bu=employer_bu,
        admin_charge=admin_charge,
        total_employer_cost=total_employer_cost,
    )


def validate_annual_limits(
    current_gross_wage: Decimal,
    employee_gross_to_date: Decimal = Decimal("0.00"),
    employer_gross_to_date: Decimal = Decimal("0.00"),
) -> None:
    """Reject a run that would exceed the employee or employer annual limit."""
    if current_gross_wage < 0:
        raise InvalidPayrollInputError("Current gross wage cannot be negative.")
    if employee_gross_to_date < 0 or employer_gross_to_date < 0:
        raise InvalidPayrollInputError("Year-to-date gross wage cannot be negative.")

    if employee_gross_to_date + current_gross_wage > Decimal(str(EMPLOYEE_GROSS_LIMIT)):
        raise AnnualLimitExceededError(
            f"Employee annual gross wage limit (CHF {EMPLOYEE_GROSS_LIMIT}) exceeded."
            " The simplified procedure no longer applies. Contact AKBS about the"
            " ordinary procedure, which PayAlign does not support."
        )
    if employer_gross_to_date + current_gross_wage > Decimal(str(EMPLOYER_GROSS_LIMIT)):
        raise AnnualLimitExceededError(
            f"Employer annual gross wage limit (CHF {EMPLOYER_GROSS_LIMIT}) exceeded."
            " The simplified procedure no longer applies. Contact AKBS about the"
            " ordinary procedure, which PayAlign does not support."
        )
