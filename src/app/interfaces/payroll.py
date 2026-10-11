from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional
from src.app.application.payroll_service import PayrollService

payroll_router = APIRouter(prefix="/api/v1")

class EmploymentCreate(BaseModel):
    employer_id: int = Field(..., description="Employer ID")
    employee_id: int = Field(..., description="Employee ID")
    start_date: str = Field(..., description="Employment start date (YYYY-MM-DD)")
    contract_type: str = Field(..., description="Contract type")
    monthly_hours: float = Field(..., description="Expected monthly hours")
    hourly_rate: float = Field(..., description="Hourly rate in CHF")

class MonthlyPayrollRequest(BaseModel):
    employment_id: int = Field(..., description="ID of the employment record")
    year: int = Field(..., description="Year of the payroll")
    month: int = Field(..., description="Month of the payroll")

class PayslipResponse(BaseModel):
    employment_id: int = Field(..., description="ID of the employment")
    year: int = Field(..., description="Year of the payslip")
    month: int = Field(..., description="Month of the payslip")
    gross_wage: float = Field(..., description="Gross wage in CHF")
    deductions: float = Field(..., description="Total deductions in CHF")
    net_pay: float = Field(..., description="Net pay in CHF")
    payslip_url: Optional[str] = Field(None, description="URL to download payslip")

payroll_service = PayrollService()

@payroll_router.post("/employments", response_model=dict)
async def create_employment(payload: EmploymentCreate):
    """Create a new employment record"""
    return payroll_service.create_employment(
        payload.employer_id,
        payload.employee_id,
        payload.start_date,
        payload.contract_type,
        payload.monthly_hours,
        payload.hourly_rate
    )

@payroll_router.post("/monthly-payroll", response_model=dict)
async def process_monthly_payroll(payload: MonthlyPayrollRequest):
    """Process monthly payroll for an employment"""
    return payroll_service.process_monthly_payroll(
        payload.employment_id,
        payload.year,
        payload.month
    )

@payroll_router.get("/payslips/{employment_id}/{year}/{month}", response_model=PayslipResponse)
async def get_payslip(employment_id: int, year: int, month: int):
    """Retrieve payslip for a specific employment, year, and month"""
    return payroll_service.get_payslip(employment_id, year, month)