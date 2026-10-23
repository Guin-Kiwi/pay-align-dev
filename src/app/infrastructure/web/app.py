from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from src.app.application.account_service import AccountService
from src.app.application.employment_read_service import EmploymentReadService
from src.app.application.payroll_service import PayrollService
from src.app.application.ports.account_repository import AccountRepository
from src.app.application.ports.employment_read_repository import EmploymentReadRepository
from src.app.application.ports.password_hasher import PasswordHasher
from src.app.application.ports.payroll_repository import PayrollRepositoryPort
from src.app.application.ports.setup_repository import SetupRepository
from src.app.application.setup_service import SetupService
from src.app.infrastructure.database import create_database_engine, create_schema
from src.app.infrastructure.pwdlib_password_hasher import PwdlibPasswordHasher
from src.app.infrastructure.sqlalchemy_account_repository import (
    SqlAlchemyAccountRepository,
)
from src.app.infrastructure.sqlalchemy_employment_read_repository import (
    SqlAlchemyEmploymentReadRepository,
)
from src.app.infrastructure.sqlalchemy_payroll_repository import (
    SqlAlchemyPayrollRepository,
)
from src.app.infrastructure.sqlalchemy_setup_repository import SqlAlchemySetupRepository
from src.app.interfaces.payroll import payroll_router
from src.app.interfaces.setup import setup_router
from src.app.interfaces.auth import auth_router
from src.app.interfaces.employment_reads import employment_reads_router


def create_app(
    setup_repository: SetupRepository | None = None,
    payroll_repository: PayrollRepositoryPort | None = None,
    account_repository: AccountRepository | None = None,
    password_hasher: PasswordHasher | None = None,
    employment_read_repository: EmploymentReadRepository | None = None,
) -> FastAPI:
    session_secret_key = os.environ.get("SESSION_SECRET_KEY", "")
    if len(session_secret_key) < 32:
        raise RuntimeError("SESSION_SECRET_KEY must contain at least 32 characters.")
    secure_value = os.environ.get("SESSION_COOKIE_SECURE", "true").strip().lower()
    if secure_value not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
        raise RuntimeError("SESSION_COOKIE_SECURE must be a boolean value.")
    session_cookie_secure = secure_value in {"true", "1", "yes", "on"}

    engine = None
    if (
        setup_repository is None
        or payroll_repository is None
        or account_repository is None
        or employment_read_repository is None
    ):
        engine = create_database_engine()
        create_schema(engine)
    if setup_repository is None:
        setup_repository = SqlAlchemySetupRepository(engine)
    if payroll_repository is None:
        payroll_repository = SqlAlchemyPayrollRepository(engine)
    if account_repository is None:
        account_repository = SqlAlchemyAccountRepository(engine)
    if employment_read_repository is None:
        employment_read_repository = SqlAlchemyEmploymentReadRepository(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if engine is not None:
            engine.dispose()

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret_key,
        max_age=4 * 60 * 60,
        same_site="lax",
        https_only=session_cookie_secure,
    )
    app.state.engine = engine
    app.state.session_cookie_secure = session_cookie_secure
    app.state.setup_repository = setup_repository
    app.state.payroll_service = PayrollService()
    app.state.payroll_repository = payroll_repository
    app.state.account_service = AccountService(
        account_repository,
        password_hasher if password_hasher is not None else PwdlibPasswordHasher(),
    )
    app.state.employment_read_service = EmploymentReadService(employment_read_repository)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(setup_router, prefix="/api/v1")
    app.include_router(payroll_router, prefix="/api/v1")
    app.include_router(employment_reads_router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
