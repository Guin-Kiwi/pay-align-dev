import pytest
from sqlalchemy import Date, Integer, String, Time, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from src.app.infrastructure.database import (
    DatabaseConfigurationError,
    create_database_engine,
    create_schema,
    get_database_url,
)
from tests.database_helpers import add_monthly_record

ENTITY_TABLES = {
    "accounts",
    "employers",
    "employees",
    "employments",
    "monthly_records",
    "payslips",
    "work_entries",
    "payroll_snapshots",
}


def test_database_url_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:////app/data/payroll.db")
    assert get_database_url() == "sqlite:////app/data/payroll.db"


@pytest.fixture
def engines():
    created = []

    def make(url):
        engine = create_database_engine(url)
        created.append(engine)
        return engine

    yield make
    for engine in created:
        engine.dispose()


@pytest.mark.parametrize("value", [None, "", "   "])
def test_unset_or_blank_database_url_is_rejected(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", value)
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        get_database_url()


@pytest.mark.parametrize(
    "url", ["postgresql://user:pw@host/db", "mysql://host/db", "not a url", "payroll.db"]
)
def test_unsupported_or_malformed_database_url_is_rejected(url):
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        create_database_engine(url)


@pytest.mark.parametrize("url", ["sqlite+foo://", "sqlite:///x.db?timeout=abc"])
def test_invalid_sqlite_engine_configuration_is_rejected(url):
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        create_database_engine(url)


def test_create_database_engine_reads_the_environment_when_no_url_is_given(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'payroll.db'}")
    engine = create_database_engine()
    try:
        assert engine.url.database == str(tmp_path / "payroll.db")
    finally:
        engine.dispose()


def test_create_database_engine_without_any_url_is_rejected(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        create_database_engine()


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///file:mem1?mode=memory&uri=true",
        "sqlite://",
        "sqlite:///:memory:",
        ":memory:",
    ],
)
def test_in_memory_url_uses_static_pool_and_shares_one_database(url, engines):
    engine = engines(url)
    assert isinstance(engine.pool, StaticPool)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE t (id INTEGER)"))
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM t")).scalar() == 0


def test_file_url_that_merely_contains_memory_is_not_treated_as_in_memory(tmp_path, engines):
    engine = engines(f"sqlite:///{tmp_path / 'memory.db'}")
    assert not isinstance(engine.pool, StaticPool)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE t (id INTEGER)"))
    assert (tmp_path / "memory.db").exists()


@pytest.mark.parametrize("memory", [True, False])
def test_every_connection_enforces_foreign_keys(memory, tmp_path, engines):
    url = "sqlite://" if memory else f"sqlite:///{tmp_path / 'payroll.db'}"
    engine = engines(url)
    create_schema(engine)

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO employments (employer_id, employee_id, start_date, "
                    "hourly_wage_cents, weekly_minutes, holiday_weeks) "
                    "VALUES (99, 99, '2026-01-01', 2500, 600, 4)"
                )
            )


def test_create_schema_creates_skeleton_tables_for_the_five_entities(tmp_path, engines):
    engine = engines(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    assert set(inspect(engine).get_table_names()) == ENTITY_TABLES


def test_accounts_table_stores_login_identity_and_hash_only(tmp_path, engines):
    engine = engines(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    inspector = inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("accounts")}

    assert set(columns) == {"id", "email", "password_hash", "first_name", "last_name"}
    assert all(columns[name]["nullable"] is False for name in columns)
    assert {tuple(item["column_names"]) for item in inspector.get_unique_constraints("accounts")} == {
        ("email",)
    }


def test_create_schema_preserves_foreign_key_relationships(tmp_path, engines):
    engine = engines(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    inspector = inspect(engine)

    def references(table):
        return {
            (tuple(fk["constrained_columns"]), fk["referred_table"])
            for fk in inspector.get_foreign_keys(table)
        }

    assert references("employments") == {
        (("employer_id",), "employers"),
        (("employee_id", "employer_id"), "employees"),
    }
    assert references("monthly_records") == {
        (("employment_id",), "employments"),
        (("employer_id",), "employers"),
        (("employee_id",), "employees"),
    }
    assert references("payslips") == {(("monthly_record_id",), "monthly_records")}
    assert references("work_entries") == {(("monthly_record_id",), "monthly_records")}
    assert references("payroll_snapshots") == {
        (("monthly_record_id",), "monthly_records")
    }


def test_monthly_records_hold_the_documented_fields(tmp_path, engines):
    engine = engines(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    columns = {c["name"] for c in inspect(engine).get_columns("monthly_records")}
    assert columns == {
        "id", "employment_id", "employer_id", "month", "year",
        "employee_id",
        "cash_bonus_cents", "expense_reimbursements_cents",
    }


def test_work_entries_hold_integer_minute_fields_and_category_constraint(
    tmp_path, engines
):
    engine = engines(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns("work_entries")
    }

    assert set(columns) == {
        "id",
        "monthly_record_id",
        "work_date",
        "category",
        "start_time",
        "end_time",
        "unpaid_break_minutes",
        "paid_minutes",
    }
    assert isinstance(columns["work_date"]["type"], Date)
    assert isinstance(columns["category"]["type"], String)
    assert isinstance(columns["start_time"]["type"], Time)
    assert isinstance(columns["end_time"]["type"], Time)
    for name in ("unpaid_break_minutes", "paid_minutes"):
        assert isinstance(columns[name]["type"], Integer)
        assert columns[name]["nullable"] is False
    assert columns["start_time"]["nullable"] is True
    assert columns["end_time"]["nullable"] is True

    add_monthly_record(engine)
    with pytest.raises(IntegrityError, match="ck_work_entries_category"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO work_entries "
                    "(monthly_record_id, work_date, category, "
                    "unpaid_break_minutes, paid_minutes) "
                    "VALUES (1, '2026-01-01', 'invalid', 0, 0)"
                )
            )


def test_payroll_snapshots_hold_integer_minute_fields_and_are_unique(tmp_path, engines):
    engine = engines(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns("payroll_snapshots")
    }

    assert set(columns) == {
        "id",
        "monthly_record_id",
        "hourly_wage_cents",
        "weekly_minutes",
        "holiday_weeks",
        "employment_start_date",
        "employment_end_date",
        "ruleset_version",
        "worked_minutes",
        "public_holiday_worked_minutes",
        "annual_holiday_taken_minutes",
        "public_holiday_taken_minutes",
        "holiday_balance_minutes",
    }
    for name, column in columns.items():
        if name in {"employment_start_date", "employment_end_date"}:
            assert isinstance(column["type"], Date)
        elif name != "ruleset_version":
            assert isinstance(column["type"], Integer)
        assert column["nullable"] is (name == "employment_end_date")

    add_monthly_record(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO payroll_snapshots "
                "(monthly_record_id, hourly_wage_cents, weekly_minutes, "
                "holiday_weeks, employment_start_date, ruleset_version, worked_minutes, "
                "public_holiday_worked_minutes, annual_holiday_taken_minutes, "
                "public_holiday_taken_minutes, holiday_balance_minutes) "
                "VALUES (1, 2500, 600, 4, '2026-01-01', '2026', 60, 0, 0, 0, 1200)"
            )
        )
    with pytest.raises(Exception):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO payroll_snapshots "
                    "(monthly_record_id, hourly_wage_cents, weekly_minutes, "
                    "holiday_weeks, employment_start_date, ruleset_version, worked_minutes, "
                    "public_holiday_worked_minutes, annual_holiday_taken_minutes, "
                    "public_holiday_taken_minutes, holiday_balance_minutes) "
                    "VALUES (1, 2500, 600, 4, '2026-01-01', '2026', 60, 0, 0, 0, 1200)"
                )
            )


def test_employments_hold_the_documented_fields_and_types(tmp_path, engines):
    engine = engines(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns("employments")
    }

    assert {
        "id",
        "employer_id",
        "employee_id",
        "start_date",
        "end_date",
        "hourly_wage_cents",
        "weekly_minutes",
        "holiday_weeks",
    } == set(columns)
    assert isinstance(columns["weekly_minutes"]["type"], Integer)
    assert isinstance(columns["holiday_weeks"]["type"], Integer)
    assert isinstance(columns["end_date"]["type"], Date)
    assert columns["end_date"]["nullable"] is True
    assert columns["weekly_minutes"]["nullable"] is False
    assert columns["holiday_weeks"]["nullable"] is False
    assert columns["weekly_minutes"]["default"] is None
    assert columns["holiday_weeks"]["default"] is None


def test_create_schema_is_idempotent(tmp_path, engines):
    engine = engines(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    create_schema(engine)
    assert set(inspect(engine).get_table_names()) == ENTITY_TABLES


def test_schema_persists_in_the_file_named_by_the_url(tmp_path, engines):
    url = f"sqlite:///{tmp_path / 'payroll.db'}"
    create_schema(engines(url))
    assert set(inspect(engines(url)).get_table_names()) == ENTITY_TABLES
