import re
from dataclasses import asdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.app.application.setup_service import EmployerAlreadyExistsError, SetupService
from src.app.interfaces.auth import require_account_id, require_csrf_token

setup_router = APIRouter()

HOURS_PATTERN = re.compile(r"([0-9]{1,2}):([0-5][0-9])")


def parse_hours(text: str) -> int:
    """Return whole minutes for hours typed as H:MM, for example 6:30 -> 390."""
    match = HOURS_PATTERN.fullmatch(text)
    minutes = int(match[1]) * 60 + int(match[2]) if match else 0
    if minutes == 0:
        raise ValueError("Invalid weekly hours. Use H:MM above 0:00, for example 6:30.")
    return minutes


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
    end_date: date | None = None
    hourly_wage: Decimal = Field(decimal_places=2)
    weekly_hours: str
    holiday_weeks: int = 4


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


def get_setup_service(
    request: Request, account_id: int = Depends(require_account_id)
) -> SetupService:
    return SetupService(request.app.state.setup_repository, account_id)


@setup_router.get("/employer", response_model=EmployerResponse)
def get_employer(service: SetupService = Depends(get_setup_service)):
    employer = service.get_employer()
    if employer is None:
        raise HTTPException(status_code=404, detail="No employer is set up yet.")
    return EmployerResponse(**asdict(employer))


@setup_router.post("/employer", response_model=EmployerResponse, status_code=201)
def set_up_employer(
    payload: EmployerDetails,
    _: None = Depends(require_csrf_token),
    service: SetupService = Depends(get_setup_service),
):
    try:
        employer = service.set_up_employer(payload.model_dump())
    except EmployerAlreadyExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return EmployerResponse(**asdict(employer))


@setup_router.put("/employer", response_model=EmployerResponse)
def update_employer(
    payload: EmployerDetails,
    _: None = Depends(require_csrf_token),
    service: SetupService = Depends(get_setup_service),
):
    try:
        employer = service.update_employer(payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if employer is None:
        raise HTTPException(status_code=404, detail="No employer is set up yet.")
    return EmployerResponse(**asdict(employer))


@setup_router.post("/employment-setup", response_model=SetupResponse, status_code=201)
def set_up_employment(
    payload: SetupRequest,
    _: None = Depends(require_csrf_token),
    service: SetupService = Depends(get_setup_service),
):
    employment = payload.employment.model_dump()
    try:
        weekly_minutes = parse_hours(employment["weekly_hours"])
    except ValueError as error:
        raise HTTPException(status_code=400, detail=f"Employment: {error}") from error
    # TODO(UC-001): Employment keeps float hours until all hour fields move to whole minutes. Owner: Nano (@Gedance23).
    employment["weekly_hours"] = weekly_minutes / 60
    try:
        result = service.set_up_employment(
            employer=payload.employer.model_dump() if payload.employer else None,
            employee=payload.employee.model_dump(),
            employment=employment,
        )
    except EmployerAlreadyExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return SetupResponse(message="Employment set up successfully", **asdict(result))
