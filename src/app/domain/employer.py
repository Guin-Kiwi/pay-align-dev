# src/app/domain/employer.py

from dataclasses import dataclass
from typing import Optional


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
        if not self.ahv_number:
            raise ValueError("AHV number is required.")
        if not self._is_valid_ahv_number(self.ahv_number):
            raise ValueError("Invalid AHV number format.")

    @staticmethod
    def _is_valid_ahv_number(ahv_number: str) -> bool:
        """Validate the format of an AHV number.
        
        Format: 756.1234.5678.97 (13 digits, dots optional).
        """
        cleaned = ahv_number.replace(".", "")
        return cleaned.isdigit() and len(cleaned) == 13