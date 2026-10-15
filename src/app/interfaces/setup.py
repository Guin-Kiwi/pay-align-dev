from dataclasses import asdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.app.application.setup_service import EmployerAlreadyExistsError, SetupService

setup_router = APIRouter()


class EmployerDetails(BaseModel):
    name: str
    address: str
    ahv_number: str
    contact_info: str


class EmployeeDetails(BaseModel):
    name: str
    address: str
    ahv_number: str
    nationality: str
    tax_status: str = "ordinary"


class EmploymentDetails(BaseModel):
    start_date: date
    hourly_wage: Decimal = Field(decimal_places=2)
    weekly_hours: float
    holiday_entitlement: int = 20


class SetupRequest(BaseModel):
    employer: EmployerDetails | None = None
    employee: EmployeeDetails
    employment: EmploymentDetails


class SetupResponse(BaseModel):
    message: str
    employer_id: int
    employee_id: int
    employment_id: int


class EmployerResponse(BaseModel):
    id: int
    name: str
    address: str
    ahv_number: str
    contact_info: str


def get_setup_service(request: Request) -> SetupService:
    return request.app.state.setup_service


@setup_router.get("/employer", response_model=EmployerResponse)
def get_employer(service: SetupService = Depends(get_setup_service)):
    employer = service.get_employer()
    if employer is None:
        raise HTTPException(status_code=404, detail="No employer is set up yet.")
    return EmployerResponse(**asdict(employer))


@setup_router.post("/setup", response_model=SetupResponse, status_code=201)
def set_up_employment(payload: SetupRequest, service: SetupService = Depends(get_setup_service)):
    try:
        result = service.set_up_employment(
            employer=payload.employer.model_dump() if payload.employer else None,
            employee=payload.employee.model_dump(),
            employment=payload.employment.model_dump(),
        )
    except EmployerAlreadyExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return SetupResponse(message="Employment set up successfully", **asdict(result))
