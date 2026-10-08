# src/app/domain/employment.py

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Employment:
    """Represents an employment relationship between an employer and an employee."""
    id: Optional[int] = None  # Database ID (None for new instances)
    employer_id: int = 0  # Foreign key to Employer
    employee_id: int = 0  # Foreign key to Employee
    start_date: date = date.today()
    hourly_wage: float = 0.0  # Gross hourly wage in CHF
    weekly_hours: float = 0.0  # Weekly working hours
    holiday_entitlement: int = 20  # Annual paid holiday days (default: 20)
    remaining_holiday_balance: float = 0.0  # Remaining holiday hours for the year

    def __post_init__(self):
        """Validate fields after initialization."""
        if self.hourly_wage <= 0:
            raise ValueError("Hourly wage must be positive.")
        if self.weekly_hours <= 0:
            raise ValueError("Weekly hours must be positive.")
        if self.holiday_entitlement < 0:
            raise ValueError("Holiday entitlement cannot be negative.")
        if self.remaining_holiday_balance < 0:
            raise ValueError("Remaining holiday balance cannot be negative.")

        # Warnings for implicit constraints
        from .constants import MIN_HOURLY_WAGE, MIN_WEEKLY_HOURS
        if self.hourly_wage < MIN_HOURLY_WAGE:
            print(f"Warning: Hourly wage (CHF {self.hourly_wage}) is below the Basel-Stadt minimum wage (CHF {MIN_HOURLY_WAGE}).")
        if self.weekly_hours < MIN_WEEKLY_HOURS:
            print(f"Warning: Weekly hours ({self.weekly_hours}) are unusually low (recommended minimum: {MIN_WEEKLY_HOURS}).")

    def deduct_holiday_hours(self, hours: float) -> None:
        """Deduct holiday hours from the remaining balance."""
        if hours > self.remaining_holiday_balance:
            raise ValueError("Insufficient holiday balance.")
        self.remaining_holiday_balance -= hours