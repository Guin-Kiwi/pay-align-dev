from fastapi import FastAPI

from src.app.application.ports.setup_repository import SetupRepository
from src.app.application.setup_service import SetupService
from src.app.infrastructure.in_memory_setup_repository import InMemorySetupRepository
from src.app.interfaces.payroll import payroll_router
from src.app.interfaces.setup import setup_router
from src.app.interfaces.ui import ui_router


def create_app(setup_repository: SetupRepository | None = None) -> FastAPI:
    if setup_repository is None:
        setup_repository = InMemorySetupRepository()

    app = FastAPI()
    app.include_router(ui_router)
    app.state.setup_service = SetupService(setup_repository)
    app.include_router(setup_router, prefix="/api/v1")
    app.include_router(payroll_router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
