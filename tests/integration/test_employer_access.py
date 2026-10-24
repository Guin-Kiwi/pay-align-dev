from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from src.app.infrastructure.web.app import create_app
from tests.database_helpers import empty_postgres_url

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


@pytest.mark.parametrize("backend", ["sqlite", "postgresql"])
def test_same_employer_ahv_can_be_set_up_independently_by_two_accounts(
    monkeypatch, tmp_path, backend
):
    database_url = empty_postgres_url() if backend == "postgresql" else f"sqlite:///{tmp_path / 'accounts.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    app = create_app()
    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as first, TestClient(
        app, base_url="https://testserver", raise_server_exceptions=False
    ) as second:
        _register(first, "first@example.ch")
        first_setup = _setup(first)
        assert first_setup.status_code == 201
        _register(second, "second@example.ch")
        second_setup = second.post(
            "/api/v1/setup",
            headers={"X-CSRF-Token": _csrf(second)},
            json={**SETUP, "employer": {**SETUP["employer"], "name": "Second Employer"}},
        )
        assert second_setup.status_code == 201, second_setup.text
        assert first_setup.json()["employer_id"] != second_setup.json()["employer_id"]
        assert first_setup.json()["employee_id"] != second_setup.json()["employee_id"]
        assert first.get("/api/v1/employer").json()["name"] == "Anna Muster"
        assert second.get("/api/v1/employer").json()["name"] == "Second Employer"
        foreign = second.get(f"/api/v1/employments/{first_setup.json()['employment_id']}")
        absent = second.get("/api/v1/employments/999")
        assert foreign.status_code == absent.status_code == 404
        assert foreign.json() == absent.json()


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


def test_same_employee_ahv_is_kept_separate_for_two_employers(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()

    with TestClient(app, base_url="https://testserver") as first, TestClient(
        app, base_url="https://testserver"
    ) as second:
        _register(first, "first@example.ch")
        first_setup = _setup(first)
        _register(second, "second@example.ch")
        second_payload = {
            **SETUP,
            "employer": {
                **SETUP["employer"],
                "name": "Beatrice Beispiel",
                "ahv_number": "756.2222.3333.44",
            },
            "employee": {**SETUP["employee"], "name": "Maria Rossi Second"},
        }
        second_setup = second.post(
            "/api/v1/setup",
            headers={"X-CSRF-Token": _csrf(second)},
            json=second_payload,
        )

        assert first_setup.status_code == 201
        assert second_setup.status_code == 201
        assert first_setup.json()["employee_id"] != second_setup.json()["employee_id"]

        repeat = first.post(
            "/api/v1/setup",
            headers={"X-CSRF-Token": _csrf(first)},
            json={
                "employee": {**SETUP["employee"], "name": "Changed by First"},
                "employment": SETUP["employment"],
            },
        )
        assert repeat.status_code == 201
        assert repeat.json()["employee_id"] == first_setup.json()["employee_id"]

    with app.state.engine.connect() as connection:
        rows = connection.execute(
            text("SELECT name FROM employees WHERE ahv_number = :ahv ORDER BY id"),
            {"ahv": SETUP["employee"]["ahv_number"]},
        ).scalars().all()
    assert rows == ["Maria Rossi", "Maria Rossi Second"]
    app.state.engine.dispose()


def test_payroll_cannot_use_another_accounts_employment_id(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()

    with TestClient(app, base_url="https://testserver") as first, TestClient(
        app, base_url="https://testserver"
    ) as second:
        _register(first, "first@example.ch")
        first_setup = _setup(first)
        _register(second, "second@example.ch")
        response = second.post(
            "/api/v1/monthly-payroll",
            headers={"X-CSRF-Token": _csrf(second)},
            json={**PAYROLL, "employment_id": first_setup.json()["employment_id"]},
        )

    assert response.status_code == 404
    with app.state.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM monthly_records")).scalar_one() == 0
    app.state.engine.dispose()


def test_employment_list_is_scoped_to_the_signed_in_account(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()

    with TestClient(app, base_url="https://testserver") as first, TestClient(
        app, base_url="https://testserver"
    ) as second, TestClient(app, base_url="https://testserver") as anonymous:
        _register(first, "first@example.ch")
        first_id = _setup(first).json()["employment_id"]
        _register(second, "second@example.ch")
        second_setup = second.post(
            "/api/v1/setup",
            headers={"X-CSRF-Token": _csrf(second)},
            json={
                **SETUP,
                "employer": {
                    **SETUP["employer"],
                    "name": "Beatrice Beispiel",
                    "ahv_number": "756.2222.3333.44",
                },
            },
        )
        assert second_setup.status_code == 201
        second_id = second_setup.json()["employment_id"]

        first_list = first.get("/api/v1/employments")
        second_list = second.get("/api/v1/employments")
        anonymous_list = anonymous.get("/api/v1/employments")
        owned_detail = first.get(f"/api/v1/employments/{first_id}")
        other_detail = second.get(f"/api/v1/employments/{first_id}")
        missing_detail = second.get("/api/v1/employments/999")

    assert first_list.status_code == 200
    assert [item["id"] for item in first_list.json()] == [first_id]
    assert first_list.json()[0]["employee_name"] == "Maria Rossi"
    assert second_list.status_code == 200
    assert [item["id"] for item in second_list.json()] == [second_id]
    assert anonymous_list.status_code == 401
    assert owned_detail.status_code == 200
    assert owned_detail.json()["id"] == first_id
    assert other_detail.status_code == missing_detail.status_code == 404
    app.state.engine.dispose()


def test_completed_months_and_payslip_are_owned_and_view_only(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()

    with TestClient(app, base_url="https://testserver") as owner, TestClient(
        app, base_url="https://testserver"
    ) as other:
        _register(owner, "owner@example.ch")
        employment_id = _setup(owner).json()["employment_id"]
        saved = owner.post(
            "/api/v1/monthly-payroll",
            headers={"X-CSRF-Token": _csrf(owner)},
            json={**PAYROLL, "employment_id": employment_id},
        )
        assert saved.status_code == 201
        _register(other, "other@example.ch")

        months_url = f"/api/v1/employments/{employment_id}/months"
        payslip_url = f"{months_url}/2026/1"
        history = owner.get(months_url)
        payslip = owner.get(payslip_url)
        other_history = other.get(months_url)
        other_payslip = other.get(payslip_url)
        missing_history = other.get("/api/v1/employments/999/months")
        change = owner.patch(payslip_url, json={"cash_bonus": "100.00"})
        deletion = owner.delete(payslip_url)

    assert history.status_code == 200
    assert history.json()["next_month"] == {"year": 2026, "month": 2}
    assert history.json()["months"] == [
        {"year": 2026, "month": 1, "monthly_record_id": saved.json()["monthly_record_id"]}
    ]
    assert payslip.status_code == 200
    assert payslip.json()["monthly_record_id"] == saved.json()["monthly_record_id"]
    assert payslip.json()["gross_wage"] == saved.json()["gross_wage"]
    assert payslip.json()["net_payout"] == saved.json()["net_payout"]
    assert {"ahv_deduction", "alv_deduction", "nbu_deduction", "tax_deduction",
            "total_employer_cost", "holiday_balance_minutes"} <= payslip.json().keys()
    assert other_history.status_code == missing_history.status_code == 404
    assert other_payslip.status_code == 404
    assert change.status_code == deletion.status_code == 405
    with app.state.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM monthly_records")).scalar_one() == 1
    app.state.engine.dispose()
