import base64
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.app.infrastructure.web.app import create_app
from tests.integration.test_employer_access import SETUP


def _csrf(client: TestClient) -> str:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _registration(client: TestClient, *, email="employer@example.ch"):
    return client.post(
        "/api/v1/auth/register",
        headers={"X-CSRF-Token": _csrf(client)},
        json={
            "email": email,
            "password": "A-long-test-password-123!",
            "first_name": "Anna",
            "last_name": "Muster",
        },
    )


def test_registration_persists_a_password_hash_and_starts_a_session(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()
    client = TestClient(app, base_url="https://testserver")

    response = _registration(client)

    assert response.status_code == 201
    account = {key: value for key, value in response.json().items() if key != "csrf_token"}
    assert account == {
        "id": 1,
        "email": "employer@example.ch",
        "first_name": "Anna",
        "last_name": "Muster",
    }
    assert "password" not in response.json()
    cookie = response.headers["set-cookie"]
    assert "httponly" in cookie.lower()
    assert "samesite=lax" in cookie.lower()
    assert "secure" in cookie.lower()
    assert "max-age=14400" in cookie.lower()
    assert client.get("/api/v1/auth/me").json() == account
    session_data = json.loads(
        base64.b64decode(client.cookies.get("session").split(".", maxsplit=1)[0])
    )
    assert session_data == {"account_id": 1}

    with app.state.engine.connect() as connection:
        row = connection.execute(
            text("SELECT password_hash FROM accounts WHERE email = :email"),
            {"email": "employer@example.ch"},
        ).one_or_none()
        assert row is not None
        assert row.password_hash != "A-long-test-password-123!"
        assert row.password_hash.startswith("$argon2id$")

    app.state.engine.dispose()


@pytest.mark.parametrize("operation", ["register", "login"])
def test_authentication_returns_the_rotated_token_for_the_next_write(
    monkeypatch, tmp_path, operation
):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    app = create_app()
    with TestClient(app, base_url="https://testserver") as client:
        if operation == "login":
            assert _registration(client).status_code == 201
            client.cookies.clear()
        old_token = _csrf(client)
        response = client.post(
            f"/api/v1/auth/{operation}",
            headers={"X-CSRF-Token": old_token},
            json={
                "email": "employer@example.ch",
                "password": "A-long-test-password-123!",
                "first_name": "Anna",
                "last_name": "Muster",
            },
        )
        assert response.status_code == (201 if operation == "register" else 200)
        token = response.json()["csrf_token"]
        assert token != old_token
        assert token == client.cookies.get("csrf_token")
        rejected = client.post(
            "/api/v1/setup", headers={"X-CSRF-Token": old_token}, json=SETUP
        )
        assert rejected.status_code == 403
        setup = client.post(
            "/api/v1/setup", headers={"X-CSRF-Token": token}, json=SETUP
        )
        assert setup.status_code == 201, setup.text
        logout = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": token})
        assert logout.status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.parametrize(
    "cookie, header",
    [(b'csrf_token="\\351"', b"ascii"), (b"csrf_token=ascii", b"\xc3\xa9")],
)
def test_non_ascii_csrf_values_are_rejected_without_a_server_error(
    monkeypatch, tmp_path, cookie, header
):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    app = create_app()
    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/auth/logout",
            headers=[(b"cookie", cookie), (b"x-csrf-token", header)],
        )
        assert response.status_code == 403


@pytest.mark.parametrize("password", ["Abc1!xy", "abcdefgh!", "abcdefg1", "abcdef1 "])
def test_registration_rejects_passwords_outside_the_selected_policy(
    monkeypatch, tmp_path, password
):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    app = create_app()
    with TestClient(app, base_url="https://testserver") as client:
        token = _csrf(client)
        response = client.post(
            "/api/v1/auth/register",
            headers={"X-CSRF-Token": token},
            json={"email": "employer@example.ch", "password": password,
                  "first_name": "Anna", "last_name": "Muster"},
        )
        assert response.status_code == 422
        assert client.get("/api/v1/auth/me").status_code == 401
        with app.state.engine.connect() as connection:
            assert connection.execute(text("SELECT COUNT(*) FROM accounts")).scalar_one() == 0


def test_registration_normalizes_email_and_rejects_duplicates(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()
    first = TestClient(app, base_url="https://testserver")
    second = TestClient(app, base_url="https://testserver")

    assert _registration(first, email=" Employer@Example.CH ").status_code == 201
    duplicate = _registration(second, email="employer@example.ch")

    assert duplicate.status_code == 409
    app.state.engine.dispose()


def test_login_uses_generic_failure_and_sets_four_hour_session(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()
    registration_client = TestClient(app, base_url="https://testserver")
    assert _registration(registration_client).status_code == 201

    client = TestClient(app, base_url="https://testserver")
    token = _csrf(client)
    payload = {"email": "employer@example.ch", "password": "A-long-test-password-123!"}
    response = client.post(
        "/api/v1/auth/login", headers={"X-CSRF-Token": token}, json=payload
    )

    assert response.status_code == 200
    assert response.json()["email"] == "employer@example.ch"
    assert "max-age=14400" in response.headers["set-cookie"].lower()
    token = _csrf(client)

    wrong_password = client.post(
        "/api/v1/auth/login",
        headers={"X-CSRF-Token": token},
        json={**payload, "password": "incorrect"},
    )
    unknown_email = client.post(
        "/api/v1/auth/login",
        headers={"X-CSRF-Token": token},
        json={**payload, "email": "unknown@example.ch"},
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    app.state.engine.dispose()


def test_sessions_are_independent_between_browser_clients(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()
    first = TestClient(app, base_url="https://testserver")
    second = TestClient(app, base_url="https://testserver")

    _registration(first, email="first@example.ch")
    _registration(second, email="second@example.ch")

    assert first.get("/api/v1/auth/me").json()["email"] == "first@example.ch"
    assert second.get("/api/v1/auth/me").json()["email"] == "second@example.ch"
    first.post("/api/v1/auth/logout", headers={"X-CSRF-Token": _csrf(first)})
    assert first.get("/api/v1/auth/me").status_code == 401
    assert second.get("/api/v1/auth/me").status_code == 200
    app.state.engine.dispose()


def test_state_changing_auth_request_requires_csrf_token(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-that-is-long-enough-for-session-signing")
    app = create_app()
    client = TestClient(app, base_url="https://testserver")

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "employer@example.ch",
            "password": "A-long-test-password-123!",
            "first_name": "Anna",
            "last_name": "Muster",
        },
    )

    assert response.status_code == 403
    app.state.engine.dispose()
