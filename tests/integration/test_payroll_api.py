"""End-to-end UC-002 saving: post a month, inspect the rows, reject a duplicate."""

from datetime import date

import pytest
from tests.integration.authenticated_client import AuthenticatedTestClient
from sqlalchemy import text

from src.app.infrastructure.database import create_database_engine, create_schema
from src.app.infrastructure.sqlalchemy_payroll_repository import (
    SqlAlchemyPayrollRepository,
)
from src.app.infrastructure.sqlalchemy_account_repository import SqlAlchemyAccountRepository
from src.app.infrastructure.sqlalchemy_employment_read_repository import (
    SqlAlchemyEmploymentReadRepository,
)
from src.app.infrastructure.sqlalchemy_setup_repository import SqlAlchemySetupRepository
from src.app.infrastructure.web.app import create_app
from tests.database_helpers import add_employment

PAYLOAD = {
    "employment_id": 7,
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
    add_employment(
        engine,
        employment_id=7,
        employer_id=3,
        employee_id=9,
        start_date=date(2026, 10, 1),
    )
    app = create_app(
        payroll_repository=SqlAlchemyPayrollRepository(engine),
        setup_repository=SqlAlchemySetupRepository(engine),
        account_repository=SqlAlchemyAccountRepository(engine),
        employment_read_repository=SqlAlchemyEmploymentReadRepository(engine),
    )
    with AuthenticatedTestClient(app, email="employer-3@example.ch", register=False) as test_client:
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


def test_posting_a_month_returns_the_saved_payslip_and_a_confirmation_message(client):
    test_client, engine = client
    payload = {
        **PAYLOAD,
        "cash_bonus": 100,
        "expense_reimbursements": 50,
    }

    response = test_client.post("/api/v1/monthly-payroll", json=payload)

    assert response.status_code == 201, response.text
    response_values = response.json()
    assert set(response_values) == {
        "monthly_record_id",
        "gross_wage",
        "ahv_deduction",
        "alv_deduction",
        "tax_deduction",
        "nbu_deduction",
        "net_payout",
        "employer_ahv",
        "employer_alv",
        "employer_fak",
        "employer_bu",
        "admin_charge",
        "total_employer_cost",
        "holiday_balance_minutes",
        "message",
    }
    assert response_values["message"] == "Payroll processed successfully."
    assert response_values["gross_wage"] == "350.00"
    assert response_values["net_payout"] == "355.09"
    assert response_values["holiday_balance_minutes"] == 605

    saved = test_client.get(
        "/api/v1/employments/7/months/2026/10"
    )

    assert saved.status_code == 200, saved.text
    assert {
        key: value for key, value in response_values.items() if key != "message"
    } == saved.json()


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
    add_employment(
        engine,
        employment_id=8,
        employer_id=3,
        employee_id=9,
        start_date=date(2026, 10, 1),
        hourly_wage_cents=100_000,
    )
    payload = {
        **PAYLOAD,
        "employment_id": 8,
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
    add_employment(
        engine, employment_id=9, employer_id=3, employee_id=9, start_date=date(2026, 5, 1)
    )
    payload = {
        **PAYLOAD,
        "employment_id": 9,
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


def holiday_payload(engine, *entries):
    add_employment(
        engine, employment_id=9, employer_id=3, employee_id=9, start_date=date(2026, 5, 1)
    )
    return {**PAYLOAD, "employment_id": 9, "month": 5, "work_entries": list(entries)}


def test_paid_holiday_on_a_public_holiday_is_a_4xx_and_saves_nothing(client):
    test_client, engine = client
    entry = {"work_date": "2026-05-14", "category": "annual_holiday_taken", "paid_minutes": 60}

    response = test_client.post("/api/v1/monthly-payroll", json=holiday_payload(engine, entry))

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

    response = test_client.post("/api/v1/monthly-payroll", json=holiday_payload(engine, leave, work))

    assert response.status_code == 400
    assert count(engine, "monthly_records") == 0


def test_an_unknown_employment_is_a_404_and_saves_nothing(client):
    test_client, engine = client

    response = test_client.post(
        "/api/v1/monthly-payroll", json={**PAYLOAD, "employment_id": 999}
    )

    assert response.status_code == 404
    for table in ("monthly_records", "work_entries", "payroll_snapshots", "payslips"):
        assert count(engine, table) == 0


def test_employment_terms_come_from_the_saved_employment_not_the_request(client):
    test_client, engine = client

    response = test_client.post(
        "/api/v1/monthly-payroll",
        json={**PAYLOAD, "hourly_wage": 99.0, "weekly_hours": "1:00", "employer_id": 5},
    )

    assert response.status_code == 201
    assert response.json()["gross_wage"] == "250.00"
    with engine.connect() as connection:
        employer_id = connection.execute(
            text("SELECT employer_id FROM monthly_records")
        ).scalar()
    assert employer_id == 3


def bonus_only(**overrides):
    return {**PAYLOAD, "work_entries": [], **overrides}


def test_wages_from_another_employer_do_not_count_towards_the_employee_limit(client):
    test_client, engine = client
    add_employment(
        engine, employment_id=10, employer_id=4, employee_id=10, start_date=date(2026, 9, 1)
    )

    with AuthenticatedTestClient(
        test_client.app, email="employer-4@example.ch", register=False
    ) as other_client:
        other_employer = other_client.post(
            "/api/v1/monthly-payroll",
            json=bonus_only(employment_id=10, month=9, cash_bonus=3_000),
        )
    this_employer = test_client.post(
        "/api/v1/monthly-payroll", json=bonus_only(cash_bonus=20_000)
    )

    assert other_employer.status_code == 201
    assert this_employer.status_code == 201
    assert count(engine, "monthly_records") == 2


def test_a_second_employments_later_months_count_towards_the_employee_limit(client):
    test_client, engine = client
    add_employment(
        engine, employment_id=8, employer_id=3, employee_id=9, start_date=date(2026, 11, 1)
    )

    november = test_client.post(
        "/api/v1/monthly-payroll",
        json=bonus_only(employment_id=8, month=11, cash_bonus=22_000),
    )
    october = test_client.post("/api/v1/monthly-payroll", json=bonus_only(cash_bonus=1_000))

    assert november.status_code == 201
    assert october.status_code == 400
    assert "22680" in october.json()["detail"]
    assert count(engine, "monthly_records") == 1


def test_a_run_after_the_end_month_is_a_4xx_and_saves_nothing(client):
    test_client, engine = client
    add_employment(
        engine,
        employment_id=8,
        employer_id=3,
        employee_id=9,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 31),
    )

    october = test_client.post("/api/v1/monthly-payroll", json=bonus_only(employment_id=8))
    november = test_client.post(
        "/api/v1/monthly-payroll", json=bonus_only(employment_id=8, month=11)
    )

    assert october.status_code == 201
    assert november.status_code == 400
    assert count(engine, "monthly_records") == 1


def entry_on(day):
    return {
        "work_date": f"2026-10-{day:02d}",
        "category": "worked",
        "start_time": "09:00",
        "end_time": "10:00",
    }


def test_entries_on_the_first_and_last_day_of_the_employment_are_saved(client):
    test_client, engine = client
    add_employment(
        engine,
        employment_id=8,
        employer_id=3,
        employee_id=9,
        start_date=date(2026, 10, 5),
        end_date=date(2026, 10, 20),
    )

    response = test_client.post(
        "/api/v1/monthly-payroll",
        json=bonus_only(employment_id=8, work_entries=[entry_on(5), entry_on(20)]),
    )

    assert response.status_code == 201
    assert count(engine, "work_entries") == 2


@pytest.mark.parametrize("day", [4, 21])
def test_an_entry_outside_the_employment_is_a_4xx_and_saves_nothing(client, day):
    test_client, engine = client
    add_employment(
        engine,
        employment_id=8,
        employer_id=3,
        employee_id=9,
        start_date=date(2026, 10, 5),
        end_date=date(2026, 10, 20),
    )

    response = test_client.post(
        "/api/v1/monthly-payroll",
        json=bonus_only(employment_id=8, work_entries=[entry_on(5), entry_on(day)]),
    )

    assert response.status_code == 400
    for table in ("monthly_records", "work_entries", "payroll_snapshots", "payslips"):
        assert count(engine, table) == 0
