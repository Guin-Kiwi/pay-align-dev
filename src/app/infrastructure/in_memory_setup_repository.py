from src.app.application.ports.setup_repository import SetupRepository, SetupResult
from src.app.domain.employee import Employee
from src.app.domain.employer import Employer
from src.app.domain.employment import Employment


class InMemorySetupRepository(SetupRepository):
    """Keeps setup data in memory, for tests. Data is lost on restart."""

    def __init__(self):
        self.employer: Employer | None = None
        self.employees: list[Employee] = []
        self.employments: list[Employment] = []

    def get_employer(self) -> Employer | None:
        return self.employer

    def get_employee(self, ahv_number: str) -> Employee | None:
        return next((e for e in self.employees if e.ahv_number == ahv_number), None)

    def get_employment(self, employment_id: int) -> Employment | None:
        return next((e for e in self.employments if e.id == employment_id), None)

    def save(self, employer: Employer, employee: Employee, employment: Employment) -> SetupResult:
        if employer.id is None:
            employer.id = 1
            self.employer = employer
        if employee.id is None:
            employee.id = len(self.employees) + 1
            self.employees.append(employee)
        employment.id = len(self.employments) + 1
        employment.employer_id = employer.id
        employment.employee_id = employee.id
        self.employments.append(employment)
        return SetupResult(employer.id, employee.id, employment.id)
