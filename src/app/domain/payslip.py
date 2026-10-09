# src/app/domain/payslip.py

from dataclasses import dataclass
from typing import Optional


@dataclass
class Payslip:
    """Represents a payslip for a monthly record."""
    id: Optional[int] = None  # Database ID (None for new instances)
    monthly_record_id: int = 0  # Foreign key to MonthlyRecord
    gross_wage: float = 0.0  # Gross wage for the month
    ahv_deduction: float = 0.0  # AHV/IV/EO deduction (5.3%)
    alv_deduction: float = 0.0  # ALV deduction (1.1%)
    tax_deduction: float = 0.0  # Simplified-procedure tax (5.0%)
    nbu_deduction: float = 0.0  # NBU deduction (1.432%, if applicable)
    net_payout: float = 0.0  # Net payout to employee
    employer_ahv: float = 0.0  # Employer AHV/IV/EO (5.3%)
    employer_alv: float = 0.0  # Employer ALV (1.1%)
    employer_fak: float = 0.0  # Employer FAK (1.65%)
    employer_bu: float = 0.0  # Employer BU (0.505%)
    admin_charge: float = 0.0  # AKBS administration charge (5% of employer AHV)
    total_employer_cost: float = 0.0  # Total cost to employer