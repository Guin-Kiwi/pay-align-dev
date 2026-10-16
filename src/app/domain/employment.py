# src/app/domain/employment.py

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from src.app.domain.constants import MIN_HOURLY_WAGE


@dataclass
class Employment:
    """Represents an employment relationship between an employer and an employee."""
    id: Optional[int] = None  # Database ID (None for new instances)
    employer_id: int = 0  # Foreign key to Employer
    employee_id: int = 0  # Foreign key to Employee
    start_date: date = field(default_factory=date.today)
    end_date: Optional[date] = None  # Last day of a fixed-term contract (None: no end date)
    hourly_wage: float = 0.0  # Gross hourly wage in CHF
    weekly_hours: float = 0.0  # Weekly working hours
    holiday_weeks: int = 4  # Paid holiday weeks per year: 4, or 5 under 20 or over 50

    def __post_init__(self):
        """Validate fields after initialization."""
        if Decimal(str(self.hourly_wage)) < Decimal(str(MIN_HOURLY_WAGE)):
            raise ValueError(
                f"Hourly wage (CHF {self.hourly_wage:.2f}) is below the Basel-Stadt "
                f"minimum wage (CHF {MIN_HOURLY_WAGE:.2f})."
            )
        if self.weekly_hours <= 0:
            raise ValueError("Weekly hours must be positive.")
        if self.holiday_weeks not in (4, 5):
            raise ValueError("Holiday weeks must be 4 or 5.")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("End date cannot be before the start date.")
