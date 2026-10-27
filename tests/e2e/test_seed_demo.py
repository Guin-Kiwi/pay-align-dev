"""End to end: the demo seed fills a running app with one up-to-date and one overdue employment."""

import importlib.util
import subprocess
import sys
import threading
from contextlib import contextmanager
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer

from tests.e2e.test_demo_flow import ROOT, _csrf_header, running_app

SEED = ROOT / "scripts" / "seed_demo.py"


def _seed_module():
    spec = importlib.util.spec_from_file_location("seed_demo", SEED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _register_demo(app, seed_demo, password=None):
    registration = app.post(
        "/api/v1/auth/register",
        headers=_csrf_header(app),
        json={
            "email": seed_demo.EMAIL,
            "password": password or seed_demo.PASSWORD,
            "first_name": "Demo",
            "last_name": "Employer",
        },
    )
    assert registration.status_code == 201, registration.text
    return {"X-CSRF-Token": registration.json()["csrf_token"]}


def _post(app, headers, path, body):
    response = app.post(path, headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


@contextmanager
def _broken_server():
    class Broken(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"boom: the database is on fire"
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_POST = do_GET

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Broken)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def _seed(*args):
    return subprocess.run(
        [sys.executable, str(SEED), *args], cwd=ROOT, capture_output=True, text=True, timeout=60
    )


def test_seed_leaves_one_employment_up_to_date_and_one_needing_attention(tmp_path):
    with running_app(f"sqlite:///{tmp_path / 'payroll.db'}", tmp_path / "server.log") as app:
        result = _seed("--url", str(app.base_url))
        assert result.returncode == 0, result.stderr
        assert "demo@example.com" in result.stdout

        login = app.post(
            "/api/v1/auth/login",
            headers=_csrf_header(app),
            json={"email": "demo@example.com", "password": "demo-pass1"},
        )
        assert login.status_code == 200, login.text

        employees = app.get("/api/v1/employees").json()["employees"]
        due = {employee["name"]: employee["months_due"] for employee in employees}
        assert due["Mara Beispiel"] == 0
        assert due["Luca Muster"] > 0
        assert all(employee["totals"]["saved_months"] > 0 for employee in employees)

        again = _seed("--url", str(app.base_url))
        assert again.returncode == 0, again.stderr
        assert "already" in again.stdout


def test_seed_refuses_a_non_local_url():
    result = _seed("--url", "https://payalign.example.com")
    assert result.returncode != 0
    assert "local" in result.stderr


def _stopped_after_registration(app, seed_demo):
    _register_demo(app, seed_demo)


def _stopped_part_way_through_mara(app, seed_demo):
    headers = _register_demo(app, seed_demo)
    _post(app, headers, "/api/v1/employer", seed_demo.EMPLOYER)
    mara = _post(app, headers, "/api/v1/setup", seed_demo.UP_TO_DATE)["employment_id"]
    _post(app, headers, "/api/v1/monthly-payroll", seed_demo._mara_month(mara, 7))


def test_seed_completes_what_an_interrupted_run_left_missing(tmp_path):
    seed_demo = _seed_module()
    for index, stopped in enumerate((_stopped_after_registration, _stopped_part_way_through_mara)):
        with running_app(f"sqlite:///{tmp_path / f'payroll{index}.db'}", tmp_path / f"server{index}.log") as app:
            stopped(app, seed_demo)

            result = _seed("--url", str(app.base_url))
            assert result.returncode == 0, result.stderr
            assert "already" in result.stdout and "added" in result.stdout

            assert app.get("/api/v1/employer").status_code == 200
            employees = app.get("/api/v1/employees").json()["employees"]
            saved = {employee["name"]: employee["totals"]["saved_months"] for employee in employees}
            assert saved == {
                "Mara Beispiel": len(range(7, seed_demo._last_month_due(date.today()) + 1)),
                "Luca Muster": 2,
            }
            assert all(len(employee["employments"]) == 1 for employee in employees)
            assert {employee["name"]: employee["months_due"] for employee in employees}["Mara Beispiel"] == 0

            again = _seed("--url", str(app.base_url))
            assert again.returncode == 0, again.stderr
            assert "already" in again.stdout and "added" not in again.stdout


def test_seed_stops_when_the_existing_account_has_another_password(tmp_path):
    seed_demo = _seed_module()
    with running_app(f"sqlite:///{tmp_path / 'payroll.db'}", tmp_path / "server.log") as app:
        _register_demo(app, seed_demo, password="someone-elses-pass1")

        result = _seed("--url", str(app.base_url))

        assert result.returncode != 0
        assert "password" in result.stderr
        assert "Traceback" not in result.stderr


def test_seed_reports_a_server_error_that_is_not_json():
    with _broken_server() as url:
        result = _seed("--url", url)

    assert result.returncode != 0
    assert "500" in result.stderr
    assert "boom: the database is on fire" in result.stderr
    assert "Traceback" not in result.stderr
