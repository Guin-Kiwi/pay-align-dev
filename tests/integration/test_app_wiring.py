from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.app.infrastructure.sqlalchemy_payroll_repository import (
    SqlAlchemyPayrollRepository,
)
from src.app.infrastructure.sqlalchemy_setup_repository import SqlAlchemySetupRepository
from src.app.infrastructure.web.app import create_app
from tests.integration.test_setup_api import EMPLOYEE, EMPLOYER, EMPLOYMENT


def test_both_repositories_share_the_apps_one_engine_and_database(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'payroll.db'}")
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/setup",
            json={"employer": EMPLOYER, "employee": EMPLOYEE, "employment": EMPLOYMENT},
        )
        setup_repository = app.state.setup_service.repository
        payroll_repository = app.state.payroll_repository

        assert response.status_code == 201
        assert isinstance(setup_repository, SqlAlchemySetupRepository)
        assert isinstance(payroll_repository, SqlAlchemyPayrollRepository)
        assert setup_repository.engine is app.state.engine
        assert payroll_repository.engine is app.state.engine
        with payroll_repository.engine.connect() as connection:
            assert connection.execute(text("SELECT COUNT(*) FROM employments")).scalar() == 1


def test_an_injected_repository_is_used_and_the_other_is_still_built(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'payroll.db'}")
    injected = object()

    app: FastAPI = create_app(payroll_repository=injected)

    assert app.state.payroll_repository is injected
    assert app.state.setup_service.repository.engine is app.state.engine
    app.state.engine.dispose()
