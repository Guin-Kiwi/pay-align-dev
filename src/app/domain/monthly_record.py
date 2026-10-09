# src/app/domain/monthly_record.py

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class MonthlyRecord:
    """Tracks monthly payroll data for an employment."""
    id: Optional[int] = None  # Database ID (None for new instances)
    employment_id: int = 0  # Foreign key to Employment
    month: int = 1  # 1-12
    year: int = 2026  # Year of the record
    hours_worked: float = 0.0  # Hours worked in the month
    holiday_hours: float = 0.0  # Paid holiday hours taken
    public_holiday_hours: float = 0.0  # Hours worked on public holidays
    cash_bonus: float = 0.0  # Cash bonus for the month
    expense_reimbursements: float = 0.0  # Documented expense reimbursements

    def __post_init__(self):
        """Validate fields after initialization."""
        if not (1 <= self.month <= 12):
            raise ValueError("Month must be between 1 and 12.")
        if self.year < 2026:
            raise ValueError("Year must be 2026 or later.")
        if self.hours_worked < 0:
            raise ValueError("Hours worked cannot be negative.")
        if self.holiday_hours < 0:
            raise ValueError("Holiday hours cannot be negative.")
        if self.public_holiday_hours < 0:
            raise ValueError("Public holiday hours cannot be negative.")
        if self.cash_bonus < 0:
            raise ValueError("Cash bonus cannot be negative.")
        if self.expense_reimbursements < 0:
            raise ValueError("Expense reimbursements cannot be negative.")

    def total_paid_hours(self) -> float:
        """Calculate total paid hours (worked + holiday + public holiday)."""
        return self.hours_worked + self.holiday_hours + self.public_holiday_hours