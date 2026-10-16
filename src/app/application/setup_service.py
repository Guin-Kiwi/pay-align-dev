# src/app/application/setup_service.py

import logging
from datetime import date
from typing import Optional

from src.app.application.ports.setup_repository import SetupRepository, SetupResult
from src.app.domain.employer import Employer
from src.app.domain.employee import Employee
from src.app.domain.employment import Employment
from src.app.domain.constants import MIN_WEEKLY_HOURS, RULES_YEAR

logger = logging.getLogger(__name__)


class EmployerAlreadyExistsError(Exception):
    """Raised when setup sends employer details although an employer is already saved."""


def _build(part: str, build, details: dict):
    try:
        return build(**details)
    except ValueError as error:
        raise ValueError(f"{part}: {error}") from error


class SetupService:
    """Handles the setup of an employment relationship for household help."""

    def __init__(self, repository: SetupRepository):
        self.repository = repository

    def get_employer(self) -> Employer | None:
        """Return the saved employer, or None if setup has not run yet."""
        return self.repository.get_employer()

    def set_up_employment(
        self,
        employee: dict,
        employment: dict,
        employer: dict | None = None,
    ) -> SetupResult:
        """Validate employer, employee and employment, then save all three together.

        Send employer details only when no employer is saved yet.
        """
        saved_employer = self.repository.get_employer()
        if saved_employer is not None and employer is not None:
            raise EmployerAlreadyExistsError("An employer already exists.")
        if saved_employer is None and employer is None:
            raise ValueError("Employer: Details are required because no employer exists yet.")

        new_employer = saved_employer or _build("Employer", self.create_employer, employer)
        new_employee = _build("Employee", self.create_employee, employee)
        new_employment = _build("Employment", self.create_employment, employment)
        return self.repository.save(new_employer, new_employee, new_employment)

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
        start_date: date, 
        hourly_wage: float, 
        weekly_hours: float,
        holiday_weeks: int = 4,
        end_date: Optional[date] = None,
        employer_id: int = 0,
        employee_id: int = 0,
    ) -> Employment:
        """Create and validate an employment relationship."""
        if start_date.year != RULES_YEAR:
            raise ValueError(
                f"Start date must be in {RULES_YEAR}; PayAlign has payroll rules for {RULES_YEAR} only."
            )
        if weekly_hours < MIN_WEEKLY_HOURS:
            logger.warning(
                "Weekly hours (%s) are unusually low (recommended minimum: %s).",
                weekly_hours,
                MIN_WEEKLY_HOURS,
            )

        employment = Employment(
            employer_id=employer_id, 
            employee_id=employee_id, 
            start_date=start_date,
            end_date=end_date,
            hourly_wage=hourly_wage,
            weekly_hours=weekly_hours,
            holiday_weeks=holiday_weeks,
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
            f"Holiday: {employment.holiday_weeks} weeks/year\n"
        )
        return contract