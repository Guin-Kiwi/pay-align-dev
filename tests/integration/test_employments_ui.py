from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from src.app.infrastructure.web.app import create_app
from src.app.domain.constants import PUBLIC_HOLIDAYS
from src.app.domain.hour_categories import HourCategory
from tests.integration.authenticated_client import AuthenticatedTestClient


FLOW = Path(__file__).resolve().parents[1] / "fixtures" / "employments_flow.js"


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def by_id(self):
        return {attrs["id"]: attrs for _, attrs in self.tags if "id" in attrs}


def node_binary():
    node = shutil.which("node")
    if node is None:
        pytest.fail("The employment UI tests require Node.js 22 on PATH.")
    return node


def run_flow(scenario):
    client = AuthenticatedTestClient(create_app())
    page = Page(client.get("/employments").text)
    result = subprocess.run(
        [node_binary(), str(FLOW)],
        input=json.dumps(
            {
                "scenario": scenario,
                "elements": page.by_id(),
                "javascript": client.get("/setup-assets/common.js").text + "\n" + client.get("/setup-assets/employments.js").text,
            }
        ),
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_root_opens_the_login_page_without_creating_a_second_login_view():
    response = TestClient(create_app()).get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_employments_page_requires_an_authenticated_session():
    response = TestClient(create_app()).get("/employments", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_employments_page_exposes_the_minimum_accessible_workspace():
    response = AuthenticatedTestClient(create_app()).get("/employments")
    assert response.status_code == 200
    page = Page(response.text)
    fields = page.by_id()
    assert ("html", {"lang": "en"}) in page.tags
    assert [
        attrs["href"]
        for tag, attrs in page.tags
        if tag == "link" and attrs.get("rel") == "stylesheet"
    ] == ["/setup-assets/setup.css", "/setup-assets/employments.css"]
    assert [attrs for tag, attrs in page.tags if tag == "script"] == [
        {"src": "/setup-assets/common.js", "defer": None},
        {"src": "/setup-assets/employments.js", "defer": None}
    ]
    for element_id in (
        "logout-button",
        "employment-list",
        "employment-empty",
        "months-section",
        "month-list",
        "open-month-entry",
        "payroll-form",
        "pattern-monday",
        "pattern-monday-start",
        "pattern-monday-end",
        "pattern-monday-break",
        "fill-month",
        "work-entry-date",
        "add-workday",
        "work-entries-body",
        "annual-holiday-date",
        "annual-holiday-minutes",
        "add-annual-holiday",
        "holiday-entries-body",
        "entry-totals",
        "cash-bonus",
        "expense-reimbursements",
        "save-payroll",
        "review-section",
        "review-entries",
        "confirm-payroll",
        "cancel-review",
        "payslip-section",
        "payslip-details",
        "page-status",
        "page-error",
    ):
        assert element_id in fields
    assert fields["page-status"]["role"] == "status"
    assert fields["page-status"]["aria-live"] == "polite"
    assert fields["page-error"]["role"] == "alert"
    assert fields["payroll-form"]["novalidate"] is None
    assert fields["save-payroll"]["type"] == "submit"
    assert fields["work-entry-date"]["type"] == "date"
    assert fields["annual-holiday-date"]["type"] == "date"
    assert fields["confirm-payroll"]["type"] == "button"
    assert fields["add-employment"]["href"] == "/setup"
    assert all(
        field in {attrs.get("for") for tag, attrs in page.tags if tag == "label"}
        for field in ("work-entry-date", "annual-holiday-date", "cash-bonus", "expense-reimbursements")
    )


def test_month_entry_only_offers_categories_accepted_by_the_backend():
    response = AuthenticatedTestClient(create_app()).get("/employments")
    page = Page(response.text)
    offered = {
        attrs["value"]
        for tag, attrs in page.tags
        if tag == "option" and "data-entry-category" in attrs
    }
    assert offered == {
        HourCategory.WORKED.value,
        HourCategory.ANNUAL_HOLIDAY_TAKEN.value,
        HourCategory.PUBLIC_HOLIDAY_TAKEN.value,
    }


def test_public_holiday_calendar_is_authenticated_and_comes_from_domain_constants():
    app = create_app()
    assert TestClient(app).get("/api/v1/public-holidays/2026").status_code == 401
    response = AuthenticatedTestClient(app).get("/api/v1/public-holidays/2026")
    assert response.status_code == 200
    assert response.json() == {
        "year": 2026,
        "dates": sorted(day.isoformat() for day in PUBLIC_HOLIDAYS),
    }


def test_public_holiday_calendar_rejects_an_unsupported_year():
    response = AuthenticatedTestClient(create_app()).get("/api/v1/public-holidays/2027")
    assert response.status_code == 422


@pytest.mark.parametrize(
    "asset, content_type",
    [("employments.css", "text/css"), ("employments.js", "javascript")],
)
def test_employment_assets_are_available(asset, content_type):
    response = TestClient(create_app()).get(f"/setup-assets/{asset}")
    assert response.status_code == 200
    assert content_type in response.headers["content-type"]


@pytest.mark.parametrize(
    "scenario",
    [
        "list",
        "empty",
        "completed-month",
        "months-401",
        "payslip-401",
        "holidays-401",
        "fill-month",
        "fill-boundaries",
        "public-holiday",
        "annual-holiday",
        "split-shift",
        "regenerate-warning",
        "submit-month",
        "duplicate-submit",
        "payroll-401",
        "payroll-403",
        "payroll-network",
        "list-401",
        "logout",
        "logout-403",
    ],
)
def test_employment_workspace_javascript(scenario):
    run_flow(scenario)
