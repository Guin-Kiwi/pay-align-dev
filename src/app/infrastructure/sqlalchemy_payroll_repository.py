from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.app.application.ports.payroll_repository import (
    PayrollRepositoryPort,
    EmploymentTerms,
    MonthlyRecordInput,
    RunSnapshot,
    PayslipInput,
    PriorRun,
    SavedPayrollRun,
    StoredEmployment,
    WorkEntryInput,
)
from src.app.domain.hour_categories import MinuteTotals
from src.app.domain.errors import (
    DuplicateMonthError,
    InvalidHolidayBalanceError,
    InvalidPayrollInputError,
)
from src.app.infrastructure.orm_models import (
    EmploymentRow,
    EmployerRow,
    MonthlyRecordRow,
    PayrollSnapshotRow,
    PayslipRow,
    WorkEntryRow,
)


POSTGRES_UNIQUE_VIOLATION = "23505"


def _is_unique_violation(error: IntegrityError) -> bool:
    if getattr(error.orig, "sqlstate", None) == POSTGRES_UNIQUE_VIOLATION:
        return True
    return "UNIQUE constraint failed" in str(error.orig)


class SqlAlchemyPayrollRepository(PayrollRepositoryPort):
    def __init__(self, engine) -> None:
        self.engine = engine

    def _snapshot_values(
        self, monthly_record_id: int, snapshot: RunSnapshot
    ) -> PayrollSnapshotRow:
        if snapshot.holiday_balance_minutes < 0:
            raise InvalidHolidayBalanceError(
                "Holiday balance cannot be negative."
            )
        terms = snapshot.employment
        hours = snapshot.hours
        return PayrollSnapshotRow(
            monthly_record_id=monthly_record_id,
            hourly_wage_cents=terms.hourly_wage_cents,
            weekly_minutes=terms.weekly_minutes,
            holiday_weeks=terms.holiday_weeks,
            employment_start_date=terms.employment_start_date,
            employment_end_date=terms.employment_end_date,
            ruleset_version=snapshot.ruleset_version,
            worked_minutes=hours.worked,
            public_holiday_worked_minutes=hours.public_holiday_worked,
            annual_holiday_taken_minutes=hours.annual_holiday_taken,
            public_holiday_taken_minutes=hours.public_holiday_taken,
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
        snapshot: RunSnapshot,
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
            raise InvalidPayrollInputError(
                "The payroll run conflicts with stored data and was not saved."
            ) from error

    def run_snapshot(self, monthly_record_id: int) -> RunSnapshot | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(PayrollSnapshotRow).where(
                    PayrollSnapshotRow.monthly_record_id == monthly_record_id
                )
            )
            if row is None:
                return None
            return RunSnapshot(
                employment=EmploymentTerms(
                    hourly_wage_cents=row.hourly_wage_cents,
                    weekly_minutes=row.weekly_minutes,
                    holiday_weeks=row.holiday_weeks,
                    employment_start_date=row.employment_start_date,
                    employment_end_date=row.employment_end_date,
                ),
                ruleset_version=row.ruleset_version,
                hours=MinuteTotals(
                    worked=row.worked_minutes,
                    public_holiday_worked=row.public_holiday_worked_minutes,
                    annual_holiday_taken=row.annual_holiday_taken_minutes,
                    public_holiday_taken=row.public_holiday_taken_minutes,
                ),
                holiday_balance_minutes=row.holiday_balance_minutes,
            )

    def _gross_of_year(self, year: int, *conditions) -> int:
        with Session(self.engine) as session:
            value = session.scalar(
                select(func.coalesce(func.sum(PayslipRow.gross_wage_cents), 0))
                .join(MonthlyRecordRow)
                .where(MonthlyRecordRow.year == year, *conditions)
            )
            return int(value)

    def employee_gross_to_date(
        self, employee_id: int, employer_id: int, year: int
    ) -> int:
        return self._gross_of_year(
            year,
            MonthlyRecordRow.employee_id == employee_id,
            MonthlyRecordRow.employer_id == employer_id,
        )

    def employer_gross_to_date(self, employer_id: int, year: int) -> int:
        return self._gross_of_year(year, MonthlyRecordRow.employer_id == employer_id)

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
            return PriorRun(
                record.id, record.year, record.month, snapshot.holiday_balance_minutes
            )

    def employment_terms(
        self, employment_id: int, account_id: int
    ) -> StoredEmployment | None:
        if not isinstance(account_id, int) or isinstance(account_id, bool) or account_id <= 0:
            return None
        with Session(self.engine) as session:
            query = select(EmploymentRow).join(EmployerRow).where(
                EmploymentRow.id == employment_id,
                EmployerRow.account_id == account_id,
            )
            row = session.scalar(query)
            if row is None:
                return None
            return StoredEmployment(
                employer_id=row.employer_id,
                employee_id=row.employee_id,
                terms=EmploymentTerms(
                    hourly_wage_cents=row.hourly_wage_cents,
                    weekly_minutes=row.weekly_minutes,
                    holiday_weeks=row.holiday_weeks,
                    employment_start_date=row.start_date,
                    employment_end_date=row.end_date,
                ),
            )
