from datetime import date, time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.app.application.payroll_service import PayrollService
from src.app.application.ports.payroll_repository import PayrollRepositoryPort
from src.app.domain.constants import RULES_YEAR
from src.app.domain.errors import (
    AnnualLimitExceededError,
    DuplicateMonthError,
    EmploymentNotFoundError,
    InvalidHolidayBalanceError,
    InvalidPayrollInputError,
)
from src.app.domain.hour_categories import HourCategory
from src.app.domain.work_entry import WorkEntry, calculate_paid_minutes

payroll_router = APIRouter()


class WorkEntryRequest(BaseModel):
    work_date: date
    category: HourCategory
    start_time: time | None = None
    end_time: time | None = None
    unpaid_break_minutes: int = Field(0, ge=0)
    paid_minutes: int | None = Field(None, ge=0)


class MonthlyPayrollRequest(BaseModel):
    employment_id: int
    year: int = Field(..., ge=RULES_YEAR, le=RULES_YEAR)
    month: int = Field(..., ge=1, le=12)
    cash_bonus: Decimal = Field(Decimal("0.00"), ge=0)
    expense_reimbursements: Decimal = Field(Decimal("0.00"), ge=0)
    work_entries: list[WorkEntryRequest]


class PayslipResponse(BaseModel):
    monthly_record_id: int
    gross_wage: Decimal
    net_payout: Decimal


def get_payroll_service(request: Request) -> PayrollService:
    return request.app.state.payroll_service


def get_payroll_repository(request: Request) -> PayrollRepositoryPort:
    return request.app.state.payroll_repository


def _to_work_entry(entry: WorkEntryRequest) -> WorkEntry:
    if entry.start_time is None and entry.end_time is None:
        if entry.category in (HourCategory.WORKED, HourCategory.PUBLIC_HOLIDAY_WORKED):
            raise InvalidPayrollInputError(
                "A work entry needs a start and an end time."
            )
        if entry.paid_minutes is None:
            raise InvalidPayrollInputError(
                "A leave entry needs paid_minutes or a start and end time."
            )
        return WorkEntry(
            work_date=entry.work_date,
            category=entry.category,
            paid_minutes=entry.paid_minutes,
        )
    if entry.start_time is None or entry.end_time is None:
        raise InvalidPayrollInputError("A work entry needs both a start and an end time.")
    paid_minutes = calculate_paid_minutes(
        entry.start_time, entry.end_time, entry.unpaid_break_minutes
    )
    if entry.paid_minutes is not None and entry.paid_minutes != paid_minutes:
        raise InvalidPayrollInputError(
            "paid_minutes does not match the start time, end time and break."
        )
    return WorkEntry(
        work_date=entry.work_date,
        category=entry.category,
        paid_minutes=paid_minutes,
        start_time=entry.start_time,
        end_time=entry.end_time,
        unpaid_break_minutes=entry.unpaid_break_minutes,
    )


@payroll_router.post("/monthly-payroll", response_model=dict, status_code=201)
def process_monthly_payroll(
    payload: MonthlyPayrollRequest,
    service: PayrollService = Depends(get_payroll_service),
    repository: PayrollRepositoryPort = Depends(get_payroll_repository),
):
    try:
        record, payslip = service.process_monthly_payroll(
            repository=repository,
            employment_id=payload.employment_id,
            month=payload.month,
            year=payload.year,
            work_entries=[_to_work_entry(entry) for entry in payload.work_entries],
            cash_bonus=payload.cash_bonus,
            expense_reimbursements=payload.expense_reimbursements,
        )
    except EmploymentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (
        AnnualLimitExceededError,
        DuplicateMonthError,
        InvalidHolidayBalanceError,
        InvalidPayrollInputError,
        ValueError,
    ) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {
        "monthly_record_id": record.id,
        "gross_wage": str(payslip.gross_wage),
        "net_payout": str(payslip.net_payout),
    }