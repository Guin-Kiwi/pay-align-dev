"""End to end: the demo seed fills a running app with one up-to-date and one overdue employment."""

import subprocess
import sys

from tests.e2e.test_demo_flow import ROOT, _csrf_header, running_app

SEED = ROOT / "scripts" / "seed_demo.py"


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
