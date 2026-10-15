# src/app/domain/employer.py

from dataclasses import dataclass
from typing import Optional

from src.app.domain.ahv_number import validate_ahv_number


@dataclass
class Employer:
    """Represents a private household employer."""
    id: Optional[int] = None  # Database ID (None for new instances)
    name: str = ""
    address: str = ""
    ahv_number: str = ""  # Swiss social security number (e.g., 756.1234.5678.97)
    contact_info: str = ""

    def __post_init__(self):
        """Validate fields after initialization."""
        validate_ahv_number(self.ahv_number)
