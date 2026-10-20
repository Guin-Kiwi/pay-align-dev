# src/app/domain/monthly_record.py

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.app.domain.constants import RULES_YEAR


@dataclass
class MonthlyRecord:
    """Tracks monthly payroll data for an employment."""
    id: Optional[int] = None  # Database ID (None for new instances)
    employment_id: int = 0  # Foreign key to Employment
    employee_id: int = 0  # Foreign key to Employee
    employer_id: int = 0  # Foreign key to Employer
    month: int = 1  # 1-12
    year: int = RULES_YEAR  # Year of the record
    cash_bonus: Decimal = Decimal("0.00")  # Cash bonus for the month
    expense_reimbursements: Decimal = Decimal("0.00")  # Documented expense reimbursements

    def __post_init__(self):
        """Validate fields after initialization."""
        if not (1 <= self.month <= 12):
            raise ValueError("Month must be between 1 and 12.")
        if self.year < RULES_YEAR:
            raise ValueError(f"Year must be {RULES_YEAR} or later.")
        if self.cash_bonus < 0:
            raise ValueError("Cash bonus cannot be negative.")
        if self.expense_reimbursements < 0:
            raise ValueError("Expense reimbursements cannot be negative.")