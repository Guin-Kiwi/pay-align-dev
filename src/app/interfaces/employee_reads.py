from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.app.application.employee_overview_service import EmployeeOverviewService
from src.app.application.employment_read_service import EmploymentReadService
from src.app.interfaces.auth import require_account_id
from src.app.interfaces.employment_reads import YearMonthResponse

employee_reads_router = APIRouter()


def _today() -> date:
    return date.today()


class EmployeeEmploymentResponse(BaseModel):
    id: int
    start_date: date
    end_date: date | None
    hourly_wage: Decimal
    weekly_minutes: int
    holiday_weeks: int
    saved_months: int
    next_month: YearMonthResponse | None
    months_due: int


class YearTotalsResponse(BaseModel):
    saved_months: int
    gross_wage: Decimal
    net_payout: Decimal
    cash_bonus: Decimal
    expense_reimbursements: Decimal
    employer_ahv: Decimal
    employer_alv: Decimal
    employer_fak: Decimal
    employer_bu: Decimal
    admin_charge: Decimal
    total_employer_cost: Decimal
    worked_minutes: int
    annual_holiday_taken_minutes: int
    public_holiday_taken_minutes: int


class WageLimitResponse(BaseModel):
    used: Decimal
    limit: Decimal
    remaining: Decimal


class EmployeeOverviewResponse(BaseModel):
    id: int
    name: str
    employments: list[EmployeeEmploymentResponse]
    totals: YearTotalsResponse
    holiday_balance_minutes: int | None
    months_due: int
    wage_limit: WageLimitResponse


class EmployeesOverviewResponse(BaseModel):
    employees: list[EmployeeOverviewResponse]
    household: WageLimitResponse | None


class EmployeeDetailsResponse(BaseModel):
    id: int
    name: str
    address: str
    ahv_number: str
    nationality: str
    tax_status: str


def get_employee_overview_service(request: Request) -> EmployeeOverviewService:
    return request.app.state.employee_overview_service


def get_employment_read_service(request: Request) -> EmploymentReadService:
    return request.app.state.employment_read_service


@employee_reads_router.get("/employees", response_model=EmployeesOverviewResponse)
def list_employees(
    account_id: int = Depends(require_account_id),
    service: EmployeeOverviewService = Depends(get_employee_overview_service),
):
    return service.overview(account_id, _today())


@employee_reads_router.get("/employees/{employee_id}", response_model=EmployeeDetailsResponse)
def get_employee(
    employee_id: int,
    account_id: int = Depends(require_account_id),
    service: EmploymentReadService = Depends(get_employment_read_service),
):
    employee = service.get_employee(account_id, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    return employee
