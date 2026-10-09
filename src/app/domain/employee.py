# src/app/domain/employee.py

from dataclasses import dataclass
from typing import Optional


@dataclass
class Employee:
    """Represents a household employee."""
    id: Optional[int] = None  # Database ID (None for new instances)
    name: str = ""
    address: str = ""
    ahv_number: str = ""  # Swiss social security number (e.g., 756.1234.5678.97)
    nationality: str = ""
    tax_status: str = "ordinary"  # "ordinary" or "tax_at_source"

    def __post_init__(self):
        """Validate fields after initialization."""
        if not self.ahv_number:
            raise ValueError("AHV number is required.")
        if not self._is_valid_ahv_number(self.ahv_number):
            raise ValueError("Invalid AHV number format.")
        if self.tax_status not in ("ordinary", "tax_at_source"):
            raise ValueError("Tax status must be 'ordinary' or 'tax_at_source'.")

    @staticmethod
    def _is_valid_ahv_number(ahv_number: str) -> bool:
        """Validate the format of an AHV number.
        
        Format: 756.1234.5678.97 (13 digits, dots optional).
        """
        cleaned = ahv_number.replace(".", "")
        return cleaned.isdigit() and len(cleaned) == 13