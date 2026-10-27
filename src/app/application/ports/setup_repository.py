from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.app.domain.employee import Employee
from src.app.domain.employer import Employer
from src.app.domain.employment import Employment


@dataclass(frozen=True)
class SetupResult:
    employer_id: int
    employee_id: int
    employment_id: int


class EmployerAlreadyExistsError(Exception):
    """The account already has an employer profile."""


class SetupRepository(ABC):
    @abstractmethod
    def save_employer(self, account_id: int, employer: Employer) -> Employer:
        """Create one employer profile for an account, or reject a duplicate."""

    @abstractmethod
    def update_employer(self, account_id: int, employer: Employer) -> Employer | None:
        """Update the account's employer, or return None if it has no profile."""

    @abstractmethod
    def get_employer(self, account_id: int) -> Employer | None:
        """Return this account's employer, or None before onboarding."""

    @abstractmethod
    def get_employee(self, ahv_number: str, account_id: int) -> Employee | None:
        """Return an employee linked to this account's employer, or None."""

    @abstractmethod
    def get_employment(self, employment_id: int, account_id: int) -> Employment | None:
        """Return an owned employment, or None if unknown or out of scope."""

    @abstractmethod
    def save(
        self, account_id: int, employer: Employer, employee: Employee, employment: Employment
    ) -> SetupResult:
        """Save all three in one transaction and link the employment to the employer and employee.

        An employer or employee that already has an id is saved already and is only linked.
        """
