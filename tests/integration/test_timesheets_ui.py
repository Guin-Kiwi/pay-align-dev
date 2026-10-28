import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app.domain.constants import PUBLIC_HOLIDAYS, RULES_YEAR
from src.app.infrastructure.web.app import create_app
from tests.integration.authenticated_client import AuthenticatedTestClient
from tests.integration.page_scripts import Page, node_binary, page_javascript

FLOW = Path(__file__).resolve().parents[1] / "fixtures" / "timesheet_flow.js"

SCENARIOS = [
    "landing-boxes", "landing-empty", "landing-401", "landing-month-failure",
    "entry-opens", "entry-first-month", "entry-balance-unavailable", "entry-unknown-employment",
    "entry-none-left", "entry-months-401", "entry-holidays-401", "cancel-entry", "cancel-entry-with-rows", "cancel-entry-discards",
    "fill-pattern", "fill-pattern-problem", "fill-stays-inside-the-employment", "edit-in-the-table",
    "add-extra-day", "extra-day-problems", "second-visit-on-one-day",
    "annual-holiday", "annual-holiday-problems", "annual-and-work-never-share-a-day", "annual-holiday-once-per-day",
    "switch-type-in-the-table", "switch-type-needs-the-day-to-itself",
    "month-without-holidays", "holiday-row-asks-worked-or-taken", "holiday-worked", "holiday-taken",
    "holiday-by-extra-day", "annual-holiday-refused-on-a-public-holiday", "public-holiday-taken-once-per-day",
    "overlap-blocked", "worked-row-needs-times", "unfinished-date", "summary-shows-bonus-and-expenses", "bonus-add-problems", "bonus-needs-add-before-saving",
    "leave-warning", "leave-warning-on-the-landing",
    "cancel-dialog", "empty-month", "submit-month", "all-row-kinds", "duplicate-submit",
    "payroll-401", "payroll-403", "payroll-network", "payroll-saved-500",
]


def test_timesheets_page_requires_an_authenticated_session():
    response = TestClient(create_app()).get("/timesheets", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_timesheets_page_has_a_landing_and_a_left_and_right_entry_page():
    response = AuthenticatedTestClient(create_app()).get("/timesheets")
    assert response.status_code == 200
    page = Page(response.text)
    fields = page.by_id()
    text = response.text
    for element_id in (
        "landing-section", "timesheet-list", "no-employments", "no-month", "entry-section", "entry-month",
        "payroll-form", "pattern-start", "pattern-end", "pattern-break", "fill-month", "pattern-message",
        "extra-date", "add-day", "extra-error", "holiday-balance", "holiday-date", "holiday-hours", "add-holiday",
        "holiday-error", "cash-bonus", "expense-reimbursements", "add-bonus", "bonus-error", "table-message", "entry-table", "entry-empty",
        "entry-list", "entry-totals", "entry-extras", "save-error", "save-payroll", "cancel-entry",
        "save-confirmation", "save-message", "view-saved-payslip", "back-to-timesheets", "page-status", "page-error",
        "timesheet-dialog", "timesheet-summary", "timesheet-confirm", "timesheet-cancel", "timesheet-status",
    ):
        assert element_id in fields, element_id
    for element_id in ("timesheet-employment", "work-date", "work-category", "start-time", "end-time", "paid-minutes",
                       "enter-following-month", "enter-another", "overview-month", "months-section"):
        assert element_id not in fields, element_id
    assert fields["timesheet-list"]["class"] == "employee-list"
    assert fields["landing-section"].get("hidden", "missing") is None
    assert fields["entry-section"].get("hidden", "missing") is None
    assert "hidden" not in fields["entry-table"]
    assert fields["page-status"]["role"] == "status"
    assert fields["page-error"]["role"] == "alert"
    for alert in ("extra-error", "holiday-error", "bonus-error", "table-message", "save-error"):
        assert fields[alert]["role"] == "alert", alert
    assert fields["pattern-message"]["role"] == "status"
    assert fields["save-payroll"]["type"] == "submit"
    assert fields["cancel-entry"]["type"] == "button"
    assert fields["timesheet-dialog"]["class"] == "warning"
    assert fields["timesheet-dialog"]["aria-labelledby"] == "timesheet-dialog-heading"
    assert fields["payroll-form"]["novalidate"] is None
    labels = {attrs.get("for") for tag, attrs in page.tags if tag == "label"}
    for field in ("pattern-start", "pattern-end", "pattern-break", "extra-date", "holiday-date", "holiday-hours",
                  "cash-bonus", "expense-reimbursements"):
        assert field in labels, field

    # the left holds exactly the four boxes you asked for, in order; the right holds the table and the save
    assert text.index('class="entry-grid"') < text.index('class="entry-inputs"') < text.index('class="entry-results"')
    inputs, results = text.index('class="entry-inputs"'), text.index('class="entry-results"')
    legends = ["Regular work schedule", "Add extra day", "Annual holidays", "Bonus and expenses"]
    positions = [text.index(f"<legend>{legend}</legend>") for legend in legends]
    assert positions == sorted(positions)
    assert all(inputs < position < results for position in positions)
    for control in ("fill-month", "extra-date", "add-day", "holiday-balance", "holiday-date", "holiday-hours",
                    "add-holiday", "cash-bonus", "expense-reimbursements", "add-bonus", "bonus-error"):
        assert inputs < text.index(f'id="{control}"') < results, control
    for control in ("entry-table", "entry-totals", "entry-extras", "save-error", "save-payroll", "cancel-entry"):
        assert results < text.index(f'id="{control}"'), control
    assert text.index('id="fill-month"') < text.index('id="pattern-message"') < text.index('id="extra-date"')
    assert text.index('id="add-day"') < text.index('id="extra-error"') < text.index('id="holiday-balance"')
    assert text.index('id="add-holiday"') < text.index('id="holiday-error"') < text.index('id="cash-bonus"')
    assert "Remaining balance" in text
    assert [attrs.get("scope") for tag, attrs in page.tags if tag == "th"] == ["col"] * 8
    for column in ("Date", "Type", "Start", "End", "Unpaid break", "Paid minutes", "Public holiday"):
        assert f">{column}" in text, column
    assert any(tag == "tbody" and attrs.get("id") == "entry-empty" for tag, attrs in page.tags)
    for label in ("Fill month", "Add", "Save", "Cancel"):
        assert f">{label}</button>" in text, label
    assert text.count(">Add</button>") == 3
    assert text.index('id="expense-reimbursements"') < text.index('id="add-bonus"') < text.index('id="bonus-error"') < results
    assert '<main class="wide">' in text
    assert "main.wide { max-width: 90rem; }" in TestClient(create_app()).get("/setup-assets/employments.css").text
    assert "<h1>Timesheets</h1>" in text
    assert "<title>Timesheets | PayAlign</title>" in text
    assert '<h2 id="timesheet-dialog-heading">Are you sure?</h2>' in text
    assert "cannot be changed" in text
    assert ">No, keep editing</button>" in text
    assert [attrs for tag, attrs in page.tags if tag == "script"] == [
        {"src": "/setup-assets/navigation.js", "defer": None},
        {"src": "/setup-assets/common.js", "defer": None},
        {"src": "/setup-assets/timesheets.js", "defer": None},
    ]
    assert [
        attrs["href"] for tag, attrs in page.tags if tag == "link" and attrs.get("rel") == "stylesheet"
    ] == ["/setup-assets/setup.css?v=20261027-back", "/setup-assets/employments.css"]
    assert 'data-current-route="/timesheets"' in text


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_timesheet_javascript(scenario):
    client = AuthenticatedTestClient(create_app())
    page = Page(client.get("/timesheets").text)
    result = subprocess.run(
        [node_binary(), str(FLOW)],
        input=json.dumps({
            "scenario": scenario,
            "year": RULES_YEAR,
            "holidays": sorted(day.isoformat() for day in PUBLIC_HOLIDAYS),
            "elements": page.by_id(),
            "javascript": page_javascript(client, "timesheets"),
        }),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == "ok"
