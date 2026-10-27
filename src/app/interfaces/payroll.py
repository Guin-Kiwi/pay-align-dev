from datetime import date, time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.app.application.payroll_service import PayrollService
from src.app.application.ports.employment_read_repository import SavedPayslip
from src.app.application.ports.payroll_repository import PayrollRepositoryPort
from src.app.domain.constants import PUBLIC_HOLIDAYS, RULES_YEAR
from src.app.domain.errors import (
    AnnualLimitExceededError,
    DuplicateMonthError,
    EmploymentNotFoundError,
    InvalidHolidayBalanceError,
    InvalidPayrollInputError,
    PayrollSnapshotReadError,
)
from src.app.domain.hour_categories import HourCategory
from src.app.domain.work_entry import WorkEntry, calculate_paid_minutes
from src.app.interfaces.auth import require_account_id, require_csrf_token
from src.app.interfaces.employment_reads import SavedPayslipResponse, saved_payslip_fields

payroll_router = APIRouter()
PAYROLL_SAVED_CONFIRMATION_UNAVAILABLE_MESSAGE = (
    "The payroll was saved, but its confirmation could not be loaded. "
    "Check the saved month before retrying."
)


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


class PayslipResponse(SavedPayslipResponse):
    message: str


class PublicHolidayCalendarResponse(BaseModel):
    year: int
    dates: list[date]


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


@payroll_router.get(
    "/public-holidays/{year}", response_model=PublicHolidayCalendarResponse
)
def public_holiday_calendar(
    year: int,
    _: int = Depends(require_account_id),
):
    if year != RULES_YEAR:
        raise HTTPException(
            status_code=422, detail="Payroll rules are not available for this year."
        )
    return {"year": year, "dates": sorted(PUBLIC_HOLIDAYS)}


@payroll_router.post("/monthly-payroll", response_model=PayslipResponse, status_code=201)
def process_monthly_payroll(
    payload: MonthlyPayrollRequest,
    _: None = Depends(require_csrf_token),
    account_id: int = Depends(require_account_id),
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
            account_id=account_id,
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
    try:
        snapshot = repository.run_snapshot(record.id)
    except PayrollSnapshotReadError as error:
        raise HTTPException(
            status_code=500,
            detail=PAYROLL_SAVED_CONFIRMATION_UNAVAILABLE_MESSAGE,
        ) from error
    if snapshot is None:
        raise HTTPException(
            status_code=500,
            detail=PAYROLL_SAVED_CONFIRMATION_UNAVAILABLE_MESSAGE,
        )
    saved = SavedPayslip(
        payslip=payslip,
        holiday_balance_minutes=snapshot.holiday_balance_minutes,
        hourly_wage=Decimal(snapshot.employment.hourly_wage_cents).scaleb(-2),
        cash_bonus=record.cash_bonus,
        expense_reimbursements=record.expense_reimbursements,
        worked_minutes=snapshot.hours.worked,
        public_holiday_worked_minutes=snapshot.hours.public_holiday_worked,
        annual_holiday_taken_minutes=snapshot.hours.annual_holiday_taken,
        public_holiday_taken_minutes=snapshot.hours.public_holiday_taken,
    )
    return PayslipResponse(
        **saved_payslip_fields(saved),
        message="Payroll processed successfully.",
    )
