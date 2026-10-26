# src/app/domain/hour_categories.py
"""The four hour categories of a payroll run and their minute totals.

Rules: ADR-004 (with Amendment 1).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from src.app.domain.errors import InvalidPayrollInputError


class HourCategory(str, Enum):
    """Category of a daily work entry."""

    WORKED = "worked"
    PUBLIC_HOLIDAY_WORKED = "public_holiday_worked"
    ANNUAL_HOLIDAY_TAKEN = "annual_holiday_taken"
    PUBLIC_HOLIDAY_TAKEN = "public_holiday_taken"


@dataclass(frozen=True)
class MinuteTotals:
    """Whole-minute totals per hour category for one monthly run."""

    worked: int = 0
    public_holiday_worked: int = 0
    annual_holiday_taken: int = 0
    public_holiday_taken: int = 0

    def __post_init__(self) -> None:
        for name in ("worked", "public_holiday_worked", "annual_holiday_taken", "public_holiday_taken"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise InvalidPayrollInputError(f"{name} minutes must be a whole number.")
            if value < 0:
                raise InvalidPayrollInputError(f"{name} minutes cannot be negative.")

    @property
    def total(self) -> int:
        return (
            self.worked
            + self.public_holiday_worked
            + self.annual_holiday_taken
            + self.public_holiday_taken
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
        public_holiday_worked=sums[HourCategory.PUBLIC_HOLIDAY_WORKED],
        annual_holiday_taken=sums[HourCategory.ANNUAL_HOLIDAY_TAKEN],
        public_holiday_taken=sums[HourCategory.PUBLIC_HOLIDAY_TAKEN],
    )
