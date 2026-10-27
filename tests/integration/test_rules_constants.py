import json
import re
import subprocess

import pytest
from fastapi.testclient import TestClient

from src.app.domain import constants
from src.app.infrastructure.web.app import create_app
from tests.integration.authenticated_client import AuthenticatedTestClient
from tests.integration.page_scripts import STATIC, node_binary

RULE_NAMES = (
    "RULES_YEAR", "RULES_YEAR_START", "RULES_YEAR_END", "MIN_PASSWORD_LENGTH",
    "MIN_HOURLY_WAGE", "MAX_HOURLY_WAGE", "ALLOWED_HOLIDAY_WEEKS",
)
SIGNED_IN_PAGES = ("/employments", "/timesheets", "/employees", "/payslips", "/setup", "/employer-setup")


def evaluate(script):
    program = (
        "let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>{"
        "const vm=require('node:vm');const context={};"
        f"vm.runInNewContext(s+';this.out={{{','.join(RULE_NAMES)}}};',context);"
        "process.stdout.write(JSON.stringify(context.out));});"
    )
    result = subprocess.run([node_binary(), "-e", program], input=script, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def expected_rules():
    return {
        "RULES_YEAR": constants.RULES_YEAR,
        "RULES_YEAR_START": constants.RULES_YEAR_START.isoformat(),
        "RULES_YEAR_END": constants.RULES_YEAR_END.isoformat(),
        "MIN_PASSWORD_LENGTH": constants.MIN_PASSWORD_LENGTH,
        "MIN_HOURLY_WAGE": f"{constants.MIN_HOURLY_WAGE:.2f}",
        "MAX_HOURLY_WAGE": f"{constants.MAX_HOURLY_WAGE:.2f}",
        "ALLOWED_HOLIDAY_WEEKS": list(constants.ALLOWED_HOLIDAY_WEEKS),
    }


def test_rules_script_is_public_and_comes_from_the_constants_module():
    response = TestClient(create_app()).get("/setup-assets/constants.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-cache"
    assert evaluate(response.text) == expected_rules()


def test_rules_script_follows_the_constants_at_request_time(monkeypatch):
    monkeypatch.setattr(constants, "RULES_YEAR", 2031)
    monkeypatch.setattr(constants, "RULES_YEAR_START", constants.date(2031, 1, 1))
    monkeypatch.setattr(constants, "RULES_YEAR_END", constants.date(2031, 12, 31))
    monkeypatch.setattr(constants, "MIN_HOURLY_WAGE", 23.5)
    monkeypatch.setattr(constants, "ALLOWED_HOLIDAY_WEEKS", (4, 5, 6))
    rules = evaluate(TestClient(create_app()).get("/setup-assets/constants.js").text)
    assert rules["RULES_YEAR"] == 2031
    assert rules["RULES_YEAR_START"] == "2031-01-01"
    assert rules["MIN_HOURLY_WAGE"] == "23.50"
    assert rules["ALLOWED_HOLIDAY_WEEKS"] == [4, 5, 6]


def test_pages_render_the_rules_into_their_html(monkeypatch):
    client = AuthenticatedTestClient(create_app())
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    employer = {"name": "A", "address": "B", "ahv_number": "756.1234.5678.97", "contact_info": "c@example.ch"}
    assert client.post("/api/v1/employer", json=employer, headers={"X-CSRF-Token": token}).status_code == 201
    monkeypatch.setattr(constants, "RULES_YEAR", 2031)
    monkeypatch.setattr(constants, "RULES_YEAR_START", constants.date(2031, 1, 1))
    monkeypatch.setattr(constants, "RULES_YEAR_END", constants.date(2031, 12, 31))
    monkeypatch.setattr(constants, "MIN_HOURLY_WAGE", 23.5)
    monkeypatch.setattr(constants, "MAX_HOURLY_WAGE", 450.0)
    monkeypatch.setattr(constants, "ALLOWED_HOLIDAY_WEEKS", (4, 5, 6))
    setup = client.get("/setup").text
    assert 'min="2031-01-01" max="2031-12-31"' in setup
    assert "Start date (2031)" in setup
    assert 'min="23.50" max="450.00"' in setup
    assert '<option value="4" selected>4</option><option value="5">5</option><option value="6">6</option>' in setup
    assert "January 2031</option>" in client.get("/employments").text


@pytest.mark.parametrize("route", SIGNED_IN_PAGES)
def test_pages_leave_no_unfilled_placeholders(route):
    client = AuthenticatedTestClient(create_app())
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    employer = {"name": "A", "address": "B", "ahv_number": "756.1234.5678.97", "contact_info": "c@example.ch"}
    client.post("/api/v1/employer", json=employer, headers={"X-CSRF-Token": token})
    assert "{{" not in client.get(route).text


LEFTOVERS = {
    "the rules year": re.compile(r"\b2026\b"),
    "the minimum wage": re.compile(r"\b22\.20\b"),
    "the maximum wage": re.compile(r"\b500\.00\b"),
    "the holiday weeks": re.compile(r"""\[\s*["']?4["']?\s*,\s*["']?5["']?\s*\]"""),
    "the password length": re.compile(r"\bMIN_PASSWORD_LENGTH\s*="),
}


YEAR_FREE_FIXTURES = ("timesheet_flow.js", "setup_submission.js", "employments_flow.js", "payslip_view.js")


def test_browser_fixtures_take_the_rules_year_from_constants_py():
    found = []
    for name in YEAR_FREE_FIXTURES:
        for number, line in enumerate((STATIC.parents[3] / "tests" / "fixtures" / name).read_text().splitlines(), start=1):
            if re.search(r"\b20[0-9]{2}\b", line):
                found.append(f"{name}:{number} repeats a year")
    assert not found, "\n".join(found)


def test_page_code_holds_no_copy_of_a_rule_that_constants_py_owns():
    found = []
    for path in sorted(STATIC.iterdir()):
        if path.suffix not in {".js", ".html"}:
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            for name, pattern in LEFTOVERS.items():
                if pattern.search(line):
                    found.append(f"{path.name}:{number} repeats {name}")
    assert not found, "\n".join(found)
