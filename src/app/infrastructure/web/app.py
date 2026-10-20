from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.app.application.payroll_service import PayrollService
from src.app.application.ports.payroll_repository import PayrollRepositoryPort
from src.app.application.ports.setup_repository import SetupRepository
from src.app.application.setup_service import SetupService
from src.app.infrastructure.database import create_database_engine, create_schema
from src.app.infrastructure.sqlalchemy_payroll_repository import (
    SqlAlchemyPayrollRepository,
)
from src.app.infrastructure.sqlalchemy_setup_repository import SqlAlchemySetupRepository
from src.app.interfaces.payroll import payroll_router
from src.app.interfaces.setup import setup_router


def create_app(
    setup_repository: SetupRepository | None = None,
    payroll_repository: PayrollRepositoryPort | None = None,
) -> FastAPI:
    engine = None
    if setup_repository is None or payroll_repository is None:
        engine = create_database_engine()
        create_schema(engine)
    if setup_repository is None:
        setup_repository = SqlAlchemySetupRepository(engine)
    if payroll_repository is None:
        payroll_repository = SqlAlchemyPayrollRepository(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if engine is not None:
            engine.dispose()

    app = FastAPI(lifespan=lifespan)
    app.state.engine = engine
    app.state.setup_service = SetupService(setup_repository)
    app.state.payroll_service = PayrollService(setup_repository)
    app.state.payroll_repository = payroll_repository
    app.include_router(setup_router, prefix="/api/v1")
    app.include_router(payroll_router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
