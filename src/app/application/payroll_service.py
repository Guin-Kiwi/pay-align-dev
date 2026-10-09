# src/app/application/payroll_service.py

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from src.app.domain.constants import (
    AHV_RATE, ALV_RATE, TAX_RATE, NBU_RATE, FAK_RATE, BU_RATE, ADMIN_CHARGE_RATE,
    EMPLOYEE_GROSS_LIMIT, EMPLOYER_GROSS_LIMIT, PUBLIC_HOLIDAYS_2026
)
from src.app.domain.employment import Employment
from src.app.domain.monthly_record import MonthlyRecord
from src.app.domain.payslip import Payslip

# Constants
HOLIDAY_PREMIUM_RATE = 0.5  # 50% premium for working on public holidays

# Custom Exceptions
class AnnualLimitExceededError(Exception):
    """Raised when the annual gross wage limit is exceeded."""
    pass

class InvalidPayrollInputError(Exception):
    """Raised when payroll input values are invalid."""
    pass


class PayrollService:
    """Handles monthly payroll processing for household employment."""

    @staticmethod
    def _round_money(value: float) -> float:
        """Round a monetary value to Swiss centimes using half-up rounding."""
        return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def calculate_gross_wage(
        self, 
        hours_worked: float, 
        hourly_wage: float, 
        holiday_hours: float = 0.0, 
        public_holiday_hours: float = 0.0, 
        cash_bonus: float = 0.0
    ) -> float:
        """Calculate the gross wage for the month.
        
        Args:
            hours_worked: Hours worked in the month (must be >= 0).
            hourly_wage: Gross hourly wage (must be >= 0).
            holiday_hours: Paid holiday hours taken (must be >= 0).
            public_holiday_hours: Hours worked on public holidays (must be >= 0).
            cash_bonus: Cash bonus for the month (must be >= 0).
            
        Returns:
            float: Gross wage for the month.
            
        Raises:
            InvalidPayrollInputError: If any input is negative.
            
        Example:
            >>> service = PayrollService()
            >>> service.calculate_gross_wage(160, 25.0, 8, 4, 100)
            4350.0  # (160 + 8) * 25 + (4 * 25 * 0.5) + 100
        """
        # Validate inputs
        if hours_worked < 0:
            raise InvalidPayrollInputError("Hours worked cannot be negative.")
        if hourly_wage < 0:
            raise InvalidPayrollInputError("Hourly wage cannot be negative.")
        if holiday_hours < 0:
            raise InvalidPayrollInputError("Holiday hours cannot be negative.")
        if public_holiday_hours < 0:
            raise InvalidPayrollInputError("Public holiday hours cannot be negative.")
        if cash_bonus < 0:
            raise InvalidPayrollInputError("Cash bonus cannot be negative.")

        base_pay = (hours_worked + holiday_hours + public_holiday_hours) * hourly_wage
        holiday_premium = public_holiday_hours * hourly_wage * HOLIDAY_PREMIUM_RATE
        return base_pay + holiday_premium + cash_bonus

    def calculate_employee_deductions(
        self, 
        gross_wage: float, 
        weekly_hours: float
    ) -> tuple[float, float, float, float]:
        """Calculate employee deductions.
        
        Args:
            gross_wage: Gross wage for the month.
            weekly_hours: Weekly working hours (NBU applies if >= 8).
            
        Returns:
            tuple: (AHV deduction, ALV deduction, tax deduction, NBU deduction)
        """
        ahv_deduction = gross_wage * AHV_RATE
        alv_deduction = gross_wage * ALV_RATE
        tax_deduction = gross_wage * TAX_RATE
        nbu_deduction = gross_wage * NBU_RATE if weekly_hours >= 8 else 0.0
        return ahv_deduction, alv_deduction, tax_deduction, nbu_deduction

    def calculate_employer_costs(
        self, 
        gross_wage: float
    ) -> tuple[float, float, float, float, float]:
        """Calculate employer social contributions.
        
        Args:
            gross_wage: Gross wage for the month.
            
        Returns:
            tuple: (Employer AHV, Employer ALV, Employer FAK, Employer BU, Admin Charge)
        """
        employer_ahv = gross_wage * AHV_RATE
        employer_alv = gross_wage * ALV_RATE
        employer_fak = gross_wage * FAK_RATE
        employer_bu = gross_wage * BU_RATE
        admin_charge = employer_ahv * ADMIN_CHARGE_RATE
        return employer_ahv, employer_alv, employer_fak, employer_bu, admin_charge

    def create_monthly_record(
        self, 
        employment: Employment, 
        month: int, 
        year: int, 
        hours_worked: float, 
        holiday_hours: float = 0.0, 
        public_holiday_hours: float = 0.0, 
        cash_bonus: float = 0.0, 
        expense_reimbursements: float = 0.0
    ) -> MonthlyRecord:
        """Create a monthly record for payroll processing.
        
        Args:
            employment: Employment relationship.
            month: Month of the record (1-12).
            year: Year of the record.
            hours_worked: Hours worked in the month (must be >= 0).
            holiday_hours: Paid holiday hours taken (must be >= 0).
            public_holiday_hours: Hours worked on public holidays (must be >= 0).
            cash_bonus: Cash bonus for the month (must be >= 0).
            expense_reimbursements: Documented expense reimbursements (must be >= 0).
            
        Returns:
            MonthlyRecord: The created monthly record.
            
        Raises:
            InvalidPayrollInputError: If any input is negative.
        """
        # Validate inputs
        if hours_worked < 0:
            raise InvalidPayrollInputError("Hours worked cannot be negative.")
        if holiday_hours < 0:
            raise InvalidPayrollInputError("Holiday hours cannot be negative.")
        if public_holiday_hours < 0:
            raise InvalidPayrollInputError("Public holiday hours cannot be negative.")
        if cash_bonus < 0:
            raise InvalidPayrollInputError("Cash bonus cannot be negative.")
        if expense_reimbursements < 0:
            raise InvalidPayrollInputError("Expense reimbursements cannot be negative.")

        monthly_record = MonthlyRecord(
            employment_id=employment.id,
            month=month,
            year=year,
            hours_worked=hours_worked,
            holiday_hours=holiday_hours,
            public_holiday_hours=public_holiday_hours,
            cash_bonus=cash_bonus,
            expense_reimbursements=expense_reimbursements
        )
        return monthly_record

    def generate_payslip(
        self, 
        monthly_record: MonthlyRecord, 
        employment: Employment
    ) -> Payslip:
        """Generate a payslip for the monthly record."""
        # Calculate gross wage
        gross_wage = self.calculate_gross_wage(
            hours_worked=monthly_record.hours_worked,
            hourly_wage=employment.hourly_wage,
            holiday_hours=monthly_record.holiday_hours,
            public_holiday_hours=monthly_record.public_holiday_hours,
            cash_bonus=monthly_record.cash_bonus
        )

        # Calculate employee deductions
        ahv_deduction, alv_deduction, tax_deduction, nbu_deduction = self.calculate_employee_deductions(
            gross_wage=gross_wage,
            weekly_hours=employment.weekly_hours
        )

        # Round payslip lines before deriving totals so displayed amounts reconcile.
        gross_wage = self._round_money(gross_wage)
        ahv_deduction = self._round_money(ahv_deduction)
        alv_deduction = self._round_money(alv_deduction)
        tax_deduction = self._round_money(tax_deduction)
        nbu_deduction = self._round_money(nbu_deduction)
        expense_reimbursements = self._round_money(monthly_record.expense_reimbursements)

        # Calculate net payout from rounded payslip lines.
        net_payout = self._round_money(
            gross_wage - (ahv_deduction + alv_deduction + tax_deduction + nbu_deduction)
            + expense_reimbursements
        )

        # Calculate employer costs
        employer_ahv, employer_alv, employer_fak, employer_bu, admin_charge = self.calculate_employer_costs(
            gross_wage=gross_wage
        )
        employer_ahv = self._round_money(employer_ahv)
        employer_alv = self._round_money(employer_alv)
        employer_fak = self._round_money(employer_fak)
        employer_bu = self._round_money(employer_bu)
        admin_charge = self._round_money(admin_charge)
        total_employer_cost = self._round_money(
            gross_wage + employer_ahv + employer_alv + employer_fak + employer_bu + admin_charge
            + expense_reimbursements
        )

        # Create payslip
        payslip = Payslip(
            monthly_record_id=monthly_record.id,
            gross_wage=gross_wage,
            ahv_deduction=ahv_deduction,
            alv_deduction=alv_deduction,
            tax_deduction=tax_deduction,
            nbu_deduction=nbu_deduction,
            net_payout=net_payout,
            employer_ahv=employer_ahv,
            employer_alv=employer_alv,
            employer_fak=employer_fak,
            employer_bu=employer_bu,
            admin_charge=admin_charge,
            total_employer_cost=total_employer_cost
        )
        return payslip

    def validate_annual_limits(
        self, 
        employment: Employment, 
        current_gross_wage: float,
        employee_gross_to_date: float = 0.0,
        employer_gross_to_date: float = 0.0,
    ) -> None:
        """Validate annual gross wage limits for the employee and employer.
        
        Args:
            employment: Employment relationship.
            current_gross_wage: Gross wage for the current month.
            employee_gross_to_date: Employee gross wage accumulated before this run.
            employer_gross_to_date: Employer gross wage accumulated before this run.
            
        Raises:
            AnnualLimitExceededError: If the annual limit for the employee or employer is exceeded.
            InvalidPayrollInputError: If a gross wage total is negative.
        """
        if current_gross_wage < 0:
            raise InvalidPayrollInputError("Current gross wage cannot be negative.")
        if employee_gross_to_date < 0 or employer_gross_to_date < 0:
            raise InvalidPayrollInputError("Year-to-date gross wage cannot be negative.")

        employee_total = employee_gross_to_date + current_gross_wage
        if employee_total > EMPLOYEE_GROSS_LIMIT:
            raise AnnualLimitExceededError(
                f"Employee annual gross wage limit (CHF {EMPLOYEE_GROSS_LIMIT}) exceeded."
            )

        employer_total = employer_gross_to_date + current_gross_wage
        if employer_total > EMPLOYER_GROSS_LIMIT:
            raise AnnualLimitExceededError(
                f"Employer annual gross wage limit (CHF {EMPLOYER_GROSS_LIMIT}) exceeded."
            )