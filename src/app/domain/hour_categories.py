# src/app/domain/hour_categories.py
"""The four hour categories of a payroll run and their minute totals.

Time is counted in whole minutes (ADR-004, Amendment 1, items 6 and 7).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from src.app.domain.errors import InvalidPayrollInputError


class HourCategory(str, Enum):
    """Category of a daily work entry."""

    WORKED = "worked"
    WORKED_PUBLIC_HOLIDAY = "worked_public_holiday"  # worked on a public holiday, +50% premium
    PAID_HOLIDAY = "paid_holiday"  # paid holiday taken, no work done
    PUBLIC_HOLIDAY_LEAVE = "public_holiday_leave"  # paid public-holiday leave, no work done


@dataclass(frozen=True)
class MinuteTotals:
    """Whole-minute totals per hour category for one monthly run."""

    worked: int = 0
    worked_public_holiday: int = 0
    paid_holiday: int = 0
    public_holiday_leave: int = 0

    def __post_init__(self) -> None:
        for name in ("worked", "worked_public_holiday", "paid_holiday", "public_holiday_leave"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise InvalidPayrollInputError(f"{name} minutes must be a whole number.")
            if value < 0:
                raise InvalidPayrollInputError(f"{name} minutes cannot be negative.")

    @property
    def total(self) -> int:
        return (
            self.worked
            + self.worked_public_holiday
            + self.paid_holiday
            + self.public_holiday_leave
        )


def sum_minutes_by_category(items: Iterable[tuple[HourCategory, int]]) -> MinuteTotals:
    """Add up (category, minutes) pairs into MinuteTotals."""
    sums = {category: 0 for category in HourCategory}
    for category, minutes in items:
        if isinstance(minutes, bool) or not isinstance(minutes, int):
            raise InvalidPayrollInputError("Minutes must be a whole number.")
        if minutes < 0:
            raise InvalidPayrollInputError("Minutes cannot be negative.")
        sums[HourCategory(category)] += minutes
    return MinuteTotals(
        worked=sums[HourCategory.WORKED],
        worked_public_holiday=sums[HourCategory.WORKED_PUBLIC_HOLIDAY],
        paid_holiday=sums[HourCategory.PAID_HOLIDAY],
        public_holiday_leave=sums[HourCategory.PUBLIC_HOLIDAY_LEAVE],
    )
