# src/app/domain/payslip.py

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class Payslip:
    """Represents a payslip for a monthly record."""
    id: Optional[int] = None  # Database ID (None for new instances)
    monthly_record_id: int = 0  # Foreign key to MonthlyRecord
    gross_wage: Decimal = Decimal("0.00")
    ahv_deduction: Decimal = Decimal("0.00")
    alv_deduction: Decimal = Decimal("0.00")
    tax_deduction: Decimal = Decimal("0.00")
    nbu_deduction: Decimal = Decimal("0.00")
    net_payout: Decimal = Decimal("0.00")
    employer_ahv: Decimal = Decimal("0.00")
    employer_alv: Decimal = Decimal("0.00")
    employer_fak: Decimal = Decimal("0.00")
    employer_bu: Decimal = Decimal("0.00")
    admin_charge: Decimal = Decimal("0.00")
    total_employer_cost: Decimal = Decimal("0.00")