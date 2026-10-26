import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.app.application.account_service import (
    AccountNotFoundError,
    AccountService,
    DuplicateAccountEmailError,
    InvalidCredentialsError,
)

auth_router = APIRouter(prefix="/auth", tags=["authentication"])


class RegistrationRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AccountResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str


class SessionResponse(AccountResponse):
    csrf_token: str


def get_account_service(request: Request) -> AccountService:
    return request.app.state.account_service


def require_csrf_token(
    request: Request,
    token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    expected = request.cookies.get("csrf_token")
    if (
        not expected or not token
        or not expected.isascii() or not token.isascii()
        or not secrets.compare_digest(expected, token)
    ):
        raise HTTPException(status_code=403, detail="Invalid CSRF token.")


def _to_response(account) -> AccountResponse:
    return AccountResponse(
        id=account.id,
        email=account.email,
        first_name=account.first_name,
        last_name=account.last_name,
    )


@auth_router.get("/csrf")
def issue_csrf_token(request: Request, response: Response) -> dict[str, str]:
    token = secrets.token_urlsafe(32)
    _set_csrf_cookie(response, request, token)
    return {"csrf_token": token}


@auth_router.post("/register", response_model=SessionResponse, status_code=201)
def register(
    payload: RegistrationRequest,
    request: Request,
    response: Response,
    _: None = Depends(require_csrf_token),
    service: AccountService = Depends(get_account_service),
) -> SessionResponse:
    try:
        account = service.register(
            payload.email, payload.password, payload.first_name, payload.last_name
        )
    except DuplicateAccountEmailError as error:
        raise HTTPException(status_code=409, detail="An account already uses this email.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    token = _start_session(request, response, account.id)
    return SessionResponse(**_to_response(account).model_dump(), csrf_token=token)


@auth_router.post("/login", response_model=SessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    _: None = Depends(require_csrf_token),
    service: AccountService = Depends(get_account_service),
) -> SessionResponse:
    try:
        account = service.authenticate(payload.email, payload.password)
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=401, detail="Invalid email or password.") from error
    token = _start_session(request, response, account.id)
    return SessionResponse(**_to_response(account).model_dump(), csrf_token=token)


@auth_router.get("/me", response_model=AccountResponse)
def current_account(
    request: Request,
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    account_id = request.session.get("account_id")
    if not isinstance(account_id, int):
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        account = service.get(account_id)
    except AccountNotFoundError as error:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Authentication required.") from error
    return _to_response(account)


def require_account_id(
    request: Request,
    service: AccountService = Depends(get_account_service),
) -> int:
    account_id = request.session.get("account_id")
    if not isinstance(account_id, int) or isinstance(account_id, bool):
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        service.get(account_id)
    except AccountNotFoundError as error:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Authentication required.") from error
    return account_id


@auth_router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    _: None = Depends(require_csrf_token),
) -> Response:
    request.session.clear()
    response.delete_cookie(
        "csrf_token",
        httponly=False,
        secure=request.app.state.session_cookie_secure,
        samesite="lax",
    )
    response.status_code = 204
    return response


def _start_session(request: Request, response: Response, account_id: int) -> str:
    request.session.clear()
    request.session["account_id"] = account_id
    token = secrets.token_urlsafe(32)
    _set_csrf_cookie(response, request, token)
    return token


def _set_csrf_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        "csrf_token",
        token,
        httponly=False,
        secure=request.app.state.session_cookie_secure,
        samesite="lax",
        path="/",
    )
