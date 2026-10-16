from src.app.application.ports.setup_repository import SetupRepository, SetupResult
from src.app.domain.employee import Employee
from src.app.domain.employer import Employer
from src.app.domain.employment import Employment


class InMemorySetupRepository(SetupRepository):
    """Keeps setup data in memory until the SQLAlchemy repository exists. Data is lost on restart."""

    def __init__(self):
        self.employer: Employer | None = None
        self.employees: list[Employee] = []
        self.employments: list[Employment] = []

    def get_employer(self) -> Employer | None:
        return self.employer

    def save(self, employer: Employer, employee: Employee, employment: Employment) -> SetupResult:
        if employer.id is None:
            employer.id = 1
            self.employer = employer
        employee.id = len(self.employees) + 1
        self.employees.append(employee)
        employment.id = len(self.employments) + 1
        employment.employer_id = employer.id
        employment.employee_id = employee.id
        self.employments.append(employment)
        return SetupResult(employer.id, employee.id, employment.id)
