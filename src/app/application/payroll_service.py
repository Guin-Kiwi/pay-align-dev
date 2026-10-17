# src/app/application/payroll_service.py

from src.app.domain.employment import Employment
from src.app.domain.errors import InvalidPayrollInputError
from src.app.domain.monthly_record import MonthlyRecord
from src.app.domain.payroll_calculation import (
    calculate_monthly_hours,
    generate_payslip,
    validate_annual_limits,
)
from src.app.domain.payslip import Payslip
from src.app.domain.work_entry import WorkEntry


class PayrollService:
    """Handles monthly payroll processing for household employment."""

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

    def process_monthly_payroll(
        self,
        repository,
        employment: Employment,
        month: int,
        year: int,
        hours_worked: float | None = None,
        holiday_hours: float = 0.0,
        public_holiday_hours: float = 0.0,
        cash_bonus: float = 0.0,
        expense_reimbursements: float = 0.0,
        work_entries: list[WorkEntry] | None = None,
    ) -> tuple[MonthlyRecord, Payslip]:
        """Calculate, validate, and persist one monthly payroll run."""
        if work_entries is not None:
            hours_worked, public_holiday_hours = calculate_monthly_hours(work_entries)
        elif hours_worked is None:
            raise InvalidPayrollInputError(
                "Either hours_worked or work_entries must be provided."
            )

        monthly_record = self.create_monthly_record(
            employment=employment,
            month=month,
            year=year,
            hours_worked=hours_worked,
            holiday_hours=holiday_hours,
            public_holiday_hours=public_holiday_hours,
            cash_bonus=cash_bonus,
            expense_reimbursements=expense_reimbursements,
        )
        payslip = generate_payslip(monthly_record, employment)

        validate_annual_limits(
            employment=employment,
            current_gross_wage=payslip.gross_wage,
            employee_gross_to_date=repository.employee_gross_to_date(
                employment.id, year
            ),
            employer_gross_to_date=repository.employer_gross_to_date(
                employment.employer_id, year
            ),
        )

        return repository.save_payroll_run(
            monthly_record, payslip, employer_id=employment.employer_id
        )
