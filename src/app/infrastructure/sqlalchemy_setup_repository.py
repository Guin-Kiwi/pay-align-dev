from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from src.app.application.ports.setup_repository import SetupRepository, SetupResult
from src.app.domain.employee import Employee
from src.app.domain.employer import Employer
from src.app.domain.employment import Employment
from src.app.infrastructure.orm_models import EmployeeRow, EmployerRow, EmploymentRow


class SqlAlchemySetupRepository(SetupRepository):
    """Saves setup data in the database; wages as centimes, weekly hours as whole minutes."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def get_employer(self, account_id: int) -> Employer | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(EmployerRow).where(EmployerRow.account_id == account_id)
            )
            return _to_employer(row) if row else None

    def get_employee(self, ahv_number: str, account_id: int) -> Employee | None:
        with Session(self.engine) as session:
            row = session.scalars(
                select(EmployeeRow)
                .join(EmploymentRow, EmploymentRow.employee_id == EmployeeRow.id)
                .join(EmployerRow, EmployerRow.id == EmploymentRow.employer_id)
                .where(
                    EmployeeRow.ahv_number == ahv_number,
                    EmployerRow.account_id == account_id,
                )
            ).first()
            return _to_employee(row) if row else None

    def get_employment(self, employment_id: int, account_id: int) -> Employment | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(EmploymentRow)
                .join(EmployerRow, EmployerRow.id == EmploymentRow.employer_id)
                .where(
                    EmploymentRow.id == employment_id,
                    EmployerRow.account_id == account_id,
                )
            )
            return _to_employment(row) if row else None

    def save(
        self, account_id: int, employer: Employer, employee: Employee, employment: Employment
    ) -> SetupResult:
        with Session(self.engine) as session, session.begin():
            if employer.id is not None:
                owned = session.scalar(
                    select(EmployerRow.id).where(
                        EmployerRow.id == employer.id,
                        EmployerRow.account_id == account_id,
                    )
                )
                if owned is None:
                    raise ValueError("Employer not found.")
            employer_id = employer.id or _insert(session, EmployerRow(
                account_id=account_id,
                name=employer.name,
                address=employer.address,
                ahv_number=employer.ahv_number,
                contact_info=employer.contact_info,
            ))
            if employee.id is not None:
                linked = session.scalar(
                    select(EmploymentRow.id).where(
                        EmploymentRow.employee_id == employee.id,
                        EmploymentRow.employer_id == employer_id,
                    )
                )
                if linked is None:
                    raise ValueError("Employee not found.")
            employee_id = employee.id or _insert(session, EmployeeRow(
                name=employee.name,
                address=employee.address,
                ahv_number=employee.ahv_number,
                nationality=employee.nationality,
                tax_status=employee.tax_status,
            ))
            employment_id = _insert(session, EmploymentRow(
                employer_id=employer_id,
                employee_id=employee_id,
                start_date=employment.start_date,
                end_date=employment.end_date,
                hourly_wage_cents=_to_cents(employment.hourly_wage),
                weekly_minutes=round(employment.weekly_hours * 60),
                holiday_weeks=employment.holiday_weeks,
            ))
        employer.id, employee.id, employment.id = employer_id, employee_id, employment_id
        employment.employer_id, employment.employee_id = employer_id, employee_id
        return SetupResult(employer_id, employee_id, employment_id)


def _insert(session: Session, row) -> int:
    session.add(row)
    session.flush()
    return row.id


def _to_cents(francs) -> int:
    return int((Decimal(str(francs)) * 100).to_integral_value(ROUND_HALF_UP))


def _to_employer(row: EmployerRow) -> Employer:
    return Employer(
        id=row.id,
        name=row.name,
        address=row.address,
        ahv_number=row.ahv_number,
        contact_info=row.contact_info,
    )


def _to_employee(row: EmployeeRow) -> Employee:
    return Employee(
        id=row.id,
        name=row.name,
        address=row.address,
        ahv_number=row.ahv_number,
        nationality=row.nationality,
        tax_status=row.tax_status,
    )


def _to_employment(row: EmploymentRow) -> Employment:
    return Employment(
        id=row.id,
        employer_id=row.employer_id,
        employee_id=row.employee_id,
        start_date=row.start_date,
        end_date=row.end_date,
        hourly_wage=row.hourly_wage_cents / 100,
        weekly_hours=row.weekly_minutes / 60,
        holiday_weeks=row.holiday_weeks,
    )
