from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from src.app.domain.constants import EMPLOYEE_GROSS_LIMIT, EMPLOYER_GROSS_LIMIT
from src.app.infrastructure.web.app import create_app
from tests.integration.authenticated_client import AuthenticatedTestClient

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

SECOND_EMPLOYEE = {
    **SETUP,
    "employer": None,
    "employee": {**SETUP["employee"], "name": "Luca Bianchi", "ahv_number": "756.1111.2222.33"},
}


def payroll(employment_id, month=1, day=6):
    return {
        "employment_id": employment_id,
        "year": 2026,
        "month": month,
        "work_entries": [
            {
                "work_date": f"2026-{month:02d}-{day:02d}",
                "category": "worked",
                "start_time": "09:00",
                "end_time": "15:00",
                "unpaid_break_minutes": 0,
            }
        ],
        "cash_bonus": "50.00",
        "expense_reimbursements": "12.40",
    }


@pytest.fixture
def owner(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'employees.db'}")
    app = create_app()
    client = AuthenticatedTestClient(app, email="employees-owner@example.ch")
    client.other = AuthenticatedTestClient(app, email="employees-other@example.ch")
    client.app_under_test = app
    assert client.post("/api/v1/setup", json=SETUP).status_code == 201
    return client


def set_today(monkeypatch, value):
    monkeypatch.setattr("src.app.interfaces.employee_reads._today", lambda: value)


def saved(client, employment_id, year=2026, month=1):
    response = client.get(f"/api/v1/employments/{employment_id}/months/{year}/{month}")
    assert response.status_code == 200
    return response.json()


def test_overview_lists_a_person_with_terms_and_nothing_saved_yet(owner, monkeypatch):
    set_today(monkeypatch, date(2026, 3, 10))
    response = owner.get("/api/v1/employees")
    assert response.status_code == 200
    person = response.json()["employees"][0]
    assert person["name"] == "Maria Rossi"
    assert "address" not in person and "ahv_number" not in person
    [employment] = person["employments"]
    assert Decimal(employment["hourly_wage"]) == Decimal("28.50")
    assert employment["weekly_minutes"] == 360
    assert employment["holiday_weeks"] == 4
    assert employment["saved_months"] == 0
    assert employment["next_month"] == {"year": 2026, "month": 1}
    assert employment["months_due"] == 3
    assert person["months_due"] == 3
    assert person["holiday_balance_minutes"] is None
    assert Decimal(person["totals"]["gross_wage"]) == 0


def test_totals_balance_and_limits_come_from_the_saved_payslips(owner):
    assert owner.post("/api/v1/monthly-payroll", json=payroll(1)).status_code == 201
    body = owner.get("/api/v1/employees").json()
    person = body["employees"][0]
    slip = saved(owner, 1)
    totals = person["totals"]
    assert totals["saved_months"] == 1
    for field in (
        "gross_wage", "net_payout", "cash_bonus", "expense_reimbursements", "employer_ahv",
        "employer_alv", "employer_fak", "employer_bu", "admin_charge", "total_employer_cost",
    ):
        assert Decimal(totals[field]) == Decimal(slip[field]), field
    assert totals["worked_minutes"] == slip["worked_minutes"] + slip["public_holiday_worked_minutes"]
    assert totals["annual_holiday_taken_minutes"] == slip["annual_holiday_taken_minutes"]
    assert totals["public_holiday_taken_minutes"] == slip["public_holiday_taken_minutes"]
    assert person["holiday_balance_minutes"] == slip["holiday_balance_minutes"]
    assert person["employments"][0]["next_month"] == {"year": 2026, "month": 2}
    limit = person["wage_limit"]
    assert Decimal(limit["used"]) == Decimal(slip["gross_wage"])
    assert Decimal(limit["limit"]) == EMPLOYEE_GROSS_LIMIT
    assert Decimal(limit["remaining"]) == EMPLOYEE_GROSS_LIMIT - Decimal(slip["gross_wage"])
    household = body["household"]
    assert Decimal(household["used"]) == Decimal(slip["gross_wage"])
    assert Decimal(household["limit"]) == EMPLOYER_GROSS_LIMIT


def test_each_person_has_their_own_figures_and_the_household_adds_them_up(owner):
    assert owner.post("/api/v1/setup", json=SECOND_EMPLOYEE).status_code == 201
    assert owner.post("/api/v1/monthly-payroll", json=payroll(1)).status_code == 201
    assert owner.post("/api/v1/monthly-payroll", json=payroll(2)).status_code == 201
    assert owner.post("/api/v1/monthly-payroll", json=payroll(2, month=2, day=3)).status_code == 201
    body = owner.get("/api/v1/employees").json()
    first, second = body["employees"]
    assert [first["name"], second["name"]] == ["Maria Rossi", "Luca Bianchi"]
    assert (first["totals"]["saved_months"], second["totals"]["saved_months"]) == (1, 2)
    used = [Decimal(person["wage_limit"]["used"]) for person in body["employees"]]
    assert used[0] == Decimal(saved(owner, 1)["gross_wage"])
    assert used[1] == Decimal(saved(owner, 2)["gross_wage"]) + Decimal(saved(owner, 2, month=2)["gross_wage"])
    assert Decimal(body["household"]["used"]) == sum(used)


@pytest.mark.parametrize(
    ("today", "due"),
    [
        (date(2026, 1, 20), 0),
        (date(2026, 2, 1), 1),
        (date(2026, 4, 15), 3),
        (date(2027, 1, 5), 11),
    ],
)
def test_months_due_run_from_the_next_month_to_the_current_one_within_the_rules_year(
    owner, monkeypatch, today, due
):
    assert owner.post("/api/v1/monthly-payroll", json=payroll(1)).status_code == 201
    set_today(monkeypatch, today)
    person = owner.get("/api/v1/employees").json()["employees"][0]
    assert person["months_due"] == due
    assert person["employments"][0]["months_due"] == due


def test_an_account_sees_only_its_own_people(owner):
    assert owner.other.get("/api/v1/employees").json() == {"employees": [], "household": None}
    assert owner.other.post("/api/v1/setup", json=SETUP).status_code == 201
    assert owner.post("/api/v1/monthly-payroll", json=payroll(1)).status_code == 201
    other_view = owner.other.get("/api/v1/employees").json()
    assert other_view["employees"][0]["totals"]["saved_months"] == 0
    assert Decimal(other_view["household"]["used"]) == 0


def test_personal_details_are_returned_only_for_one_person_on_request(owner):
    person = owner.get("/api/v1/employees").json()["employees"][0]
    response = owner.get(f"/api/v1/employees/{person['id']}")
    assert response.status_code == 200
    details = response.json()
    assert details["name"] == "Maria Rossi"
    assert details["address"] == "Clarastrasse 10, 4058 Basel"
    assert details["ahv_number"] == "756.9876.5432.10"
    assert details["nationality"] == "Italy"
    assert details["tax_status"]
    assert set(details) == {"id", "name", "address", "ahv_number", "nationality", "tax_status"}


def test_another_accounts_person_and_an_absent_person_look_the_same(owner):
    assert owner.other.post("/api/v1/setup", json=SETUP).status_code == 201
    foreign = owner.other.get("/api/v1/employees").json()["employees"][0]["id"]
    absent = owner.get(f"/api/v1/employees/{foreign + 1000}")
    foreign_response = owner.get(f"/api/v1/employees/{foreign}")
    assert absent.status_code == foreign_response.status_code == 404
    assert absent.json() == foreign_response.json()


def test_the_overview_requires_a_signed_in_account(owner):
    anonymous = TestClient(owner.app_under_test)
    assert anonymous.get("/api/v1/employees").status_code == 401
    assert anonymous.get("/api/v1/employees/1").status_code == 401
