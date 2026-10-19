# src/app/domain/holiday_balance.py
"""Holiday entitlement and derived holiday balance in whole minutes.

Rules: ADR-004, Amendment 1 (items 1-5) and ADR-003 (half-up rounding, once).
Only the 2026 ruleset exists, so the year is fixed and the denominator is 365.
"""

from datetime import date
from typing import Optional

from src.app.domain.errors import InvalidPayrollInputError

RULES_YEAR_START = date(2026, 1, 1)
RULES_YEAR_END = date(2026, 12, 31)
DAYS_IN_RULES_YEAR = 365
ALLOWED_HOLIDAY_WEEKS = (4, 5)


def contract_days_in_year(start_date: date, end_date: Optional[date] = None) -> int:
    """Days under contract in 2026, counting both start and end date."""
    first = max(start_date, RULES_YEAR_START)
    last = min(end_date, RULES_YEAR_END) if end_date is not None else RULES_YEAR_END
    if end_date is not None and end_date < start_date:
        raise InvalidPayrollInputError("End date cannot be before start date.")
    if last < first:
        raise InvalidPayrollInputError("The employment has no days in 2026.")
    return (last - first).days + 1


def holiday_entitlement_minutes(
    holiday_weeks: int,
    weekly_minutes: int,
    start_date: date,
    end_date: Optional[date] = None,
) -> int:
    """Yearly holiday entitlement in whole minutes, pro-rated and rounded half-up once."""
    if holiday_weeks not in ALLOWED_HOLIDAY_WEEKS:
        raise InvalidPayrollInputError("Holiday weeks must be 4 or 5.")
    if isinstance(weekly_minutes, bool) or not isinstance(weekly_minutes, int) or weekly_minutes <= 0:
        raise InvalidPayrollInputError("Weekly minutes must be a positive whole number.")

    days = contract_days_in_year(start_date, end_date)
    # round_half_up(weeks * weekly_minutes * days / 365) using integers only
    numerator = holiday_weeks * weekly_minutes * days
    return (2 * numerator + DAYS_IN_RULES_YEAR) // (2 * DAYS_IN_RULES_YEAR)


def remaining_holiday_minutes(previous_balance: int, paid_holiday_minutes: int) -> int:
    """Balance after a run: previous balance minus the run's paid holiday minutes.

    For the first run, pass the pro-rated entitlement as previous_balance.
    A negative result is rejected (ADR-004).
    """
    for value in (previous_balance, paid_holiday_minutes):
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidPayrollInputError("Holiday minutes must be whole numbers.")
    if previous_balance < 0:
        raise InvalidPayrollInputError("Previous holiday balance cannot be negative.")
    if paid_holiday_minutes < 0:
        raise InvalidPayrollInputError("Paid holiday minutes cannot be negative.")
    remaining = previous_balance - paid_holiday_minutes
    if remaining < 0:
        raise InvalidPayrollInputError("Holiday taken exceeds the remaining holiday balance.")
    return remaining
