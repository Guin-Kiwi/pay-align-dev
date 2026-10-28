import re
import json
from pathlib import Path
import subprocess

import pytest
from fastapi.testclient import TestClient
from src.app.domain.constants import PUBLIC_HOLIDAYS, RULES_YEAR

from src.app.infrastructure.web.app import create_app
from tests.integration.authenticated_client import AuthenticatedTestClient
from tests.integration.page_scripts import Page, node_binary, page_javascript


FLOW = Path(__file__).resolve().parents[1] / "fixtures" / "home_flow.js"


def test_public_holidays_are_the_configured_dates_and_require_login():
    assert TestClient(create_app()).get('/api/v1/public-holidays?year=2026').status_code == 401
    client = AuthenticatedTestClient(create_app())
    response = client.get('/api/v1/public-holidays?year=2026')
    assert response.status_code == 200
    assert response.json() == [day.isoformat() for day in sorted(PUBLIC_HOLIDAYS)]
    assert client.get('/api/v1/public-holidays?year=2027').status_code == 422


def test_home_offers_account_details_and_add_employment_buttons():
    page = AuthenticatedTestClient(create_app()).get("/home").text
    assert '<h2 id="household-heading">Household overview</h2>' in page
    assert '<button id="employer-details-button" type="button">Account details</button>' in page
    assert '<button id="add-employment" type="button" disabled>Add employment</button>' in page


def test_home_combines_household_costs_workspace_and_tasks():
    page = AuthenticatedTestClient(create_app()).get("/home").text
    assert page.index('id="overview-month"') < page.index('class="household-strip"')
    assert page.index('id="household-rows"') < page.index('id="overview-heading"') < page.index('class="overview-grid"')
    assert page.index('id="workspace-employment-list-heading"') < page.index('id="employment-list-heading"')
    assert 'id="workspace-payroll-form"' in page
    assert 'id="show-breakdown"' not in page
    assert 'id="overview-breakdown"' not in page
    assert 'data-route="/timesheets"' in page




def run_flow(scenario):
    client = AuthenticatedTestClient(create_app())
    page = Page(client.get("/home").text)
    result = subprocess.run(
        [node_binary(), str(FLOW)],
        input=json.dumps(
            {
                "scenario": scenario,
                "year": RULES_YEAR,
                "elements": page.by_id(),
                "javascript": page_javascript(client, "home", rules=True),
            }
        ),
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_root_opens_the_welcome_page():
    response = TestClient(create_app()).get("/", follow_redirects=False)
    assert response.status_code == 200
    assert 'href="/login"' in response.text
    assert 'href="/login#signup"' in response.text


def test_employments_page_requires_an_authenticated_session():
    response = TestClient(create_app()).get("/home", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_employments_page_exposes_the_minimum_accessible_workspace():
    response = AuthenticatedTestClient(create_app()).get("/home")
    assert response.status_code == 200
    page = Page(response.text)
    fields = page.by_id()
    assert ("html", {"lang": "en"}) in page.tags
    assert [
        attrs["href"]
        for tag, attrs in page.tags
        if tag == "link" and attrs.get("rel") == "stylesheet"
    ] == ["/setup-assets/base.css?v=20261027-back", "/setup-assets/overview.css"]
    assert [attrs for tag, attrs in page.tags if tag == "script"] == [
        {"src": "/setup-assets/navigation.js", "defer": None},
        {"src": "/setup-assets/constants.js", "defer": None},
        {"src": "/setup-assets/common.js", "defer": None},
        {"src": "/setup-assets/home.js", "defer": None},
        {"src": "/setup-assets/home-workspace.js", "defer": None},
    ]
    assert 'data-current-route="/home"' in response.text
    for element_id in (
        "logout-button", "employment-list", "employment-empty", "show-employments", "overview-month",
        "overview-completeness", "overview-payout", "overview-reserve", "overview-cost", "workspace-payroll-form",
        "add-employment", "employer-details-button", "employer-status", "page-status", "page-error",
        "household-status", "household-rows", "household-note",
    ):
        assert element_id in fields, element_id
    for element_id in (
        "months-section", "month-list", "open-month-entry", "entry-section", "payroll-form", "work-date",
        "save-payroll", "add-entry", "entry-list", "save-confirmation", "view-saved-payslip",
    ):
        assert element_id not in fields, element_id
    assert fields["page-status"]["role"] == "status"
    assert fields["page-status"]["aria-live"] == "polite"
    assert fields["page-error"]["role"] == "alert"
    assert fields["add-employment"]["type"] == "button"
    assert fields["employment-list"]["class"] == "employee-list"
    assert "months-hint" not in fields
    assert "Months must be entered in order" not in response.text
    assert "overview-month" in {attrs.get("for") for tag, attrs in page.tags if tag == "label"}


@pytest.mark.parametrize(
    "asset, content_type",
    [("overview.css", "text/css"), ("home.js", "javascript")],
)
def test_employment_assets_are_available(asset, content_type):
    response = TestClient(create_app()).get(f"/setup-assets/{asset}")
    assert response.status_code == 200
    assert content_type in response.headers["content-type"]


@pytest.mark.parametrize(
    "scenario",
    [
        "overview-refresh-after-save", "cost-boxes", "no-saved-payroll", "months-unavailable",
        "default-month-latest-saved", "default-month-across-employments", "default-month-nothing-saved",
        "default-month-after-the-year", "overview", "overview-view-payslip", "empty", "no-employer",
        "account-buttons", "many", "list-401", "logout", "logout-403",
        "actions-in-the-boxes", "one-action-is-singular", "household-strip", "household-none", "household-unavailable",
    ],
)
def test_employment_workspace_javascript(scenario):
    run_flow(scenario)


def test_employee_boxes_share_one_compact_row_style_with_right_aligned_buttons():
    css = TestClient(create_app()).get("/setup-assets/overview.css").text
    for rule in (".employee-card .subheading", ".card-rows", ".card-rows th", ".card-rows tr:nth-child(even)", ".card-rows .action"):
        assert rule in css, rule
    for rule in (".household-strip", ".limit-bar", ".employee-card.pending", ".employee-card .tasks.pending", ".employee-card .tasks.done"):
        assert rule in css, rule
    assert re.search(r"\.card-rows \.action \{[^}]*text-align: right", css)
    assert re.search(r"\.card-rows tr:nth-child\(even\) \{[^}]*background: #f4f8f7", css)


def test_original_calendar_route_requires_authentication_and_returns_rules():
    app = create_app()
    path = f'/api/v1/public-holidays/{RULES_YEAR}'
    assert TestClient(app).get(path).status_code == 401
    client = AuthenticatedTestClient(app)
    response = client.get(path)
    assert response.status_code == 200
    assert response.json() == {
        'year': RULES_YEAR,
        'dates': [day.isoformat() for day in sorted(PUBLIC_HOLIDAYS)],
    }
    assert client.get(f'/api/v1/public-holidays/{RULES_YEAR + 1}').status_code == 422
