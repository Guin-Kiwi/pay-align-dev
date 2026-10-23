from fastapi.testclient import TestClient
from sqlalchemy import text

from src.app.infrastructure.web.app import create_app

SETUP = {
    "employer": {
        "name": "Anna Muster",
        "address": "Freie Strasse 1, 4001 Basel",
        "ahv_number": "756.1234.5678.97",
        "contact_info": "anna.muster@example.ch",
    },
    "employee": {
        "name": "Maria Rossi",
        "address": "Clarastrasse 10, 4058 Basel",
        "ahv_number": "756.9876.5432.10",
        "nationality": "Italy",
    },
    "employment": {
        "start_date": "2026-01-01",
        "hourly_wage": "28.50",
        "weekly_hours": "6:00",
        "holiday_weeks": 4,
    },
}

PAYROLL = {
    "employment_id": 1,
    "year": 2026,
    "month": 1,
    "work_entries": [
        {
            "work_date": "2026-01-06",
            "category": "worked",
            "start_time": "09:00",
            "end_time": "15:00",
            "unpaid_break_minutes": 0,
        }
    ],
}


def _csrf(client: TestClient) -> str:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        headers={"X-CSRF-Token": _csrf(client)},
        json={
            "email": email,
            "password": "A-long-test-password-123!",
            "first_name": "Anna",
            "last_name": "Muster",
        },
    )
    assert response.status_code == 201
    return response.json()


def _setup(client: TestClient, *, with_csrf: bool = True):
    headers = {"X-CSRF-Token": _csrf(client)} if with_csrf else {}
    return client.post("/api/v1/setup", headers=headers, json=SETUP)


def test_setup_rejects_an_unauthenticated_request(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()

    with TestClient(app, base_url="https://testserver") as client:
        response = client.post("/api/v1/setup", json=SETUP)

    assert response.status_code >= 400
    with app.state.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM employers")).scalar_one() == 0
    app.state.engine.dispose()


def test_setup_requires_csrf_after_login(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()

    with TestClient(app, base_url="https://testserver") as client:
        _register(client, "employer@example.ch")
        response = _setup(client, with_csrf=False)

    assert response.status_code >= 400
    with app.state.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM employers")).scalar_one() == 0
    app.state.engine.dispose()


def test_setup_associates_the_new_employer_with_the_authenticated_account(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()

    with TestClient(app, base_url="https://testserver") as client:
        account = _register(client, "employer@example.ch")
        response = _setup(client)

    assert response.status_code == 201
    with app.state.engine.connect() as connection:
        owner_id = connection.execute(
            text("SELECT account_id FROM employers WHERE id = :employer_id"),
            {"employer_id": response.json()["employer_id"]},
        ).scalar_one()
    assert owner_id == account["id"]
    app.state.engine.dispose()


def test_employer_lookup_does_not_expose_another_accounts_profile(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()

    with TestClient(app, base_url="https://testserver") as first, TestClient(
        app, base_url="https://testserver"
    ) as second:
        _register(first, "first@example.ch")
        assert _setup(first).status_code == 201
        _register(second, "second@example.ch")
        response = second.get("/api/v1/employer")

    assert response.status_code >= 400
    app.state.engine.dispose()


def test_payroll_write_rejects_an_unauthenticated_browser(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()

    with TestClient(app, base_url="https://testserver") as owner, TestClient(
        app, base_url="https://testserver"
    ) as anonymous:
        _register(owner, "employer@example.ch")
        assert _setup(owner).status_code == 201
        response = anonymous.post("/api/v1/monthly-payroll", json=PAYROLL)

    assert response.status_code >= 400
    app.state.engine.dispose()


def test_payroll_write_requires_csrf_after_login(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()

    with TestClient(app, base_url="https://testserver") as client:
        _register(client, "employer@example.ch")
        assert _setup(client).status_code == 201
        response = client.post("/api/v1/monthly-payroll", json=PAYROLL)

    assert response.status_code >= 400
    app.state.engine.dispose()
