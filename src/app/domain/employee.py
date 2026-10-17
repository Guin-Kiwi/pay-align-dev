# src/app/domain/employee.py

from dataclasses import dataclass
from typing import Optional

from src.app.domain.ahv_number import validate_ahv_number
from src.app.domain.required_fields import require_fields


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
        require_fields(name=self.name, address=self.address, nationality=self.nationality)
        validate_ahv_number(self.ahv_number)
        if self.tax_status not in ("ordinary", "tax_at_source"):
            raise ValueError("Tax status must be 'ordinary' or 'tax_at_source'.")
