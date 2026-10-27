from dataclasses import asdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.app.application.employment_read_service import EmploymentReadService
from src.app.interfaces.auth import require_account_id

employment_reads_router = APIRouter()


class EmploymentOverviewResponse(BaseModel):
    id: int
    employee_name: str
    start_date: date
    end_date: date | None


class CompletedMonthResponse(BaseModel):
    monthly_record_id: int
    year: int
    month: int


class YearMonthResponse(BaseModel):
    year: int
    month: int


class MonthHistoryResponse(BaseModel):
    months: list[CompletedMonthResponse]
    next_month: YearMonthResponse | None


class SavedPayslipResponse(BaseModel):
    monthly_record_id: int
    gross_wage: Decimal
    ahv_deduction: Decimal
    alv_deduction: Decimal
    tax_deduction: Decimal
    nbu_deduction: Decimal
    net_payout: Decimal
    employer_ahv: Decimal
    employer_alv: Decimal
    employer_fak: Decimal
    employer_bu: Decimal
    admin_charge: Decimal
    total_employer_cost: Decimal
    holiday_balance_minutes: int
    hourly_wage: Decimal
    cash_bonus: Decimal
    expense_reimbursements: Decimal
    worked_minutes: int
    public_holiday_worked_minutes: int
    annual_holiday_taken_minutes: int
    public_holiday_taken_minutes: int


def get_employment_read_service(request: Request) -> EmploymentReadService:
    return request.app.state.employment_read_service


@employment_reads_router.get(
    "/employments", response_model=list[EmploymentOverviewResponse]
)
def list_employments(
    account_id: int = Depends(require_account_id),
    service: EmploymentReadService = Depends(get_employment_read_service),
):
    return service.list_employments(account_id)


@employment_reads_router.get(
    "/employments/{employment_id}", response_model=EmploymentOverviewResponse
)
def get_employment(
    employment_id: int,
    account_id: int = Depends(require_account_id),
    service: EmploymentReadService = Depends(get_employment_read_service),
):
    employment = service.get_employment(account_id, employment_id)
    if employment is None:
        raise HTTPException(status_code=404, detail="Employment not found.")
    return employment


@employment_reads_router.get(
    "/employments/{employment_id}/months", response_model=MonthHistoryResponse
)
def list_months(
    employment_id: int,
    account_id: int = Depends(require_account_id),
    service: EmploymentReadService = Depends(get_employment_read_service),
):
    history = service.month_history(account_id, employment_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Employment not found.")
    return history


@employment_reads_router.get(
    "/employments/{employment_id}/months/{year}/{month}",
    response_model=SavedPayslipResponse,
)
def get_saved_payslip(
    employment_id: int,
    year: int,
    month: int,
    account_id: int = Depends(require_account_id),
    service: EmploymentReadService = Depends(get_employment_read_service),
):
    saved = service.saved_payslip(account_id, employment_id, year, month)
    if saved is None:
        raise HTTPException(status_code=404, detail="Employment or month not found.")
    values = asdict(saved.payslip)
    values.pop("id")
    details = asdict(saved)
    details.pop("payslip")
    return SavedPayslipResponse(**values, **details)
