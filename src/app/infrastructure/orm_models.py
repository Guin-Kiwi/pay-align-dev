from datetime import date, time

from sqlalchemy import CheckConstraint, event, Date, ForeignKey, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.app.domain.errors import ImmutableRecordError


class Base(DeclarativeBase):
    pass


class AccountRow(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)


class EmployerRow(Base):
    __tablename__ = "employers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    ahv_number: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    contact_info: Mapped[str] = mapped_column(String, nullable=False)


class EmployeeRow(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    ahv_number: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    nationality: Mapped[str] = mapped_column(String, nullable=False)
    tax_status: Mapped[str] = mapped_column(String, nullable=False)


class EmploymentRow(Base):
    __tablename__ = "employments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    hourly_wage_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    holiday_weeks: Mapped[int] = mapped_column(Integer, nullable=False)


class MonthlyRecordRow(Base):
    __tablename__ = "monthly_records"
    __table_args__ = (UniqueConstraint("employment_id", "month", "year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employment_id: Mapped[int] = mapped_column(ForeignKey("employments.id"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id"), nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    cash_bonus_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    expense_reimbursements_cents: Mapped[int] = mapped_column(Integer, nullable=False)


class WorkEntryRow(Base):
    __tablename__ = "work_entries"
    __table_args__ = (
        CheckConstraint(
            "category IN ('worked', 'public_holiday_worked', 'annual_holiday_taken', "
            "'public_holiday_taken')",
            name="ck_work_entries_category",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    monthly_record_id: Mapped[int] = mapped_column(
        ForeignKey("monthly_records.id"), nullable=False
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    unpaid_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_minutes: Mapped[int] = mapped_column(Integer, nullable=False)


class PayrollSnapshotRow(Base):
    __tablename__ = "payroll_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    monthly_record_id: Mapped[int] = mapped_column(
        ForeignKey("monthly_records.id"), nullable=False, unique=True
    )
    hourly_wage_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    holiday_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    employment_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    employment_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ruleset_version: Mapped[str] = mapped_column(String, nullable=False)
    worked_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    public_holiday_worked_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    annual_holiday_taken_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    public_holiday_taken_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    holiday_balance_minutes: Mapped[int] = mapped_column(Integer, nullable=False)


class PayslipRow(Base):
    __tablename__ = "payslips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    monthly_record_id: Mapped[int] = mapped_column(
        ForeignKey("monthly_records.id"), nullable=False, unique=True
    )
    gross_wage_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    ahv_deduction_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    alv_deduction_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_deduction_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    nbu_deduction_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    net_payout_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    employer_ahv_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    employer_alv_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    employer_fak_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    employer_bu_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    admin_charge_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_employer_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False)


def _reject_change(mapper, connection, target) -> None:
    raise ImmutableRecordError(f"{mapper.local_table.name} rows cannot be changed.")


for _row_class in (PayrollSnapshotRow, WorkEntryRow):
    event.listen(_row_class, "before_update", _reject_change)
    event.listen(_row_class, "before_delete", _reject_change)
