"""End-to-end UC-002 saving: post a month, inspect the rows, reject a duplicate."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.app.infrastructure.database import create_database_engine, create_schema
from src.app.infrastructure.sqlalchemy_payroll_repository import (
    SqlAlchemyPayrollRepository,
)
from src.app.infrastructure.web.app import create_app
from tests.database_helpers import add_employment

PAYLOAD = {
    "employment_id": 7,
    "employer_id": 3,
    "employee_id": 9,
    "hourly_wage": 25.0,
    "weekly_hours": "10:00",
    "start_date": "2026-10-01",
    "holiday_weeks": 4,
    "year": 2026,
    "month": 10,
    "cash_bonus": 0,
    "expense_reimbursements": 0,
    "work_entries": [
        {
            "work_date": "2026-10-01",
            "category": "worked",
            "start_time": "09:00",
            "end_time": "19:00",
            "unpaid_break_minutes": 0,
        }
    ],
}


@pytest.fixture
def client(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    add_employment(engine, employment_id=7, employer_id=3, employee_id=9)
    repository = SqlAlchemyPayrollRepository(engine)
    app = create_app(payroll_repository=repository)
    with TestClient(app) as test_client:
        yield test_client, engine
    engine.dispose()


def count(engine, table):
    with engine.connect() as connection:
        return connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def test_posting_a_month_saves_entries_snapshot_record_and_payslip(client):
    test_client, engine = client

    response = test_client.post("/api/v1/monthly-payroll", json=PAYLOAD)

    assert response.status_code == 201
    assert response.json()["monthly_record_id"] == 1
    assert count(engine, "monthly_records") == 1
    assert count(engine, "work_entries") == 1
    assert count(engine, "payroll_snapshots") == 1
    assert count(engine, "payslips") == 1


def test_saved_snapshot_holds_the_minute_totals_and_balance(client):
    test_client, engine = client

    test_client.post("/api/v1/monthly-payroll", json=PAYLOAD)

    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT worked_minutes, holiday_balance_minutes, ruleset_version "
                "FROM payroll_snapshots"
            )
        ).one()

    assert row.worked_minutes == 600
    assert row.holiday_balance_minutes == 605
    assert row.ruleset_version == "2026"


def test_posting_the_same_month_again_is_a_4xx_and_duplicates_nothing(client):
    test_client, engine = client
    test_client.post("/api/v1/monthly-payroll", json=PAYLOAD)

    response = test_client.post("/api/v1/monthly-payroll", json=PAYLOAD)

    assert 400 <= response.status_code < 500
    assert count(engine, "monthly_records") == 1
    assert count(engine, "work_entries") == 1
    assert count(engine, "payroll_snapshots") == 1
    assert count(engine, "payslips") == 1


def test_holiday_taken_beyond_the_balance_is_a_4xx_and_saves_nothing(client):
    test_client, engine = client
    payload = {
        **PAYLOAD,
        "work_entries": [
            {
                "work_date": "2026-10-01",
                "category": "annual_holiday_taken",
                "start_time": None,
                "end_time": None,
                "unpaid_break_minutes": 0,
                "paid_minutes": 99999,
            }
        ],
    }

    response = test_client.post("/api/v1/monthly-payroll", json=payload)

    assert 400 <= response.status_code < 500
    assert count(engine, "monthly_records") == 0
    assert count(engine, "work_entries") == 0


def test_annual_limit_breach_is_a_4xx_and_saves_nothing(client):
    test_client, engine = client
    payload = {
        **PAYLOAD,
        "hourly_wage": 1000.0,
        "work_entries": [
            {
                "work_date": "2026-10-01",
                "category": "worked",
                "start_time": "00:00",
                "end_time": "23:59",
                "unpaid_break_minutes": 0,
            }
        ],
    }

    response = test_client.post("/api/v1/monthly-payroll", json=payload)

    assert 400 <= response.status_code < 500
    assert count(engine, "monthly_records") == 0


def test_entries_are_stored_as_submitted(client):
    test_client, engine = client
    payload = {
        **PAYLOAD,
        "work_entries": [
            {
                "work_date": "2026-10-01",
                "category": "worked",
                "start_time": "09:00",
                "end_time": "13:00",
                "unpaid_break_minutes": 15,
            },
            {
                "work_date": "2026-10-01",
                "category": "worked",
                "start_time": "14:00",
                "end_time": "16:00",
            },
        ],
    }

    response = test_client.post("/api/v1/monthly-payroll", json=payload)

    assert response.status_code == 201
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT start_time, end_time, unpaid_break_minutes, paid_minutes "
                "FROM work_entries ORDER BY id"
            )
        ).all()
    assert [tuple(row) for row in rows] == [
        ("09:00:00.000000", "13:00:00.000000", 15, 225),
        ("14:00:00.000000", "16:00:00.000000", 0, 120),
    ]


def test_overlapping_entries_are_a_4xx_and_save_nothing(client):
    test_client, engine = client
    entry = PAYLOAD["work_entries"][0]
    payload = {**PAYLOAD, "work_entries": [entry, {**entry, "start_time": "18:00", "end_time": "20:00"}]}

    response = test_client.post("/api/v1/monthly-payroll", json=payload)

    assert 400 <= response.status_code < 500
    assert count(engine, "monthly_records") == 0
    assert count(engine, "work_entries") == 0


def test_an_empty_month_is_saved_with_a_snapshot_and_a_zero_payslip(client):
    test_client, engine = client

    response = test_client.post(
        "/api/v1/monthly-payroll", json={**PAYLOAD, "work_entries": []}
    )

    assert response.status_code == 201
    assert response.json()["gross_wage"] == "0.00"
    assert count(engine, "monthly_records") == 1
    assert count(engine, "work_entries") == 0
    assert count(engine, "payroll_snapshots") == 1
    assert count(engine, "payslips") == 1


def test_months_must_follow_one_another(client):
    test_client, engine = client
    november = {**PAYLOAD, "month": 11, "work_entries": []}
    december = {**PAYLOAD, "month": 12, "work_entries": []}

    skipped_first = test_client.post("/api/v1/monthly-payroll", json=november)
    test_client.post("/api/v1/monthly-payroll", json={**PAYLOAD, "work_entries": []})
    skipped_second = test_client.post("/api/v1/monthly-payroll", json=december)
    in_order = test_client.post("/api/v1/monthly-payroll", json=november)

    assert skipped_first.status_code == 400
    assert skipped_second.status_code == 400
    assert in_order.status_code == 201
    assert count(engine, "monthly_records") == 2


def test_the_balance_carries_from_one_run_to_the_next(client):
    test_client, engine = client
    holiday = {
        "work_date": "2026-10-05",
        "category": "annual_holiday_taken",
        "paid_minutes": 100,
    }
    test_client.post("/api/v1/monthly-payroll", json={**PAYLOAD, "work_entries": [holiday]})

    test_client.post(
        "/api/v1/monthly-payroll", json={**PAYLOAD, "month": 11, "work_entries": []}
    )

    with engine.connect() as connection:
        balances = connection.execute(
            text("SELECT holiday_balance_minutes FROM payroll_snapshots ORDER BY id")
        ).scalars().all()
    assert balances == [505, 505]


def test_public_holiday_work_is_stored_with_the_holiday_category(client):
    test_client, engine = client
    payload = {
        **PAYLOAD,
        "start_date": "2026-05-01",
        "month": 5,
        "work_entries": [
            {
                "work_date": "2026-05-14",
                "category": "worked",
                "start_time": "09:00",
                "end_time": "13:00",
            }
        ],
    }

    response = test_client.post("/api/v1/monthly-payroll", json=payload)

    assert response.status_code == 201
    with engine.connect() as connection:
        category = connection.execute(text("SELECT category FROM work_entries")).scalar()
    assert category == "public_holiday_worked"
    assert response.json()["gross_wage"] == "150.00"


def test_paid_minutes_that_contradict_the_times_are_a_4xx(client):
    test_client, engine = client
    entry = {**PAYLOAD["work_entries"][0], "paid_minutes": 5}

    response = test_client.post(
        "/api/v1/monthly-payroll", json={**PAYLOAD, "work_entries": [entry]}
    )

    assert 400 <= response.status_code < 500
    assert count(engine, "monthly_records") == 0


def test_worked_hours_without_times_are_a_4xx(client):
    test_client, engine = client
    entry = {"work_date": "2026-10-01", "category": "worked", "paid_minutes": 60}

    response = test_client.post(
        "/api/v1/monthly-payroll", json={**PAYLOAD, "work_entries": [entry]}
    )

    assert 400 <= response.status_code < 500
    assert count(engine, "monthly_records") == 0


def holiday_payload(*entries):
    return {**PAYLOAD, "start_date": "2026-05-01", "month": 5, "work_entries": list(entries)}


def test_paid_holiday_on_a_public_holiday_is_a_4xx_and_saves_nothing(client):
    test_client, engine = client
    entry = {"work_date": "2026-05-14", "category": "annual_holiday_taken", "paid_minutes": 60}

    response = test_client.post("/api/v1/monthly-payroll", json=holiday_payload(entry))

    assert response.status_code == 400
    assert count(engine, "monthly_records") == 0
    assert count(engine, "work_entries") == 0


def test_public_holiday_leave_with_work_on_one_day_is_a_4xx_and_saves_nothing(client):
    test_client, engine = client
    leave = {"work_date": "2026-05-14", "category": "public_holiday_taken", "paid_minutes": 60}
    work = {
        "work_date": "2026-05-14",
        "category": "worked",
        "start_time": "09:00",
        "end_time": "10:00",
    }

    response = test_client.post("/api/v1/monthly-payroll", json=holiday_payload(leave, work))

    assert response.status_code == 400
    assert count(engine, "monthly_records") == 0
