from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


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
    hourly_wage_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_hours: Mapped[float] = mapped_column(Float, nullable=False)
    holiday_entitlement: Mapped[int] = mapped_column(Integer, nullable=False)


class MonthlyRecordRow(Base):
    __tablename__ = "monthly_records"
    __table_args__ = (UniqueConstraint("employment_id", "month", "year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employment_id: Mapped[int] = mapped_column(ForeignKey("employments.id"), nullable=False)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id"), nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    hours_worked: Mapped[float] = mapped_column(Float, nullable=False)
    holiday_hours: Mapped[float] = mapped_column(Float, nullable=False)
    public_holiday_hours: Mapped[float] = mapped_column(Float, nullable=False)
    cash_bonus_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    expense_reimbursements_cents: Mapped[int] = mapped_column(Integer, nullable=False)


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
