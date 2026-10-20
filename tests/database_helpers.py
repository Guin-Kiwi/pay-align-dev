from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.app.domain.constants import RULES_YEAR_START
from src.app.infrastructure.orm_models import (
    EmployeeRow,
    EmployerRow,
    EmploymentRow,
    MonthlyRecordRow,
)


def add_employment(
    engine: Engine,
    employment_id: int = 1,
    employer_id: int = 1,
    employee_id: int = 1,
) -> int:
    """Create the employer, employee and employment rows a payroll run points at."""
    with Session(engine) as session, session.begin():
        if session.get(EmployerRow, employer_id) is None:
            session.add(
                EmployerRow(
                    id=employer_id,
                    name=f"Employer {employer_id}",
                    address="Freie Strasse 1, 4001 Basel",
                    ahv_number=f"employer-{employer_id}",
                    contact_info="employer@example.ch",
                )
            )
        if session.get(EmployeeRow, employee_id) is None:
            session.add(
                EmployeeRow(
                    id=employee_id,
                    name=f"Employee {employee_id}",
                    address="Clarastrasse 10, 4058 Basel",
                    ahv_number=f"employee-{employee_id}",
                    nationality="Switzerland",
                    tax_status="resident",
                )
            )
        session.flush()
        if session.get(EmploymentRow, employment_id) is None:
            session.add(
                EmploymentRow(
                    id=employment_id,
                    employer_id=employer_id,
                    employee_id=employee_id,
                    start_date=RULES_YEAR_START,
                    end_date=None,
                    hourly_wage_cents=2500,
                    weekly_minutes=600,
                    holiday_weeks=4,
                )
            )
    return employment_id


def add_monthly_record(engine: Engine, month: int = 1) -> int:
    """Create a monthly record (and the employment it needs) and return its id."""
    employment_id = add_employment(engine)
    with Session(engine) as session, session.begin():
        row = MonthlyRecordRow(
            employment_id=employment_id,
            employee_id=1,
            employer_id=1,
            month=month,
            year=RULES_YEAR_START.year,
            cash_bonus_cents=0,
            expense_reimbursements_cents=0,
        )
        session.add(row)
        session.flush()
        return row.id
