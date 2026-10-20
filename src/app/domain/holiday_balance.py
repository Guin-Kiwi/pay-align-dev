# src/app/domain/holiday_balance.py
"""Holiday entitlement and derived holiday balance.

Rules: ADR-002, ADR-003 and ADR-004 (with Amendment 1).
"""

from datetime import date
from typing import Optional

from src.app.domain.constants import (
    ALLOWED_HOLIDAY_WEEKS,
    DAYS_IN_RULES_YEAR,
    RULES_YEAR,
    RULES_YEAR_END,
    RULES_YEAR_START,
)
from src.app.domain.errors import InvalidPayrollInputError


def contract_days_in_year(start_date: date, end_date: Optional[date] = None) -> int:
    first = max(start_date, RULES_YEAR_START)
    last = min(end_date, RULES_YEAR_END) if end_date is not None else RULES_YEAR_END
    if end_date is not None and end_date < start_date:
        raise InvalidPayrollInputError("End date cannot be before start date.")
    if last < first:
        raise InvalidPayrollInputError(f"The employment has no days in {RULES_YEAR}.")
    return (last - first).days + 1


def holiday_entitlement_minutes(
    holiday_weeks: int,
    weekly_minutes: int,
    start_date: date,
    end_date: Optional[date] = None,
) -> int:
    if holiday_weeks not in ALLOWED_HOLIDAY_WEEKS:
        raise InvalidPayrollInputError("Holiday weeks must be 4 or 5.")
    if isinstance(weekly_minutes, bool) or not isinstance(weekly_minutes, int) or weekly_minutes <= 0:
        raise InvalidPayrollInputError("Weekly minutes must be a positive whole number.")

    days = contract_days_in_year(start_date, end_date)
    numerator = holiday_weeks * weekly_minutes * days
    return (2 * numerator + DAYS_IN_RULES_YEAR) // (2 * DAYS_IN_RULES_YEAR)


def remaining_holiday_minutes(previous_balance: int, annual_holiday_taken_minutes: int) -> int:
    for value in (previous_balance, annual_holiday_taken_minutes):
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidPayrollInputError("Holiday minutes must be whole numbers.")
    if previous_balance < 0:
        raise InvalidPayrollInputError("Previous holiday balance cannot be negative.")
    if annual_holiday_taken_minutes < 0:
        raise InvalidPayrollInputError("Annual holiday taken minutes cannot be negative.")
    remaining = previous_balance - annual_holiday_taken_minutes
    if remaining < 0:
        raise InvalidPayrollInputError("Holiday taken exceeds the remaining holiday balance.")
    return remaining
