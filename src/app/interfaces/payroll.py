import sqlite3
from datetime import date, time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.app.application.payroll_service import PayrollService
from src.app.domain.constants import RULES_YEAR
from src.app.domain.employment import Employment
from src.app.domain.work_entry import WorkEntry
from src.app.infrastructure.sqlite_payroll_repository import SQLitePayrollRepository

payroll_router = APIRouter()
payroll_service = PayrollService()
# TODO(PR #3 review): in-memory database; read DATABASE_URL, to be replaced by SQLAlchemy. Owner: Ayla (@Guin-Kiwi).
repository = SQLitePayrollRepository(sqlite3.connect(":memory:", check_same_thread=False))

class MonthlyPayrollRequest(BaseModel):
    employment_id: int
    employer_id: int
    employee_id: int
    hourly_wage: float = Field(..., gt=0)
    weekly_hours: float = Field(..., gt=0)
    year: int = Field(..., ge=RULES_YEAR, le=RULES_YEAR)
    month: int = Field(..., ge=1, le=12)
    hours_worked: float | None = Field(None, ge=0)
    holiday_hours: float = Field(0, ge=0)
    public_holiday_hours: float = Field(0, ge=0)
    cash_bonus: float = Field(0, ge=0)
    expense_reimbursements: float = Field(0, ge=0)


class WorkEntryRequest(BaseModel):
    work_date: date
    start_time: time
    end_time: time
    unpaid_break_hours: float = Field(0, ge=0)
    paid: bool = True


# TODO(PR #3 review): duplicate class; merge into one. Owner: payroll router (Ayla (@Guin-Kiwi), then Aaron (@aaroncasula)).
class MonthlyPayrollRequest(MonthlyPayrollRequest):
    work_entries: list[WorkEntryRequest] | None = None

class PayslipResponse(BaseModel):
    monthly_record_id: int
    gross_wage: float = Field(..., description="Gross wage in CHF")
    net_payout: float

@payroll_router.post("/monthly-payroll", response_model=dict)
async def process_monthly_payroll(payload: MonthlyPayrollRequest):
    employment = Employment(
        id=payload.employment_id,
        employer_id=payload.employer_id,
        employee_id=payload.employee_id,
        hourly_wage=payload.hourly_wage,
        weekly_hours=payload.weekly_hours,
    )
    entries = None
    if payload.work_entries is not None:
        entries = [WorkEntry(**entry.model_dump()) for entry in payload.work_entries]
    try:
        record, payslip = payroll_service.process_monthly_payroll(
            repository=repository,
            employment=employment,
            month=payload.month,
            year=payload.year,
            hours_worked=payload.hours_worked,
            holiday_hours=payload.holiday_hours,
            public_holiday_hours=payload.public_holiday_hours,
            cash_bonus=payload.cash_bonus,
            expense_reimbursements=payload.expense_reimbursements,
            work_entries=entries,
        )
    # TODO(PR #3 review): AnnualLimitExceededError, InvalidPayrollInputError and IntegrityError become HTTP 500. Owner: payroll router (Ayla (@Guin-Kiwi), then Aaron (@aaroncasula)).
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"monthly_record_id": record.id, **payslip.__dict__}

# TODO(PR #3 review): TASKS.md specifies /payslips/{employment_id}/{year}/{month}. Owner: payroll router (Ayla (@Guin-Kiwi), then Aaron (@aaroncasula)).
@payroll_router.get("/payslips/{monthly_record_id}", response_model=PayslipResponse)
async def get_payslip(monthly_record_id: int):
    try:
        return repository.get_payslip(monthly_record_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error