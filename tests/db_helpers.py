from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.app.infrastructure.orm_models import (
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


def count_rows(engine, table_name: str) -> int:
    with Session(engine) as session:
        return int(session.scalar(select(func.count()).select_from(TABLES[table_name])))
