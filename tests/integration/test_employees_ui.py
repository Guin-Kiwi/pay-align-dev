import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app.domain.constants import RULES_YEAR
from src.app.infrastructure.web.app import create_app
from tests.integration.authenticated_client import AuthenticatedTestClient
from tests.integration.page_scripts import Page, node_binary, page_javascript

FLOW = Path(__file__).resolve().parents[1] / "fixtures" / "employees_flow.js"

SCENARIOS = [
    "person-boxes", "agreement", "payslip-picker", "payslip-picker-names-the-employment", "no-saved-months",
    "months-unavailable", "details-on-request", "details-failure", "todo-months-due", "todo-nothing",
    "wage-limit-is-never-a-to-do", "numbers", "wage-limit-bars", "nothing-saved-yet",
    "empty", "list-401", "list-500",
]


def test_employees_page_requires_login():
    response = TestClient(create_app()).get("/employees", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_employees_page_is_a_list_of_bound_boxes_with_a_details_dialog():
    response = AuthenticatedTestClient(create_app()).get("/employees")
    assert response.status_code == 200
    page = Page(response.text)
    fields = page.by_id()
    for element_id in ("page-status", "page-error", "no-employees", "employee-list", "details-dialog",
                       "details-title", "details-status", "details-rows", "details-close"):
        assert element_id in fields, element_id
    assert "<title>Employees | PayAlign</title>" in response.text
    assert "<h1>Your employees</h1>" in response.text
    assert '<main class="wide">' in response.text
    assert fields["page-status"]["role"] == "status"
    assert fields["page-error"]["role"] == "alert"
    assert fields["details-status"]["role"] == "status"
    assert fields["employee-list"]["class"] == "employee-list"
    assert fields["no-employees"].get("hidden", "missing") is None
    assert fields["details-dialog"]["aria-labelledby"] == "details-title"
    assert [attrs for tag, attrs in page.tags if tag == "script"] == [
        {"src": "/setup-assets/navigation.js", "defer": None},
        {"src": "/setup-assets/common.js", "defer": None},
        {"src": "/setup-assets/employees.js", "defer": None},
    ]
    assert [
        attrs["href"] for tag, attrs in page.tags if tag == "link" and attrs.get("rel") == "stylesheet"
    ] == ["/setup-assets/setup.css?v=20261027-back", "/setup-assets/employments.css", "/setup-assets/employees.css"]
    assert 'data-current-route="/employees"' in response.text
    assert "household" not in response.text.lower()


def test_employees_page_holds_no_personal_details_until_asked_for():
    html = AuthenticatedTestClient(create_app()).get("/employees").text
    for word in ("Address", "AHV number", "Nationality", "Tax status"):
        assert word not in html, word


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_employees_javascript(scenario):
    client = AuthenticatedTestClient(create_app())
    page = Page(client.get("/employees").text)
    result = subprocess.run(
        [node_binary(), str(FLOW)],
        input=json.dumps({
            "scenario": scenario,
            "year": RULES_YEAR,
            "elements": page.by_id(),
            "javascript": page_javascript(client, "employees"),
        }),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == "ok"
