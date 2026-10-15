# src/app/domain/employment.py

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from src.app.domain.constants import MIN_HOURLY_WAGE


@dataclass
class Employment:
    """Represents an employment relationship between an employer and an employee."""
    id: Optional[int] = None  # Database ID (None for new instances)
    employer_id: int = 0  # Foreign key to Employer
    employee_id: int = 0  # Foreign key to Employee
    start_date: date = field(default_factory=date.today)
    hourly_wage: float = 0.0  # Gross hourly wage in CHF
    weekly_hours: float = 0.0  # Weekly working hours
    holiday_entitlement: int = 20  # Annual paid holiday days (default: 20)
    remaining_holiday_balance: float = 0.0  # Remaining holiday hours for the year

    def __post_init__(self):
        """Validate fields after initialization."""
        if self.hourly_wage < MIN_HOURLY_WAGE:
            raise ValueError(
                f"Hourly wage (CHF {self.hourly_wage:.2f}) is below the Basel-Stadt "
                f"minimum wage (CHF {MIN_HOURLY_WAGE:.2f})."
            )
        if self.weekly_hours <= 0:
            raise ValueError("Weekly hours must be positive.")
        if self.holiday_entitlement < 0:
            raise ValueError("Holiday entitlement cannot be negative.")
        if self.remaining_holiday_balance < 0:
            raise ValueError("Remaining holiday balance cannot be negative.")

    def deduct_holiday_hours(self, hours: float) -> None:
        """Deduct holiday hours from the remaining balance."""
        if hours > self.remaining_holiday_balance:
            raise ValueError("Insufficient holiday balance.")
        self.remaining_holiday_balance -= hours