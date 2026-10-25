from src.app.application.ports.setup_repository import SetupRepository, SetupResult
from src.app.domain.employee import Employee
from src.app.domain.employer import Employer
from src.app.domain.employment import Employment


class InMemorySetupRepository(SetupRepository):
    """Keeps setup data in memory, for tests. Data is lost on restart."""

    def __init__(self):
        self.employers: dict[int, Employer] = {}
        self.employees: list[Employee] = []
        self.employments: list[Employment] = []
        self._employee_employers: dict[int, int] = {}

    def get_employer(self, account_id: int) -> Employer | None:
        return self.employers.get(account_id)

    def get_employee(self, ahv_number: str, account_id: int) -> Employee | None:
        employer = self.get_employer(account_id)
        if employer is None:
            return None
        return next((e for e in self.employees if e.ahv_number == ahv_number
                     and self._employee_employers.get(e.id) == employer.id), None)

    def get_employment(self, employment_id: int, account_id: int) -> Employment | None:
        employer = self.get_employer(account_id)
        if employer is None:
            return None
        return next((e for e in self.employments if e.id == employment_id
                     and e.employer_id == employer.id), None)

    def save(
        self, account_id: int, employer: Employer, employee: Employee, employment: Employment
    ) -> SetupResult:
        owned = self.get_employer(account_id)
        if employer.id is not None and (owned is None or owned.id != employer.id):
            raise ValueError("Employer not found.")
        if employer.id is None and owned is not None:
            raise ValueError("An employer already exists.")
        if employee.id is not None and (
            owned is None or self._employee_employers.get(employee.id) != owned.id
        ):
            raise ValueError("Employee not found.")
        if employer.id is None:
            employer.id = max((e.id for e in self.employers.values()), default=0) + 1
            self.employers[account_id] = employer
        if employee.id is None:
            employee.id = len(self.employees) + 1
            self.employees.append(employee)
            self._employee_employers[employee.id] = employer.id
        employment.id = len(self.employments) + 1
        employment.employer_id = employer.id
        employment.employee_id = employee.id
        self.employments.append(employment)
        return SetupResult(employer.id, employee.id, employment.id)
