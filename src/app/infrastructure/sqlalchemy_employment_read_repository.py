from decimal import Decimal

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from src.app.application.ports.employment_read_repository import (
    CompletedMonth,
    EmploymentOverview,
    EmploymentReadRepository,
    SavedPayslip,
)
from src.app.domain.payslip import Payslip
from src.app.infrastructure.orm_models import (
    EmployeeRow,
    EmployerRow,
    EmploymentRow,
    MonthlyRecordRow,
    PayrollSnapshotRow,
    PayslipRow,
)


class SqlAlchemyEmploymentReadRepository(EmploymentReadRepository):
    def __init__(self, engine: Engine):
        self.engine = engine

    def _employment_query(self, account_id: int):
        return (
            select(EmploymentRow, EmployeeRow.name)
            .join(EmployerRow, EmployerRow.id == EmploymentRow.employer_id)
            .join(EmployeeRow, EmployeeRow.id == EmploymentRow.employee_id)
            .where(EmployerRow.account_id == account_id)
        )

    @staticmethod
    def _overview(row) -> EmploymentOverview:
        employment, employee_name = row
        return EmploymentOverview(
            id=employment.id,
            employee_name=employee_name,
            start_date=employment.start_date,
            end_date=employment.end_date,
        )

    def list_employments(self, account_id: int) -> list[EmploymentOverview]:
        with Session(self.engine) as session:
            rows = session.execute(
                self._employment_query(account_id).order_by(EmploymentRow.id)
            ).all()
            return [self._overview(row) for row in rows]

    def get_employment(
        self, account_id: int, employment_id: int
    ) -> EmploymentOverview | None:
        with Session(self.engine) as session:
            row = session.execute(
                self._employment_query(account_id).where(
                    EmploymentRow.id == employment_id
                )
            ).first()
            return self._overview(row) if row else None

    def list_months(self, account_id: int, employment_id: int) -> list[CompletedMonth]:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(MonthlyRecordRow)
                .join(EmploymentRow, EmploymentRow.id == MonthlyRecordRow.employment_id)
                .join(EmployerRow, EmployerRow.id == EmploymentRow.employer_id)
                .where(
                    EmployerRow.account_id == account_id,
                    EmploymentRow.id == employment_id,
                )
                .order_by(MonthlyRecordRow.year, MonthlyRecordRow.month)
            ).all()
            return [
                CompletedMonth(row.id, row.year, row.month) for row in rows
            ]

    def get_payslip(
        self, account_id: int, employment_id: int, year: int, month: int
    ) -> SavedPayslip | None:
        with Session(self.engine) as session:
            row = session.execute(
                select(MonthlyRecordRow, PayslipRow, PayrollSnapshotRow)
                .join(EmploymentRow, EmploymentRow.id == MonthlyRecordRow.employment_id)
                .join(EmployerRow, EmployerRow.id == EmploymentRow.employer_id)
                .join(PayslipRow, PayslipRow.monthly_record_id == MonthlyRecordRow.id)
                .join(
                    PayrollSnapshotRow,
                    PayrollSnapshotRow.monthly_record_id == MonthlyRecordRow.id,
                )
                .where(
                    EmployerRow.account_id == account_id,
                    EmploymentRow.id == employment_id,
                    MonthlyRecordRow.year == year,
                    MonthlyRecordRow.month == month,
                )
            ).first()
            if row is None:
                return None
            record, saved, snapshot = row
            amounts = {
                name: Decimal(getattr(saved, f"{name}_cents")).scaleb(-2)
                for name in Payslip.__dataclass_fields__
                if name not in {"id", "monthly_record_id"}
            }
            return SavedPayslip(
                payslip=Payslip(
                    id=saved.id,
                    monthly_record_id=record.id,
                    **amounts,
                ),
                holiday_balance_minutes=snapshot.holiday_balance_minutes,
                hourly_wage=Decimal(snapshot.hourly_wage_cents).scaleb(-2),
                cash_bonus=Decimal(record.cash_bonus_cents).scaleb(-2),
                expense_reimbursements=Decimal(record.expense_reimbursements_cents).scaleb(-2),
                worked_minutes=snapshot.worked_minutes,
                public_holiday_worked_minutes=snapshot.public_holiday_worked_minutes,
                annual_holiday_taken_minutes=snapshot.annual_holiday_taken_minutes,
                public_holiday_taken_minutes=snapshot.public_holiday_taken_minutes,
            )
