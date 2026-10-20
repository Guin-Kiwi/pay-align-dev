from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.app.application.ports.payroll_repository import (
    MonthlyRecordInput,
    PayrollSnapshotInput,
    PayslipInput,
    PriorRun,
    SavedPayrollRun,
    WorkEntryInput,
)
from src.app.domain.errors import (
    DuplicateMonthError,
    InvalidHolidayBalanceError,
    InvalidPayrollInputError,
)
from src.app.infrastructure.orm_models import (
    MonthlyRecordRow,
    PayrollSnapshotRow,
    PayslipRow,
    WorkEntryRow,
)


def _is_unique_violation(error: IntegrityError) -> bool:
    return "UNIQUE constraint failed" in str(error.orig)


class SqlAlchemyPayrollRepository:
    def __init__(self, engine) -> None:
        self.engine = engine

    def _snapshot_values(
        self, monthly_record_id: int, snapshot: PayrollSnapshotInput
    ) -> PayrollSnapshotRow:
        if snapshot.holiday_balance_minutes < 0:
            raise InvalidHolidayBalanceError(
                "Holiday balance cannot be negative."
            )
        return PayrollSnapshotRow(
            monthly_record_id=monthly_record_id,
            hourly_wage_cents=snapshot.hourly_wage_cents,
            weekly_minutes=snapshot.weekly_minutes,
            holiday_weeks=snapshot.holiday_weeks,
            ruleset_version=snapshot.ruleset_version,
            worked_minutes=snapshot.worked_minutes,
            public_holiday_worked_minutes=snapshot.public_holiday_worked_minutes,
            annual_holiday_taken_minutes=snapshot.annual_holiday_taken_minutes,
            public_holiday_taken_minutes=snapshot.public_holiday_taken_minutes,
            holiday_balance_minutes=snapshot.holiday_balance_minutes,
        )

    @staticmethod
    def _payslip_values(monthly_record_id: int, payslip: PayslipInput) -> PayslipRow:
        return PayslipRow(
            monthly_record_id=monthly_record_id,
            **payslip.__dict__,
        )

    def save_payroll_run(
        self,
        record: MonthlyRecordInput,
        entries: tuple[WorkEntryInput, ...],
        snapshot: PayrollSnapshotInput,
        payslip: PayslipInput,
    ) -> SavedPayrollRun:
        try:
            with Session(self.engine) as session, session.begin():
                monthly_record = MonthlyRecordRow(**record.__dict__)
                session.add(monthly_record)
                session.flush()
                session.add_all(
                    WorkEntryRow(monthly_record_id=monthly_record.id, **entry.__dict__)
                    for entry in entries
                )
                session.add(self._snapshot_values(monthly_record.id, snapshot))
                payroll_payslip = self._payslip_values(monthly_record.id, payslip)
                session.add(payroll_payslip)
                session.flush()
                return SavedPayrollRun(monthly_record.id, payroll_payslip.id)
        except IntegrityError as error:
            if _is_unique_violation(error):
                raise DuplicateMonthError(
                    "Payroll month or snapshot already exists."
                ) from error
            raise InvalidPayrollInputError(str(error.orig)) from error

    def save_snapshot(self, record_id: int, snapshot: PayrollSnapshotInput) -> int:
        try:
            with Session(self.engine) as session, session.begin():
                row = self._snapshot_values(record_id, snapshot)
                session.add(row)
                session.flush()
                return row.id
        except IntegrityError as error:
            if _is_unique_violation(error):
                raise DuplicateMonthError("Snapshot already exists.") from error
            raise InvalidPayrollInputError(str(error.orig)) from error

    def employee_gross_to_date(self, employee_id: int, year: int) -> int:
        with Session(self.engine) as session:
            value = session.scalar(
                select(func.coalesce(func.sum(PayslipRow.gross_wage_cents), 0))
                .join(MonthlyRecordRow)
                .where(
                    MonthlyRecordRow.employee_id == employee_id,
                    MonthlyRecordRow.year == year,
                )
            )
            return int(value)

    def employer_gross_to_date(self, employer_id: int, year: int) -> int:
        with Session(self.engine) as session:
            value = session.scalar(
                select(func.coalesce(func.sum(PayslipRow.gross_wage_cents), 0))
                .join(MonthlyRecordRow)
                .where(
                    MonthlyRecordRow.employer_id == employer_id,
                    MonthlyRecordRow.year == year,
                )
            )
            return int(value)

    def prior_run(self, employment_id: int) -> PriorRun | None:
        with Session(self.engine) as session:
            row = session.execute(
                select(MonthlyRecordRow, PayrollSnapshotRow)
                .join(
                    PayrollSnapshotRow,
                    PayrollSnapshotRow.monthly_record_id == MonthlyRecordRow.id,
                )
                .where(MonthlyRecordRow.employment_id == employment_id)
                .order_by(MonthlyRecordRow.year.desc(), MonthlyRecordRow.month.desc())
                .limit(1)
            ).first()
            if row is None:
                return None
            record, snapshot = row
            return PriorRun(record.id, record.year, snapshot.holiday_balance_minutes)

    def count_rows(self, table_name: str) -> int:
        allowed = {
            "monthly_records": MonthlyRecordRow,
            "work_entries": WorkEntryRow,
            "payroll_snapshots": PayrollSnapshotRow,
            "payslips": PayslipRow,
        }
        with Session(self.engine) as session:
            return int(session.scalar(select(func.count()).select_from(allowed[table_name])))