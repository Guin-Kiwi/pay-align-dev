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


class SetupRepository(ABC):
    @abstractmethod
    def get_employer(self) -> Employer | None:
        """Return the one employer, or None if none is saved yet."""

    @abstractmethod
    def save(self, employer: Employer, employee: Employee, employment: Employment) -> SetupResult:
        """Save all three in one transaction and link the employment to the employer and employee.

        An employer that already has an id is saved already and is only linked.
        """
