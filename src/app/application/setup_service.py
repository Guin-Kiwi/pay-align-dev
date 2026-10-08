# src/app/application/setup_service.py

from datetime import date
from typing import Optional

from src.app.domain.employer import Employer
from src.app.domain.employee import Employee
from src.app.domain.employment import Employment
from src.app.domain.constants import MIN_HOURLY_WAGE, MIN_WEEKLY_HOURS


class SetupService:
    """Handles the setup of an employment relationship for household help."""

    def create_employer(
        self, 
        name: str, 
        address: str, 
        ahv_number: str, 
        contact_info: str
    ) -> Employer:
        """Create and validate an employer record."""
        employer = Employer(
            name=name, 
            address=address, 
            ahv_number=ahv_number, 
            contact_info=contact_info
        )
        return employer

    def create_employee(
        self, 
        name: str, 
        address: str, 
        ahv_number: str, 
        nationality: str, 
        tax_status: str = "ordinary"
    ) -> Employee:
        """Create and validate an employee record."""
        employee = Employee(
            name=name, 
            address=address, 
            ahv_number=ahv_number, 
            nationality=nationality, 
            tax_status=tax_status
        )
        return employee

    def create_employment(
        self, 
        employer_id: int, 
        employee_id: int, 
        start_date: date, 
        hourly_wage: float, 
        weekly_hours: float, 
        holiday_entitlement: int = 20
    ) -> Employment:
        """Create and validate an employment relationship."""
        # Validate wage and hours
        if hourly_wage < MIN_HOURLY_WAGE:
            raise ValueError(f"Hourly wage (CHF {hourly_wage}) is below the Basel-Stadt minimum wage (CHF {MIN_HOURLY_WAGE}).")
        if weekly_hours < MIN_WEEKLY_HOURS:
            print(f"Warning: Weekly hours ({weekly_hours}) are unusually low (recommended minimum: {MIN_WEEKLY_HOURS}).")

        employment = Employment(
            employer_id=employer_id, 
            employee_id=employee_id, 
            start_date=start_date, 
            hourly_wage=hourly_wage, 
            weekly_hours=weekly_hours, 
            holiday_entitlement=holiday_entitlement,
            remaining_holiday_balance=holiday_entitlement * weekly_hours  # Convert days to hours
        )
        return employment

    def generate_contract(
        self, 
        employment: Employment, 
        employer: Employer, 
        employee: Employee
    ) -> str:
        """Generate a legally compliant employment contract (placeholder).
        
        Returns:
            str: Path to the generated contract (e.g., PDF or digital document).
        """
        # Placeholder: In a real implementation, this would generate a PDF or digital document.
        # Example: Use a template engine (e.g., Jinja2) to populate a contract template.
        contract = (
            f"Employment Contract\n"
            f"===================\n"
            f"Employer: {employer.name} ({employer.ahv_number})\n"
            f"Employee: {employee.name} ({employee.ahv_number})\n"
            f"Start Date: {employment.start_date}\n"
            f"Hourly Wage: CHF {employment.hourly_wage}\n"
            f"Weekly Hours: {employment.weekly_hours}\n"
            f"Holiday Entitlement: {employment.holiday_entitlement} days/year\n"
        )
        return contract