from datetime import date

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from src.app.domain.constants import RULES_YEAR_START
from src.app.infrastructure.orm_models import (
    EmployeeRow,
    EmployerRow,
    EmploymentRow,
    MonthlyRecordRow,
    PayrollSnapshotRow,
    PayslipRow,
    WorkEntryRow,
)

TABLES = {
    "monthly_records": MonthlyRecordRow,
    "work_entries": WorkEntryRow,
    "payroll_snapshots": PayrollSnapshotRow,
    "payslips": PayslipRow,
}


def add_employment(
    engine: Engine,
    employment_id: int = 1,
    employer_id: int = 1,
    employee_id: int = 1,
    start_date: date = RULES_YEAR_START,
    end_date: date | None = None,
    hourly_wage_cents: int = 2500,
    weekly_minutes: int = 600,
    holiday_weeks: int = 4,
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
                    start_date=start_date,
                    end_date=end_date,
                    hourly_wage_cents=hourly_wage_cents,
                    weekly_minutes=weekly_minutes,
                    holiday_weeks=holiday_weeks,
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


def count_rows(engine: Engine, table_name: str) -> int:
    with Session(engine) as session:
        return int(session.scalar(select(func.count()).select_from(TABLES[table_name])))
