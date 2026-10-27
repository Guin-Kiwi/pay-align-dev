"""End to end: the demo flow over HTTP against the app running as a real server."""

import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

from tests.database_helpers import empty_postgres_url

ROOT = Path(__file__).resolve().parents[2]
START_TIMEOUT_SECONDS = 20

SETUP = {
    "employer": {
        "name": "Anna Muster",
        "address": "Musterstrasse 1, 4051 Basel",
        "ahv_number": "756.9876.5432.17",
        "contact_info": "anna.muster@example.ch",
    },
    "employee": {
        "name": "Lea Beispiel",
        "address": "Beispielweg 2, 4052 Basel",
        "ahv_number": "756.1234.5678.97",
        "nationality": "CH",
    },
    "employment": {
        "start_date": "2026-01-05",
        "hourly_wage": "28.50",
        "weekly_hours": "6:30",
        "holiday_weeks": 4,
    },
}


def _worked(work_date):
    return {
        "work_date": work_date,
        "category": "worked",
        "start_time": "08:00",
        "end_time": "14:30",
        "unpaid_break_minutes": 0,
    }


def _january(employment_id):
    return {
        "employment_id": employment_id,
        "year": 2026,
        "month": 1,
        "work_entries": [_worked(f"2026-01-{day:02d}") for day in (6, 13, 20, 27)],
    }


def _february(employment_id):
    return {
        "employment_id": employment_id,
        "year": 2026,
        "month": 2,
        "cash_bonus": "50.00",
        "expense_reimbursements": "12.40",
        "work_entries": [_worked(f"2026-02-{day:02d}") for day in (3, 10, 17)]
        + [{"work_date": "2026-02-24", "category": "annual_holiday_taken", "paid_minutes": 390}],
    }


def _free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _wait_until_healthy(base_url, process, log_file):
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"The app stopped during start-up:\n{log_file.read_text()}")
        try:
            if httpx.get(f"{base_url}/health", timeout=1).json() == {"status": "ok"}:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"The app did not answer /health in {START_TIMEOUT_SECONDS} s:\n{log_file.read_text()}")


@contextmanager
def running_app(database_url, log_file):
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "DATABASE_URL": database_url,
        "SESSION_COOKIE_SECURE": "false",
    }
    with log_file.open("a") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.app.infrastructure.web.app:app",
             "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
        )
    try:
        _wait_until_healthy(base_url, process, log_file)
        with httpx.Client(base_url=base_url, timeout=10) as client:
            yield client
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@pytest.fixture(params=["sqlite", "postgresql"])
def database_url(request, tmp_path):
    if request.param == "postgresql":
        return empty_postgres_url()
    return f"sqlite:///{tmp_path / 'payroll.db'}"


def test_demo_flow_keeps_its_data_across_a_restart(database_url, tmp_path):
    log_file = tmp_path / "server.log"

    with running_app(database_url, log_file) as app:
        entry = app.get("/", follow_redirects=False)
        assert entry.status_code == 200
        assert 'href="/login"' in entry.text
        assert "Log in" in app.get("/login").text
        registration = app.post(
            "/api/v1/auth/register",
            headers=_csrf_header(app),
            json={
                "email": "demo@example.ch",
                "password": "A-long-test-password-123!",
                "first_name": "Anna",
                "last_name": "Muster",
            },
        )
        assert registration.status_code == 201, registration.text
        assert "Set up employment" in app.get("/setup").text
        setup = app.post("/api/v1/setup", headers=_csrf_header(app), json=SETUP)
        assert setup.status_code == 201, setup.text
        employment_id = setup.json()["employment_id"]
        assert "Your employments" in app.get("/employments").text
        employments = app.get("/api/v1/employments")
        assert employments.status_code == 200
        assert [employment["id"] for employment in employments.json()] == [employment_id]
        months_url = f"/api/v1/employments/{employment_id}/months"
        assert app.get(months_url).json() == {
            "months": [], "next_month": {"year": 2026, "month": 1}
        }

        january = app.post(
            "/api/v1/monthly-payroll",
            headers=_csrf_header(app),
            json=_january(employment_id),
        )
        assert january.status_code == 201, january.text
        assert january.json()["gross_wage"] == "741.00"
        assert january.json()["net_payout"] == "656.53"
        history = app.get(months_url)
        assert history.json()["months"] == [{
            "monthly_record_id": january.json()["monthly_record_id"],
            "year": 2026,
            "month": 1,
        }]
        saved = app.get(f"{months_url}/2026/1")
        assert saved.status_code == 200
        assert saved.json()["net_payout"] == "656.53"
        assert {"ahv_deduction", "total_employer_cost", "holiday_balance_minutes"} <= saved.json().keys()

        logout = app.post("/api/v1/auth/logout", headers=_csrf_header(app))
        assert logout.status_code == 204
        protected = app.get("/employments", follow_redirects=False)
        assert protected.status_code == 303
        assert protected.headers["location"] == "/login"

    with running_app(database_url, log_file) as app:
        login = app.post(
            "/api/v1/auth/login",
            headers=_csrf_header(app),
            json={"email": "demo@example.ch", "password": "A-long-test-password-123!"},
        )
        assert login.status_code == 200, login.text
        assert "Your employments" in app.get("/employments").text
        february = app.post(
            "/api/v1/monthly-payroll",
            headers=_csrf_header(app),
            json=_february(employment_id),
        )
        assert february.status_code == 201, february.text
        assert february.json()["gross_wage"] == "791.00"
        assert february.json()["net_payout"] == "713.23"
        assert app.get(f"/api/v1/employments/{employment_id}/months/2026/2").json()["net_payout"] == "713.23"

        again = app.post(
            "/api/v1/monthly-payroll",
            headers=_csrf_header(app),
            json=_february(employment_id),
        )
        assert again.status_code == 400
        assert again.json()["detail"] == "This month was already processed."


def _csrf_header(app):
    token = app.get("/api/v1/auth/csrf").json()["csrf_token"]
    return {"X-CSRF-Token": token}
